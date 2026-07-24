"""Endpoint health probe: know which data sources are up BEFORE the run.

    python -m scraper.preflight

Prints a table of every external dependency with status + latency, writes
data/preflight.json, and always exits 0 (informational — the pipeline itself
degrades per-source). CI runs this first so every day's logs start with a
source-health snapshot; when a signal goes quiet in the data, this tells you
whether the endpoint died or the market did.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import time

from . import config
from .http import make_session

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_PATH = os.path.join(ROOT, "data", "preflight.json")

_Y = dt.date.today() - dt.timedelta(days=2)
CHECKS = [
    ("yahoo_screener",
     "https://query2.finance.yahoo.com/v1/finance/screener/predefined/saved"
     "?scrIds=day_gainers&count=1"),
    ("yahoo_chart", "https://query1.finance.yahoo.com/v8/finance/chart/AAPL"
                    "?range=5d&interval=1d"),
    ("sec_tickers", "https://www.sec.gov/files/company_tickers.json"),
    ("sec_submissions", "https://data.sec.gov/submissions/CIK0000320193.json"),
    ("google_news_rss", "https://news.google.com/rss/search?q=%22AAPL%22+stock"
                        "&hl=en-US&gl=US&ceid=US:en"),
    ("reddit_json", "https://www.reddit.com/r/wallstreetbets/hot.json?limit=1"),
    ("stocktwits", "https://api.stocktwits.com/api/2/trending/symbols.json"),
    ("wikimedia_pageviews",
     "https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
     "en.wikipedia/all-access/user/Apple_Inc./daily/"
     f"{(_Y - dt.timedelta(days=7)).strftime('%Y%m%d')}/{_Y.strftime('%Y%m%d')}"),
    ("finra_regsho", "https://cdn.finra.org/equity/regsho/daily/CNMSshvol"
                     f"{_Y.strftime('%Y%m%d')}.txt"),
    ("sec_tickers_mirror", "https://data.sec.gov/files/company_tickers.json"),
    ("nasdaq_listing", "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"),
]


def probe() -> dict:
    session = make_session(user_agent=config.SEC_USER_AGENT)
    results = {}
    for name, url in CHECKS:
        t0 = time.monotonic()
        try:
            resp = session.get(url, timeout=10)
            ms = int((time.monotonic() - t0) * 1000)
            ok = resp.status_code == 200
            results[name] = {"ok": ok, "status": resp.status_code, "ms": ms}
        except Exception as e:  # noqa: BLE001
            ms = int((time.monotonic() - t0) * 1000)
            results[name] = {"ok": False, "status": type(e).__name__[:40], "ms": ms}
    return results


def main():
    results = probe()
    up = sum(1 for r in results.values() if r["ok"])
    print(f"Preflight: {up}/{len(results)} sources reachable")
    for name, r in results.items():
        mark = "UP  " if r["ok"] else "DOWN"
        print(f"  [{mark}] {name:22s} status={r['status']} {r['ms']}ms")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as fh:
        json.dump({"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "sources": results}, fh, indent=2)


if __name__ == "__main__":
    main()
