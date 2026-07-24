"""Turn accumulated snapshots (and raw price history) into labeled examples.

Two label sources:

1. store-derived (multi-source, grows over time): for each snapshot of a
   ticker on date D with price P0, find that same ticker's snapshot nearest
   to D + horizon days with price P1, and label it with the realized forward
   return P1/P0 - 1. This is fully leakage-free because P1 comes strictly
   from the future relative to the features, and it needs no network access.

2. price-history-derived (price signals only, available immediately): given a
   single OHLCV DataFrame, reconstruct the point-in-time price features at
   many past dates and label each with the realized forward return from the
   same series. Lets you estimate the edge of the price/volume signals today
   instead of waiting months. (News/Reddit/SEC signals cannot be
   reconstructed historically — that is exactly why the store exists.)
"""
from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd


def _to_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s[:10])


def build_forward_returns(
    records: list[dict], horizon_days: int = 63, tolerance_days: int = 10
) -> list[dict]:
    """Attach realized forward returns to snapshot records from the store.

    Returns a new list of {date, ticker, features, score, fwd_ret, horizon}
    for every snapshot that has a matching future price within tolerance.
    """
    # Index prices by ticker -> sorted list of (date, price).
    by_ticker: dict[str, list[tuple[dt.date, float]]] = {}
    for r in records:
        price = r.get("last_price")
        if price is None or price <= 0:
            continue
        by_ticker.setdefault(r["ticker"], []).append((_to_date(r["date"]), float(price)))
    for tk in by_ticker:
        by_ticker[tk].sort(key=lambda x: x[0])

    def future_price(tk: str, d0: dt.date) -> float | None:
        target = d0 + dt.timedelta(days=horizon_days)
        best = None
        best_gap = None
        for d, p in by_ticker.get(tk, []):
            if d <= d0:
                continue
            gap = abs((d - target).days)
            if gap <= tolerance_days and (best_gap is None or gap < best_gap):
                best, best_gap = p, gap
        return best

    labeled: list[dict] = []
    for r in records:
        p0 = r.get("last_price")
        if p0 is None or p0 <= 0:
            continue
        p1 = future_price(r["ticker"], _to_date(r["date"]))
        if p1 is None:
            continue
        labeled.append(
            {
                "date": r["date"],
                "ticker": r["ticker"],
                "features": r.get("features", {}),
                "components": r.get("components", {}),
                "score": r.get("score"),
                "fwd_ret": p1 / float(p0) - 1.0,
                "horizon_days": horizon_days,
            }
        )
    return labeled


# --- price-history reconstruction (immediate, price signals only) -----------

def _rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    v = rsi.iloc[-1]
    return float(v) if pd.notna(v) else None


def features_asof(df: pd.DataFrame, i: int) -> dict | None:
    """Reconstruct price features using ONLY rows 0..i (no look-ahead)."""
    if i < 21:
        return None
    window = df.iloc[: i + 1]
    close = window["Close"]
    volume = window["Volume"]
    if len(close) < 21:
        return None

    def ret(lb):
        if len(close) <= lb:
            return None
        past = close.iloc[-lb - 1]
        return float(close.iloc[-1] / past - 1.0) if past > 0 else None

    recent_vol = volume.iloc[-5:].mean()
    base_vol = volume.iloc[-60:-5].mean() if len(volume) > 65 else volume.mean()
    vol_spike = float(recent_vol / base_vol) if base_vol and base_vol > 0 else None
    return {
        "ret_5d": ret(5),
        "ret_21d": ret(21),
        "ret_63d": ret(63),
        "volume_spike_ratio": vol_spike,
        "rsi_14": _rsi(close),
    }


def price_history_examples(
    df: pd.DataFrame, horizon: int = 63, step: int = 5, min_history: int = 63
) -> list[dict]:
    """Sample (features_asof, realized forward return) pairs from one series.

    df must have a DatetimeIndex and Close/Volume columns, ascending in time.
    """
    df = df.dropna(subset=["Close", "Volume"])
    n = len(df)
    out: list[dict] = []
    close = df["Close"].to_numpy()
    for i in range(min_history, n - horizon, step):
        feats = features_asof(df, i)
        if feats is None:
            continue
        p0 = close[i]
        p1 = close[i + horizon]
        if p0 <= 0:
            continue
        out.append(
            {
                "date": str(df.index[i].date()) if hasattr(df.index[i], "date") else str(i),
                "features": feats,
                "fwd_ret": float(p1 / p0 - 1.0),
                "horizon_days": horizon,
            }
        )
    return out
