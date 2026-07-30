"""Proper point-in-time data store for a multi-month collection effort.

Design goals (this is the layer that must not be sloppy, because you cannot
re-collect point-in-time data after the fact):

  * Idempotent — re-running a day never duplicates rows. Every record is
    upserted on its (date, ticker) key, so manual + scheduled runs on the same
    day converge to one row instead of double-counting and biasing every IC.
  * Partitioned by month — `.../YYYY-MM.jsonl`. Loads stay fast and git diffs
    stay small as history grows for months.
  * Versioned — every record carries `schema_version`, so a later feature
    change doesn't silently corrupt older rows.
  * Two separate archives:
      - features/  : point-in-time signal snapshots (the hot list each day)
      - prices/    : a DENSE daily close archive for every ticker ever seen,
                     so forward-return labels survive universe churn — critical
                     because a name often leaves the momentum screen right
                     around its big move.
  * Self-describing — `manifest.json` records coverage so you can eyeball the
    dataset's health at a glance.

JSONL (text) is used rather than a binary DB because history is persisted by
committing it to git from ephemeral CI runners; text merges and diffs, binary
blobs don't.
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os

SCHEMA_VERSION = 2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(ROOT, "data", "history")
FEATURES_DIR = os.path.join(HISTORY_DIR, "features")
PRICES_DIR = os.path.join(HISTORY_DIR, "prices")
MANIFEST_PATH = os.path.join(HISTORY_DIR, "manifest.json")
LEGACY_FEATURES_PATH = os.path.join(HISTORY_DIR, "features.jsonl")  # v1 flat file


# --------------------------------------------------------------------------- #
# low-level partitioned JSONL with idempotent upsert
# --------------------------------------------------------------------------- #

def _month(date: str) -> str:
    return date[:7]  # YYYY-MM


def _partition_path(base_dir: str, date: str) -> str:
    return os.path.join(base_dir, f"{_month(date)}.jsonl")


def _read_jsonl(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _write_jsonl(path: str, records: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as fh:
        for r in records:
            fh.write(json.dumps(r, separators=(",", ":"), sort_keys=True) + "\n")
    os.replace(tmp, path)  # atomic; never leaves a half-written partition


def _upsert(base_dir: str, records: list[dict]) -> int:
    """Upsert records into month partitions, keyed on (date, ticker).

    Returns the number of rows written (new or replaced). Existing rows with
    the same (date, ticker) are overwritten, guaranteeing no duplicates.
    """
    by_month: dict[str, list[dict]] = {}
    for r in records:
        by_month.setdefault(_month(r["date"]), []).append(r)

    written = 0
    for month, recs in by_month.items():
        path = os.path.join(base_dir, f"{month}.jsonl")
        existing = _read_jsonl(path)
        merged: dict[tuple, dict] = {(e["date"], e["ticker"]): e for e in existing}
        for r in recs:
            merged[(r["date"], r["ticker"])] = r
            written += 1
        ordered = sorted(merged.values(), key=lambda e: (e["date"], e["ticker"]))
        _write_jsonl(path, ordered)
    return written


def _load_all(base_dir: str) -> list[dict]:
    out: list[dict] = []
    for path in sorted(glob.glob(os.path.join(base_dir, "*.jsonl"))):
        out.extend(_read_jsonl(path))
    return out


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def _valid_date(date: str) -> bool:
    try:
        dt.date.fromisoformat(date[:10])
        return True
    except (ValueError, TypeError):
        return False


def _num_or_none(x):
    return float(x) if isinstance(x, (int, float)) and x == x else None  # x==x drops NaN


# --------------------------------------------------------------------------- #
# features archive
# --------------------------------------------------------------------------- #

def append_snapshot(results: list[dict], date: str | None = None) -> int:
    """Write one point-in-time feature record per result (idempotent)."""
    date = date or dt.date.today().isoformat()
    if not _valid_date(date):
        raise ValueError(f"bad date: {date!r}")
    records = []
    for r in results:
        tk = r.get("ticker")
        if not tk:
            continue
        feats = r.get("features") or {}
        rec = {
            "schema_version": SCHEMA_VERSION,
            "date": date,
            "ticker": tk,
            "score": _num_or_none(r.get("score")),
            "last_price": _num_or_none(feats.get("last_price")),
            "components": r.get("components", {}),
            "features": feats,
        }
        # Reconstructed rows are marked so evaluation can separate them from
        # true point-in-time captures: their universe and signal coverage
        # differ from a live run (see scraper/backfill.py).
        if r.get("backfilled"):
            rec["backfilled"] = True
            rec["backfilled_missing"] = r.get("backfilled_missing", [])
        records.append(rec)
    n = _upsert(FEATURES_DIR, records)
    _migrate_legacy_features()
    update_manifest()
    return n


def load_features() -> list[dict]:
    """All feature snapshots (partitions + migrated legacy v1 file)."""
    recs = _load_all(FEATURES_DIR)
    if os.path.exists(LEGACY_FEATURES_PATH):
        legacy = _read_jsonl(LEGACY_FEATURES_PATH)
        seen = {(r["date"], r["ticker"]) for r in recs}
        for r in legacy:
            if "date" in r and "ticker" in r and (r["date"], r["ticker"]) not in seen:
                r.setdefault("schema_version", 1)
                recs.append(r)
    return recs


# Backwards-compatible alias used by earlier code/tests.
def load_history() -> list[dict]:
    return load_features()


def _migrate_legacy_features() -> None:
    """One-time fold of any v1 flat features.jsonl into partitions."""
    if not os.path.exists(LEGACY_FEATURES_PATH):
        return
    legacy = _read_jsonl(LEGACY_FEATURES_PATH)
    good = [r for r in legacy if "date" in r and "ticker" in r and _valid_date(r["date"])]
    if good:
        for r in good:
            r.setdefault("schema_version", 1)
        _upsert(FEATURES_DIR, good)
    os.replace(LEGACY_FEATURES_PATH, LEGACY_FEATURES_PATH + ".migrated")


# --------------------------------------------------------------------------- #
# prices archive (dense; survives universe churn)
# --------------------------------------------------------------------------- #

def append_prices(price_panel: dict[str, dict[str, float]]) -> int:
    """Archive daily closes. `price_panel` = {ticker: {isodate: close}}.

    Backfills multiple recent days per run so missed runs / weekends self-heal.
    """
    records = []
    for tk, series in price_panel.items():
        for date, close in series.items():
            c = _num_or_none(close)
            if not tk or not _valid_date(date) or c is None or c <= 0:
                continue
            records.append({
                "schema_version": SCHEMA_VERSION,
                "date": date[:10],
                "ticker": tk,
                "close": c,
            })
    n = _upsert(PRICES_DIR, records)
    update_manifest()
    return n


def load_prices() -> list[dict]:
    return _load_all(PRICES_DIR)


def price_panel() -> dict[str, list[tuple[str, float]]]:
    """{ticker: [(date, close), ...]} sorted ascending by date."""
    panel: dict[str, list[tuple[str, float]]] = {}
    for r in load_prices():
        panel.setdefault(r["ticker"], []).append((r["date"], r["close"]))
    for tk in panel:
        panel[tk].sort(key=lambda x: x[0])
    return panel


def tracked_tickers() -> list[str]:
    """Every ticker ever seen in features OR prices.

    Used to keep archiving prices for names that have dropped off the hot list,
    so their forward-return labels remain available.
    """
    seen = set()
    for r in _load_all(FEATURES_DIR):
        seen.add(r.get("ticker"))
    for r in _load_all(PRICES_DIR):
        seen.add(r.get("ticker"))
    seen.discard(None)
    return sorted(seen)


# --------------------------------------------------------------------------- #
# manifest / health
# --------------------------------------------------------------------------- #

def distinct_dates(records: list[dict]) -> list[str]:
    return sorted({r["date"] for r in records if "date" in r})


def update_manifest() -> dict:
    feats = _load_all(FEATURES_DIR)
    prices = _load_all(PRICES_DIR)
    fdates = distinct_dates(feats)
    pdates = distinct_dates(prices)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "updated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "features": {
            "rows": len(feats),
            "dates": len(fdates),
            "first_date": fdates[0] if fdates else None,
            "last_date": fdates[-1] if fdates else None,
            "distinct_tickers": len({r.get("ticker") for r in feats}),
        },
        "prices": {
            "rows": len(prices),
            "dates": len(pdates),
            "first_date": pdates[0] if pdates else None,
            "last_date": pdates[-1] if pdates else None,
            "distinct_tickers": len({r.get("ticker") for r in prices}),
        },
    }
    os.makedirs(HISTORY_DIR, exist_ok=True)
    with open(MANIFEST_PATH, "w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest
