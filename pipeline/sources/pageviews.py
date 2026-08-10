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
_NEUTRAL = {"wiki_views_7d": 0, "wiki_spike_ratio": None}

# Security-type descriptor after a dash, as used by the NASDAQ listing file:
# "Artius II Acquisition Inc. - Class A Ordinary Shares" -> "Artius II Acquisition Inc."
_DESCRIPTOR_RE = re.compile(r"\s+-\s+.*$")

# The NYSE/other-listed file appends the same descriptors with NO dash
# ("Agnico Eagle Mines Limited Common Stock", "Aegon Ltd. New York Registry
# Shares"), which made the whole string the search query and matched nothing.
# Strip a trailing descriptor phrase: qualifier words followed by a security
# noun. Anchored at the end, so a company whose NAME starts with one of these
# words (e.g. "American Eagle Outfitters") keeps it.
_DESC_QUALIFIER = (
    r"(?:class|series)\s+[A-Z0-9]{1,2}|new|york|registry|american|depositary|"
    r"depository|subordinate|voting|ordinary|common|preferred|capital|"
    r"beneficial|redeemable|convertible|non|par|value|limited|partnership"
)
_TRAILING_DESC_RE = re.compile(
    rf"[\s,\-]+(?:(?:{_DESC_QUALIFIER})\s+)*"
    r"(?:stock|shares?|units?|rights?|warrants?|interests?)\s*$",
    re.IGNORECASE)
# Legal suffixes that hurt Wikipedia title matching.
_SUFFIX_RE = re.compile(
    r",?\s+(inc|corp|corporation|co|company|ltd|plc|holdings|group|sa|nv|ag|"
    r"limited|incorporated|lp|llc|trust|fund)\.?$", re.IGNORECASE)

# Re-attempt a failed article lookup after this many days rather than caching
# the failure forever.
_NEGATIVE_TTL_DAYS = 7


def _cache_path() -> str:
    """Resolved at call time so tests can redirect config.WATCHLIST_FILE."""
    return os.path.join(os.path.dirname(config.WATCHLIST_FILE), "wiki_articles.json")


def _load_cache() -> dict:
    path = _cache_path()
    if os.path.exists(path):
        try:
            with open(path) as fh:
                raw = json.load(fh)
        except (json.JSONDecodeError, OSError):
            return {}
        # Legacy format was {ticker: article-or-""}. Treat those as
        # ticker-sourced so they get re-resolved once a real name exists.
        out = {}
        for k, v in raw.items():
            out[k] = v if isinstance(v, dict) else {
                "article": v or "", "src": "ticker" if v else "none", "date": ""}
        return out
    return {}


def _save_cache(cache: dict) -> None:
    path = _cache_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as fh:
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


def _strip_descriptor(name: str) -> str:
    """Drop the security-type descriptor, dash-separated or not."""
    name = _DESCRIPTOR_RE.sub("", name or "").strip()
    prev = None
    while prev != name:  # e.g. "... Common Stock" then a leftover qualifier
        prev = name
        name = _TRAILING_DESC_RE.sub("", name).strip(" ,-")
    return name


def _clean_name(name: str) -> str:
    """Strip security-type descriptors AND legal suffixes for search."""
    name = _strip_descriptor(name)
    prev = None
    while prev != name:
        prev = name
        name = _SUFFIX_RE.sub("", name).strip()
    return name


def _search_queries(tk: str, raw_name: str) -> list[str]:
    """Candidate search queries, most disambiguating first.

    The legal suffix is a feature, not noise, when searching: 'Apple Inc.'
    finds the company while 'Apple' finds the fruit. So try the
    descriptor-stripped name (which keeps 'Inc.') before the fully cleaned
    one, and only fall back to the bare ticker.
    """
    with_suffix = _strip_descriptor(raw_name)
    stripped = _clean_name(raw_name)
    out = []
    for q in (with_suffix, stripped, tk):
        if q and q not in out:
            out.append(q)
    return out


def _stale(entry: dict) -> bool:
    if not entry.get("date"):
        return True
    try:
        age = (dt.date.today() - dt.date.fromisoformat(entry["date"][:10])).days
    except ValueError:
        return True
    return age >= _NEGATIVE_TTL_DAYS


def _resolve_article(session, tk: str, names: dict[str, str], cache: dict) -> str | None:
    """Ticker -> Wikipedia article, cached, without freezing bad resolutions.

    A lookup made before company names were available (or one that failed)
    must not be cached forever: it is retried once a real name exists, or
    after the negative TTL.
    """
    company = _clean_name(names.get(tk, ""))
    entry = cache.get(tk)
    if isinstance(entry, dict):
        good = entry.get("article") and entry.get("src") == "name"
        # A ticker-fallback hit is superseded as soon as a company name exists.
        usable_fallback = (entry.get("article") and entry.get("src") == "ticker"
                           and not company)
        if good or usable_fallback:
            return entry["article"]
        if not entry.get("article") and not company and not _stale(entry):
            return None  # nothing new to try yet

    article = None
    used = None
    for query in _search_queries(tk, names.get(tk, "")):
        data = get_json(session, _SEARCH_URL.format(q=urllib.parse.quote(query)))
        if isinstance(data, list) and len(data) >= 2 and data[1]:
            article = str(data[1][0]).replace(" ", "_")
            used = query
            break
    cache[tk] = {
        "article": article or "",
        "src": ("name" if (used and used != tk) else "ticker") if article else "none",
        "date": dt.date.today().isoformat(),
    }
    return article


def fetch_asof(tickers: list[str], as_of: dt.date) -> dict[str, dict]:
    """Pageviews as they stood on a PAST date.

    The Wikimedia API serves per-day counts for an arbitrary range, so this
    returns exactly what a live run on `as_of` would have seen — no
    look-ahead. Used by pipeline/backfill.py to recover missed days.
    """
    return fetch(tickers, as_of=as_of)


def fetch(tickers: list[str], as_of: dt.date | None = None) -> dict[str, dict]:
    # Wikimedia policy: identify the tool, don't spoof a browser.
    get_session = parallel.thread_local(
        lambda: make_session(user_agent=config.WIKI_USER_AGENT))
    names = _company_names()
    cache = _load_cache()

    end = (as_of or dt.date.today()) - dt.timedelta(days=1)
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
    # Distinguish the two very different failure modes: article resolution
    # failing (search host blocked / no match) vs resolution succeeding but
    # pageviews coming back empty. Without this the source just reads "0".
    resolved = sum(1 for tk in tickers
                   if isinstance(cache.get(tk), dict) and cache[tk].get("article"))
    with_views = sum(1 for v in out.values() if (v.get("wiki_views_7d") or 0) > 0)
    print(f"[wikipedia] resolved {resolved}/{len(tickers)} articles, "
          f"{with_views} with pageviews, {len(names)} company names available")
    return out
