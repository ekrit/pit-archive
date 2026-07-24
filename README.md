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
