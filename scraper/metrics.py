"""Pure-numpy evaluation metrics for signal research.

No scipy/sklearn dependency. These are the tools that tell you whether a
signal actually predicts anything:

  - Information Coefficient (IC): cross-sectional Spearman rank correlation
    between a signal and the subsequent forward return. Averaged over many
    dates, a positive mean IC with a decent t-stat (information ratio) is
    the core evidence that a signal has edge. As a rule of thumb, a
    *consistent* mean IC of 0.03-0.05 is already a genuinely useful signal
    in equities; 0.10+ is exceptional (and usually too good to be true).
  - Decile spread: return of the top-decile-ranked names minus the
    bottom-decile. The economic (not just statistical) size of the edge.
  - Hit rate: fraction of top-ranked names that actually went up.
"""
from __future__ import annotations

import math

import numpy as np


def rankdata(a: np.ndarray) -> np.ndarray:
    """Average-rank of each element (ties share the mean rank). 1-indexed."""
    a = np.asarray(a, dtype=float)
    n = a.size
    if n == 0:
        return a
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(n, dtype=float)
    sorted_a = a[order]
    i = 0
    while i < n:
        j = i
        while j + 1 < n and sorted_a[j + 1] == sorted_a[i]:
            j += 1
        avg_rank = (i + j) / 2.0 + 1.0  # 1-indexed average
        ranks[order[i : j + 1]] = avg_rank
        i = j + 1
    return ranks


def spearman(x: np.ndarray, y: np.ndarray) -> float | None:
    """Spearman rank correlation. Returns None if undefined (n<2 or no var)."""
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    if x.size < 2:
        return None
    rx, ry = rankdata(x), rankdata(y)
    if rx.std() == 0 or ry.std() == 0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def ic_summary(ics: list[float]) -> dict:
    """Summarize a series of per-date ICs into mean, std, and t-stat (IR)."""
    vals = np.array([v for v in ics if v is not None and math.isfinite(v)], dtype=float)
    if vals.size == 0:
        return {"n": 0, "mean_ic": None, "std_ic": None, "ic_ir": None, "t_stat": None}
    mean = float(vals.mean())
    std = float(vals.std(ddof=1)) if vals.size > 1 else 0.0
    # Information Ratio of the IC series == its t-stat scaled by sqrt(n).
    ir = (mean / std) if std > 0 else None
    t_stat = (ir * math.sqrt(vals.size)) if ir is not None else None
    return {
        "n": int(vals.size),
        "mean_ic": round(mean, 4),
        "std_ic": round(std, 4),
        "ic_ir": round(ir, 3) if ir is not None else None,
        "t_stat": round(t_stat, 2) if t_stat is not None else None,
    }


def decile_spread(signal: np.ndarray, fwd_ret: np.ndarray, q: int = 10) -> dict:
    """Top-quantile minus bottom-quantile mean forward return."""
    signal = np.asarray(signal, dtype=float)
    fwd_ret = np.asarray(fwd_ret, dtype=float)
    mask = np.isfinite(signal) & np.isfinite(fwd_ret)
    signal, fwd_ret = signal[mask], fwd_ret[mask]
    if signal.size < q * 2:
        return {"top": None, "bottom": None, "spread": None, "n": int(signal.size)}
    order = np.argsort(signal)
    k = max(1, signal.size // q)
    bottom = fwd_ret[order[:k]].mean()
    top = fwd_ret[order[-k:]].mean()
    return {
        "top": round(float(top), 4),
        "bottom": round(float(bottom), 4),
        "spread": round(float(top - bottom), 4),
        "n": int(signal.size),
    }


def hit_rate(signal: np.ndarray, fwd_ret: np.ndarray, top_frac: float = 0.2) -> float | None:
    """Fraction of the top-ranked fraction whose forward return is positive."""
    signal = np.asarray(signal, dtype=float)
    fwd_ret = np.asarray(fwd_ret, dtype=float)
    mask = np.isfinite(signal) & np.isfinite(fwd_ret)
    signal, fwd_ret = signal[mask], fwd_ret[mask]
    if signal.size == 0:
        return None
    k = max(1, int(round(signal.size * top_frac)))
    top_idx = np.argsort(signal)[-k:]
    return float((fwd_ret[top_idx] > 0).mean())


def brier_score(probs: np.ndarray, labels: np.ndarray) -> float | None:
    """Mean squared error of probabilities. Lower is better; 0.25 = coin flip.

    AUC only measures RANKING. Brier measures whether the numbers mean what
    they say — the difference between "these 20 names are the most likely"
    and "each of these has a 30% chance", which is what position sizing needs.
    """
    probs = np.asarray(probs, dtype=float)
    labels = np.asarray(labels, dtype=float)
    mask = np.isfinite(probs) & np.isfinite(labels)
    if mask.sum() == 0:
        return None
    return float(np.mean((probs[mask] - labels[mask]) ** 2))


def calibration_table(probs: np.ndarray, labels: np.ndarray,
                      bins: int = 5) -> list[dict]:
    """Predicted vs realized rate per probability bucket.

    The reality check on a prediction list: of the names the model called
    30%, how many actually delivered? Systematic overshoot here is the
    classic way a model looks confident and loses money.
    """
    probs = np.asarray(probs, dtype=float)
    labels = np.asarray(labels, dtype=float)
    mask = np.isfinite(probs) & np.isfinite(labels)
    probs, labels = probs[mask], labels[mask]
    if probs.size == 0:
        return []
    edges = np.quantile(probs, np.linspace(0, 1, bins + 1))
    edges[-1] += 1e-9
    out = []
    for i in range(bins):
        sel = (probs >= edges[i]) & (probs < edges[i + 1])
        if sel.sum() == 0:
            continue
        out.append({
            "bucket": i + 1,
            "n": int(sel.sum()),
            "mean_predicted": round(float(probs[sel].mean()), 4),
            "actual_rate": round(float(labels[sel].mean()), 4),
        })
    return out


def isotonic_fit(scores: np.ndarray, labels: np.ndarray):
    """Pool-Adjacent-Violators isotonic regression (pure numpy).

    Maps raw model scores to calibrated probabilities using only the
    monotone assumption (higher score -> not-lower probability), which is
    exactly what a ranking model gives you. Returns (x, y) knots for
    `isotonic_predict`.
    """
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=float)
    mask = np.isfinite(scores) & np.isfinite(labels)
    scores, labels = scores[mask], labels[mask]
    if scores.size == 0:
        return np.array([0.0]), np.array([0.5])
    order = np.argsort(scores, kind="mergesort")
    x = scores[order]
    y = labels[order].astype(float)

    # PAV: merge adjacent blocks that violate monotonicity.
    values = list(y)
    weights = [1.0] * len(y)
    idx = list(range(len(y)))
    i = 0
    while i < len(values) - 1:
        if values[i] <= values[i + 1] + 1e-12:
            i += 1
            continue
        tot_w = weights[i] + weights[i + 1]
        merged = (values[i] * weights[i] + values[i + 1] * weights[i + 1]) / tot_w
        values[i:i + 2] = [merged]
        weights[i:i + 2] = [tot_w]
        idx[i:i + 2] = [idx[i]]
        if i > 0:
            i -= 1
    # Expand blocks back over the sorted x positions.
    fitted = np.empty(len(y))
    pos = 0
    for v, w in zip(values, weights):
        n = int(round(w))
        fitted[pos:pos + n] = v
        pos += n
    return x, fitted


def isotonic_predict(knots, scores: np.ndarray) -> np.ndarray:
    """Apply a fitted isotonic map, clipped to [0, 1]."""
    x, y = knots
    scores = np.asarray(scores, dtype=float)
    out = np.interp(scores, x, y, left=y[0], right=y[-1])
    return np.clip(out, 0.0, 1.0)


def auc(scores: np.ndarray, labels: np.ndarray) -> float | None:
    """Area under ROC via the rank (Mann-Whitney U) identity. labels in {0,1}."""
    scores = np.asarray(scores, dtype=float)
    labels = np.asarray(labels, dtype=float)
    mask = np.isfinite(scores) & np.isfinite(labels)
    scores, labels = scores[mask], labels[mask]
    pos = labels == 1
    n_pos, n_neg = int(pos.sum()), int((~pos).sum())
    if n_pos == 0 or n_neg == 0:
        return None
    r = rankdata(scores)
    auc_val = (r[pos].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg)
    return float(auc_val)
