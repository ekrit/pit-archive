"""Point-in-time feature store (append-only JSONL).

This is the single most important piece for the "predict in a few months"
goal. Every daily run appends one record per ticker capturing the features
*as they were known that day*. Over weeks and months this accumulates into a
leakage-free labeled dataset you can backtest and train on — something you
cannot reconstruct after the fact for news/social/filing signals, because
those are not stored historically anywhere you can query.

JSONL (one JSON object per line) is used rather than parquet so the history
is diffable in git and needs no binary dependency.
"""
from __future__ import annotations

import datetime as dt
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HISTORY_DIR = os.path.join(ROOT, "data", "history")
FEATURES_PATH = os.path.join(HISTORY_DIR, "features.jsonl")


def append_snapshot(results: list[dict], date: str | None = None, path: str = FEATURES_PATH) -> int:
    """Append one record per ranked result. Returns number of rows written."""
    date = date or dt.date.today().isoformat()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    written = 0
    with open(path, "a") as fh:
        for r in results:
            rec = {
                "date": date,
                "ticker": r["ticker"],
                "score": r.get("score"),
                "last_price": (r.get("features") or {}).get("last_price"),
                "components": r.get("components", {}),
                "features": r.get("features", {}),
            }
            fh.write(json.dumps(rec, separators=(",", ":")) + "\n")
            written += 1
    return written


def load_history(path: str = FEATURES_PATH) -> list[dict]:
    """Load all snapshot records. Returns [] if the store doesn't exist yet."""
    if not os.path.exists(path):
        return []
    out: list[dict] = []
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


def distinct_dates(records: list[dict]) -> list[str]:
    return sorted({r["date"] for r in records if "date" in r})
