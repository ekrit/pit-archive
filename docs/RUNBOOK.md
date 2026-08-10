# Execution runbook: how these scripts run, and what to do when they don't

## Where things run

| What | Where | When |
|---|---|---|
| Daily collection (`pipeline.main`) | GitHub Actions (`scan.yml`) | 06:30 UTC weekdays + manual `workflow_dispatch` |
| Self-tests + dress rehearsal | Same job, before collection | Every run |
| Preflight endpoint probe | Same job | Every run — logs which sources are up |
| Warehouse compaction | Same job, after collection | Every run |
| Evaluation (`pipeline.evaluate`) | Same job | Every run (meaningful after ~40 dates) |

Everything commits back to `main`; git history doubles as the run ledger.

## Daily (automatic — you do nothing)

The Actions job: self-test → rehearse → preflight → collect → compact →
evaluate → commit. If the job is green, the day's data is in. A red job means
code, not data — sources degrade to neutral values rather than failing.

## Weekly (5 minutes, manual)

1. Open the latest Actions log → check the preflight table. A source DOWN for
   a week needs a fix or replacement; a source UP but yielding zeros (see
   `data/dataset/quality_*.json` missingness) has a silent parsing break —
   the worse failure mode. Missingness spiking on one feature = investigate.
2. Glance at `data/history/manifest.json`: `dates` should grow by ~5/week and
   `last_date` should be this week. If not, the commit step is failing.
3. Skim `data/eval_report.md`. Early months: expect noise; you're checking the
   tables render and the example count grows, not hunting signals yet.

## Monthly (30 minutes)

1. Run the go/no-go review against `STRATEGY.md` gates.
2. Prune: any feature with 3 months of neutralized |t| < 1 gets dropped from
   the model feature list (keep collecting it — cheap, and regimes change).
3. Check repo size (`git count-objects -vH`). Past ~1 GB, execute the
   `SCALING.md` object-storage migration (~30 min, one-time).

## Failure modes and responses

| Symptom | Likely cause | Response |
|---|---|---|
| Yahoo endpoints 401/999 | Yahoo tightened anonymous access (happens periodically) | yfinance usually ships a workaround within days: bump the pin, re-run. Meanwhile screener universe falls back to watchlist + tracked names |
| Reddit 403/429 | Anonymous JSON blocked | Accept neutral zeros short-term; the durable fix is free Reddit API credentials via PRAW |

### Known unavailable on shared CI runners

`sec_filings` and `reddit` are listed in `EXPECTED_UNAVAILABLE`
(`pipeline/quality_gate.py`), so the gate reports them as **EXPECTED-DOWN**
instead of DEAD. They are still collected every run, and the gate prints a
loud "is ALIVE again" line the moment either starts returning data.

Why they are down, and what would actually fix them:

- **sec_filings** — SEC throttles by IP (`Request Rate Threshold Exceeded`),
  and GitHub runners share outbound IPs with other tenants who have already
  spent the budget. Our own pacing (2 req/s) and patient backoff are not
  enough because the IP is throttled before we start. Real fixes: run
  collection from a non-shared IP (a $5/mo VPS cron runs the identical
  scripts), or wait for a window where one map fetch succeeds — the CIK map
  is committed once obtained, which immunizes all later runs.
- **reddit** — anonymous JSON access is refused by design. Only free Reddit
  API credentials (PRAW) fix this; no server-side workaround exists.

Remove a family from `EXPECTED_UNAVAILABLE` as soon as it works, so a later
regression is caught rather than silently tolerated.
| Stocktwits 429 | Anonymous rate limit | Lower `STOCKTWITS_RATE_PER_SEC` to 0.5; it recovers |
| SEC 403 "Request Rate Threshold Exceeded" | SEC caps ~10 req/s **per IP**, and CI runners share outbound IPs with other tenants, so part of the budget is already spent before the run starts. Confirmed live: this is throttling, not a UA rejection or an IP ban | Handled automatically — requests are paced at `SEC_RATE_PER_SEC` (2/s) and a throttle is waited out (`SEC_THROTTLE_BACKOFF_SECONDS`). Once one fetch succeeds the CIK map is committed and reused, so later runs do not need it. If it persists for days, lower `SEC_RATE_PER_SEC` or run collection from a non-shared IP |
| SEC 403 with a different message | Genuine block or UA policy | Set the `SEC_USER_AGENT` secret to `<project> <your-email>` |
| Actions job hits 6h limit | Universe too large for runner | Lower `MAX_PRICE_ARCHIVE_TICKERS`, or move collection to a $5/mo VPS cron (same scripts, unchanged) |
| **Every run fails in ~3s with no steps and no runner** (scheduled *and* manual) | Not a code fault — GitHub is refusing to start jobs. On a **private** repo this is almost always the monthly Actions minutes allowance being exhausted (or a spending-limit/billing issue). Observed 2026-07-27: run #9 succeeded, every run after failed instantly | Three fixes, cheapest first: **(1) make the repo public** — public repos get unlimited free Actions minutes and this problem disappears permanently; **(2)** wait for the monthly quota reset, with the weekly-sweep optimization below cutting burn ~5x; **(3)** move collection to a $5/mo VPS cron, which also fixes SEC throttling. Check Settings → Billing → Actions to confirm |

### Keeping CI minutes low

The full-market price sweep (~7k tickers) takes 25-35 min; without it a run is
~5 min. Because **prices are backfillable from Yahoo at any time and attention
data is not**, the sweep is gated to one weekday (`FULL_MARKET_WEEKDAY`,
default Monday) while the daily run always captures the unbackfillable
signals. A cold/empty archive sweeps immediately regardless of weekday.
| Commit conflicts | Concurrent manual + scheduled runs | Safe: writes are idempotent upserts; re-run the job |
| "No space" in Actions | Warehouse grew past runner disk | `SCALING.md` migration time |

## Manual operations

```bash
# Trigger a collection immediately (instead of waiting for the schedule):
#   GitHub → Actions → daily-screener → Run workflow

# Local run against real internet (from any machine):
pip install -r requirements.txt
python -m pipeline.preflight             # what's reachable from here?
python -m pipeline.main --limit 20       # small live run
python -m pipeline.main                  # full run

# Rebuild analytics from accumulated data (no network needed):
python -m pipeline.warehouse compact
python -m pipeline.warehouse sql "SELECT date, COUNT(*) FROM features GROUP BY date ORDER BY date"
python -m pipeline.evaluate --from-store --horizon 63 --horizons 21,63,126

# Verify everything still works after any edit:
python -m tests.selftest && python -m tests.dress_rehearsal
```

## The one rule

**Never edit collected history by hand.** `data/history/` is append-only
truth; every derived artifact (warehouse, dataset, evaluation) rebuilds from
it. If something looks wrong downstream, fix the compiler and rebuild — the
bronze layer is the only thing you cannot regenerate.
