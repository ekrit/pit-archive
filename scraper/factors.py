"""Alpha-factor library, inspired by Microsoft Qlib's Alpha158 feature set.

Qlib (MIT-licensed, github.com/microsoft/qlib) ships a battery of ~158 simple
price/volume factors ("Alpha158") that is the de-facto open-source baseline for
cross-sectional stock ranking. This module is a clean-room, pure-pandas
implementation of the most useful families from that set — K-bar shape factors
plus rolling window statistics — kept dependency-light and point-in-time safe
(every factor uses only rows up to and including the evaluation row).

Families (windows w ∈ {5, 10, 20, 60}):
  K-bar:  KMID, KLEN, KMID2, KUP, KLOW, KSFT          (candle geometry, today)
  ROC_w:  close_{t-w} / close_t                        (momentum)
  MA_w:   mean(close, w) / close_t                     (trend position)
  STD_w:  std(close, w) / close_t                      (volatility)
  MAX_w:  max(high, w) / close_t                       (breakout distance)
  MIN_w:  min(low, w) / close_t                        (support distance)
  RSV_w:  (close - min(low,w)) / (max(high,w) - min(low,w))   (stochastic %K)
  CORR_w: corr(close, log(volume+1), w)                (price/volume coupling)
  CNTP_w: fraction of up days in w                     (persistence)
  SUMP_w: sum(gains) / sum(|moves|) in w               (RSI-like strength)
  VMA_w:  mean(volume, w) / volume_t                   (volume trend)

All ratios are relative to the current bar, making them scale-free and
comparable across stocks — the property that makes cross-sectional ranking
work. Total: 6 + 10*4 = 46 factors.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOWS = (5, 10, 20, 60)

_KBAR = ["KMID", "KLEN", "KMID2", "KUP", "KLOW", "KSFT"]
_ROLLING = ["ROC", "MA", "STD", "MAX", "MIN", "RSV", "CORR", "CNTP", "SUMP", "VMA"]

FACTOR_NAMES: list[str] = _KBAR + [f"{f}_{w}" for f in _ROLLING for w in WINDOWS]


def _f(x) -> float | None:
    """Finite float or None (keeps the store JSON-clean)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if np.isfinite(v) else None


def compute_factors(df: pd.DataFrame) -> dict[str, float | None]:
    """Compute all factors at the LAST row of df (point-in-time by slicing).

    df needs Open/High/Low/Close/Volume columns, ascending in time. For an
    as-of computation at row i, pass df.iloc[:i+1].
    """
    out: dict[str, float | None] = {name: None for name in FACTOR_NAMES}
    if df is None or len(df) < 2:
        return out
    o = df["Open"].astype(float)
    h = df["High"].astype(float)
    l = df["Low"].astype(float)
    c = df["Close"].astype(float)
    v = df["Volume"].astype(float)

    o0, h0, l0, c0, v0 = o.iloc[-1], h.iloc[-1], l.iloc[-1], c.iloc[-1], v.iloc[-1]
    if not (np.isfinite(c0) and c0 > 0):
        return out

    # --- K-bar (candle geometry of the current bar) ---
    if np.isfinite(o0) and o0 > 0:
        out["KMID"] = _f((c0 - o0) / o0)
        out["KLEN"] = _f((h0 - l0) / o0)
        out["KUP"] = _f((h0 - max(o0, c0)) / o0)
        out["KLOW"] = _f((min(o0, c0) - l0) / o0)
        out["KSFT"] = _f((2 * c0 - h0 - l0) / o0)
    rng = h0 - l0
    out["KMID2"] = _f((c0 - o0) / rng) if rng > 0 else None

    # --- rolling families ---
    ret = c.diff()
    logv = np.log1p(v)
    for w in WINDOWS:
        if len(c) <= w:
            continue  # leave this window's factors as None
        cw = c.iloc[-w:]
        hw = h.iloc[-w:]
        lw = l.iloc[-w:]
        vw = v.iloc[-w:]
        rw = ret.iloc[-w:]

        past = c.iloc[-w - 1]
        out[f"ROC_{w}"] = _f(past / c0) if past > 0 else None
        out[f"MA_{w}"] = _f(cw.mean() / c0)
        out[f"STD_{w}"] = _f(cw.std(ddof=0) / c0)
        out[f"MAX_{w}"] = _f(hw.max() / c0)
        out[f"MIN_{w}"] = _f(lw.min() / c0)

        hi, lo = hw.max(), lw.min()
        out[f"RSV_{w}"] = _f((c0 - lo) / (hi - lo)) if hi > lo else None

        cs = cw.reset_index(drop=True)
        vs = logv.iloc[-w:].reset_index(drop=True)
        if cs.std(ddof=0) > 0 and vs.std(ddof=0) > 0:
            out[f"CORR_{w}"] = _f(cs.corr(vs))

        out[f"CNTP_{w}"] = _f((rw > 0).mean())
        gains = rw.clip(lower=0).sum()
        total = rw.abs().sum()
        out[f"SUMP_{w}"] = _f(gains / total) if total > 0 else None

        out[f"VMA_{w}"] = _f(vw.mean() / v0) if v0 > 0 else None

    return out
