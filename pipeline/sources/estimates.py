"""Analyst earnings-estimate revisions — the one signal family with a
documented lead on price.

Why this source exists: every other signal here is either price itself
(momentum, factors) or attention (news, social, pageviews). Both are
*coincident-to-late* — they describe a move already underway. Estimate
revisions sit earlier in the causal chain:

    supply/demand shifts -> analysts revise EPS -> price follows, with lag

The lag is the opportunity. Analysts revise in small sticky increments and
the market under-reacts to them, which is among the most durable documented
effects in equities. A cyclical inflection (the SanDisk pattern: trough
margins, capex cuts, then a demand shock) shows up as a sharp upward
revision *before* the multi-month re-rating.

Signals per ticker, from Yahoo's earnings-trend endpoint (free, no key):

  eps_rev_30d       next-FY EPS estimate change over 30 days, as a fraction
  eps_rev_90d       ...over 90 days — the slower, less noisy version
  eps_rev_breadth   (analysts revising up - down) / total, last 30 days;
                    direction agreement, independent of magnitude
  eps_rev_vs_price  eps_rev_90d MINUS the 63-day price return. The core
                    screen: a large positive value means estimates have
                    risen but the price has NOT yet paid for it.
  analyst_count     coverage. Rising estimates on a THINLY covered name is
                    the classic under-followed setup; the same revision on a
                    mega-cap is already in the price.
  pt_upside         mean analyst price target / current price - 1

Everything degrades to None rather than raising: most small caps have no
coverage at all, and that absence is itself information the model can use.
"""
from __future__ import annotations

import math

from .. import config, parallel

_NEUTRAL = {
    "eps_rev_30d": None, "eps_rev_90d": None, "eps_rev_breadth": None,
    "eps_rev_vs_price": None, "analyst_count": None, "pt_upside": None,
}
# '+1y' = next fiscal year: far enough out to reflect a changed outlook,
# near enough that analysts actually maintain it.
_PERIOD = "+1y"


def _cell(df, period: str, column: str):
    """Value at (period, column) of a yfinance periodic frame, or None."""
    try:
        if df is None or getattr(df, "empty", True):
            return None
        if period not in df.index or column not in df.columns:
            return None
        v = float(df.loc[period, column])
        return v if math.isfinite(v) else None
    except Exception:  # noqa: BLE001 - upstream shapes drift; never fail a run
        return None


def _pct_change(now, then):
    """Relative change, guarded for the sign flips EPS estimates love.

    A move from -0.10 to +0.40 is a genuine inflection, but naive division by
    a negative base reports it as negative. Using |base| keeps the sign of
    the actual change, which is what matters here.
    """
    if now is None or then is None or then == 0:
        return None
    return (now - then) / abs(then)


def _one(tk: str, price_ret_63d: float | None) -> dict:
    import yfinance as yf

    out = dict(_NEUTRAL)
    t = yf.Ticker(tk)

    trend = None
    try:
        trend = t.eps_trend
    except Exception:  # noqa: BLE001
        trend = None
    cur = _cell(trend, _PERIOD, "current")
    out["eps_rev_30d"] = _pct_change(cur, _cell(trend, _PERIOD, "30daysAgo"))
    out["eps_rev_90d"] = _pct_change(cur, _cell(trend, _PERIOD, "90daysAgo"))

    try:
        rev = t.eps_revisions
        up = _cell(rev, _PERIOD, "upLast30days")
        down = _cell(rev, _PERIOD, "downLast30days")
        if up is not None and down is not None and (up + down) > 0:
            out["eps_rev_breadth"] = round((up - down) / (up + down), 4)
    except Exception:  # noqa: BLE001
        pass

    try:
        est = t.earnings_estimate
        n = _cell(est, _PERIOD, "numberOfAnalysts")
        out["analyst_count"] = int(n) if n is not None else None
    except Exception:  # noqa: BLE001
        pass

    try:
        pt = t.analyst_price_targets or {}
        mean, current = pt.get("mean"), pt.get("current")
        if mean and current and current > 0:
            out["pt_upside"] = round(float(mean) / float(current) - 1.0, 4)
    except Exception:  # noqa: BLE001
        pass

    # The screen itself: revision not yet reflected in price.
    if out["eps_rev_90d"] is not None and price_ret_63d is not None:
        out["eps_rev_vs_price"] = round(out["eps_rev_90d"] - price_ret_63d, 4)

    for k in ("eps_rev_30d", "eps_rev_90d"):
        if out[k] is not None:
            out[k] = round(out[k], 4)
    return out


def fetch(tickers: list[str],
          price_returns: dict[str, float] | None = None) -> dict[str, dict]:
    """{ticker: estimate-revision features}.

    `price_returns` maps ticker -> 63-day return, used for eps_rev_vs_price.
    """
    price_returns = price_returns or {}
    return parallel.fetch_map(
        tickers,
        lambda tk: _one(tk, price_returns.get(tk)),
        max_workers=config.PARALLEL_WORKERS,
        rate_per_sec=config.ESTIMATES_RATE_PER_SEC,
        default=dict(_NEUTRAL),
    )
