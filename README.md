# pit-archive

A point-in-time (PIT) data collection and evaluation framework.

Many interesting signals are **observation-time only**: they describe the state
of the world right now, and the provider keeps no history you can query later.
Fetch them tomorrow and you get tomorrow's answer, not today's. If you want to
know whether such a signal predicts anything, you have to start recording it
before you know the answer — and record it in a way you can trust months later.

This repository is the machinery for doing that properly.

## What it does

Every run captures a snapshot of many observed variables across a set of
entities, appends it to an append-only archive, and — once enough history and
outcomes have accumulated — measures whether any of those variables actually
predicted the outcome.

```
collect  ->  archive (point-in-time)  ->  label  ->  evaluate  ->  model
```

## Design guarantees

The storage layer is the part that must not be sloppy, because a point-in-time
archive cannot be re-created after the fact:

- **Idempotent** — every write upserts on `(date, entity)`, so a re-run
  converges to one row instead of double-counting and biasing every statistic.
- **Atomic** — partitions are written to a temp file and renamed, so a crash
  never leaves a half-written partition.
- **Partitioned & versioned** — monthly files, and every row carries a schema
  version so a later change cannot silently corrupt older rows.
- **Self-describing** — a manifest records coverage; a quality gate checks each
  variable family for liveness and for collapse against its trailing average,
  which is how a source that starts returning empty results gets caught.

See [`docs/DATA.md`](docs/DATA.md) for the full schema and guarantees.

## Evaluation

Naive evaluation of time-series data is misleading in well-documented ways, so
the analysis layer is built around avoiding them:

Signal families are grouped by where they sit in the causal chain: most are
coincident (price, attention), while estimate revisions are the one family
expected to *lead*, which is why they are measured separately.

- **Cross-sectional rank correlation per date**, averaged with a t-statistic —
  not one pooled correlation, which mixes broad market-wide movement into the
  measurement.
- **Purged, embargoed walk-forward** validation: training rows whose outcome
  window overlaps the test period are dropped (López de Prado, *Advances in
  Financial Machine Learning*, ch. 7), removing a subtle leak that inflates
  results.
- **Neutralized scores** — each variable is also measured after removing its
  linear dependence on a baseline, so a repackaged version of something you
  already have is not mistaken for new information.
- **Calibration** — probabilities are fitted out-of-sample and reported with a
  predicted-vs-actual table, because ranking well and being well-calibrated are
  different things and only the second supports sizing decisions.

## Layout

| Path | Purpose |
|---|---|
| `pipeline/` | collection, storage, evaluation and modeling code |
| `pipeline/sources/` | one module per upstream provider |
| `data/history/` | the append-only point-in-time archive |
| `data/warehouse/` | Parquet compaction, queryable with DuckDB |
| `data/dataset/` | compiled, labeled tables for modeling |
| `docs/` | design notes, methodology, operations |
| `tests/` | unit tests plus a full-pipeline rehearsal against a simulated network |

## Usage

```bash
pip install -r requirements.txt

python -m pipeline.status                 # archive health and coverage
python -m pipeline.main                   # collect one snapshot
python -m pipeline.warehouse compact      # JSONL -> Parquet
python -m pipeline.evaluate --from-store  # what actually predicts anything
python -m pipeline.predict                # calibrated model output
python -m pipeline.backfill --since YYYY-MM-DD   # recover recoverable gaps
```

Ad-hoc queries over the compacted archive:

```bash
python -m pipeline.warehouse sql "SELECT date, COUNT(*) FROM features GROUP BY date"
```

## Tests

```bash
python -m tests.selftest          # math verified against known answers
python -m tests.dress_rehearsal   # whole pipeline against a simulated network
```

The rehearsal exercises the real entry point end-to-end with every network call
stubbed, which catches integration faults that unit tests miss.

## Notes

- All upstream sources are public and require no credentials.
- Collection runs on a schedule via `.github/workflows/`, committing each
  snapshot back to the archive.
- Outputs under `data/` are generated — do not edit them by hand. The archive
  in `data/history/` is the only thing that cannot be regenerated.
