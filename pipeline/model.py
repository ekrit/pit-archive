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


def _dead_features(train: np.ndarray) -> np.ndarray:
    """Boolean mask of columns with no finite value anywhere in the training window.

    A short training window can miss a whole feature family: the estimates
    sources only start on 2026-08-20, so a fold training on 2026-07-20 has
    nothing but NaN in those six columns while the test rows have real
    values. Naive standardization turns that into NaN/NaN -> 0 silently,
    which quietly feeds the model a column it could never learn from.
    """
    return ~np.isfinite(train).any(axis=0)


def _standardize(train: np.ndarray, *others: np.ndarray):
    dead = _dead_features(train)
    mu = np.zeros(train.shape[1], dtype=float)
    sd = np.ones(train.shape[1], dtype=float)
    live = ~dead
    if live.any():
        mu[live] = np.nanmean(train[:, live], axis=0)
        s = np.nanstd(train[:, live], axis=0)
        sd[live] = np.where(s == 0, 1.0, s)

    def norm(m):
        z = (m - mu) / sd
        if dead.any():
            z[:, dead] = 0.0   # unlearnable from this window; carry no signal
        return np.nan_to_num(z, nan=0.0, posinf=0.0, neginf=0.0)

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


def label_big_move(examples: list[dict], threshold: float = 0.30) -> np.ndarray:
    """1 if the ABSOLUTE forward return clears `threshold` (e.g. +30%).

    This is the "next big riser" question stated honestly: a rare-event
    classification, not a ranking. It is deliberately separate from the
    top-quintile target because in a falling market the best relative
    performer can still lose money — and a +30% hit rate is the number that
    actually corresponds to what you are hunting.
    """
    return np.array(
        [1.0 if e.get("fwd_ret", 0.0) >= threshold else 0.0 for e in examples],
        dtype=float)


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


def _purge_train_indices(ex: list[dict], tr_end: int, test_start_date: str,
                         embargo_days: int = 0) -> np.ndarray:
    """Purged + embargoed training indices (Lopez de Prado, AFML ch.7).

    A training example whose forward-return window [date, date+horizon] reaches
    into the test period leaks the test period's prices into training labels.
    Purging drops any training row whose label window ends on/after the test
    start (minus an optional embargo buffer).
    """
    import datetime as dt

    t0 = dt.date.fromisoformat(test_start_date[:10])
    cutoff = t0 - dt.timedelta(days=embargo_days)
    keep = []
    for i in range(tr_end):
        d = ex[i].get("date")
        h = int(ex[i].get("horizon_days", 0) or 0)
        try:
            label_end = dt.date.fromisoformat(str(d)[:10]) + dt.timedelta(days=h)
        except (ValueError, TypeError):
            continue
        if label_end < cutoff:
            keep.append(i)
    return np.array(keep, dtype=int)


def purged_folds(ex: list[dict], n_folds: int = 4, embargo_days: int = 2,
                 min_train: int = 20, min_test: int = 5) -> list[tuple]:
    """Test blocks placed where purging can still leave a usable training set.

    Returns [(train_idx, test_lo, test_hi), ...], expanding-window.

    Fixed index-fraction folds -- train on the first f/5 of the rows, test on
    the next fifth -- silently collapse to ZERO folds whenever the labeled
    span is short relative to the horizon: every training row's label window
    still reaches past the test start, purging empties the training set, and
    the model reports "no valid folds" while holding thousands of rows. That
    is not a shortage of data, it is the test windows being placed where no
    purged training data can exist.

    This finds the earliest index whose purged training set clears
    `min_train` (the count is monotone in the index, so bisect), then splits
    everything after it into contiguous test blocks. A fold appears as soon
    as the calendar permits one, and never before.
    """
    n = len(ex)
    if n == 0:
        return []
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        cnt = len(_purge_train_indices(ex, mid, ex[mid].get("date", ""), embargo_days))
        if cnt >= min_train:
            hi = mid
        else:
            lo = mid + 1
    start = lo
    if start >= n - min_test:
        return []
    block = max(min_test, (n - start) // max(n_folds, 1))
    folds, te_lo = [], start
    while te_lo < n and len(folds) < n_folds:
        te_hi = min(te_lo + block, n)
        if te_hi - te_lo < min_test:
            break
        tr_idx = _purge_train_indices(ex, te_lo, ex[te_lo].get("date", ""), embargo_days)
        if len(tr_idx) >= min_train:
            folds.append((tr_idx, te_lo, te_hi))
        te_lo = te_hi
    return folds


def fold_shortfall(ex: list[dict], embargo_days: int = 2) -> str:
    """Plain-calendar explanation of why no fold is possible yet."""
    import datetime as dt
    if not ex:
        return "no labeled examples"
    d0, dn = str(ex[0].get("date"))[:10], str(ex[-1].get("date"))[:10]
    h = int(ex[0].get("horizon_days", 0) or 0)
    try:
        span = (dt.date.fromisoformat(dn) - dt.date.fromisoformat(d0)).days
    except ValueError:
        return "unparseable example dates"
    return (f"labeled dates span {span}d ({d0} -> {dn}); a {h}d label window plus "
            f"{embargo_days}d embargo means no training row is clean until the test "
            f"start is past {d0}+{h + embargo_days}d, and a test block must follow "
            f"it. Needs >{h + embargo_days}d of labeled span; keep collecting.")


def walk_forward(
    examples: list[dict], feature_keys: list[str], n_folds: int = 4,
    top_frac: float = 0.2, embargo_days: int = 2,
) -> dict:
    """Purged, embargoed, expanding-window walk-forward. Returns OOS AUC/IC.

    Purging matters because forward-return labels overlap in time: without it,
    training rows near the fold boundary contain the test period's prices in
    their labels — the subtle leak that makes naive financial backtests
    look better than reality.
    """
    ex = sorted(examples, key=lambda e: e.get("date", ""))
    if len(ex) < 40:
        return {"error": "not enough labeled examples for walk-forward (need >=40)",
                "n": len(ex), "backend": "sklearn" if _HAVE_SKLEARN else "numpy"}

    y_all = label_top_quantile(ex, top_frac)
    X_all = _matrix(ex, feature_keys)
    fwd_all = np.array([e["fwd_ret"] for e in ex])

    n = len(ex)
    oos_scores, oos_labels, oos_fwd = [], [], []
    purged_total = 0
    used = 0
    dead_max = 0

    for tr_idx, tr_end, te_end in purged_folds(ex, n_folds, embargo_days,
                                               min_train=20, min_test=5):
        purged_total += tr_end - len(tr_idx)
        Xtr_raw, Xte_raw = X_all[tr_idx], X_all[tr_end:te_end]
        ytr = y_all[tr_idx]
        if len(np.unique(ytr)) < 2:
            continue
        dead_max = max(dead_max, int(_dead_features(Xtr_raw).sum()))
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
        used += 1

    if not oos_scores:
        return {"error": "no fold has a purged training set yet", "n": n,
                "why": fold_shortfall(ex, embargo_days),
                "backend": "sklearn" if _HAVE_SKLEARN else "numpy"}

    s = np.array(oos_scores)
    lab = np.array(oos_labels)
    fwd = np.array(oos_fwd)
    return {
        "backend": "sklearn-HGB" if _HAVE_SKLEARN else "numpy-logreg",
        "n_folds_used": used,
        "dead_features_max": dead_max,
        "purged_rows": int(purged_total),
        "embargo_days": embargo_days,
        "n_oos": int(s.size),
        "oos_auc": round(metrics.auc(s, lab), 4) if metrics.auc(s, lab) is not None else None,
        "oos_ic": round(metrics.spearman(s, fwd), 4) if metrics.spearman(s, fwd) is not None else None,
        "oos_top_quintile_hit_rate": round(metrics.hit_rate(s, fwd), 3)
        if metrics.hit_rate(s, fwd) is not None else None,
        "oos_decile_spread": metrics.decile_spread(s, fwd)["spread"],
        "feature_keys": feature_keys,
    }
