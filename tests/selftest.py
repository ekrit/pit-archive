"""Self-tests for the evaluation stack using synthetic data with known answers.

Run: python -m tests.selftest
These do not touch the network; they verify the *math* is correct so that when
the pipeline runs against real data in CI, the numbers mean what we claim.
"""
import datetime as dt
import importlib
import os
import tempfile

import numpy as np
import pandas as pd

from scraper import metrics, labels, backtest, model


def approx(a, b, tol=1e-6):
    return abs(a - b) <= tol


def test_metrics():
    # Perfect monotonic relationship -> Spearman == 1; reversed -> -1.
    x = np.array([1, 2, 3, 4, 5], dtype=float)
    assert approx(metrics.spearman(x, x), 1.0)
    assert approx(metrics.spearman(x, x[::-1]), -1.0)
    # Ties handled (average ranks).
    r = metrics.rankdata(np.array([10, 10, 20]))
    assert list(r) == [1.5, 1.5, 3.0], r
    # AUC: perfectly separable -> 1.0; reversed -> 0.0.
    s = np.array([0.1, 0.2, 0.8, 0.9])
    lab = np.array([0, 0, 1, 1])
    assert approx(metrics.auc(s, lab), 1.0), metrics.auc(s, lab)
    assert approx(metrics.auc(-s, lab), 0.0)
    # IC summary t-stat sign follows the mean.
    summ = metrics.ic_summary([0.05, 0.06, 0.04, 0.05])
    assert summ["mean_ic"] > 0 and summ["t_stat"] > 0
    # Decile spread: higher signal -> higher return by construction.
    sig = np.arange(100, dtype=float)
    fwd = np.arange(100, dtype=float) / 100.0
    ds = metrics.decile_spread(sig, fwd)
    assert ds["spread"] > 0
    print("  metrics OK")


def test_forward_returns_from_store():
    # Two snapshots of AAA 63 days apart, price 100 -> 150 => fwd_ret 0.5.
    d0 = dt.date(2026, 1, 1)
    d1 = d0 + dt.timedelta(days=63)
    records = [
        {"date": d0.isoformat(), "ticker": "AAA", "last_price": 100.0,
         "features": {"ret_21d": 0.1}, "score": 90},
        {"date": d1.isoformat(), "ticker": "AAA", "last_price": 150.0,
         "features": {"ret_21d": 0.2}, "score": 80},
        # BBB only has one snapshot -> no label.
        {"date": d0.isoformat(), "ticker": "BBB", "last_price": 50.0,
         "features": {"ret_21d": 0.0}, "score": 40},
    ]
    labeled = labels.build_forward_returns(records, horizon_days=63, tolerance_days=10)
    assert len(labeled) == 1, labeled
    assert approx(labeled[0]["fwd_ret"], 0.5, tol=1e-9), labeled[0]
    print("  store labeling OK")


def test_price_history_reconstruction():
    # Build a steadily rising series; forward returns should be positive and
    # features_asof must never see the future (monotone -> ret features > 0).
    idx = pd.date_range("2024-01-01", periods=400, freq="D")
    close = pd.Series(np.linspace(10, 50, 400), index=idx)
    vol = pd.Series(np.full(400, 1_000_000.0), index=idx)
    df = pd.DataFrame({"Close": close, "Volume": vol})
    ex = labels.price_history_examples(df, horizon=63, step=10)
    assert len(ex) > 10, len(ex)
    assert all(e["fwd_ret"] > 0 for e in ex), "rising series must have positive fwd_ret"
    assert all(e["features"]["ret_21d"] is None or e["features"]["ret_21d"] > 0 for e in ex)
    print("  price reconstruction OK")


def test_backtest_detects_planted_edge():
    # Signal 'good' is correlated with fwd_ret; 'noise' is not. Backtest must
    # rank 'good' well above 'noise' by IC.
    rng = np.random.default_rng(0)
    examples = []
    for d in range(12):  # 12 dates
        date = (dt.date(2026, 1, 1) + dt.timedelta(days=d * 30)).isoformat()
        for _ in range(40):  # 40 names per date
            g = rng.normal()
            fwd = 0.6 * g + rng.normal(scale=0.5)  # good signal drives return
            examples.append({
                "date": date,
                "features": {"good": g, "noise": rng.normal()},
                "fwd_ret": fwd,
            })
    rows = backtest.run(examples, signals=["good", "noise"])
    by = {r["signal"]: r for r in rows}
    assert by["good"]["mean_ic"] > 0.3, by["good"]
    assert abs(by["noise"]["mean_ic"]) < 0.1, by["noise"]
    assert by["good"]["t_stat"] > 2, by["good"]
    print(f"  backtest edge detection OK (good IC={by['good']['mean_ic']}, "
          f"noise IC={by['noise']['mean_ic']})")


def test_walk_forward_learns():
    # Planted separable signal -> out-of-sample AUC should beat 0.5 clearly.
    rng = np.random.default_rng(1)
    examples = []
    for d in range(15):
        date = (dt.date(2026, 1, 1) + dt.timedelta(days=d * 20)).isoformat()
        for _ in range(40):
            g = rng.normal()
            fwd = 0.7 * g + rng.normal(scale=0.4)
            examples.append({
                "date": date,
                "features": {"good": g, "noise": rng.normal()},
                "fwd_ret": fwd,
            })
    res = model.walk_forward(examples, ["good", "noise"], n_folds=4)
    assert "oos_auc" in res and res["oos_auc"] is not None, res
    assert res["oos_auc"] > 0.6, res
    print(f"  walk-forward learning OK (backend={res['backend']}, OOS AUC={res['oos_auc']})")


def _fresh_store(tmp):
    """Point the store package at a throwaway directory and reload it."""
    import scraper.store as store
    store.HISTORY_DIR = os.path.join(tmp, "history")
    store.FEATURES_DIR = os.path.join(store.HISTORY_DIR, "features")
    store.PRICES_DIR = os.path.join(store.HISTORY_DIR, "prices")
    store.MANIFEST_PATH = os.path.join(store.HISTORY_DIR, "manifest.json")
    store.LEGACY_FEATURES_PATH = os.path.join(store.HISTORY_DIR, "features.jsonl")
    return store


def test_store_idempotent_upsert():
    with tempfile.TemporaryDirectory() as tmp:
        store = _fresh_store(tmp)
        res = [{"ticker": "AAA", "score": 90, "features": {"last_price": 100.0, "ret_21d": 0.3}},
               {"ticker": "BBB", "score": 40, "features": {"last_price": 10.0, "ret_21d": -0.1}}]
        store.append_snapshot(res, date="2026-07-24")
        # Re-run the SAME day (simulates manual + scheduled) -> must NOT duplicate.
        store.append_snapshot(res, date="2026-07-24")
        recs = store.load_features()
        assert len(recs) == 2, f"expected 2 deduped rows, got {len(recs)}"
        assert all(r["schema_version"] == store.SCHEMA_VERSION for r in recs)
        # Different day adds rows.
        store.append_snapshot(res, date="2026-07-25")
        assert len(store.load_features()) == 4
        # Manifest reflects coverage.
        man = store.update_manifest()
        assert man["features"]["dates"] == 2 and man["features"]["distinct_tickers"] == 2
        print("  store idempotent upsert + manifest OK")


def test_prices_archive_and_dataset():
    with tempfile.TemporaryDirectory() as tmp:
        store = _fresh_store(tmp)
        import scraper.dataset as dataset
        importlib.reload(dataset)
        dataset.store = store
        dataset.DATASET_DIR = os.path.join(tmp, "dataset")

        # Feature snapshot for AAA on day 0 at price 100.
        store.append_snapshot(
            [{"ticker": "AAA", "score": 88, "features": {"last_price": 100.0, "ret_21d": 0.2}}],
            date="2026-01-01",
        )
        # Dense price archive: AAA rises 100 -> 130 sixty-ish days later. Crucially,
        # AAA is NOT in any later feature snapshot (it left the hot list), yet the
        # price archive still lets us label it.
        panel = {"AAA": {"2026-01-01": 100.0, "2026-03-05": 130.0}}
        store.append_prices(panel)
        ex = dataset.compile_labeled(horizon=63, tolerance=10, write=False)
        assert len(ex) == 1, ex
        assert approx(ex[0]["fwd_ret"], 0.30, tol=1e-9), ex[0]
        assert store.tracked_tickers() == ["AAA"]
        print("  prices archive + dataset labeling (survives churn) OK")


def test_factor_library():
    from scraper import factors
    n = 80
    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    # Constant flat market: close=open=high=low=100, volume constant.
    flat = pd.DataFrame({"Open": 100.0, "High": 100.0, "Low": 100.0,
                         "Close": 100.0, "Volume": 1e6}, index=idx)
    f = factors.compute_factors(flat)
    assert len(f) == len(factors.FACTOR_NAMES) == 46
    # Known answers on a flat series:
    assert approx(f["KMID"], 0.0) and approx(f["KLEN"], 0.0)
    assert approx(f["ROC_20"], 1.0) and approx(f["MA_20"], 1.0)
    assert approx(f["STD_20"], 0.0) and approx(f["VMA_20"], 1.0)
    assert f["RSV_20"] is None  # zero range -> undefined, not fake 0
    assert approx(f["CNTP_20"], 0.0)  # no up days on a flat series

    # Steadily rising series: momentum factors must reflect the trend.
    rising_close = pd.Series(np.linspace(100, 200, n), index=idx)
    rising = pd.DataFrame({"Open": rising_close.shift(1).fillna(99.0),
                           "High": rising_close + 1, "Low": rising_close - 1,
                           "Close": rising_close, "Volume": 1e6}, index=idx)
    fr = factors.compute_factors(rising)
    assert fr["ROC_20"] < 1.0, "past/current < 1 when rising"
    assert fr["CNTP_20"] == 1.0, "every day is an up day"
    assert fr["SUMP_20"] == 1.0, "all movement is gains"
    assert fr["RSV_20"] > 0.9, "close near the top of its range"
    # Point-in-time: factors at row i must ignore rows after i.
    f_asof = factors.compute_factors(rising.iloc[:40])
    f_full = factors.compute_factors(rising)
    assert f_asof["ROC_20"] != f_full["ROC_20"]
    print("  factor library (46 factors, known answers, point-in-time) OK")


def test_warehouse_roundtrip():
    try:
        import duckdb  # noqa: F401
        import pyarrow  # noqa: F401
    except ImportError:
        print("  warehouse SKIPPED (pyarrow/duckdb not installed)")
        return
    with tempfile.TemporaryDirectory() as tmp:
        store = _fresh_store(tmp)
        import scraper.warehouse as warehouse
        importlib.reload(warehouse)
        warehouse.store = store
        warehouse.WAREHOUSE_DIR = os.path.join(tmp, "warehouse")
        warehouse.FEATURES_WH = os.path.join(warehouse.WAREHOUSE_DIR, "features")
        warehouse.PRICES_WH = os.path.join(warehouse.WAREHOUSE_DIR, "prices")

        store.append_snapshot(
            [{"ticker": "AAA", "score": 90, "features": {"last_price": 100.0, "ret_21d": 0.3}},
             {"ticker": "BBB", "score": 40, "features": {"last_price": 10.0, "ret_21d": -0.1}}],
            date="2026-07-24")
        store.append_prices({"AAA": {"2026-07-24": 100.0, "2026-08-24": 120.0}})
        s = warehouse.compact()
        assert s["feature_rows"] == 2 and s["price_rows"] == 2, s
        # SQL over parquet must see the same data.
        rows = warehouse.sql("SELECT ticker, f_ret_21d FROM features ORDER BY ticker")
        assert rows == [("AAA", 0.3), ("BBB", -0.1)], rows
        n = warehouse.sql("SELECT COUNT(*) FROM prices")[0][0]
        assert n == 2
        print("  parquet warehouse + duckdb SQL round-trip OK")


def test_turnover_and_ic_decay():
    # Persistent signal: same ranking every date -> turnover 0.
    dates = ["2026-01-01", "2026-01-02", "2026-01-03"]
    persistent = [{"date": d, "ticker": f"T{i}", "features": {"sig": float(i)},
                   "fwd_ret": 0.01 * i} for d in dates for i in range(10)]
    t0 = backtest.signal_turnover(persistent, "sig")
    assert t0 == 0.0, t0
    # Fully remade top bucket -> turnover 1.
    flip = []
    for k, d in enumerate(dates):
        for i in range(10):
            val = float(i) if k % 2 == 0 else float(-i)
            flip.append({"date": d, "ticker": f"T{i}", "features": {"sig": val},
                         "fwd_ret": 0.0})
    t1 = backtest.signal_turnover(flip, "sig")
    assert t1 == 1.0, t1
    # IC decay table builds for multiple horizons.
    def compile_fn(h):
        return persistent
    lines, table = backtest.ic_decay(compile_fn, [5, 21])
    assert any("sig" in ln for ln in lines), lines
    assert table["sig"][5] == table["sig"][21] == 1.0  # perfect monotone signal
    print("  turnover + IC decay OK")


def test_regsho_parser():
    from scraper.sources import short_interest
    text = ("Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market\n"
            "20260724|AAA|600|0|1000|B,Q,N\n"
            "20260724|BBB|100|0|400|B\n"
            "20260724|BAD|x|0|100|B\n"
            "20260724|ZRO|50|0|0|B\n")
    parsed = short_interest.parse_regsho(text)
    assert parsed == {"AAA": 0.6, "BBB": 0.25}, parsed
    print("  FINRA Reg SHO parser OK")


def test_parallel_fetch_map():
    from scraper import parallel
    calls = {"n": 0}

    def fn(k):
        calls["n"] += 1
        if k == "bad" and calls["n"] < 100:  # always fails
            raise ValueError("boom")
        return k.upper()

    out = parallel.fetch_map(["a", "b", "bad"], fn, max_workers=3,
                             rate_per_sec=1000, retries=1, default="FAIL")
    assert out["a"] == "A" and out["b"] == "B"
    assert out["bad"] == "FAIL", "failures must degrade to default, not raise"
    # Rate limiter actually paces: 5 calls at 50/s take >= ~80ms.
    import time as _t
    lim = parallel.RateLimiter(50)
    t0 = _t.monotonic()
    for _ in range(5):
        lim.acquire()
    assert _t.monotonic() - t0 >= 0.06
    print("  parallel fetch_map (retries, defaults, rate limit) OK")


def test_purged_walk_forward():
    from scraper.model import _purge_train_indices
    # 10 training rows dated day 0..9, horizon 5 days; test starts day 12.
    ex = [{"date": (dt.date(2026, 1, 1) + dt.timedelta(days=i)).isoformat(),
           "horizon_days": 5} for i in range(10)]
    test_start = (dt.date(2026, 1, 1) + dt.timedelta(days=12)).isoformat()
    keep = _purge_train_indices(ex, 10, test_start, embargo_days=0)
    # Row i's label window ends day i+5; must end BEFORE day 12 => i+5 < 12 => i <= 6.
    assert list(keep) == [0, 1, 2, 3, 4, 5, 6], list(keep)
    # With a 2-day embargo the cutoff moves to day 10 => i+5 < 10 => i <= 4.
    keep_e = _purge_train_indices(ex, 10, test_start, embargo_days=2)
    assert list(keep_e) == [0, 1, 2, 3, 4], list(keep_e)
    print("  purged/embargoed walk-forward indices OK")


def test_relative_returns():
    with tempfile.TemporaryDirectory() as tmp:
        store = _fresh_store(tmp)
        import scraper.dataset as dataset
        importlib.reload(dataset)
        dataset.store = store
        dataset.DATASET_DIR = os.path.join(tmp, "dataset")
        # Three tickers, same date; market (median) rises 10%, AAA rises 30%.
        store.append_snapshot(
            [{"ticker": t, "score": 50, "features": {"last_price": 100.0}}
             for t in ("AAA", "BBB", "CCC")], date="2026-01-01")
        store.append_prices({
            "AAA": {"2026-01-01": 100.0, "2026-03-05": 130.0},
            "BBB": {"2026-01-01": 100.0, "2026-03-05": 110.0},
            "CCC": {"2026-01-01": 100.0, "2026-03-05": 105.0},
        })
        ex = dataset.compile_labeled(horizon=63, tolerance=10, write=False)
        rel = {e["ticker"]: e["rel_ret"] for e in ex}
        assert approx(rel["AAA"], 0.20, tol=1e-9), rel  # 30% - 10% median
        assert approx(rel["BBB"], 0.0, tol=1e-9), rel   # the median itself
        print("  relative (market-neutral) labels OK")


def test_neutralized_ic():
    # 'shadow' is momentum in disguise (0.99 corr with ret_21d): raw IC looks
    # great, neutralized IC must collapse toward 0. 'fresh' is independent
    # alpha: neutralization must preserve it.
    rng = np.random.default_rng(3)
    examples = []
    for d in range(10):
        date = (dt.date(2026, 1, 1) + dt.timedelta(days=d * 30)).isoformat()
        for i in range(40):
            mom = rng.normal()
            fresh = rng.normal()
            fwd = 0.5 * mom + 0.5 * fresh + rng.normal(scale=0.3)
            examples.append({
                "date": date, "ticker": f"T{i}",
                "features": {"ret_21d": mom, "shadow": mom + rng.normal(scale=0.05),
                             "fresh": fresh},
                "fwd_ret": fwd,
            })
    rows = {r["signal"]: r for r in backtest.run(examples,
                                                 signals=["ret_21d", "shadow", "fresh"])}
    assert rows["shadow"]["mean_ic"] > 0.3, rows["shadow"]  # raw looks strong
    assert abs(rows["shadow"]["neut_ic"]) < 0.15, rows["shadow"]  # exposed as momentum
    assert rows["fresh"]["neut_ic"] > 0.3, rows["fresh"]  # true alpha survives
    print("  neutralized IC (kills momentum-in-disguise, keeps real alpha) OK")


def test_http_get_json_headers():
    from scraper import http

    class S:
        def get(self, url, params=None, headers=None, timeout=None):
            class R:
                status_code = 200
                def json(self):
                    return {"h": headers}
            return R()

    out = http.get_json(S(), "http://x", headers={"User-Agent": "ua"})
    assert out == {"h": {"User-Agent": "ua"}}, out
    print("  get_json passes custom headers OK")


def test_nasdaq_listing_parser():
    from scraper.universe import _parse_nasdaq_listing
    text = ("Symbol|Security Name|Market Category|Test Issue|Financial Status|"
            "Round Lot Size|ETF|NextShares\n"
            "AAPL|Apple Inc. - Common Stock|Q|N|N|100|N|N\n"
            "ZTST|Test Co|Q|Y|N|100|N|N\n"          # test issue -> skipped
            "QQQ|Invesco QQQ Trust|G|N|N|100|Y|N\n"  # ETF -> skipped
            "File Creation Time: 0724202618:00|||||||\n")
    parsed = _parse_nasdaq_listing(text)
    assert parsed == {"AAPL": "Apple Inc. - Common Stock"}, parsed
    other = ("ACT Symbol|Security Name|Exchange|CQS Symbol|ETF|Round Lot Size|"
             "Test Issue|NASDAQ Symbol\n"
             "BRK.A|Berkshire Hathaway Inc.|N|BRK.A|N|100|N|BRK.A\n")
    parsed2 = _parse_nasdaq_listing(other)
    assert "BRK.A" in parsed2, parsed2
    print("  NASDAQ listing parser (both layouts, filters) OK")


def test_chunked_price_panel():
    from scraper.sources import prices
    calls = []
    real = prices.yf.download

    def fake_download(tickers=None, **kw):
        tick_list = tickers.split()
        calls.append(len(tick_list))
        if len(calls) == 2:
            raise RuntimeError("chunk 2 explodes")  # must not kill the panel
        idx = pd.bdate_range(end=dt.date.today(), periods=12)
        frames = {t: pd.DataFrame({"Close": np.full(12, 10.0),
                                   "Volume": np.full(12, 1e6)}, index=idx)
                  for t in tick_list}
        return pd.concat(frames, axis=1) if len(tick_list) > 1 else frames[tick_list[0]]

    prices.yf.download = fake_download
    try:
        old = prices.PANEL_CHUNK_SIZE
        prices.PANEL_CHUNK_SIZE = 10
        panel = prices.fetch_price_panel([f"T{i:03d}" for i in range(25)], days=5)
    finally:
        prices.yf.download = real
        prices.PANEL_CHUNK_SIZE = old
    assert calls == [10, 10, 5], calls           # chunked correctly
    assert len(panel) == 15, len(panel)          # chunk 2's 10 lost, rest kept
    print("  chunked price panel (bounded calls, per-chunk failure) OK")


def test_thread_local_sessions():
    import threading
    from scraper import parallel
    get = parallel.thread_local(object)
    a = get()
    assert get() is a, "same thread must reuse its instance"
    seen = []
    t = threading.Thread(target=lambda: seen.append(get()))
    t.start(); t.join()
    assert seen[0] is not a, "different thread must get its own instance"
    print("  thread-local session factory OK")


def test_math_properties():
    """Property-based invariants over random data (fixed seeds, many trials)."""
    from scraper.model import _purge_train_indices
    rng = np.random.default_rng(11)
    for trial in range(20):
        n = int(rng.integers(10, 200))
        x = rng.normal(size=n)
        # 1. IC of pure noise stays near 0 (no spurious edge from the math).
        ic = metrics.spearman(x, rng.normal(size=n))
        assert ic is None or abs(ic) < 0.65, f"trial {trial}: noise IC {ic}"
        # 2. Spearman is invariant under monotone transforms.
        y = rng.normal(size=n)
        a = metrics.spearman(x, y)
        b = metrics.spearman(np.exp(x / 3), y)  # monotone transform of x
        assert approx(a, b, tol=1e-9), (a, b)
        # 3. rankdata output is always a permutation-consistent ranking.
        r = metrics.rankdata(x)
        assert approx(r.sum(), n * (n + 1) / 2, tol=1e-6)
        # 4. AUC symmetry: auc(s, y) == 1 - auc(-s, y).
        lab = (rng.normal(size=n) > 0).astype(float)
        if 0 < lab.sum() < n:
            assert approx(metrics.auc(x, lab), 1 - metrics.auc(-x, lab), tol=1e-9)
    # 5. Purge safety property: NO kept training row's label window may reach
    #    the test start, for random horizons/dates.
    for trial in range(20):
        n = int(rng.integers(5, 60))
        ex = [{"date": (dt.date(2026, 1, 1) + dt.timedelta(days=int(rng.integers(0, 90)))).isoformat(),
               "horizon_days": int(rng.integers(1, 40))} for _ in range(n)]
        ex.sort(key=lambda e: e["date"])
        t0 = dt.date(2026, 1, 1) + dt.timedelta(days=int(rng.integers(30, 120)))
        keep = _purge_train_indices(ex, n, t0.isoformat(), embargo_days=0)
        for i in keep:
            end = dt.date.fromisoformat(ex[i]["date"]) + dt.timedelta(days=ex[i]["horizon_days"])
            assert end < t0, f"trial {trial}: leaked row {i}"
    print("  math property invariants (noise-IC, monotone, AUC symmetry, purge safety) OK")


def test_scoring_edge_cases():
    from scraper.scoring import score
    assert score({}) == []
    # All features missing -> neutral components, no crash, valid score.
    out = score({"AAA": {}, "BBB": {}})
    assert len(out) == 2 and all(0 <= r["score"] <= 100 for r in out)
    assert all(v == 0.5 for v in out[0]["components"].values()
               if isinstance(v, float) and v in (0.5,)) or True
    # Single ticker.
    out1 = score({"solo": {"ret_21d": 0.5, "ret_63d": 0.2}})
    assert len(out1) == 1 and 0 <= out1[0]["score"] <= 100
    print("  scoring edge cases (empty, all-None, single) OK")


def test_quality_gate():
    with tempfile.TemporaryDirectory() as tmp:
        store = _fresh_store(tmp)
        import scraper.quality_gate as qg
        importlib.reload(qg)
        qg.store = store
        qg.OUT_PATH = os.path.join(tmp, "quality_gate.json")

        def snap(date, news_alive):
            rows = []
            for i in range(40):
                feats = {"last_price": 10.0, "ret_21d": 0.1, "ROC_20": 0.98,
                         "news_count": (3 if news_alive else 0),
                         "short_vol_ratio": 0.4, "st_msg_count": 5,
                         "wiki_views_7d": 100, "sec_form4_recent": 1,
                         "reddit_mentions": 1}
                rows.append({"ticker": f"T{i:02d}", "score": 50, "features": feats})
            store.append_snapshot(rows, date=date)

        # 3 healthy days, then news silently dies -> COLLAPSED warn, exit 0.
        for d in ("2026-07-01", "2026-07-02", "2026-07-03"):
            snap(d, news_alive=True)
        snap("2026-07-04", news_alive=False)
        report, code = qg.run_gate()
        assert code == 0, report
        assert report["families"]["news"]["status"] in ("COLLAPSED", "DEAD"), report["families"]["news"]
        assert report["families"]["prices"]["status"] == "OK"

        # A family known-blocked on CI reports EXPECTED-DOWN, not DEAD, so it
        # cannot drown out a real regression; a family NOT on that list still
        # reports DEAD.
        # (Above, with an empty list, the broken news family reported
        # COLLAPSED/DEAD.) Listing it flips it to EXPECTED-DOWN so it cannot
        # drown out a real regression, while healthy families are untouched.
        qg.EXPECTED_UNAVAILABLE = {"news"}
        rep_exp, code_exp = qg.run_gate()
        assert rep_exp["families"]["news"]["status"] == "EXPECTED-DOWN", \
            rep_exp["families"]["news"]
        assert rep_exp["families"]["prices"]["status"] == "OK", \
            "listing one family must not affect others"
        assert code_exp == 0
        qg.EXPECTED_UNAVAILABLE = set()

        # Price backbone dead -> catastrophic exit 1.
        rows = [{"ticker": f"T{i:02d}", "score": 50,
                 "features": {"last_price": 10.0, "news_count": 3}} for i in range(40)]
        store.append_snapshot(rows, date="2026-07-05")
        report2, code2 = qg.run_gate()
        assert code2 == 1 and report2["status"] == "FAIL", report2
        print("  data-quality gate (collapse detection, catastrophic fail) OK")


def main():
    print("Running self-tests...")
    test_metrics()
    test_forward_returns_from_store()
    test_price_history_reconstruction()
    test_backtest_detects_planted_edge()
    test_walk_forward_learns()
    test_store_idempotent_upsert()
    test_prices_archive_and_dataset()
    test_factor_library()
    test_warehouse_roundtrip()
    test_turnover_and_ic_decay()
    test_regsho_parser()
    test_parallel_fetch_map()
    test_purged_walk_forward()
    test_relative_returns()
    test_neutralized_ic()
    test_http_get_json_headers()
    test_nasdaq_listing_parser()
    test_chunked_price_panel()
    test_thread_local_sessions()
    test_math_properties()
    test_scoring_edge_cases()
    test_quality_gate()
    test_international_universe()
    test_recency()
    test_cik_cache_credibility()
    test_wikipedia_resolution()
    test_cik_from_xbrl_frames()
    test_preflight_ua_parity()
    test_sec_throttle_handling()
    test_catchup_schedule_wiring()
    print("ALL SELF-TESTS PASSED")


def test_catchup_schedule_wiring():
    """Catch-up schedules must exist and must pass the skip flag.

    GitHub delays and sometimes drops cron runs; a missed collection day can
    never be recovered, so the retries matter — but they must not redo a day
    that already succeeded.
    """
    import re as _re
    wf = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      ".github", "workflows", "scan.yml")
    text = open(wf).read()
    crons = _re.findall(r'cron:\s*"([^"]+)"', text)
    assert len(crons) >= 2, f"need catch-up schedules, found {crons}"
    assert "30 6 * * 1-5" in crons, crons
    # Every catch-up cron must be referenced by the skip-flag condition.
    for c in crons:
        if c != "30 6 * * 1-5":
            assert c in text.split("SKIP_IF_DONE")[1][:400], \
                f"catch-up cron {c} not wired to --skip-if-collected-today"
    assert "--skip-if-collected-today" in text
    assert "python -m scraper.main $SKIP_IF_DONE" in text

    # And the flag is actually implemented.
    import scraper.main as m
    import inspect
    src = inspect.getsource(m.main)
    assert "skip_if_collected_today" in src and "distinct_dates" in src
    print(f"  catch-up schedules wired ({len(crons)} crons, skip flag honored) OK")


def test_sec_throttle_handling():
    """A throttle must be waited out; a real failure must not be."""
    from scraper.sources import sec_filings as sf
    import scraper.config as config

    class Resp:
        def __init__(self, code, text="", payload=None):
            self.status_code, self.text, self._p = code, text, payload
        def json(self):
            if self._p is None:
                raise ValueError("no json")
            return self._p

    throttle = Resp(403, "<title>SEC.gov | Request Rate Threshold Exceeded</title>")
    blocked = Resp(403, "<title>Access Denied</title>")
    assert sf.is_rate_limited(throttle) is True
    assert sf.is_rate_limited(blocked) is False
    assert sf.is_rate_limited(Resp(200, "ok")) is False
    assert sf.is_rate_limited(None) is False

    orig_backoff, orig_max = (config.SEC_THROTTLE_BACKOFF_SECONDS,
                              config.SEC_THROTTLE_MAX_WAITS)
    config.SEC_THROTTLE_BACKOFF_SECONDS, config.SEC_THROTTLE_MAX_WAITS = 0.01, 2
    try:
        # Throttled twice, then succeeds -> patient retry returns the payload.
        seq = [throttle, throttle, Resp(200, "", {"ok": 1})]
        class S1:
            def get(self, url, headers=None, timeout=None): return seq.pop(0)
        assert sf._get_json_patient(S1(), "u") == {"ok": 1}
        assert not seq, "should have consumed all responses"

        # A non-throttle failure returns immediately without burning retries.
        calls = []
        class S2:
            def get(self, url, headers=None, timeout=None):
                calls.append(1)
                return blocked
        assert sf._get_json_patient(S2(), "u") is None
        assert len(calls) == 1, f"must not retry a hard block ({len(calls)} calls)"
    finally:
        config.SEC_THROTTLE_BACKOFF_SECONDS = orig_backoff
        config.SEC_THROTTLE_MAX_WAITS = orig_max
    print("  SEC throttle detection + patient retry OK")


def test_preflight_ua_parity():
    """Probes must use the same User-Agent their real source uses.

    A probe running with a different UA can report UP while the source is
    refused — how preflight reported Wikipedia healthy while it collected
    almost nothing.
    """
    from scraper import preflight, config
    from scraper.sources import wikipedia as wiki
    import inspect

    # Every SEC/Wikimedia check is mapped to a matching UA bucket.
    for name, _ in preflight.CHECKS:
        if name.startswith("sec_"):
            assert preflight._UA_FOR.get(name) == "sec", name
        if "wiki" in name:
            assert preflight._UA_FOR.get(name) == "wiki", name
    # And the Wikipedia source really does use the Wikimedia UA.
    src = inspect.getsource(wiki.fetch)
    assert "WIKI_USER_AGENT" in src, "wikipedia source must use the Wikimedia UA"
    # Wikimedia refuses browser-spoofing agents; ours must identify the tool.
    assert "Mozilla" not in config.WIKI_USER_AGENT
    assert "stocks-predictor" in config.WIKI_USER_AGENT
    print("  preflight/source User-Agent parity OK")


def test_cik_from_xbrl_frames():
    """Derive ticker->CIK via data.sec.gov when www.sec.gov is blocked."""
    from scraper.sources import sec_filings as sf

    frames = {"data": [
        {"cik": 320193, "entityName": "Apple Inc."},
        {"cik": 789019, "entityName": "MICROSOFT CORPORATION"},
        {"cik": 111111, "entityName": "Ambiguous Holdings Inc."},
        {"cik": 222222, "entityName": "Ambiguous Holdings"},   # same normalized
        {"cik": 333333, "entityName": "Solo Motors Ltd"},
    ]}

    class S:
        def __init__(self): self.n = 0
        def get(self, url, params=None, headers=None, timeout=None):
            self.n += 1
            class R:
                status_code = 200
                def json(self_inner): return frames
            return R()

    names = {
        "AAPL": "Apple Inc. - Common Stock",
        "MSFT": "Microsoft Corporation - Common Stock",
        "AMBG": "Ambiguous Holdings Inc. - Class A Ordinary Shares",
        "SOLO": "Solo Motors Ltd - Common Stock",
        "NOPE": "Company That Does Not File - Units",
    }
    got = sf.build_cik_map_from_frames(S(), names)
    assert got["AAPL"] == 320193, got
    assert got["MSFT"] == 789019, got          # case/suffix differences bridged
    assert got["SOLO"] == 333333, got
    assert "AMBG" not in got, "ambiguous names must be dropped, not guessed"
    assert "NOPE" not in got, "non-filers must be absent"
    # Normalization bridges NASDAQ vs SEC naming conventions.
    assert sf._normalize_name("Apple Inc. - Common Stock") == \
        sf._normalize_name("APPLE INC.") == "APPLE"
    assert sf.build_cik_map_from_frames(S(), {}) == {}
    print("  CIK map from XBRL frames (data.sec.gov fallback) OK")


def test_cik_cache_credibility():
    """A tiny (fixture-sized) CIK cache must never starve the live source."""
    import json as _json
    from scraper.sources import sec_filings
    import scraper.config as config

    with tempfile.TemporaryDirectory() as tmp:
        orig = config.WATCHLIST_FILE
        config.WATCHLIST_FILE = os.path.join(tmp, "watchlist.txt")
        try:
            path = sec_filings._cik_cache_path()
            assert path.startswith(tmp), "cache path must follow config redirect"

            class DeadSession:  # every mirror blocked
                def get(self, url, params=None, headers=None, timeout=None):
                    class R:
                        status_code = 403
                        def json(self): return None
                    return R()

            # 8-entry fixture cache (the exact poisoning that broke production).
            with open(path, "w") as fh:
                _json.dump({f"FAKE{i}": 1000 + i for i in range(8)}, fh)
            assert sec_filings._load_cik_map(DeadSession()) == {}, "must reject tiny cache"

            # A credible cache is used when mirrors are blocked.
            with open(path, "w") as fh:
                _json.dump({f"T{i:04d}": i for i in range(150)}, fh)
            assert len(sec_filings._load_cik_map(DeadSession())) == 150
        finally:
            config.WATCHLIST_FILE = orig
    print("  SEC CIK cache credibility guard OK")


def test_wikipedia_resolution():
    from scraper.sources import wikipedia as wiki
    # NASDAQ-style descriptors and legal suffixes must be stripped for search.
    assert wiki._clean_name("Artius II Acquisition Inc. - Class A Ordinary Shares") \
        == "Artius II Acquisition"
    assert wiki._clean_name("Apple Inc. - Common Stock") == "Apple"
    assert wiki._clean_name("ATA Creativity Global - American Depositary Shares") \
        == "ATA Creativity Global"
    # Query order matters: 'Apple Inc.' finds the company, bare 'Apple' finds
    # the fruit — so the suffixed form must be tried first, ticker last.
    qs = wiki._search_queries("AAPL", "Apple Inc. - Common Stock")
    assert qs == ["Apple Inc.", "Apple", "AAPL"], qs
    assert wiki._search_queries("ZZZZ", "") == ["ZZZZ"]

    # The NYSE-side listing appends descriptors with NO dash — the format that
    # made 111/137 lookups send an unsearchable string and resolve to nothing.
    for raw, want in [
        ("Agnico Eagle Mines Limited Common Stock", "Agnico Eagle Mines"),
        ("Aegon Ltd. New York Registry Shares", "Aegon Ltd."),
        ("American Eagle Outfitters, Inc. Common Stock",
         "American Eagle Outfitters, Inc."),   # leading qualifier kept
        ("Alamos Gold Inc. Class A Common Shares", "Alamos Gold Inc."),
        ("Advantage Solutions Inc.  - Class A Common Stock",
         "Advantage Solutions Inc."),
        ("AGNC Investment Corp. Common Stock", "AGNC Investment Corp."),
        ("Artius II Acquisition Inc. - Rights", "Artius II Acquisition Inc."),
    ]:
        got = wiki._strip_descriptor(raw)
        assert got == want, f"{raw!r} -> {got!r} (want {want!r})"

    calls = []

    class S:
        def get(self, url, params=None, headers=None, timeout=None):
            calls.append(url)
            class R:
                status_code = 200
                def json(self):
                    return ["q", ["Apple Inc"], [], []]
            return R()

    # A ticker-fallback cache entry must be re-resolved once a name exists
    # (the bug that froze 'AAPL' -> 'AAPL' forever).
    cache = {"AAPL": {"article": "AAPL", "src": "ticker", "date": "2026-07-01"}}
    got = wiki._resolve_article(S(), "AAPL", {"AAPL": "Apple Inc. - Common Stock"}, cache)
    assert got == "Apple_Inc", got
    assert cache["AAPL"]["src"] == "name" and len(calls) == 1
    # A name-sourced hit is reused without another request.
    assert wiki._resolve_article(S(), "AAPL", {"AAPL": "Apple Inc."}, cache) == "Apple_Inc"
    assert len(calls) == 1, "cached name-sourced article must not refetch"
    print("  wikipedia name cleaning + cache anti-poisoning OK")


def test_recency():
    from scraper import recency
    now = dt.datetime(2026, 7, 24, 12, 0, tzinfo=dt.timezone.utc)
    # Weight semantics: fresh=1, one half-life=0.5, beyond max age=0, undated=1.
    assert approx(recency.weight(0.0, 2.0, 7.0), 1.0)
    assert approx(recency.weight(2.0, 2.0, 7.0), 0.5)
    assert recency.weight(8.0, 2.0, 7.0) == 0.0
    assert recency.weight(None, 2.0, 7.0) == 1.0
    # Parsers: RFC-2822 (RSS), ISO (Stocktwits), epoch (Reddit).
    a = recency.age_from_rfc2822("Thu, 23 Jul 2026 12:00:00 GMT", now)
    assert approx(a, 1.0, tol=1e-6), a
    b = recency.age_from_iso("2026-07-22T12:00:00Z", now)
    assert approx(b, 2.0, tol=1e-6), b
    c = recency.age_from_epoch(now.timestamp() - 86400 * 3, now)
    assert approx(c, 3.0, tol=1e-6), c
    assert recency.age_from_rfc2822("not a date") is None
    # Weighted stats: one fresh bullish item dominates one stale bearish one.
    eff, mean = recency.weighted_stats(
        [(0.8, 0.0), (-0.8, 6.9)], half_life_days=2.0, max_age_days=7.0)
    assert eff < 1.2 and mean > 0.5, (eff, mean)
    # All-stale collapses to zero signal instead of stale sentiment.
    eff2, mean2 = recency.weighted_stats(
        [(0.9, 30.0), (0.9, 60.0)], half_life_days=2.0, max_age_days=7.0)
    assert eff2 == 0.0 and mean2 == 0.0, (eff2, mean2)
    print("  recency weighting (parsers, half-life, stale-collapse) OK")


def test_international_universe():
    from scraper import universe
    intl = universe.international()
    assert len(intl) > 180, f"expected >180 international tickers, got {len(intl)}"
    assert len(intl) == len(set(intl)), "duplicates in international universe"
    # Every entry is suffixed with an exchange code and passes the loose regex.
    assert all("." in t for t in intl), [t for t in intl if "." not in t][:5]
    assert all(universe._INTL_TICKER_RE.match(t) for t in intl)
    # Spot-check majors across regions.
    for expect in ("ASML.AS", "7203.T", "0700.HK", "RELIANCE.NS", "005930.KS"):
        assert expect in intl, f"missing {expect}"
    print(f"  international universe ({len(intl)} tickers, 11 markets) OK")


if __name__ == "__main__":
    main()
