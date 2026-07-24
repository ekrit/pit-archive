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


def _headlines(session, url: str) -> list[str]:
    try:
        resp = session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
    except (ET.ParseError, Exception):
        return []
    titles = []
    for item in root.iter("item"):
        title_el = item.find("title")
        if title_el is not None and title_el.text:
            titles.append(title_el.text)
    return titles


def fetch(tickers: list[str]) -> dict[str, dict]:
    session = make_session()
    results: dict[str, dict] = {}
    for tk in tickers:
        url = _RSS_TEMPLATE.format(query=_query_for(tk))
        titles = _headlines(session, url)[: config.NEWS_ARTICLES_PER_TICKER]
        if not titles:
            results[tk] = {"news_count": 0, "news_sentiment": 0.0}
            time.sleep(0.4)
            continue
        scores = [_analyzer.polarity_scores(t)["compound"] for t in titles]
        results[tk] = {
            "news_count": len(titles),
            "news_sentiment": sum(scores) / len(scores),
        }
        time.sleep(0.5)  # be polite to the RSS endpoint
    return results
