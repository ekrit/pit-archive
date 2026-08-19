"""Compile the raw archives into a clean, deduplicated, training-ready dataset.

Ingestion (store.py) is optimized for safe, idempotent daily writes. Modeling
wants something different: one flat table of `(point-in-time features -> realized
forward return)` with labels computed from the DENSE price archive rather than
from sparse feature snapshots, so a name that left the hot list still gets a
label. This module is that bridge, plus a data-quality report so you can trust
what you're training on.

Outputs (written under data/dataset/):
  * labeled_<H>d.jsonl   — one row per (date, ticker) with features + fwd_ret
  * quality_<H>d.json    — coverage / missingness / label stats
"""
from __future__ import annotations

import bisect
import datetime as dt
import json
import os

from . import factors, store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET_DIR = os.path.join(ROOT, "data", "dataset")

BASE_FEATURE_KEYS = [
    "ret_5d", "ret_21d", "ret_63d", "volume_spike_ratio", "rsi_14",
    "pct_off_52w_high", "pct_above_52w_low", "annualized_vol",
    "news_count", "news_sentiment", "reddit_mentions", "reddit_sentiment",
    "sec_form4_recent", "sec_8k_recent",
    "st_trending", "st_msg_count", "st_sentiment",
    "wiki_views_7d", "wiki_spike_ratio", "short_vol_ratio",
    "eps_rev_30d", "eps_rev_90d", "eps_rev_breadth", "eps_rev_vs_price",
    "analyst_count", "pt_upside",
]
FEATURE_KEYS = BASE_FEATURE_KEYS + factors.FACTOR_NAMES


def _future_close(series: list[tuple[str, float]], d0: str, horizon: int,
                  tolerance: int) -> float | None:
    """Close nearest to d0 + horizon days, within `tolerance` days, strictly after d0."""
    target = (dt.date.fromisoformat(d0) + dt.timedelta(days=horizon)).isoformat()
    dates = [d for d, _ in series]
    # first index with date > d0
    lo = bisect.bisect_right(dates, d0)
    best = None
    best_gap = None
    tgt = dt.date.fromisoformat(target)
    for i in range(lo, len(series)):
        d, c = series[i]
        gap = abs((dt.date.fromisoformat(d) - tgt).days)
        if gap <= tolerance and (best_gap is None or gap < best_gap):
            best, best_gap = c, gap
        if dt.date.fromisoformat(d) > tgt and best is not None:
            break  # past the window and we already have a candidate
    return best


def _close_asof(series: list[tuple[str, float]], d0: str, back_tolerance: int = 4) -> float | None:
    """Close on d0, or the most recent close within `back_tolerance` days before it."""
    dates = [d for d, _ in series]
    i = bisect.bisect_right(dates, d0) - 1
    if i < 0:
        return None
    d, c = series[i]
    if (dt.date.fromisoformat(d0) - dt.date.fromisoformat(d)).days <= back_tolerance:
        return c
    return None


def compile_labeled(horizon: int = 63, tolerance: int = 7, write: bool = True) -> list[dict]:
    """Join features to the dense price archive; return labeled examples."""
    features = store.load_features()
    panel = store.price_panel()

    examples: list[dict] = []
    for rec in features:
        tk, d0 = rec.get("ticker"), rec.get("date")
        if not tk or not d0:
            continue
        series = panel.get(tk, [])
        # Entry price: prefer the archive; fall back to the snapshot's last_price.
        p0 = _close_asof(series, d0) if series else None
        if p0 is None:
            p0 = rec.get("last_price")
        if not p0 or p0 <= 0:
            continue
        p1 = _future_close(series, d0, horizon, tolerance) if series else None
        if p1 is None:
            continue
        examples.append({
            "date": d0,
            "ticker": tk,
            "features": rec.get("features", {}),
            "score": rec.get("score"),
            "entry_price": p0,
            "exit_price": p1,
            "fwd_ret": p1 / p0 - 1.0,
            "horizon_days": horizon,
        })

    # Relative forward return: raw return minus the same-date cross-sectional
    # median. This is the better modeling target — it strips the market-wide
    # move (beta) out of the label, so a signal must pick WHICH names outrun
    # their peers, not merely notice that everything rose together.
    from collections import defaultdict
    by_date: dict[str, list[float]] = defaultdict(list)
    for e in examples:
        by_date[e["date"]].append(e["fwd_ret"])
    medians = {d: sorted(v)[len(v) // 2] for d, v in by_date.items()}
    for e in examples:
        e["rel_ret"] = e["fwd_ret"] - medians[e["date"]]

    if write:
        os.makedirs(DATASET_DIR, exist_ok=True)
        out_path = os.path.join(DATASET_DIR, f"labeled_{horizon}d.jsonl")
        with open(out_path, "w") as fh:
            for e in examples:
                fh.write(json.dumps(e, separators=(",", ":"), sort_keys=True) + "\n")
        quality_report(examples, horizon, write=True)
    return examples


def quality_report(examples: list[dict], horizon: int, write: bool = False) -> dict:
    n = len(examples)
    missing = {k: 0 for k in FEATURE_KEYS}
    for e in examples:
        feats = e.get("features") or {}
        for k in FEATURE_KEYS:
            v = feats.get(k)
            if not isinstance(v, (int, float)) or v != v:
                missing[k] += 1
    rets = [e["fwd_ret"] for e in examples]
    pos = sum(1 for r in rets if r > 0)
    report = {
        "horizon_days": horizon,
        "labeled_rows": n,
        "distinct_dates": len({e["date"] for e in examples}),
        "distinct_tickers": len({e["ticker"] for e in examples}),
        "label_positive_rate": round(pos / n, 4) if n else None,
        "fwd_ret_mean": round(sum(rets) / n, 4) if n else None,
        "feature_missing_pct": {
            k: round(100 * missing[k] / n, 1) if n else None for k in FEATURE_KEYS
        },
    }
    if write:
        os.makedirs(DATASET_DIR, exist_ok=True)
        with open(os.path.join(DATASET_DIR, f"quality_{horizon}d.json"), "w") as fh:
            json.dump(report, fh, indent=2)
    return report
