"""Stocktwits public API (free, no auth): trending tickers + message sentiment.

Two signals per ticker:
  st_trending   1.0 if the ticker is on Stocktwits' trending list (a strong
                retail-attention spike marker), else 0.0
  st_msg_count  recent public message count for the symbol stream
  st_sentiment  mean VADER compound over recent message bodies

Endpoints (public, key-free):
  https://api.stocktwits.com/api/2/trending/symbols.json
  https://api.stocktwits.com/api/2/streams/symbol/{TICKER}.json

Best-effort: Stocktwits may rate-limit anonymous clients; failures degrade to
neutral values, never crash the run.
"""
from __future__ import annotations

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .. import config, parallel
from ..http import make_session, get_json

_TRENDING_URL = "https://api.stocktwits.com/api/2/trending/symbols.json"
_STREAM_URL = "https://api.stocktwits.com/api/2/streams/symbol/{tk}.json"
_analyzer = SentimentIntensityAnalyzer()

_NEUTRAL = {"st_trending": 0.0, "st_msg_count": 0, "st_sentiment": 0.0}


def _trending_set(session) -> set[str]:
    data = get_json(session, _TRENDING_URL)
    out: set[str] = set()
    if isinstance(data, dict):
        for sym in data.get("symbols", []):
            s = sym.get("symbol")
            if s:
                out.add(str(s).upper())
    return out


def fetch(tickers: list[str]) -> dict[str, dict]:
    session = make_session()
    trending = _trending_set(session)

    def one(tk: str) -> dict:
        data = get_json(session, _STREAM_URL.format(tk=tk))
        msgs = (data or {}).get("messages", []) if isinstance(data, dict) else []
        bodies = [m.get("body", "") for m in msgs if m.get("body")]
        sent = (
            sum(_analyzer.polarity_scores(b)["compound"] for b in bodies) / len(bodies)
            if bodies else 0.0
        )
        return {
            "st_trending": 1.0 if tk in trending else 0.0,
            "st_msg_count": len(bodies),
            "st_sentiment": round(sent, 4),
        }

    return parallel.fetch_map(
        tickers, one,
        max_workers=config.PARALLEL_WORKERS,
        rate_per_sec=config.STOCKTWITS_RATE_PER_SEC,
        default=dict(_NEUTRAL),
    )
