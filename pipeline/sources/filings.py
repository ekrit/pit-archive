"""Recent SEC filing activity via EDGAR's free JSON APIs (no key).

Signals:
  - recent Form 4 count (insider transactions; clustered insider *buying*
    is a classic pre-move tell, though Form 4 alone doesn't tell buy vs sell
    without parsing the document, so we treat volume of Form 4s as an
    "insider activity" proxy).
  - recent 8-K count (material events / catalysts).

SEC asks for a descriptive User-Agent and rate limits to ~10 req/s. We map
tickers to CIK via the public company_tickers.json.
"""
import datetime as dt
import json
import os
import re
import time

from .. import config
from ..http import make_session, get_json

# www.sec.gov 403s many cloud IPs (GitHub runners included) while data.sec.gov
# stays open, so the ticker->CIK map is fetched through a mirror chain before
# falling back to the committed cache.
# NOTE: data.sec.gov/files/... does NOT exist (verified 404 from CI); only
# www.sec.gov serves the ticker map, and it 403s clients whose User-Agent
# lacks a declared contact email (SEC fair-access policy). Setting the
# SEC_USER_AGENT secret to "<project> <email>" is what unblocks this source.
_TICKER_MAP_URLS = [
    "https://www.sec.gov/files/company_tickers.json",
]
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_LOOKBACK_DAYS = 45
# Minimum entries for a cache to be considered real. Guards against a tiny
# fixture map (e.g. written by a test) starving the live source.
_MIN_CREDIBLE_CIK_ENTRIES = 100


def _cik_cache_path() -> str:
    """Resolved at call time so tests can redirect config.WATCHLIST_FILE."""
    return os.path.join(os.path.dirname(config.WATCHLIST_FILE), "cik_map.json")


# --- fallback: derive ticker->CIK without www.sec.gov -----------------------
# data.sec.gov is reachable from CI (its submissions API answers 200) while
# www.sec.gov/files/company_tickers.json 403s. The XBRL "frames" API lives on
# data.sec.gov and returns thousands of {cik, entityName} pairs in ONE request,
# which we can join to the ticker->company-name map already built from the
# NASDAQ listing. Fuzzy-but-safe: names are normalized, and any name that maps
# to more than one CIK is dropped rather than guessed.
_FRAMES_URL = ("https://data.sec.gov/api/xbrl/frames/dei/"
               "EntityCommonStockSharesOutstanding/shares/CY{year}Q{q}I.json")
_NAME_NOISE_RE = re.compile(
    r"\b(inc|corp|corporation|co|company|ltd|plc|holdings?|group|sa|nv|ag|"
    r"limited|incorporated|lp|llc|trust|fund|the|new|class|common|stock|"
    r"shares?|ordinary|depositary|american)\b", re.IGNORECASE)


def _normalize_name(name: str) -> str:
    """Aggressively normalize a company name for cross-source matching."""
    name = re.sub(r"\s+-\s+.*$", "", name or "")          # NASDAQ descriptor
    name = re.sub(r"[^A-Za-z0-9 ]+", " ", name)            # punctuation
    name = _NAME_NOISE_RE.sub(" ", name)                   # legal/security noise
    return " ".join(name.split()).upper()


def _company_name_map() -> dict[str, str]:
    path = os.path.join(os.path.dirname(config.WATCHLIST_FILE),
                        "sec_company_names.json")
    try:
        with open(path) as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def build_cik_map_from_frames(session, names: dict[str, str]) -> dict[str, int]:
    """ticker -> CIK by joining the XBRL frames entity list to company names."""
    if not names:
        return {}
    today = dt.date.today()
    # Walk back a few quarters; the newest frame may not be published yet.
    quarters = []
    y, q = today.year, (today.month - 1) // 3 + 1
    for _ in range(5):
        quarters.append((y, q))
        q -= 1
        if q == 0:
            y, q = y - 1, 4

    entities: list[dict] = []
    tried = []
    for year, quarter in quarters:
        data = _get_json_patient(session, _FRAMES_URL.format(year=year, q=quarter))
        tried.append(f"CY{year}Q{quarter}I")
        if isinstance(data, dict) and data.get("data"):
            entities = data["data"]
            print(f"[sec] XBRL frame CY{year}Q{quarter}I -> {len(entities)} entities")
            break
    if not entities:
        # Say which quarters were attempted, so a naming/publication problem is
        # distinguishable from data.sec.gov refusing us.
        print(f"[sec] no XBRL frame returned data (tried {', '.join(tried)})")
        return {}

    # Normalized SEC name -> CIK, dropping ambiguous names.
    by_name: dict[str, int | None] = {}
    for e in entities:
        try:
            cik = int(e["cik"])
        except (KeyError, TypeError, ValueError):
            continue
        key = _normalize_name(e.get("entityName", ""))
        if not key:
            continue
        if key in by_name and by_name[key] != cik:
            by_name[key] = None  # ambiguous: refuse to guess
        else:
            by_name.setdefault(key, cik)

    out: dict[str, int] = {}
    for ticker, company in names.items():
        cik = by_name.get(_normalize_name(company))
        if cik:
            out[ticker.upper()] = cik
    print(f"[sec] frames join: {len(out)} of {len(names)} tickers matched "
          f"({len(by_name)} distinct SEC entity names)")
    return out


def is_rate_limited(resp) -> bool:
    """True when SEC is throttling rather than refusing us outright.

    SEC answers 403 with a 'Request Rate Threshold Exceeded' page when an IP
    exceeds its ~10 req/s budget — on shared CI runners that budget is partly
    spent by other tenants. Distinguishing this from a real block matters:
    a throttle clears if you wait, a block never does.
    """
    if resp is None or getattr(resp, "status_code", None) not in (403, 429):
        return False
    body = (getattr(resp, "text", "") or "")[:2000].lower()
    return ("rate threshold" in body or "request rate" in body
            or "too many requests" in body)


def _get_json_patient(session, url: str):
    """GET that waits out SEC throttling instead of hammering through it."""
    for attempt in range(config.SEC_THROTTLE_MAX_WAITS + 1):
        try:
            resp = session.get(url, headers={"User-Agent": config.SEC_USER_AGENT},
                               timeout=config.REQUEST_TIMEOUT_SECONDS)
        except Exception:  # noqa: BLE001 - network hiccup
            resp = None
        if resp is not None and resp.status_code == 200:
            try:
                return resp.json()
            except ValueError:
                return None
        if not is_rate_limited(resp):
            return None  # genuine failure: no point waiting
        if attempt < config.SEC_THROTTLE_MAX_WAITS:
            wait = config.SEC_THROTTLE_BACKOFF_SECONDS * (attempt + 1)
            print(f"[sec] throttled by SEC, waiting {wait:.0f}s "
                  f"(attempt {attempt + 1}/{config.SEC_THROTTLE_MAX_WAITS})")
            time.sleep(wait)
    return None


def _load_cik_map(session) -> dict[str, int]:
    out: dict[str, int] = {}
    for url in _TICKER_MAP_URLS:
        data = _get_json_patient(session, url)
        if not data:
            continue
        for row in data.values():
            try:
                out[row["ticker"].upper()] = int(row["cik_str"])
            except (KeyError, ValueError, TypeError):
                continue
        if out:
            break
    if not out:
        # www.sec.gov blocked -> derive the map from data.sec.gov instead.
        out = build_cik_map_from_frames(session, _company_name_map())
        if out:
            print(f"[sec] CIK map derived from XBRL frames: {len(out)} tickers")

    path = _cik_cache_path()
    if len(out) >= _MIN_CREDIBLE_CIK_ENTRIES:
        try:  # refresh the committed cache for the next blocked run
            with open(path, "w") as fh:
                json.dump(out, fh)
        except OSError:
            pass
        return out
    if out:  # small but live result: use it, don't overwrite a bigger cache
        return out
    # Every mirror blocked -> committed cache, if it looks credible.
    if os.path.exists(path):
        try:
            with open(path) as fh:
                cached = {k: int(v) for k, v in json.load(fh).items()}
            if len(cached) >= _MIN_CREDIBLE_CIK_ENTRIES:
                return cached
            print(f"[sec] ignoring implausible CIK cache ({len(cached)} entries)")
        except (json.JSONDecodeError, OSError, ValueError):
            pass
    return out


def fetch(tickers: list[str]) -> dict[str, dict]:
    session = make_session(user_agent=config.SEC_USER_AGENT)
    cik_map = _load_cik_map(session)
    if not cik_map:
        return {}

    cutoff = dt.date.today() - dt.timedelta(days=_LOOKBACK_DAYS)
    results: dict[str, dict] = {}

    # Shared CI IPs already spend part of SEC's per-IP budget, so pace well
    # under the published cap instead of racing to it.
    from .. import parallel
    limiter = parallel.RateLimiter(config.SEC_RATE_PER_SEC)

    for tk in tickers:
        cik = cik_map.get(tk.upper())
        if cik is None:
            continue
        limiter.acquire()
        data = _get_json_patient(session, _SUBMISSIONS_URL.format(cik=cik))
        if not data:
            continue
        try:
            recent = data["filings"]["recent"]
            forms = recent["form"]
            dates = recent["filingDate"]
        except (KeyError, TypeError):
            continue

        form4 = 0
        eightk = 0
        for form, date_str in zip(forms, dates):
            try:
                fdate = dt.date.fromisoformat(date_str)
            except ValueError:
                continue
            if fdate < cutoff:
                continue
            if form == "4":
                form4 += 1
            elif form.startswith("8-K"):
                eightk += 1

        results[tk] = {
            "sec_form4_recent": form4,
            "sec_8k_recent": eightk,
        }
    return results
