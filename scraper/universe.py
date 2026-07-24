"""Discover a candidate universe of tickers to score.

Combines Yahoo Finance predefined screeners (movers, most active, small-cap
gainers, etc.) with a user-maintained static watchlist. All free / no-auth.
"""
import os
import re

from . import config
from .http import make_session, get_json

_YAHOO_SCREENER_URL = "https://query2.finance.yahoo.com/v1/finance/screener/predefined/saved"
_TICKER_RE = re.compile(r"^[A-Z][A-Z.\-]{0,6}$")


def _from_screeners(session) -> set[str]:
    tickers: set[str] = set()
    for scr_id in config.YAHOO_SCREENER_IDS:
        data = get_json(
            session,
            _YAHOO_SCREENER_URL,
            params={"scrIds": scr_id, "count": config.YAHOO_SCREENER_COUNT},
        )
        if not data:
            continue
        try:
            quotes = data["finance"]["result"][0]["quotes"]
        except (KeyError, IndexError, TypeError):
            continue
        for q in quotes:
            sym = q.get("symbol")
            if sym and _TICKER_RE.match(sym):
                tickers.add(sym)
    return tickers


def _from_watchlist() -> set[str]:
    path = config.WATCHLIST_FILE
    if not os.path.exists(path):
        return set()
    out: set[str] = set()
    with open(path) as fh:
        for line in fh:
            line = line.split("#", 1)[0].strip().upper()
            if line and _TICKER_RE.match(line):
                out.add(line)
    return out


def discover() -> list[str]:
    """Return a deduped, capped list of candidate tickers."""
    session = make_session()
    tickers = _from_screeners(session) | _from_watchlist()
    ordered = sorted(tickers)
    return ordered[: config.MAX_TICKERS_TO_SCORE]
