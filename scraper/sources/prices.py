"""Price / volume / technical signals via yfinance (free, no key).

For each ticker we compute momentum and unusual-activity features over a
~6 month lookback. All values are best-effort; missing data yields None
fields which the scorer treats as neutral.
"""
import pandas as pd
import yfinance as yf


def _rsi(close: pd.Series, period: int = 14) -> float | None:
    if len(close) < period + 1:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period).mean()
    loss = (-delta.clip(upper=0)).rolling(period).mean()
    rs = gain / loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    return float(val) if pd.notna(val) else None


def _safe_ret(close: pd.Series, lookback: int) -> float | None:
    if len(close) <= lookback:
        return None
    past = close.iloc[-lookback - 1]
    last = close.iloc[-1]
    if past and past > 0:
        return float(last / past - 1.0)
    return None


def fetch(tickers: list[str]) -> dict[str, dict]:
    """Return {ticker: {feature: value}} for price-derived features."""
    results: dict[str, dict] = {}
    if not tickers:
        return results

    # Batch download is far kinder to the API than per-ticker calls.
    data = yf.download(
        tickers=" ".join(tickers),
        period="6mo",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    for tk in tickers:
        try:
            if len(tickers) == 1:
                df = data
            else:
                df = data[tk]
            df = df.dropna(subset=["Close"])
        except (KeyError, TypeError):
            continue
        if df is None or df.empty or len(df) < 20:
            continue

        close = df["Close"]
        volume = df["Volume"]

        recent_vol = volume.iloc[-5:].mean()
        base_vol = volume.iloc[-60:-5].mean() if len(volume) > 65 else volume.mean()
        vol_spike = float(recent_vol / base_vol) if base_vol and base_vol > 0 else None

        hi_52 = float(close.max())
        lo_52 = float(close.min())
        last = float(close.iloc[-1])

        results[tk] = {
            "last_price": last,
            "ret_5d": _safe_ret(close, 5),
            "ret_21d": _safe_ret(close, 21),
            "ret_63d": _safe_ret(close, 63),
            "volume_spike_ratio": vol_spike,
            "rsi_14": _rsi(close),
            "pct_off_52w_high": (last / hi_52 - 1.0) if hi_52 > 0 else None,
            "pct_above_52w_low": (last / lo_52 - 1.0) if lo_52 > 0 else None,
            "annualized_vol": float(close.pct_change().std() * (252 ** 0.5)) if len(close) > 2 else None,
        }
    return results
