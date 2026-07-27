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

def _last_business_day(lag_days: int = 1) -> dt.date:
    """Most recent weekday at least `lag_days` back.

    Publishers like FINRA post nothing on weekends, so probing a fixed
    'today - 2' lands on Saturday every Monday and reports a healthy source
    as DOWN — a false alarm trains you to ignore the monitor.
    """
    d = dt.date.today() - dt.timedelta(days=lag_days)
    while d.weekday() >= 5:
        d -= dt.timedelta(days=1)
    return d


_Y = _last_business_day(2)

# Which User-Agent each source actually uses. A probe that runs with a
# different UA than the real source can report UP while the source is being
# refused — the exact way preflight lied about Wikipedia.
_UA_FOR = {
    "sec_tickers": "sec", "sec_submissions": "sec",
    "wikimedia_pageviews": "wiki", "wikipedia_search": "wiki",
}

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
    ("nasdaq_listing", "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"),
    # Wikipedia article RESOLUTION uses a different host than pageviews; when
    # this is blocked, every wiki_* feature silently reads zero.
    ("wikipedia_search",
     "https://en.wikipedia.org/w/api.php?action=opensearch&limit=1"
     "&namespace=0&format=json&search=Apple%20Inc."),
]


def probe() -> dict:
    sessions = {
        "sec": make_session(user_agent=config.SEC_USER_AGENT),
        "wiki": make_session(user_agent=config.WIKI_USER_AGENT),
        "default": make_session(),
    }
    results = {}
    for name, url in CHECKS:
        session = sessions[_UA_FOR.get(name, "default")]
        t0 = time.monotonic()
        try:
            resp = session.get(url, timeout=10)
            ms = int((time.monotonic() - t0) * 1000)
            ok = resp.status_code == 200
            entry = {"ok": ok, "status": resp.status_code, "ms": ms}
            if not ok:
                # The body explains WHY: SEC returns a specific "undeclared
                # automated tool" page for User-Agent policy rejections, which
                # is a different fix from an IP block.
                # Long enough to reach SEC's actual message, which sits below
                # a boilerplate XHTML doctype header.
                entry["body"] = " ".join(resp.text.split())[:600]
            results[name] = entry
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
        line = f"  [{mark}] {name:22s} status={r['status']} {r['ms']}ms"
        if r.get("body"):
            line += f"\n           body: {r['body'][:120]}"
        print(line)

    # SEC's fair-access policy asks for a declared contact EMAIL in the
    # User-Agent; without one, requests are refused regardless of rate.
    if "@" not in config.SEC_USER_AGENT:
        print("\n  [!] SEC_USER_AGENT has no contact email — SEC endpoints will "
              "likely 403.\n      Set a repo secret SEC_USER_AGENT like "
              "'your-project your.email@example.com'.")
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w") as fh:
        json.dump({"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                   "sources": results}, fh, indent=2)


if __name__ == "__main__":
    main()
