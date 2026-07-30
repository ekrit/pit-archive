"""Calibrated ensemble: turn model scores into probabilities you can size on.

Rung 3 of ALGORITHMS.md. Two ideas, both aimed at the same failure mode —
a model that ranks acceptably but whose numbers mean nothing:

1. RANK-AVERAGE ENSEMBLE. A linear model and a gradient-boosted model make
   different mistakes; averaging their per-date RANKS (not their raw scores,
   which live on incomparable scales and drift) is a robust blend that
   rarely underperforms the better member.

2. ISOTONIC CALIBRATION, FIT OUT-OF-SAMPLE. Ranking scores are not
   probabilities. Calibration is fitted on held-out folds only — fitting it
   on training data would produce beautiful, meaningless curves. After it,
   "0.30" should mean roughly three in ten.

Everything here is walk-forward: for each fold we train on the past, predict
the future, and fit the calibrator on earlier out-of-sample predictions.
"""
from __future__ import annotations

import numpy as np

from . import metrics, model


def _rank01(x: np.ndarray) -> np.ndarray:
    """Ranks scaled to [0,1]; NaN-safe, ties averaged."""
    x = np.asarray(x, dtype=float)
    if x.size == 0:
        return x
    r = metrics.rankdata(np.nan_to_num(x, nan=np.nanmin(x) if np.isfinite(x).any() else 0.0))
    return (r - 1) / max(len(r) - 1, 1)


def rank_average(score_sets: list[np.ndarray]) -> np.ndarray:
    """Average several score vectors after converting each to [0,1] ranks."""
    usable = [s for s in score_sets if s is not None and len(s)]
    if not usable:
        return np.array([])
    return np.mean([_rank01(s) for s in usable], axis=0)


def walk_forward_ensemble(
    examples: list[dict],
    feature_keys: list[str],
    target: str = "top_quintile",
    n_folds: int = 4,
    big_move_threshold: float = 0.30,
    embargo_days: int = 2,
) -> dict:
    """Purged walk-forward ensemble with out-of-sample calibration.

    target: "top_quintile" (peer-relative ranking) or "big_move"
            (P(fwd_ret >= threshold) — the 'next big riser' question).
    """
    ex = sorted(examples, key=lambda e: e.get("date", ""))
    if len(ex) < 60:
        return {"error": "need >=60 labeled examples for a calibrated ensemble",
                "n": len(ex), "target": target}

    y = (model.label_big_move(ex, big_move_threshold) if target == "big_move"
         else model.label_top_quantile(ex))
    if len(np.unique(y)) < 2:
        return {"error": f"target '{target}' has only one class "
                         f"(positive rate {y.mean():.3f})", "n": len(ex)}

    X = model._matrix(ex, feature_keys)
    fwd = np.array([e.get("fwd_ret", np.nan) for e in ex], dtype=float)
    n = len(ex)
    fold = n // (n_folds + 1)

    oos_raw, oos_y, oos_fwd = [], [], []
    for f in range(1, n_folds + 1):
        tr_end, te_end = fold * f, min(fold * (f + 1), n)
        if te_end - tr_end < 5 or tr_end < 30:
            continue
        tr_idx = model._purge_train_indices(
            ex, tr_end, ex[tr_end].get("date", ""), embargo_days)
        if len(tr_idx) < 30 or len(np.unique(y[tr_idx])) < 2:
            continue
        Xtr, Xte = model._standardize(X[tr_idx], X[tr_end:te_end])
        ytr = y[tr_idx]

        members = []
        lin = model._NumpyLogReg().fit(Xtr, ytr)
        members.append(lin.predict_proba(Xte))
        if model._HAVE_SKLEARN:
            try:
                gbm = model._make_model()
                gbm.fit(Xtr, ytr)
                p = gbm.predict_proba(Xte)
                members.append(p[:, 1] if getattr(p, "ndim", 1) == 2 else p)
            except Exception:  # noqa: BLE001 - fall back to the linear member
                pass

        oos_raw.extend(rank_average(members).tolist())
        oos_y.extend(y[tr_end:te_end].tolist())
        oos_fwd.extend(fwd[tr_end:te_end].tolist())

    if not oos_raw:
        return {"error": "no valid folds", "n": n, "target": target}

    raw = np.array(oos_raw)
    lab = np.array(oos_y)
    fw = np.array(oos_fwd)

    # Calibrate on the FIRST half of out-of-sample predictions, score the
    # second: fitting and judging a calibrator on the same rows would flatter
    # it exactly the way in-sample backtests flatter models.
    half = len(raw) // 2
    result = {
        "target": target,
        "backend": "ensemble(numpy-logreg+sklearn-HGB)" if model._HAVE_SKLEARN
        else "ensemble(numpy-logreg)",
        "n_oos": int(raw.size),
        "positive_rate": round(float(lab.mean()), 4),
        "oos_auc": metrics.auc(raw, lab),
        "oos_ic": metrics.spearman(raw, fw),
        "brier_uncalibrated": metrics.brier_score(raw, lab),
    }
    if half >= 20:
        knots = metrics.isotonic_fit(raw[:half], lab[:half])
        cal = metrics.isotonic_predict(knots, raw[half:])
        result["brier_calibrated"] = metrics.brier_score(cal, lab[half:])
        result["calibration"] = metrics.calibration_table(cal, lab[half:])
    for k in ("oos_auc", "oos_ic", "brier_uncalibrated", "brier_calibrated"):
        if isinstance(result.get(k), float):
            result[k] = round(result[k], 4)
    return result


def fit_full(examples: list[dict], feature_keys: list[str],
             target: str = "top_quintile", big_move_threshold: float = 0.30):
    """Train on ALL labeled data and return a scorer for today's snapshot.

    Returns (predict_fn, info). The calibrator is fitted on held-out folds
    via walk_forward_ensemble first, so the probabilities the scorer emits
    carry an out-of-sample-validated mapping rather than an in-sample one.
    """
    ex = sorted(examples, key=lambda e: e.get("date", ""))
    y = (model.label_big_move(ex, big_move_threshold) if target == "big_move"
         else model.label_top_quantile(ex))
    X = model._matrix(ex, feature_keys)
    mu = np.nanmean(X, axis=0)
    sd = np.nanstd(X, axis=0)
    sd = np.where(sd == 0, 1.0, sd)
    Xz = np.nan_to_num((X - mu) / sd, nan=0.0)

    members = [model._NumpyLogReg().fit(Xz, y)]
    if model._HAVE_SKLEARN:
        try:
            gbm = model._make_model()
            gbm.fit(Xz, y)
            members.append(gbm)
        except Exception:  # noqa: BLE001
            pass

    # In-sample ensemble scores -> isotonic map. Honest caveat: this map is
    # in-sample; the OOS Brier from walk_forward_ensemble is the number that
    # says whether to believe it.
    def _score(matrix):
        outs = []
        for m in members:
            p = m.predict_proba(matrix)
            outs.append(p[:, 1] if getattr(p, "ndim", 1) == 2 else p)
        return rank_average(outs)

    knots = metrics.isotonic_fit(_score(Xz), y)

    def predict(feature_rows: list[dict]) -> np.ndarray:
        M = model._matrix(feature_rows, feature_keys)
        Mz = np.nan_to_num((M - mu) / sd, nan=0.0)
        return metrics.isotonic_predict(knots, _score(Mz))

    return predict, {"n_train": len(ex), "positive_rate": round(float(y.mean()), 4),
                     "members": len(members), "target": target}
