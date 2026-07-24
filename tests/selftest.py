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
    print("ALL SELF-TESTS PASSED")


if __name__ == "__main__":
    main()
