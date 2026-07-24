"""Combine per-source signals into a single heuristic composite score.

IMPORTANT: the weights and transforms here are hand-picked heuristics, NOT
the output of any validated backtest. A high score means "this name shows
unusual momentum + attention right now," which is a screening signal, not a
prediction that the stock will go up. See README for the full disclaimer.
"""
from . import config


def _percentile_rank(values: dict[str, float]) -> dict[str, float]:
    """Map raw values to [0,1] percentile ranks. Missing -> neutral 0.5.

    O(n log n) via bisect so it stays instant even on a full-market universe.
    """
    import bisect

    present = {k: v for k, v in values.items() if v is not None}
    if not present:
        return {k: 0.5 for k in values}
    ordered = sorted(present.values())
    n = len(ordered)

    def rank(v):
        # fraction of values <= v
        return bisect.bisect_right(ordered, v) / n

    return {k: (rank(values[k]) if values[k] is not None else 0.5) for k in values}


def _collect(rows: dict[str, dict], key: str) -> dict[str, float]:
    return {tk: row.get(key) for tk, row in rows.items()}


def score(merged: dict[str, dict]) -> list[dict]:
    """Given {ticker: {all merged features}}, return ranked list of dicts."""
    tickers = list(merged.keys())
    if not tickers:
        return []

    # Feature -> the merged key it derives from. For signals where "more is
    # better" we percentile-rank directly; sentiment is already in [-1,1] so
    # we shift to [0,1].
    momentum_raw = {}
    for tk in tickers:
        r = merged[tk]
        parts = [r.get("ret_21d"), r.get("ret_63d")]
        parts = [p for p in parts if p is not None]
        momentum_raw[tk] = sum(parts) / len(parts) if parts else None

    price_momentum = _percentile_rank(momentum_raw)
    volume_spike = _percentile_rank(_collect(merged, "volume_spike_ratio"))
    news_buzz = _percentile_rank(_collect(merged, "news_count"))
    reddit_buzz = _percentile_rank(_collect(merged, "reddit_mentions"))

    sec_raw = {}
    for tk in tickers:
        r = merged[tk]
        sec_raw[tk] = (r.get("sec_form4_recent") or 0) + (r.get("sec_8k_recent") or 0)
    sec_activity = _percentile_rank(sec_raw)

    def sentiment01(key):
        return {tk: ((merged[tk].get(key) or 0.0) + 1.0) / 2.0 for tk in tickers}

    news_sentiment = sentiment01("news_sentiment")
    reddit_sentiment = sentiment01("reddit_sentiment")

    # Stocktwits attention: trending flag dominates, message count adds nuance.
    st_raw = {}
    for tk in tickers:
        r = merged[tk]
        st_raw[tk] = (r.get("st_trending") or 0.0) * 100 + (r.get("st_msg_count") or 0)
    st_attention = _percentile_rank(st_raw)
    wiki_attention = _percentile_rank(_collect(merged, "wiki_spike_ratio"))
    short_pressure = _percentile_rank(_collect(merged, "short_vol_ratio"))

    w = config.SCORE_WEIGHTS
    out = []
    for tk in tickers:
        components = {
            "price_momentum": price_momentum[tk],
            "volume_spike": volume_spike[tk],
            "news_buzz": news_buzz[tk],
            "news_sentiment": news_sentiment[tk],
            "reddit_buzz": reddit_buzz[tk],
            "reddit_sentiment": reddit_sentiment[tk],
            "sec_activity": sec_activity[tk],
            "st_attention": st_attention[tk],
            "wiki_attention": wiki_attention[tk],
            "short_pressure": short_pressure[tk],
        }
        composite = sum(components[k] * w[k] for k in w)
        out.append(
            {
                "ticker": tk,
                "score": round(composite * 100, 2),
                "components": {k: round(v, 3) for k, v in components.items()},
                "features": merged[tk],
            }
        )

    out.sort(key=lambda d: d["score"], reverse=True)
    return out
