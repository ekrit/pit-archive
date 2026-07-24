# Data layout & storage guarantees

The whole plan — collect for months, then train — lives or dies on data quality.
This documents how the store works and the guarantees it gives you, so the
dataset you train on in a few months is trustworthy.

## Directory layout

```
data/
├── rankings/                 # daily human/JSON output (one file per day)
│   └── YYYY-MM-DD.json
├── history/                  # the durable, point-in-time archives
│   ├── features/             # signal snapshots, partitioned by month
│   │   └── YYYY-MM.jsonl
│   ├── prices/               # DENSE daily closes, partitioned by month
│   │   └── YYYY-MM.jsonl
│   └── manifest.json         # coverage/health summary (auto-updated)
└── dataset/                  # compiled, training-ready output
    ├── labeled_<H>d.jsonl    # (features -> realized forward return) rows
    └── quality_<H>d.json     # missingness / label-balance report
```

## Record schemas

**features/YYYY-MM.jsonl** — one row per (date, ticker):
```json
{"schema_version":2,"date":"2026-07-24","ticker":"NVDA","score":91.2,
 "last_price":123.45,"components":{...},"features":{"ret_63d":0.4,...}}
```

**prices/YYYY-MM.jsonl** — one row per (date, ticker):
```json
{"schema_version":2,"date":"2026-07-24","ticker":"NVDA","close":123.45}
```

## Guarantees (why this is "proper")

1. **Idempotent.** Every write upserts on `(date, ticker)`. Running the job
   twice on the same day (e.g. a manual run plus the scheduled one) converges
   to a single row — it never double-counts, which would bias every Information
   Coefficient you later compute.
2. **Atomic writes.** Partitions are written to a `.tmp` file and `os.replace`d
   into place, so a crash mid-write never leaves a corrupt partition.
3. **Partitioned by month.** Loads stay fast and git diffs stay readable as the
   archive grows across many months.
4. **Schema-versioned.** Every row carries `schema_version`. If features change
   later, old rows remain identifiable and safe to migrate rather than being
   silently misread.
5. **Label durability through churn.** The `prices/` archive is kept dense for
   *every ticker ever tracked*, not just today's hot list. This matters because
   a stock frequently drops off the momentum screen right around its big move —
   without its forward prices you'd have no label for exactly the cases you care
   about most. `store.tracked_tickers()` is the union of all names ever seen, and
   the daily job re-archives their closes (capped by
   `MAX_PRICE_ARCHIVE_TICKERS`).
6. **Self-describing.** `manifest.json` and `quality_<H>d.json` let you see, at a
   glance, how many dates/tickers you have, the label positive rate, and the
   per-feature missingness — so you know when the dataset is mature enough to
   trust.

## Building the training dataset

```bash
# Compile features + dense prices into labeled examples at a 63-day horizon,
# writing data/dataset/labeled_63d.jsonl and a quality report:
python -m scraper.evaluate --from-store --horizon 63
```

`scraper/dataset.compile_labeled()` computes each label from the **price
archive** (falling back to the snapshot's `last_price` only if the archive has a
gap), so labels are robust to universe churn. See `STRATEGY.md` for how to use
the accumulating dataset month by month, and `README.md` for the evaluation
tooling.
