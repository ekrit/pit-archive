# stocks-predictor

An automated, multi-source **momentum & attention screener** for US equities.
Every day it discovers a candidate universe of tickers, gathers free public
signals about each one, blends them into a single composite score, and commits
a ranked list to this repo.

> ⚠️ **This is not financial advice and not a prediction.** It's a research
> tool that surfaces stocks showing *unusual momentum and attention right now*.
> The scores are hand-tuned heuristics with **no validated backtest** behind
> them. Markets are largely efficient — no scraper can reliably predict which
> stock will "5x." Treat the output as a starting point for your own research,
> not a buy list, and never risk money you can't afford to lose. See
> [`RESEARCH.md`](RESEARCH.md) for why reliable prediction is so hard.

## What it does

For each candidate ticker it collects, from **free / no-API-key** sources:

| Source | Signal | Provider |
|--------|--------|----------|
| Price & volume | 5/21/63-day momentum, volume-spike ratio, RSI, distance from 52-wk high/low, volatility | Yahoo Finance (via `yfinance`) |
| SEC filings | recent Form 4 (insider activity) and 8-K (material events) counts | SEC EDGAR JSON API |
| News | headline buzz volume + VADER sentiment | Google News RSS |
| Reddit | mention counts + VADER sentiment across r/wallstreetbets, r/stocks, r/investing | Reddit public JSON |

Each signal is percentile-ranked across the universe, then combined with the
weights in [`scraper/config.py`](scraper/config.py) into a 0–100 composite
score. Results are written to:

- `data/rankings/<YYYY-MM-DD>.json` — full detail, every ticker, every feature.
- `RANKINGS.md` — human-readable top-25 table with a disclaimer header.
- `data/history/features/` and `data/history/prices/` — the durable,
  point-in-time archives that accumulate over months. **These are the important
  ones.** Storage is idempotent (no double-counting on re-runs), month-partitioned,
  schema-versioned, and the price archive stays dense for every ticker ever seen
  so labels survive universe churn. Full schema & guarantees in
  [`DATA.md`](DATA.md).

## Measuring what actually works (the point of the whole thing)

A ranked list is worthless if the signals don't predict anything. The
evaluation layer answers "which of these scrapers actually has edge?" honestly:

- **New attention/positioning sources** (all free, no key):
  [Stocktwits public API](https://api.stocktwits.com/api/2/trending/symbols.json)
  (trending flag + message sentiment),
  [Wikimedia pageviews](https://wikimedia.org/api/rest_v1/) (attention-spike
  ratio — an academically documented investor-attention proxy), and
  [FINRA Reg SHO daily short volume](https://www.finra.org/rules-guidance/notices/information-notice-051019)
  (whole-market short-pressure ratio from one file per day).
- **`scraper/parallel.py`** threads every per-ticker source through a shared
  token-bucket rate limiter with retries — ~8-10x faster collection at the same
  politeness per host.
- **Purged + embargoed walk-forward** (`scraper/model.py`): training rows whose
  forward-return window overlaps the test period are dropped (López de Prado,
  *Advances in Financial ML* ch.7) — removing the subtle leak that inflates
  naive financial backtests.
- **Market-neutral labels**: the dataset stores `rel_ret` (return minus
  same-date universe median) alongside raw `fwd_ret`, so models learn to pick
  *which names beat their peers* rather than "the market went up."
- **`scraper/factors.py`** computes a 46-factor battery (candle geometry +
  rolling momentum/volatility/volume families) inspired by
  [Microsoft Qlib's Alpha158](https://github.com/microsoft/qlib) — the
  open-source baseline feature set for cross-sectional stock ranking. Every
  factor is stored point-in-time and automatically evaluated.
- **`scraper/store.py`** is the point-in-time data store: idempotent,
  month-partitioned, schema-versioned, with a dense price archive so labels
  survive universe churn (see [`DATA.md`](DATA.md)). News/Reddit/SEC signals
  can't be reconstructed historically — recording them now is the only way to
  ever evaluate them.
- **`scraper/warehouse.py`** compacts the JSONL archives into a zstd Parquet
  warehouse queryable with DuckDB SQL (`python -m scraper.warehouse sql
  "SELECT ..."`) — the scale path to multi-GB/TB collection, mapped out in
  [`SCALING.md`](SCALING.md).
- **`scraper/universe.py::full_market()`** pulls the full US listing (~10k
  tickers) from SEC's free `company_tickers.json`; with `FULL_MARKET_ARCHIVE=1`
  the daily job archives closes for the *whole market*, not just the hot list.
- **`scraper/dataset.py`** compiles the raw archives into a clean, deduplicated,
  training-ready table (`data/dataset/labeled_<H>d.jsonl`) plus a data-quality
  report, computing labels from the dense price archive.
- **`scraper/labels.py`** turns snapshots into `(features → realized forward
  return)` examples, and can reconstruct price features from raw history for an
  immediate price-only backtest.
- **`scraper/metrics.py` + `scraper/backtest.py`** compute each signal's
  Information Coefficient (cross-sectional Spearman corr vs forward return,
  averaged per-date with a t-stat), decile spread, hit rate, plus
  [Alphalens](https://alphalens.ml4trading.io/)-style top-quantile **turnover**
  and an **IC-decay table** across horizons (`--horizons 21,63,126`).
- **`scraper/model.py`** trains a walk-forward model (pure-numpy logistic
  regression, or gradient boosting if scikit-learn is installed) that *learns*
  the weights and is scored strictly out-of-sample.

Run it:

```bash
# Immediate price-signal backtest (works today, price signals only):
python -m scraper.evaluate --from-prices --horizon 63 --limit 60

# Evaluate accumulated multi-source history (grows meaningful over months):
python -m scraper.evaluate --from-store --horizon 63
```

Both write [`EVALUATION.md`](EVALUATION.md) with a ranked signal table and the
out-of-sample model result. **Read [`STRATEGY.md`](STRATEGY.md) for the full
month-by-month playbook** — it's the honest answer to "how do I predict stock
growth in a few months."

The math is unit-tested against synthetic data with known answers:

```bash
python -m tests.selftest
```

## How the candidate universe is built

`scraper/universe.py` combines:
1. Yahoo's predefined screeners (`day_gainers`, `most_actives`,
   `small_cap_gainers`, `undervalued_growth_stocks`, `growth_technology_stocks`),
   so small/micro-caps outside the S&P 500 can surface.
2. Your static watchlist in [`data/watchlist.txt`](data/watchlist.txt) — add
   your own high-conviction names there, one ticker per line.

The universe is capped (`MAX_TICKERS_TO_SCORE`, default 120) to bound runtime
and stay polite to the free data providers.

## Running locally

```bash
pip install -r requirements.txt

# Full run
python -m scraper.main

# Fast smoke test (cap universe, skip slower/blockable sources)
python -m scraper.main --limit 15 --no-reddit --no-sec
```

Flags: `--limit N`, `--no-reddit`, `--no-sec`, `--no-news`.

Set a descriptive SEC contact (SEC's fair-access policy requests one):

```bash
export SEC_USER_AGENT="my-project contact:you@example.com"
```

## Scheduled runs

[`.github/workflows/scan.yml`](.github/workflows/scan.yml) runs the screener
every weekday at 06:30 UTC (and on-demand via the Actions tab), then commits
the fresh rankings back to `main`. No secrets are required — all sources are
public.

## Limitations & honest caveats

- **Not a predictor.** High composite score ≠ "will go up." It means "showing
  unusual momentum + attention," which is often *already priced in*.
- **Weights are unvalidated.** They're reasonable-looking guesses, not the
  result of a rigorous, leakage-free backtest. Tune them against your own
  evaluation before trusting them.
- **Free sources are flaky.** Anonymous Reddit JSON and Yahoo endpoints get
  rate-limited or blocked from datacenter IPs; the pipeline degrades
  gracefully (missing signals count as neutral) rather than crashing.
- **Momentum chasing is risky.** The names this surfaces are, by construction,
  volatile and crowded — exactly the ones where you can lose money fastest.

## Extending it

- Add a paid/gated source (Reddit official API via PRAW, NewsAPI, Alpha
  Vantage, Twitter/X) as a new module under `scraper/sources/` returning
  `{ticker: {feature: value}}`, then wire it into `scraper/main.py` and add a
  weight in `config.py`.
- **The single biggest improvement** would be a proper walk-forward backtest
  to learn the signal weights instead of hand-setting them — see `RESEARCH.md`.
