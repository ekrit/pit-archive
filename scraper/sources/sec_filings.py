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

_TICKER_MAP_URL = "https://www.sec.gov/files/company_tickers.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_LOOKBACK_DAYS = 45
# www.sec.gov 403s many cloud IPs (GitHub runners included) while data.sec.gov
# stays open. The CIK map is committed to the repo as a cache, so a 403 on the
# live fetch degrades to yesterday's map instead of losing the whole source.
_CIK_CACHE = os.path.join(os.path.dirname(config.WATCHLIST_FILE), "cik_map.json")


def _load_cik_map(session) -> dict[str, int]:
    data = get_json(session, _TICKER_MAP_URL)
    out: dict[str, int] = {}
    if data:
        for row in data.values():
            try:
                out[row["ticker"].upper()] = int(row["cik_str"])
            except (KeyError, ValueError, TypeError):
                continue
        if out:  # refresh the committed cache for the next blocked run
            try:
                with open(_CIK_CACHE, "w") as fh:
                    json.dump(out, fh)
            except OSError:
                pass
        return out
    # Live fetch blocked -> committed cache.
    if os.path.exists(_CIK_CACHE):
        try:
            with open(_CIK_CACHE) as fh:
                return {k: int(v) for k, v in json.load(fh).items()}
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
