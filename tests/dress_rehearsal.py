"""Full-pipeline dress rehearsal with a simulated internet.

Runs the REAL `scraper.main` end-to-end — universe discovery, all 7 sources,
scoring, store writes, warehouse compaction, dataset compilation, evaluation —
against a fake HTTP layer that mimics each real endpoint's response shape.
Catches integration bugs (merge keys, response parsing, file plumbing) that
unit tests can't, without any network access.

Run:  python -m tests.dress_rehearsal
Exits non-zero on any failure. Used as a CI gate before the live run.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import sys
import tempfile

import numpy as np
import pandas as pd

TICKERS = ["ALFA", "BRVO", "CHRL", "DLTA", "ECHO", "FXTR", "GOLF", "HTEL"]
_START = dt.date.today() - dt.timedelta(days=190)


# --------------------------------------------------------------------------- #
# fake HTTP layer
# --------------------------------------------------------------------------- #

class FakeResponse:
    def __init__(self, payload, kind="json", status=200):
        self.status_code = status
        self._payload = payload
        self._kind = kind

    def json(self):
        if self._kind != "json":
            raise ValueError("not json")
        return self._payload

    @property
    def text(self):
        return self._payload if isinstance(self._payload, str) else json.dumps(self._payload)

    @property
    def content(self):
        return self.text.encode()


def _news_rss(ticker: str) -> str:
    # Two fresh items plus one stale (40 days old) that recency must discount.
    now = dt.datetime.now(dt.timezone.utc)
    fresh = now.strftime("%a, %d %b %Y %H:%M:%S GMT")
    stale = (now - dt.timedelta(days=40)).strftime("%a, %d %b %Y %H:%M:%S GMT")
    phrases = [("surges on earnings beat", fresh),
               ("attracts analyst upgrades", fresh),
               ("saw unusual volume last quarter", stale)]
    items = "".join(
        f"<item><title>{ticker} stock {p}</title><pubDate>{d}</pubDate></item>"
        for p, d in phrases
    )
    return f'<?xml version="1.0"?><rss><channel>{items}</channel></rss>'


def _finra_file() -> str:
    rows = ["Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market"]
    for i, tk in enumerate(TICKERS):
        total = 1000 + i * 100
        rows.append(f"20260722|{tk}|{int(total*0.4+i*20)}|0|{total}|B,Q,N")
    return "\n".join(rows)


class FakeSession:
    """Routes every URL the pipeline touches to a canned, shape-accurate reply."""

    headers: dict = {}

    def __init__(self):
        self.headers = {}
        self.calls: list[str] = []

    def get(self, url, params=None, timeout=None, headers=None, **kw):
        self.calls.append(url)
        p = params or {}
        if "finance/screener" in url:
            quotes = [{"symbol": t} for t in TICKERS]
            return FakeResponse({"finance": {"result": [{"quotes": quotes}]}})
        if "company_tickers" in url:
            payload = {str(i): {"cik_str": 1000 + i, "ticker": t, "title": f"{t.title()} Corp"}
                       for i, t in enumerate(TICKERS)}
            return FakeResponse(payload)
        if "data.sec.gov/submissions" in url:
            today = dt.date.today().isoformat()
            return FakeResponse({"filings": {"recent": {
                "form": ["4", "8-K", "10-Q"], "filingDate": [today, today, today]}}})
        if "reddit.com" in url:
            now_ts = dt.datetime.now(dt.timezone.utc).timestamp()
            posts = [{"data": {"title": f"${t} to the moon, incredible setup",
                               "selftext": f"{t} looks great",
                               "created_utc": now_ts - 3600}} for t in TICKERS[:4]]
            return FakeResponse({"data": {"children": posts}})
        if "news.google.com" in url:
            tk = next((t for t in TICKERS if t in url), TICKERS[0])
            return FakeResponse(_news_rss(tk), kind="text")
        if "trending/symbols" in url:
            return FakeResponse({"symbols": [{"symbol": t} for t in TICKERS[:2]]})
        if "streams/symbol" in url:
            iso_now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            return FakeResponse({"messages": [
                {"body": "bullish breakout, loving this", "created_at": iso_now},
                {"body": "solid earnings, adding more", "created_at": iso_now}]})
        if "action=opensearch" in url:
            name = url.split("search=")[-1]
            return FakeResponse([name, [f"{name} page"], [], []])
        if "metrics/pageviews" in url:
            base = _START + dt.timedelta(days=160)
            items = [{"timestamp": (base + dt.timedelta(days=i)).strftime("%Y%m%d") + "00",
                      "views": 100 + (200 if i >= 21 else 0)} for i in range(28)]
            return FakeResponse({"items": items})
        if "cdn.finra.org" in url:
            return FakeResponse(_finra_file(), kind="text")
        return FakeResponse({}, status=404)


def _fake_yf_download(tickers=None, period=None, interval=None, group_by=None,
                      auto_adjust=None, threads=None, progress=None, **kw):
    """Shape-accurate yfinance.download stand-in (MultiIndex ticker columns)."""
    rng = np.random.default_rng(42)
    tick_list = tickers.split() if isinstance(tickers, str) else list(tickers)
    n = 130
    idx = pd.bdate_range(end=dt.date.today(), periods=n)
    frames = {}
    for j, tk in enumerate(tick_list):
        drift = 0.0005 * (j + 1)  # higher-index tickers trend harder
        steps = rng.normal(drift, 0.02, n)
        close = 50 * np.exp(np.cumsum(steps))
        open_ = close * (1 + rng.normal(0, 0.004, n))
        high = np.maximum(open_, close) * (1 + abs(rng.normal(0, 0.004, n)))
        low = np.minimum(open_, close) * (1 - abs(rng.normal(0, 0.004, n)))
        vol = rng.integers(500_000, 5_000_000, n).astype(float)
        frames[tk] = pd.DataFrame(
            {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": vol},
            index=idx)
    if len(tick_list) == 1:
        return frames[tick_list[0]]
    return pd.concat(frames, axis=1)


# --------------------------------------------------------------------------- #
# harness
# --------------------------------------------------------------------------- #

def main() -> int:
    tmp = tempfile.mkdtemp(prefix="rehearsal-")
    print(f"[rehearsal] sandbox: {tmp}")

    # Route every module's HTTP + yfinance to the fakes.
    fake = FakeSession()
    import scraper.http as http_mod
    http_mod.make_session = lambda user_agent=None: fake
    import scraper.universe as universe
    import scraper.sources.prices as prices
    import scraper.sources.news as news
    import scraper.sources.reddit as reddit
    import scraper.sources.sec_filings as sec_filings
    import scraper.sources.stocktwits as stocktwits
    import scraper.sources.wikipedia as wikipedia
    import scraper.sources.short_interest as short_interest
    for mod in (universe, news, reddit, sec_filings, stocktwits, wikipedia,
                short_interest):
        if hasattr(mod, "make_session"):
            mod.make_session = lambda user_agent=None: fake
    import yfinance
    yfinance.download = _fake_yf_download
    prices.yf.download = _fake_yf_download

    # Redirect all writes into the sandbox.
    import scraper.store as store
    store.HISTORY_DIR = os.path.join(tmp, "history")
    store.FEATURES_DIR = os.path.join(store.HISTORY_DIR, "features")
    store.PRICES_DIR = os.path.join(store.HISTORY_DIR, "prices")
    store.MANIFEST_PATH = os.path.join(store.HISTORY_DIR, "manifest.json")
    store.LEGACY_FEATURES_PATH = os.path.join(store.HISTORY_DIR, "features.jsonl")
    import scraper.config as config
    config.WATCHLIST_FILE = os.path.join(tmp, "watchlist.txt")
    wikipedia._CACHE = os.path.join(tmp, "wiki_articles.json")
    import scraper.main as main_mod
    main_mod.RANKINGS_DIR = os.path.join(tmp, "rankings")
    main_mod.RANKINGS_MD = os.path.join(tmp, "RANKINGS.md")
    import scraper.dataset as dataset
    dataset.DATASET_DIR = os.path.join(tmp, "dataset")

    failures: list[str] = []

    def check(name, cond, detail=""):
        status = "PASS" if cond else "FAIL"
        print(f"  [{status}] {name} {detail}")
        if not cond:
            failures.append(name)

    # ---- 1. full screener run ----
    payload = main_mod.run(limit=None, use_reddit=True, use_sec=True, use_news=True)
    results = payload["results"]
    check("pipeline returns results", len(results) == len(TICKERS),
          f"({len(results)}/{len(TICKERS)} tickers)")
    feats = results[0]["features"]
    expected_signals = ["ret_21d", "news_count", "news_sentiment", "reddit_mentions",
                        "sec_form4_recent", "st_trending", "st_msg_count",
                        "wiki_views_7d", "wiki_spike_ratio", "short_vol_ratio",
                        "KMID", "ROC_20", "RSV_60"]
    missing = [k for k in expected_signals if k not in feats]
    check("all source families present in features", not missing, f"missing={missing}")
    check("factor battery populated",
          sum(1 for k in feats if feats[k] is not None) > 40,
          f"({sum(1 for k in feats if feats[k] is not None)} non-null features)")
    check("wiki spike detected", any(
        (r['features'].get('wiki_spike_ratio') or 0) > 1.5 for r in results))
    check("short ratio parsed", all(
        r['features'].get('short_vol_ratio') is not None for r in results))
    check("components complete", set(results[0]["components"]) ==
          set(config.SCORE_WEIGHTS))

    # ---- 2. outputs + store ----
    main_mod.write_outputs(payload)
    check("rankings md written", os.path.exists(main_mod.RANKINGS_MD))
    check("feature partitions written", len(store.load_features()) == len(TICKERS))
    check("price archive written", len(store.load_prices()) > 0)

    # Idempotency under a same-day re-run.
    main_mod.write_outputs(payload)
    check("second run does not duplicate",
          len(store.load_features()) == len(TICKERS))

    # ---- 3. warehouse ----
    try:
        import scraper.warehouse as warehouse
        warehouse.WAREHOUSE_DIR = os.path.join(tmp, "warehouse")
        warehouse.FEATURES_WH = os.path.join(warehouse.WAREHOUSE_DIR, "features")
        warehouse.PRICES_WH = os.path.join(warehouse.WAREHOUSE_DIR, "prices")
        s = warehouse.compact()
        check("warehouse compacts", s["feature_rows"] == len(TICKERS))
        n = warehouse.sql("SELECT COUNT(DISTINCT ticker) FROM features")[0][0]
        check("duckdb queries features", n == len(TICKERS))
    except SystemExit:
        print("  [SKIP] warehouse (pyarrow/duckdb missing)")

    # ---- 4. labeled dataset across simulated history ----
    # Backdate extra snapshots so labels exist, then compile.
    for back in (100, 80):
        d = (dt.date.today() - dt.timedelta(days=back)).isoformat()
        store.append_snapshot(results, date=d)
    panel = {r["ticker"]: {(dt.date.today() - dt.timedelta(days=back)).isoformat():
                           r["features"]["last_price"] * (1 + 0.001 * back)
                           for back in (100, 80, 30, 0)}
             for r in results}
    store.append_prices(panel)
    examples = dataset.compile_labeled(horizon=63, tolerance=15, write=True)
    check("dataset labels compile", len(examples) > 0, f"({len(examples)} examples)")
    if examples:
        check("relative labels attached", "rel_ret" in examples[0])

    print()
    if failures:
        print(f"REHEARSAL FAILED: {failures}")
        return 1
    print(f"REHEARSAL PASSED — {len(fake.calls)} simulated HTTP calls, "
          "full pipeline integrates cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(main())
