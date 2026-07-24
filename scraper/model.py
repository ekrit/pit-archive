"""Walk-forward learned model: let the data pick the weights.

The screener's hand-set weights are a guess. This module instead *learns* how
to combine signals to predict a big forward move — and, crucially, evaluates
that model the only honest way for time series: walk-forward. We sort examples
by date, repeatedly train on the past and predict the strictly-future next
block, and report out-of-sample performance. No shuffled train/test split (a
shuffle leaks the future into the past and is the #1 way backtests lie).

Primary implementation is a pure-numpy standardized L2 logistic regression so
it runs with no heavy dependencies. If scikit-learn is installed (see
requirements.txt), a GradientBoosting model is used instead for its ability to
capture non-linear interactions.
"""
from __future__ import annotations

import numpy as np

from . import metrics

try:  # optional upgrade
    from sklearn.ensemble import HistGradientBoostingClassifier  # type: ignore

    _HAVE_SKLEARN = True
except Exception:  # pragma: no cover - env dependent
    _HAVE_SKLEARN = False


def _matrix(examples: list[dict], feature_keys: list[str]) -> np.ndarray:
    rows = []
    for e in examples:
        feats = e.get("features") or {}
        rows.append([_num(feats.get(k)) for k in feature_keys])
    return np.array(rows, dtype=float)


def _num(x):
    return float(x) if isinstance(x, (int, float)) else np.nan


def _standardize(train: np.ndarray, *others: np.ndarray):
    mu = np.nanmean(train, axis=0)
    sd = np.nanstd(train, axis=0)
    sd = np.where(sd == 0, 1.0, sd)

    def norm(m):
        z = (m - mu) / sd
        return np.nan_to_num(z, nan=0.0)  # missing -> mean (0 after centering)

    return (norm(train), *[norm(o) for o in others])


class _NumpyLogReg:
    def __init__(self, l2: float = 1.0, lr: float = 0.1, epochs: int = 400):
        self.l2, self.lr, self.epochs = l2, lr, epochs
        self.w = None
        self.b = 0.0

    def fit(self, X, y):
        n, d = X.shape
        self.w = np.zeros(d)
        self.b = 0.0
        for _ in range(self.epochs):
            z = X @ self.w + self.b
            p = 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))
            err = p - y
            gw = X.T @ err / n + self.l2 * self.w / n
            gb = err.mean()
            self.w -= self.lr * gw
            self.b -= self.lr * gb
        return self

    def predict_proba(self, X):
        z = X @ self.w + self.b
        return 1.0 / (1.0 + np.exp(-np.clip(z, -30, 30)))


def _make_model():
    if _HAVE_SKLEARN:
        return HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05,
                                              max_iter=200, l2_regularization=1.0)
    return _NumpyLogReg()


def label_top_quantile(examples: list[dict], top_frac: float = 0.2) -> np.ndarray:
    """Label = 1 if fwd_ret is in the top `top_frac` of its own date's names."""
    from collections import defaultdict

    by_date = defaultdict(list)
    for idx, e in enumerate(examples):
        by_date[e.get("date", "?")].append(idx)
    y = np.zeros(len(examples))
    for _, idxs in by_date.items():
        rets = np.array([examples[i]["fwd_ret"] for i in idxs])
        if len(rets) < 5:
            continue
        thresh = np.quantile(rets, 1 - top_frac)
        for i in idxs:
            if examples[i]["fwd_ret"] >= thresh:
                y[i] = 1.0
    return y


def walk_forward(
    examples: list[dict], feature_keys: list[str], n_folds: int = 4, top_frac: float = 0.2
) -> dict:
    """Expanding-window walk-forward evaluation. Returns OOS AUC and IC."""
    ex = sorted(examples, key=lambda e: e.get("date", ""))
    if len(ex) < 40:
        return {"error": "not enough labeled examples for walk-forward (need >=40)",
                "n": len(ex), "backend": "sklearn" if _HAVE_SKLEARN else "numpy"}

    y_all = label_top_quantile(ex, top_frac)
    X_all = _matrix(ex, feature_keys)
    fwd_all = np.array([e["fwd_ret"] for e in ex])

    n = len(ex)
    fold_size = n // (n_folds + 1)
    oos_scores, oos_labels, oos_fwd = [], [], []

    for f in range(1, n_folds + 1):
        tr_end = fold_size * f
        te_end = min(fold_size * (f + 1), n)
        if te_end - tr_end < 5 or tr_end < 20:
            continue
        Xtr_raw, Xte_raw = X_all[:tr_end], X_all[tr_end:te_end]
        ytr = y_all[:tr_end]
        if len(np.unique(ytr)) < 2:
            continue
        Xtr, Xte = _standardize(Xtr_raw, Xte_raw)
        model = _make_model()
        model.fit(Xtr, ytr)
        if hasattr(model, "predict_proba"):
            proba = model.predict_proba(Xte)
            if proba.ndim == 2:
                proba = proba[:, 1]
        else:  # numpy model
            proba = model.predict_proba(Xte)
        oos_scores.extend(proba.tolist())
        oos_labels.extend(y_all[tr_end:te_end].tolist())
        oos_fwd.extend(fwd_all[tr_end:te_end].tolist())

    if not oos_scores:
        return {"error": "no valid folds", "n": n,
                "backend": "sklearn" if _HAVE_SKLEARN else "numpy"}

    s = np.array(oos_scores)
    lab = np.array(oos_labels)
    fwd = np.array(oos_fwd)
    return {
        "backend": "sklearn-HGB" if _HAVE_SKLEARN else "numpy-logreg",
        "n_oos": int(s.size),
        "oos_auc": round(metrics.auc(s, lab), 4) if metrics.auc(s, lab) is not None else None,
        "oos_ic": round(metrics.spearman(s, fwd), 4) if metrics.spearman(s, fwd) is not None else None,
        "oos_top_quintile_hit_rate": round(metrics.hit_rate(s, fwd), 3)
        if metrics.hit_rate(s, fwd) is not None else None,
        "oos_decile_spread": metrics.decile_spread(s, fwd)["spread"],
        "feature_keys": feature_keys,
    }
