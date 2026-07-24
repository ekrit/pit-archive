"""Recent SEC filing activity via EDGAR's free JSON APIs (no key).

Signals:
  - recent Form 4 count (insider transactions; clustered insider *buying*
    is a classic pre-move tell, though Form 4 alone doesn't tell buy vs sell
    without parsing the document, so we treat volume of Form 4s as an
    "insider activity" proxy).
  - recent 8-K count (material events / catalysts).

SEC asks for a descriptive User-Agent and rate limits to ~10 req/s. We map
tickers to CIK via the public company_tickers.json.
"""
import datetime as dt
import json
import os
import time

from .. import config
from ..http import make_session, get_json

# www.sec.gov 403s many cloud IPs (GitHub runners included) while data.sec.gov
# stays open, so the ticker->CIK map is fetched through a mirror chain before
# falling back to the committed cache.
# NOTE: data.sec.gov/files/... does NOT exist (verified 404 from CI); only
# www.sec.gov serves the ticker map, and it 403s clients whose User-Agent
# lacks a declared contact email (SEC fair-access policy). Setting the
# SEC_USER_AGENT secret to "<project> <email>" is what unblocks this source.
_TICKER_MAP_URLS = [
    "https://www.sec.gov/files/company_tickers.json",
]
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_LOOKBACK_DAYS = 45
# Minimum entries for a cache to be considered real. Guards against a tiny
# fixture map (e.g. written by a test) starving the live source.
_MIN_CREDIBLE_CIK_ENTRIES = 100


def _cik_cache_path() -> str:
    """Resolved at call time so tests can redirect config.WATCHLIST_FILE."""
    return os.path.join(os.path.dirname(config.WATCHLIST_FILE), "cik_map.json")


def _load_cik_map(session) -> dict[str, int]:
    out: dict[str, int] = {}
    for url in _TICKER_MAP_URLS:
        data = get_json(session, url, headers={"User-Agent": config.SEC_USER_AGENT})
        if not data:
            continue
        for row in data.values():
            try:
                out[row["ticker"].upper()] = int(row["cik_str"])
            except (KeyError, ValueError, TypeError):
                continue
        if out:
            break
    path = _cik_cache_path()
    if len(out) >= _MIN_CREDIBLE_CIK_ENTRIES:
        try:  # refresh the committed cache for the next blocked run
            with open(path, "w") as fh:
                json.dump(out, fh)
        except OSError:
            pass
        return out
    if out:  # small but live result: use it, don't overwrite a bigger cache
        return out
    # Every mirror blocked -> committed cache, if it looks credible.
    if os.path.exists(path):
        try:
            with open(path) as fh:
                cached = {k: int(v) for k, v in json.load(fh).items()}
            if len(cached) >= _MIN_CREDIBLE_CIK_ENTRIES:
                return cached
            print(f"[sec] ignoring implausible CIK cache ({len(cached)} entries)")
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return out


def fetch(tickers: list[str]) -> dict[str, dict]:
    session = make_session(user_agent=config.SEC_USER_AGENT)
    cik_map = _load_cik_map(session)
    if not cik_map:
        return {}

    cutoff = dt.date.today() - dt.timedelta(days=_LOOKBACK_DAYS)
    results: dict[str, dict] = {}

    for tk in tickers:
        cik = cik_map.get(tk.upper())
        if cik is None:
            continue
        data = get_json(session, _SUBMISSIONS_URL.format(cik=cik))
        time.sleep(0.15)  # stay under SEC's ~10 req/s fair-access limit
        if not data:
            continue
        try:
            recent = data["filings"]["recent"]
            forms = recent["form"]
            dates = recent["filingDate"]
        except (KeyError, TypeError):
            continue

        form4 = 0
        eightk = 0
        for form, date_str in zip(forms, dates):
            try:
                fdate = dt.date.fromisoformat(date_str)
            except ValueError:
                continue
            if fdate < cutoff:
                continue
            if form == "4":
                form4 += 1
            elif form.startswith("8-K"):
                eightk += 1

        results[tk] = {
            "sec_form4_recent": form4,
            "sec_8k_recent": eightk,
        }
    return results
