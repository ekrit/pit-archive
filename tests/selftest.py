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


def main():
    print("Running self-tests...")
    test_metrics()
    test_forward_returns_from_store()
    test_price_history_reconstruction()
    test_backtest_detects_planted_edge()
    test_walk_forward_learns()
    test_store_idempotent_upsert()
    test_prices_archive_and_dataset()
    print("ALL SELF-TESTS PASSED")


if __name__ == "__main__":
    main()
