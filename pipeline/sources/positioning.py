"""FINRA Reg SHO daily short-sale volume (free public files, no key).

FINRA publishes, every trading day, per-symbol short volume across TRFs:
    https://cdn.finra.org/equity/regsho/daily/CNMSshvolYYYYMMDD.txt
Pipe-delimited: Date|Symbol|ShortVolume|ShortExemptVolume|TotalVolume|Market

Signal per ticker:
  short_vol_ratio  ShortVolume / TotalVolume for the latest available day.
                   Elevated ratios flag heavy shorting pressure — a squeeze
                   precondition — while very low ratios flag one-sided buying.

One file covers the whole market, so this source is a single HTTP request per
day regardless of universe size. The parsed map is cached in-process.
"""
from __future__ import annotations

import datetime as dt

from .. import config
from ..http import make_session

_URL = "https://cdn.finra.org/equity/regsho/daily/CNMSshvol{ymd}.txt"
_cache: dict[str, dict[str, float]] = {}


def parse_regsho(text: str) -> dict[str, float]:
    """Parse a Reg SHO daily file into {symbol: short_vol_ratio}."""
    out: dict[str, float] = {}
    for line in text.splitlines():
        parts = line.strip().split("|")
        if len(parts) < 5 or parts[0] == "Date":
            continue
        sym = parts[1].upper()
        try:
            short_vol = float(parts[2])
            total_vol = float(parts[4])
        except ValueError:
            continue
        if total_vol > 0:
            out[sym] = round(short_vol / total_vol, 4)
    return out


def _latest_map(session) -> dict[str, float]:
    """Try today then walk back a few days (weekends/holidays/lag)."""
    for back in range(0, 6):
        day = dt.date.today() - dt.timedelta(days=back)
        ymd = day.strftime("%Y%m%d")
        if ymd in _cache:
            return _cache[ymd]
        try:
            resp = session.get(_URL.format(ymd=ymd),
                               timeout=config.REQUEST_TIMEOUT_SECONDS)
        except Exception:  # noqa: BLE001
            continue
        if resp.status_code == 200 and "|" in resp.text[:200]:
            parsed = parse_regsho(resp.text)
            if parsed:
                _cache[ymd] = parsed
                return parsed
    return {}


def fetch(tickers: list[str]) -> dict[str, dict]:
    session = make_session()
    ratios = _latest_map(session)
    return {
        tk: {"short_vol_ratio": ratios.get(tk)}
        for tk in tickers
    }
