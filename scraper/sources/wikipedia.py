"""Wikipedia pageview attention signal (Wikimedia REST API, free, no key).

Academic backing: Wikipedia pageviews are a documented proxy for investor
attention (e.g. "Wikipedia pageviews as investors' attention indicator for
Nasdaq", Wiley 2022; ElBannan 2024). The tradeable observation is the *spike*:
recent views vs the trailing baseline.

Signals per ticker:
  wiki_views_7d     total article views over the last 7 days
  wiki_spike_ratio  mean(last 7d) / mean(prior 21d)  — attention acceleration

Ticker→article resolution uses the SEC company-name map (already cached by
universe.full_market) plus Wikipedia's search API as fallback, cached on disk
so each name resolves once, ever.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import re
import urllib.parse

from .. import config, parallel
from ..http import make_session, get_json

_PV_URL = ("https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/"
           "en.wikipedia/all-access/user/{article}/daily/{start}/{end}")
_SEARCH_URL = ("https://en.wikipedia.org/w/api.php?action=opensearch&limit=1"
               "&namespace=0&format=json&search={q}")
_CACHE = os.path.join(os.path.dirname(config.WATCHLIST_FILE), "wiki_articles.json")

_NEUTRAL = {"wiki_views_7d": 0, "wiki_spike_ratio": None}

# Legal suffixes that hurt Wikipedia title matching.
_SUFFIX_RE = re.compile(
    r",?\s+(inc|corp|corporation|co|company|ltd|plc|holdings|group|sa|nv|ag|"
    r"limited|incorporated|lp|llc|trust|fund)\.?$", re.IGNORECASE)


def _load_cache() -> dict:
    if os.path.exists(_CACHE):
        try:
            with open(_CACHE) as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache: dict) -> None:
    os.makedirs(os.path.dirname(_CACHE), exist_ok=True)
    with open(_CACHE, "w") as fh:
        json.dump(cache, fh)


def _company_names() -> dict[str, str]:
    """ticker -> SEC company title, from the cached full-market listing."""
    path = os.path.join(os.path.dirname(config.WATCHLIST_FILE), "sec_company_names.json")
    if os.path.exists(path):
        try:
            with open(path) as fh:
                return json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _clean_name(name: str) -> str:
    prev = None
    while prev != name:
        prev = name
        name = _SUFFIX_RE.sub("", name).strip()
    return name


def _resolve_article(session, tk: str, names: dict[str, str], cache: dict) -> str | None:
    if tk in cache:
        return cache[tk] or None
    query = _clean_name(names.get(tk, "")) or tk
    data = get_json(session, _SEARCH_URL.format(q=urllib.parse.quote(query)))
    article = None
    if isinstance(data, list) and len(data) >= 2 and data[1]:
        article = str(data[1][0]).replace(" ", "_")
    cache[tk] = article or ""
    return article


def fetch(tickers: list[str]) -> dict[str, dict]:
    get_session = parallel.thread_local(make_session)
    names = _company_names()
    cache = _load_cache()

    end = dt.date.today() - dt.timedelta(days=1)
    start = end - dt.timedelta(days=28)
    fmt = "%Y%m%d"

    def one(tk: str) -> dict:
        session = get_session()
        article = _resolve_article(session, tk, names, cache)
        if not article:
            return dict(_NEUTRAL)
        url = _PV_URL.format(article=urllib.parse.quote(article, safe=""),
                             start=start.strftime(fmt), end=end.strftime(fmt))
        data = get_json(session, url)
        items = (data or {}).get("items", []) if isinstance(data, dict) else []
        if not items:
            return dict(_NEUTRAL)
        views = [(it["timestamp"][:8], it.get("views", 0)) for it in items]
        views.sort()
        counts = [v for _, v in views]
        recent = counts[-7:]
        base = counts[:-7]
        spike = (
            (sum(recent) / max(len(recent), 1)) / (sum(base) / len(base))
            if base and sum(base) > 0 else None
        )
        return {
            "wiki_views_7d": int(sum(recent)),
            "wiki_spike_ratio": round(spike, 3) if spike is not None else None,
        }

    out = parallel.fetch_map(
        tickers, one,
        max_workers=config.PARALLEL_WORKERS,
        rate_per_sec=config.WIKI_RATE_PER_SEC,
        default=dict(_NEUTRAL),
    )
    _save_cache(cache)
    return out
