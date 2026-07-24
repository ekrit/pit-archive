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
# full-market universe (SEC company_tickers.json, ~10k names, free/no-key)
# --------------------------------------------------------------------------- #

_SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"


def full_market(session=None) -> list[str]:
    """Every US-listed ticker the SEC knows about (~10k), cached daily.

    This is what lets the price archive cover the whole market instead of just
    the daily hot list — the base requirement for finding names *before* they
    show up on anyone's screener. Cached to disk so one fetch per day suffices.
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
    # SEC fair-access policy: identify yourself via User-Agent.
    data = get_json(session, _SEC_TICKERS_URL,
                    headers={"User-Agent": config.SEC_USER_AGENT})
    tickers: set[str] = set()
    names: dict[str, str] = {}
    if isinstance(data, dict):
        for entry in data.values():
            sym = str(entry.get("ticker", "")).upper().replace("/", "-")
            if _TICKER_RE.match(sym):
                tickers.add(sym)
                title = entry.get("title")
                if title:
                    names[sym] = str(title)
    ordered = sorted(tickers)
    if ordered:
        with open(cache, "w") as fh:
            json.dump({"date": today, "tickers": ordered}, fh)
        # Ticker -> company-name map, used by the Wikipedia attention source.
        names_path = os.path.join(os.path.dirname(config.WATCHLIST_FILE),
                                  "sec_company_names.json")
        with open(names_path, "w") as fh:
            json.dump(names, fh)
        return ordered
    # Live fetch blocked (www.sec.gov 403s many cloud IPs): fall back to the
    # committed cache even if stale — listings churn slowly.
    if os.path.exists(cache):
        try:
            with open(cache) as fh:
                payload = json.load(fh)
            if payload.get("tickers"):
                return payload["tickers"]
        except (json.JSONDecodeError, OSError):
            pass
    return ordered
