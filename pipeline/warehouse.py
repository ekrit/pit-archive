"""Columnar warehouse: compact JSONL archives into Parquet, query with DuckDB.

This is the scale path (lakehouse pattern — the same bronze/silver layering
used by production data platforms):

  bronze  data/history/*.jsonl   git-friendly, idempotent daily ingest (small)
  silver  data/warehouse/*.parquet  compressed columnar, engine-queryable
  gold    data/dataset/labeled_*.jsonl  training-ready labeled table

JSONL stays the write format because it merges and diffs in git from ephemeral
CI runners. Parquet is ~10-40x smaller and column-scannable, which is what
makes a multi-GB→TB archive tractable: DuckDB scans parquet globs without
loading them into memory, and the identical files can later be pushed to
object storage (S3/R2/B2) and queried in place when they outgrow git.

Usage:
    python -m pipeline.warehouse compact          # rebuild parquet from JSONL
    python -m pipeline.warehouse sql "SELECT ..." # ad-hoc DuckDB query
    python -m pipeline.warehouse stats            # size/coverage summary

Tables (hive-style month partitions):
    data/warehouse/features/month=YYYY-MM/part.parquet   flat: one column per feature
    data/warehouse/prices/month=YYYY-MM/part.parquet     date, ticker, close
"""
from __future__ import annotations

import glob
import json
import os
import sys

from . import store

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WAREHOUSE_DIR = os.path.join(ROOT, "data", "warehouse")
FEATURES_WH = os.path.join(WAREHOUSE_DIR, "features")
PRICES_WH = os.path.join(WAREHOUSE_DIR, "prices")


def _require_engines():
    try:
        import duckdb  # noqa: F401
        import pyarrow  # noqa: F401
    except ImportError as e:  # pragma: no cover - env dependent
        raise SystemExit(
            f"warehouse needs pyarrow+duckdb ({e}); pip install pyarrow duckdb"
        )


def _flatten_feature_record(r: dict) -> dict:
    """Flatten nested feature dict into scalar columns for columnar storage."""
    flat = {
        "date": r.get("date"),
        "ticker": r.get("ticker"),
        "score": r.get("score"),
        "last_price": r.get("last_price"),
        "schema_version": r.get("schema_version", 1),
    }
    for k, v in (r.get("features") or {}).items():
        if k == "last_price":
            continue
        flat[f"f_{k}"] = v if isinstance(v, (int, float)) else None
    return flat


def _write_partitioned(records: list[dict], base_dir: str) -> int:
    import pyarrow as pa
    import pyarrow.parquet as pq

    by_month: dict[str, list[dict]] = {}
    for r in records:
        d = r.get("date") or ""
        if len(d) >= 7:
            by_month.setdefault(d[:7], []).append(r)

    written = 0
    for month, recs in sorted(by_month.items()):
        # Union of keys across the month so schema covers every feature column.
        cols: list[str] = []
        for r in recs:
            for k in r:
                if k not in cols:
                    cols.append(k)
        arrays = {k: [r.get(k) for r in recs] for k in cols}
        table = pa.table(arrays)
        part_dir = os.path.join(base_dir, f"month={month}")
        os.makedirs(part_dir, exist_ok=True)
        pq.write_table(table, os.path.join(part_dir, "part.parquet"),
                       compression="zstd")
        written += len(recs)
    return written


def compact() -> dict:
    """Rebuild the parquet warehouse from the JSONL archives (idempotent)."""
    _require_engines()
    feats = [_flatten_feature_record(r) for r in store.load_features()]
    prices = [
        {"date": r["date"], "ticker": r["ticker"], "close": r["close"]}
        for r in store.load_prices()
    ]
    n_f = _write_partitioned(feats, FEATURES_WH) if feats else 0
    n_p = _write_partitioned(prices, PRICES_WH) if prices else 0
    summary = {"feature_rows": n_f, "price_rows": n_p, **stats(print_out=False)}
    with open(os.path.join(WAREHOUSE_DIR, "compact_summary.json"), "w") as fh:
        json.dump(summary, fh, indent=2)
    return summary


def connect():
    """DuckDB connection with `features` and `prices` views over the parquet."""
    _require_engines()
    import duckdb

    con = duckdb.connect()
    for name, base in (("features", FEATURES_WH), ("prices", PRICES_WH)):
        pattern = os.path.join(base, "month=*", "*.parquet")
        if glob.glob(pattern):
            con.execute(
                f"CREATE VIEW {name} AS SELECT * FROM read_parquet('{pattern}', "
                f"union_by_name=true)"
            )
    return con


def sql(query: str):
    con = connect()
    return con.execute(query).fetchall()


def stats(print_out: bool = True) -> dict:
    def _dir_bytes(d):
        return sum(
            os.path.getsize(p)
            for p in glob.glob(os.path.join(d, "**", "*"), recursive=True)
            if os.path.isfile(p)
        )

    jsonl_bytes = _dir_bytes(store.HISTORY_DIR)
    parquet_bytes = _dir_bytes(WAREHOUSE_DIR)
    out = {
        "jsonl_bytes": jsonl_bytes,
        "parquet_bytes": parquet_bytes,
        "compression_ratio": round(jsonl_bytes / parquet_bytes, 1)
        if parquet_bytes else None,
    }
    if print_out:
        print(json.dumps(out, indent=2))
    return out


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("compact", "sql", "stats"):
        print(__doc__)
        raise SystemExit(1)
    cmd = sys.argv[1]
    if cmd == "compact":
        s = compact()
        print(f"[warehouse] compacted {s['feature_rows']} feature rows, "
              f"{s['price_rows']} price rows "
              f"(compression {s.get('compression_ratio')}x)")
    elif cmd == "stats":
        stats()
    else:
        for row in sql(" ".join(sys.argv[2:])):
            print(row)


if __name__ == "__main__":
    main()
