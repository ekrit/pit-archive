"""News buzz + headline sentiment via Google News RSS (free, no key).

For each ticker we query Google News RSS, count recent articles (buzz)
and average VADER compound sentiment over the headlines. RSS is parsed with
the stdlib (xml.etree) to avoid fragile third-party feed-parser build deps.
"""
import time
import urllib.parse
import xml.etree.ElementTree as ET

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .. import config
from ..http import make_session

_RSS_TEMPLATE = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
_analyzer = SentimentIntensityAnalyzer()


def _query_for(ticker: str) -> str:
    # Quote the ticker and add "stock" to reduce false positives on common
    # words (e.g. ticker "ALL", "ON").
    return urllib.parse.quote_plus(f'"{ticker}" stock')


def _headlines(session, url: str) -> list[tuple[str, str | None]]:
    """[(title, pubDate-string-or-None), ...] from an RSS feed."""
    try:
        resp = session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
    except (ET.ParseError, Exception):
        return []
    out = []
    for item in root.iter("item"):
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            date_el = item.find("pubDate")
            out.append((title_el.text,
                        date_el.text if date_el is not None else None))
    return out


def fetch(tickers: list[str]) -> dict[str, dict]:
    """Threaded fetch — pacing enforced by a shared rate limiter, not sleeps."""
    from .. import parallel

    get_session = parallel.thread_local(make_session)

    def one(tk: str) -> dict:
        from .. import recency

        url = _RSS_TEMPLATE.format(query=_query_for(tk))
        items = _headlines(get_session(), url)[: config.NEWS_ARTICLES_PER_TICKER]
        if not items:
            return {"news_count": 0, "news_sentiment": 0.0}
        # Recency-weighted: a stale headline must not count like today's.
        scored = [(_analyzer.polarity_scores(title)["compound"],
                   recency.age_from_rfc2822(pub)) for title, pub in items]
        eff_count, sentiment = recency.weighted_stats(
            scored, recency.NEWS_HALF_LIFE_DAYS, recency.NEWS_MAX_AGE_DAYS)
        return {"news_count": eff_count, "news_sentiment": sentiment}

    return parallel.fetch_map(
        tickers, one,
        max_workers=config.PARALLEL_WORKERS,
        rate_per_sec=config.NEWS_RATE_PER_SEC,
        default={"news_count": 0, "news_sentiment": 0.0},
    )
