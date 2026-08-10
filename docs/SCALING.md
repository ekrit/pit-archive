# Scaling plan: from MBs in git to TBs in object storage

Goal: over the next year, accumulate as much point-in-time data as the
algorithms need — up to TBs if necessary — while keeping every byte queryable.
This document is the honest map of how data volume grows and what to change at
each threshold. The architecture (JSONL ingest → Parquet warehouse → DuckDB
query) is already built to make each step a config change, not a rewrite.

## What actually weighs something (realistic math)

| Data | Volume | A year of it |
|---|---|---|
| Daily closes, full US market (~10k tickers) | ~250k rows/day | **~25–50 MB** in Parquet |
| 46 Alpha factors + attention signals, screened universe | ~120 rows/day × ~70 cols | **~10 MB** |
| Full-market factor snapshots (~10k × 70 cols) | ~10k rows/day | **~1–2 GB** |
| News headlines + sentiment, full market | ~50–200k rows/day | **~5–20 GB** |
| **Minute bars**, full market | ~3.9M rows/day | **~150–300 GB** |
| Options chains / order-book snapshots | huge | **TBs** |

Two lessons from that table:

1. **The TB regime comes from minute bars, raw text, and options** — not from
   daily data. Don't collect them until a daily-resolution edge exists;
   storage costs money and none of the big-data sources matter if the
   daily-resolution signals show nothing (see `STRATEGY.md` go/no-go gates).
2. **Everything through "news, full market" fits in git + Parquet unchanged.**
   That covers the entire first year of the plan by default.

## The three storage tiers (already implemented)

```
bronze  data/history/*.jsonl      idempotent daily ingest, git-diffable
silver  data/warehouse/*.parquet  zstd columnar, DuckDB-queryable, ~10-40x smaller
gold    data/dataset/labeled_*.jsonl  training-ready labeled table
```

`python -m pipeline.warehouse compact` rebuilds silver from bronze at any time —
bronze is the source of truth, silver is disposable/rebuildable, which is what
makes the whole thing safe to evolve.

## Thresholds and what to do at each

**< 1 GB (now → ~6 months):** nothing. Git holds bronze+silver; CI commits daily.

**1–5 GB (git getting slow):** stop committing `data/warehouse/` to git and
upload it to object storage instead (Cloudflare R2 / Backblaze B2 / S3 — R2 has
zero egress fees and a free 10 GB tier). One workflow step:
`rclone sync data/warehouse r2:bucket/warehouse`. DuckDB queries parquet on S3
APIs natively (`read_parquet('s3://bucket/warehouse/prices/month=*/part.parquet')`),
so `pipeline/warehouse.py` needs only the glob string changed — the SQL and all
analysis code stay identical.

**> 5 GB (minute bars / full-market news):** move bronze off git too — write
JSONL to object storage, keep only `manifest.json` + rankings in git. Partition
parquet by `month/ticker-prefix` so DuckDB prunes partitions. Still no
database server needed: DuckDB comfortably scans hundreds of GB of partitioned
parquet from a laptop or a CI runner.

**TB territory (options/order-book):** same layout, bigger bucket. Add a
compaction job that merges small daily files into monthly files (small-file
overhead is the real killer at this scale, not raw bytes). If query latency
matters, put a $5/mo VPS with DuckDB next to the bucket. You do NOT need
Spark/Snowflake/a data team for single-digit TBs of parquet — DuckDB over
object storage is exactly the workload it was built for.

## Cost reality check

- 100 GB on R2/B2: **~$0.50–1.50/month**. 1 TB: **~$5–15/month**.
- GitHub Actions stays free (public repo) but has a 6-hour job limit — full-market
  minute-bar collection would need a $5 VPS cron instead. Daily-resolution
  collection fits in Actions indefinitely.

## Provenance of the design

- Ingest/warehouse split and factor battery: [Microsoft Qlib](https://github.com/microsoft/qlib)
  ([data layer docs](https://qlib.readthedocs.io/en/stable/component/data.html)) —
  Qlib converts raw data to a compact binary column store for exactly this reason.
- Evaluation metrics (IC decay, quantile turnover): [Alphalens](https://alphalens.ml4trading.io/)
  ([API](https://alphalens.ml4trading.io/api-reference.html)).
- Multi-source provider aggregation pattern: [OpenBB](https://github.com/OpenBB-finance/OpenBB).
- RL-based strategy layer to consider much later: [FinRL](https://github.com/AI4Finance-Foundation/FinRL).
