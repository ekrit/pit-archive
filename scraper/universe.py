"""Discover a candidate universe of tickers to score.

Combines Yahoo Finance predefined screeners (movers, most active, small-cap
gainers, etc.) with a user-maintained static watchlist. All free / no-auth.
"""
import os
import re

from . import config
from .http import make_session, get_json

_YAHOO_SCREENER_URL = "https://query2.finance.yahoo.com/v1/finance/screener/predefined/saved"
_TICKER_RE = re.compile(r"^[A-Z][A-Z.\-]{0,6}$")


def _from_screeners(session) -> set[str]:
    tickers: set[str] = set()
    for scr_id in config.YAHOO_SCREENER_IDS:
        data = get_json(
            session,
            _YAHOO_SCREENER_URL,
            params={"scrIds": scr_id, "count": config.YAHOO_SCREENER_COUNT},
        )
        if not data:
            continue
        try:
            quotes = data["finance"]["result"][0]["quotes"]
        except (KeyError, IndexError, TypeError):
            continue
        for q in quotes:
            sym = q.get("symbol")
            if sym and _TICKER_RE.match(sym):
                tickers.add(sym)
    return tickers


def _from_watchlist() -> set[str]:
    path = config.WATCHLIST_FILE
    if not os.path.exists(path):
        return set()
    out: set[str] = set()
    with open(path) as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip().upper()
            if line and _TICKER_RE.match(line):
                out.add(line)
    return out


def discover() -> list[str]:
    """Return a deduped, capped list of candidate tickers."""
    session = make_session()
    tickers = _from_screeners(session) | _from_watchlist()
    ordered = sorted(tickers)
    return ordered[: config.MAX_TICKERS_TO_SCORE]


# --------------------------------------------------------------------------- #
# full-market universe (~10k names) with layered free fallbacks
# --------------------------------------------------------------------------- #
# www.sec.gov 403s many cloud IPs (GitHub runners included), so the listing is
# fetched through a fallback chain, all free/no-key:
#   1. SEC company_tickers.json (www.sec.gov)      tickers + names + best quality
#   2. same file via data.sec.gov mirror           (data.sec.gov is not blocked)
#   3. NASDAQ Trader symbol directory              tickers + names, open CDN
#   4. committed cache from any earlier success    (listings churn slowly)

_SEC_TICKERS_URLS = [
    "https://www.sec.gov/files/company_tickers.json",
    "https://data.sec.gov/files/company_tickers.json",
]
_NASDAQ_URLS = [
    "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt",
    "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt",
]


def _parse_nasdaq_listing(text: str) -> dict[str, str]:
    """Parse a NASDAQ Trader pipe-delimited symbol file -> {ticker: name}.

    Skips test issues and ETFs; tolerant of both nasdaqlisted (Symbol) and
    otherlisted (ACT Symbol) layouts.
    """
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {}
    header = [h.strip() for h in lines[0].split("|")]

    def col(*cands):
        for c in cands:
            if c in header:
                return header.index(c)
        return None

    i_sym = col("Symbol", "ACT Symbol")
    i_name = col("Security Name")
    i_test = col("Test Issue")
    i_etf = col("ETF")
    if i_sym is None or i_name is None:
        return {}
    out: dict[str, str] = {}
    for ln in lines[1:]:
        if ln.startswith("File Creation Time"):
            continue
        parts = ln.split("|")
        if len(parts) <= max(i_sym, i_name):
            continue
        if i_test is not None and len(parts) > i_test and parts[i_test].strip() == "Y":
            continue
        if i_etf is not None and len(parts) > i_etf and parts[i_etf].strip() == "Y":
            continue
        sym = parts[i_sym].strip().upper().replace("/", "-").replace("$", "")
        if _TICKER_RE.match(sym):
            out[sym] = parts[i_name].strip()
    return out


def _write_universe_caches(tickers: list[str], names: dict[str, str], today: str) -> None:
    import json

    base = os.path.dirname(config.WATCHLIST_FILE)
    with open(os.path.join(base, "universe_full.json"), "w") as fh:
        json.dump({"date": today, "tickers": tickers}, fh)
    if names:
        with open(os.path.join(base, "sec_company_names.json"), "w") as fh:
            json.dump(names, fh)


def full_market(session=None) -> list[str]:
    """Every US-listed ticker (~10k), from a chain of free sources, cached.

    This is what lets the price archive cover the whole market instead of just
    the daily hot list — the base requirement for finding names *before* they
    show up on anyone's screener.
    """
    import datetime as dt
    import json

    cache = os.path.join(os.path.dirname(config.WATCHLIST_FILE), "universe_full.json")
    today = dt.date.today().isoformat()
    if os.path.exists(cache):
        try:
            with open(cache) as fh:
                payload = json.load(fh)
            if payload.get("date") == today and payload.get("tickers"):
                return payload["tickers"]
        except (json.JSONDecodeError, OSError):
            pass

    session = session or make_session()
    tickers: set[str] = set()
    names: dict[str, str] = {}

    # 1+2: SEC listing (direct, then mirror).
    for url in _SEC_TICKERS_URLS:
        data = get_json(session, url, headers={"User-Agent": config.SEC_USER_AGENT})
        if isinstance(data, dict) and data:
            for entry in data.values():
                sym = str(entry.get("ticker", "")).upper().replace("/", "-")
                if _TICKER_RE.match(sym):
                    tickers.add(sym)
                    if entry.get("title"):
                        names[sym] = str(entry["title"])
            break

    # 3: NASDAQ Trader symbol directory.
    if not tickers:
        for url in _NASDAQ_URLS:
            try:
                resp = session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
                if resp.status_code == 200:
                    parsed = _parse_nasdaq_listing(resp.text)
                    tickers.update(parsed)
                    names.update(parsed)
            except Exception:  # noqa: BLE001 - best-effort chain
                continue

    ordered = sorted(tickers)
    if ordered:
        _write_universe_caches(ordered, names, today)
        return ordered

    # 4: stale committed cache.
    if os.path.exists(cache):
        try:
            with open(cache) as fh:
                payload = json.load(fh)
            if payload.get("tickers"):
                return payload["tickers"]
        except (json.JSONDecodeError, OSError):
            pass
    return ordered


# --------------------------------------------------------------------------- #
# international tier-1 universe (curated world markets, Yahoo suffixes)
# --------------------------------------------------------------------------- #
# International symbols carry digits and exchange suffixes (7203.T, 0700.HK,
# RELIANCE.NS), so they get their own, looser validation pattern.
_INTL_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.\-]{0,14}$")


def international() -> list[str]:
    """Curated world-market tickers for the tier-1 price archive.

    Read from data/markets/international.txt (editable; '#' comments). These
    names get daily closes archived — and therefore labels and, later,
    factor screening — while the deep attention sources remain US-only
    (EDGAR/FINRA/WSB have no international equivalents).
    """
    path = os.path.join(os.path.dirname(config.WATCHLIST_FILE),
                        "markets", "international.txt")
    if not os.path.exists(path):
        return []
    out: list[str] = []
    seen: set[str] = set()
    with open(path) as fh:
        for line in fh:
            sym = line.split("#", 1)[0].strip().upper()
            if sym and _INTL_TICKER_RE.match(sym) and sym not in seen:
                seen.add(sym)
                out.append(sym)
    return out
