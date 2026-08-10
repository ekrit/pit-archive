"""Reddit mention counts + sentiment via public JSON (read-only, no OAuth).

We pull recent 'hot'/'new' posts from a few finance subreddits, then count
how often each ticker is mentioned in titles + selftext and average the
VADER sentiment of those mentions.

This is best-effort: anonymous access to reddit.com JSON is frequently
rate-limited or blocked. For reliable use, switch to the official Reddit
API (PRAW) with free credentials. The pipeline degrades gracefully to
zeros when Reddit is unavailable.
"""
import re
import time

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .. import config
from ..http import make_session, get_json

_LISTING_URL = "https://www.reddit.com/r/{sub}/hot.json"
_analyzer = SentimentIntensityAnalyzer()

# Common English words that are also tickers -- exclude to cut false hits.
_STOPWORD_TICKERS = {
    "A", "I", "IT", "BE", "SO", "ON", "OR", "AT", "GO", "NO", "AM", "PM",
    "ALL", "ANY", "FOR", "ARE", "CEO", "CFO", "DD", "EPS", "IPO", "USA",
    "YOLO", "FD", "ATH", "EV", "AI", "US", "UK", "TV", "PR", "HODL",
}


def _mention_pattern(tickers: list[str]) -> re.Pattern:
    usable = [t for t in tickers if t.upper() not in _STOPWORD_TICKERS]
    if not usable:
        return re.compile(r"(?!x)x")  # matches nothing
    # Match $TICKER or bare uppercase TICKER on word boundaries.
    alt = "|".join(re.escape(t) for t in sorted(usable, key=len, reverse=True))
    return re.compile(rf"(?:\$)?\b({alt})\b")


def fetch(tickers: list[str]) -> dict[str, dict]:
    pattern = _mention_pattern(tickers)
    valid = {t.upper() for t in tickers if t.upper() not in _STOPWORD_TICKERS}
    counts: dict[str, int] = {t: 0 for t in tickers}
    sent_sum: dict[str, float] = {t: 0.0 for t in tickers}

    session = make_session()
    for sub in config.REDDIT_SUBREDDITS:
        data = get_json(
            session,
            _LISTING_URL.format(sub=sub),
            params={"limit": config.REDDIT_POSTS_PER_SUBREDDIT},
        )
        time.sleep(config.REDDIT_REQUEST_DELAY_SECONDS)
        if not data:
            continue
        try:
            children = data["data"]["children"]
        except (KeyError, TypeError):
            continue
        from .. import recency

        for child in children:
            post = child.get("data", {})
            text = f"{post.get('title', '')} {post.get('selftext', '')}"
            found = {m.upper() for m in pattern.findall(text)}
            found &= valid
            if not found:
                continue
            # Recency weight: 'hot' listings mix hours-old and days-old posts;
            # only genuinely fresh chatter should move today's signal.
            w = recency.weight(
                recency.age_from_epoch(post.get("created_utc")),
                recency.SOCIAL_HALF_LIFE_DAYS, recency.SOCIAL_MAX_AGE_DAYS)
            if w <= 0:
                continue
            compound = _analyzer.polarity_scores(text[:1000])["compound"]
            for tk in found:
                # counts/sent dicts are keyed by original case; map back
                for orig in tickers:
                    if orig.upper() == tk:
                        counts[orig] += w
                        sent_sum[orig] += compound * w

    results: dict[str, dict] = {}
    for tk in tickers:
        c = counts[tk]
        results[tk] = {
            "reddit_mentions": round(c, 2),
            "reddit_sentiment": round(sent_sum[tk] / c, 4) if c else 0.0,
        }
    return results
