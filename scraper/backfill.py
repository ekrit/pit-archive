"""Reconstruct the recoverable part of a missed collection day.

    python -m scraper.backfill --since 2026-07-28
    python -m scraper.backfill --dates 2026-07-28,2026-07-29 --dry-run

When collection stops (CI outage, quota block, a bad deploy), some of the
missed data is gone forever and some is not. The split is what matters:

  RECOVERABLE — the publisher exposes it by date, so fetching it later gives
  exactly what a live run would have captured, with no look-ahead:
    * price history and every price-derived factor (sliced to that date)
    * FINRA Reg SHO daily short volume (one file per date)
    * Wikipedia pageviews (the API returns per-day counts for a range)

  LOST FOREVER — recent-only feeds with no historical query:
    * news headlines, Stocktwits messages, Reddit posts (and their sentiment)

So a backfilled snapshot is genuinely useful but NOT equivalent to a live
one, for two reasons that are recorded on every row rather than hidden:
  1. the attention signals above are absent, and
  2. the universe is borrowed from the nearest real snapshot, because which
     tickers the screener would have surfaced that day is itself
     unrecoverable.

Rows are written with backfilled=True and the list of missing families, and
an existing real snapshot for a date is never overwritten.
"""
from __future__ import annotations

import argparse
import datetime as dt

from . import config, factors, store
from .sources import short_interest, wikipedia

RECOVERABLE = ["prices", "factors", "finra_short", "wikipedia"]
UNRECOVERABLE = ["news", "stocktwits", "reddit", "sec_filings"]


def missing_business_days(start: dt.date, end: dt.date,
                          have: set[str]) -> list[dt.date]:
    """Weekdays in [start, end] with no snapshot yet."""
    out = []
    d = start
    while d <= end:
        if d.weekday() < 5 and d.isoformat() not in have:
            out.append(d)
        d += dt.timedelta(days=1)
    return out


def _price_features_asof(df, date: dt.date) -> dict | None:
    """Point-in-time features from history sliced to `date` (no look-ahead)."""
    if df is None or df.empty:
        return None
    upto = df[df.index.date <= date] if hasattr(df.index, "date") else df
    if len(upto) < 21:
        return None
    close = upto["Close"]
    volume = upto["Volume"]
    last = float(close.iloc[-1])
    if last <= 0:
        return None

    def ret(lb):
        if len(close) <= lb:
            return None
        past = float(close.iloc[-lb - 1])
        return (last / past - 1.0) if past > 0 else None

    recent = volume.iloc[-5:].mean()
    base = volume.iloc[-60:-5].mean() if len(volume) > 65 else volume.mean()
    hi, lo = float(close.max()), float(close.min())
    feats = {
        "last_price": last,
        "ret_5d": ret(5), "ret_21d": ret(21), "ret_63d": ret(63),
        "volume_spike_ratio": float(recent / base) if base and base > 0 else None,
        "pct_off_52w_high": (last / hi - 1.0) if hi > 0 else None,
        "pct_above_52w_low": (last / lo - 1.0) if lo > 0 else None,
        "annualized_vol": float(close.pct_change().std() * (252 ** 0.5))
        if len(close) > 2 else None,
    }
    if {"Open", "High", "Low"}.issubset(upto.columns):
        feats.update(factors.compute_factors(upto))
    return feats


def backfill_date(date: dt.date, tickers: list[str], dry_run: bool = False) -> int:
    """Reconstruct and store one missed date. Returns rows written."""
    import yfinance as yf

    iso = date.isoformat()
    print(f"[backfill] {iso}: {len(tickers)} tickers from the nearest real snapshot")

    # Price history through the target date (a generous window covers the
    # 63-day lookbacks the factors need).
    start = (date - dt.timedelta(days=400)).isoformat()
    end = (date + dt.timedelta(days=1)).isoformat()
    data = yf.download(tickers=" ".join(tickers), start=start, end=end,
                       group_by="ticker", auto_adjust=True, threads=True,
                       progress=False)

    # FINRA publishes one file per date — genuinely point-in-time.
    short_map = {}
    try:
        session = short_interest.make_session()
        url = short_interest._URL.format(ymd=date.strftime("%Y%m%d"))
        resp = session.get(url, timeout=config.REQUEST_TIMEOUT_SECONDS)
        if resp.status_code == 200 and "|" in resp.text[:200]:
            short_map = short_interest.parse_regsho(resp.text)
        print(f"[backfill] FINRA short volume: {len(short_map)} symbols")
    except Exception as e:  # noqa: BLE001
        print(f"[backfill] FINRA unavailable for {iso}: {type(e).__name__}")

    # Wikipedia pageviews for the 28 days ending at the target date.
    wiki_map = {}
    try:
        wiki_map = wikipedia.fetch_asof(tickers, date)
        print(f"[backfill] wikipedia: {sum(1 for v in wiki_map.values() if v.get('wiki_views_7d'))} with views")
    except Exception as e:  # noqa: BLE001
        print(f"[backfill] wikipedia unavailable: {type(e).__name__}")

    results = []
    for tk in tickers:
        try:
            df = data if len(tickers) == 1 else data[tk]
        except (KeyError, TypeError):
            continue
        feats = _price_features_asof(df, date)
        if not feats:
            continue
        feats["short_vol_ratio"] = short_map.get(tk)
        feats.update(wiki_map.get(tk, {}))
        results.append({
            "ticker": tk,
            "score": None,           # no composite: attention inputs are absent
            "components": {},
            "features": feats,
            "backfilled": True,
            "backfilled_missing": UNRECOVERABLE,
        })

    if dry_run:
        print(f"[backfill] dry run — would write {len(results)} rows for {iso}")
        return len(results)
    if not results:
        return 0
    n = store.append_snapshot(results, date=iso)
    # Archive the closes too, so labels for this date are dense.
    panel = {r["ticker"]: {iso: r["features"]["last_price"]} for r in results}
    store.append_prices(panel)
    print(f"[backfill] wrote {n} rows for {iso}")
    return n


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since", type=str, help="backfill missing weekdays from this date")
    ap.add_argument("--dates", type=str, help="comma-separated explicit dates")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    records = store.load_features()
    have = set(store.distinct_dates(records))
    if not have:
        raise SystemExit("no existing snapshots — nothing to borrow a universe from")

    if args.dates:
        targets = [dt.date.fromisoformat(d.strip()) for d in args.dates.split(",")]
        targets = [d for d in targets if d.isoformat() not in have]
    elif args.since:
        targets = missing_business_days(
            dt.date.fromisoformat(args.since), dt.date.today(), have)
    else:
        raise SystemExit("pass --since or --dates")

    if not targets:
        print("[backfill] nothing missing in that range.")
        return

    print(f"[backfill] {len(targets)} missing date(s): "
          f"{', '.join(d.isoformat() for d in targets)}")
    print(f"[backfill] recoverable: {', '.join(RECOVERABLE)}")
    print(f"[backfill] NOT recoverable (absent from these rows): "
          f"{', '.join(UNRECOVERABLE)}")

    for date in targets:
        # Borrow the universe from the nearest real snapshot before the gap.
        prior = [d for d in sorted(have) if d < date.isoformat()] or sorted(have)
        universe = sorted({r["ticker"] for r in records if r["date"] == prior[-1]})
        backfill_date(date, universe, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
