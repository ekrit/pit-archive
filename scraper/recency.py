"""Recency filtering/weighting: make attention signals reflect the NEWEST data.

Without this, a bullish headline from three months ago counts exactly like one
from this morning — Google News RSS, Stocktwits streams, and Reddit hot lists
all return items of mixed age. Every attention source now:

  1. drops items older than its max age (stale content is not signal), and
  2. weights survivors with an exponential half-life, so this morning's story
     counts roughly double one from `half_life_days` ago.

Missing timestamps are treated as fresh (lenient by design — better to keep an
undated item than silently drop a live source that stopped sending dates).
"""
from __future__ import annotations

import datetime as dt
import email.utils

NEWS_MAX_AGE_DAYS = 7.0
NEWS_HALF_LIFE_DAYS = 2.0
SOCIAL_MAX_AGE_DAYS = 3.0
SOCIAL_HALF_LIFE_DAYS = 1.0


def weight(age_days: float | None, half_life_days: float, max_age_days: float) -> float:
    """0.0 for too-old items; exponential decay otherwise. None age -> 1.0."""
    if age_days is None:
        return 1.0
    if age_days < 0:
        age_days = 0.0
    if age_days > max_age_days:
        return 0.0
    return 0.5 ** (age_days / half_life_days)


def _age_days(ts: dt.datetime | None, now: dt.datetime | None = None) -> float | None:
    if ts is None:
        return None
    now = now or dt.datetime.now(dt.timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=dt.timezone.utc)
    return max(0.0, (now - ts).total_seconds() / 86400.0)


def age_from_rfc2822(s: str | None, now: dt.datetime | None = None) -> float | None:
    """RSS pubDate ('Fri, 24 Jul 2026 12:34:56 GMT') -> age in days, or None."""
    if not s:
        return None
    try:
        return _age_days(email.utils.parsedate_to_datetime(s), now)
    except (TypeError, ValueError):
        return None


def age_from_iso(s: str | None, now: dt.datetime | None = None) -> float | None:
    """ISO timestamp ('2026-07-24T12:00:00Z') -> age in days, or None."""
    if not s:
        return None
    try:
        return _age_days(dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")), now)
    except (TypeError, ValueError):
        return None


def age_from_epoch(ts: float | None, now: dt.datetime | None = None) -> float | None:
    """Unix epoch seconds -> age in days, or None."""
    if ts is None:
        return None
    try:
        return _age_days(dt.datetime.fromtimestamp(float(ts), dt.timezone.utc), now)
    except (TypeError, ValueError, OSError):
        return None


def weighted_stats(items: list[tuple[float, float | None]],
                   half_life_days: float, max_age_days: float) -> tuple[float, float]:
    """[(sentiment, age_days), ...] -> (effective_count, weighted_mean_sentiment).

    effective_count is the weight sum: 10 fresh items ~ 10.0, 10 stale ones ~ 0.
    """
    wsum = 0.0
    swsum = 0.0
    for sent, age in items:
        w = weight(age, half_life_days, max_age_days)
        wsum += w
        swsum += sent * w
    mean = (swsum / wsum) if wsum > 0 else 0.0
    return round(wsum, 2), round(mean, 4)
