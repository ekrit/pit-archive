"""Learned daily predictions: replace hand-tuned weights with trained ones.

    python -m scraper.predict

Once the archive holds enough labeled history (>= MIN_DATES dates and
>= MIN_EXAMPLES labeled examples), this trains the model on ALL labeled data
and scores the LATEST snapshot, writing PREDICTIONS.md — a ranked list with
P(top-quintile relative return). Until then it writes an honest "not enough
data yet" status instead of fake numbers.

This automatically retires the composite score's biggest weakness (guessed
weights): the learned list strengthens daily as history accumulates, with
out-of-sample quality tracked separately in EVALUATION.md. The heuristic
RANKINGS.md stays as the attention screen; PREDICTIONS.md is the model's view.
"""
from __future__ import annotations

import datetime as dt
import os

import numpy as np

from . import dataset, model, store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_MD = os.path.join(ROOT, "PREDICTIONS.md")

MIN_DATES = 8
MIN_EXAMPLES = 200
HORIZON = 63
TOP_N = 20

DISCLAIMER = (
    "Model output, not advice. Probabilities are only as good as the "
    "walk-forward numbers in EVALUATION.md say they are — check them first. "
    "If OOS IC there is ~0, this list is noise with confident formatting."
)


def _not_ready(n_dates: int, n_examples: int) -> str:
    need_d = max(0, MIN_DATES - n_dates)
    return "\n".join([
        "# Model Predictions",
        "",
        f"_Status: **collecting** — {n_dates} snapshot dates, {n_examples} labeled "
        f"examples so far (need ≥{MIN_DATES} dates & ≥{MIN_EXAMPLES} examples; "
        f"roughly {need_d} more collection days plus the {HORIZON}d label lag)._",
        "",
        "The daily heuristic screen is in RANKINGS.md. Learned predictions appear "
        "here automatically once enough labeled history exists to train on.",
        "",
    ])


def run() -> str:
    features_all = store.load_features()
    dates = store.distinct_dates(features_all)
    examples = dataset.compile_labeled(horizon=HORIZON, write=False)

    if len(dates) < MIN_DATES or len(examples) < MIN_EXAMPLES:
        return _not_ready(len(dates), len(examples))

    # Train on every labeled example (relative-return top-quintile target).
    for e in examples:
        e["fwd_ret"] = e.get("rel_ret", e["fwd_ret"])  # peer-relative target
    feature_keys = dataset.FEATURE_KEYS
    ex_sorted = sorted(examples, key=lambda e: e.get("date", ""))
    y = model.label_top_quantile(ex_sorted)
    X = model._matrix(ex_sorted, feature_keys)
    Xz, = model._standardize(X)
    clf = model._make_model()
    clf.fit(Xz, y)

    # Score the latest snapshot.
    latest = dates[-1]
    todays = [r for r in features_all if r.get("date") == latest]
    Xt = model._matrix(
        [{"features": r.get("features", {})} for r in todays], feature_keys)
    # standardize with training stats
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0)
    sd = np.where(sd == 0, 1.0, sd)
    Xtz = np.nan_to_num((Xt - mu) / sd, nan=0.0)
    proba = clf.predict_proba(Xtz)
    if getattr(proba, "ndim", 1) == 2:
        proba = proba[:, 1]

    ranked = sorted(zip(todays, proba), key=lambda t: -t[1])[:TOP_N]
    lines = [
        "# Model Predictions",
        "",
        f"_Trained on {len(ex_sorted)} labeled examples across "
        f"{len({e['date'] for e in ex_sorted})} dates · scored snapshot: {latest} · "
        f"target: top-quintile {HORIZON}d relative return · "
        f"generated {dt.datetime.now(dt.timezone.utc).isoformat()}_",
        "",
        f"> {DISCLAIMER}",
        "",
        "| # | Ticker | P(top quintile) | Heuristic score |",
        "|--:|:------:|----------------:|----------------:|",
    ]
    for i, (rec, p) in enumerate(ranked, 1):
        lines.append(f"| {i} | {rec['ticker']} | {p:.3f} | {rec.get('score', '—')} |")
    lines.append("")
    return "\n".join(lines)


def main():
    md = run()
    with open(OUT_MD, "w") as fh:
        fh.write(md)
    print(f"[predict] wrote {OUT_MD}")
    print(md.split("\n")[2][:120])


if __name__ == "__main__":
    main()
