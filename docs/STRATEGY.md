# Strategy: how to actually get to "predicting stock growth" in a few months

This is the honest playbook. It won't hand you a money printer — nobody can,
and anyone who says otherwise is selling something. What it *will* do is give
you a rigorous process that, over the next few months, tells you whether any of
these signals have real predictive edge, learns how to combine the ones that
do, and proves it out-of-sample before a cent is at risk.

## The core problem, stated plainly

Markets are close to efficient. The obvious signals (a stock is up, it's in the
news, Reddit likes it) are already priced in by the time you see them. So the
game is **not** "find the signal that predicts a 5x" — that signal, if it
existed publicly, would stop working the moment enough people used it. The game
is to find a **small, consistent statistical edge**, combine several weak
edges, size positions for uncertainty, and let the law of large numbers work
over hundreds of bets. A signal with an Information Coefficient (IC) of just
0.03–0.05 that holds up out-of-sample is genuinely valuable. If you find one
claiming 0.30, you have a bug (look-ahead leakage) 99% of the time.

## Why you can't just backtest your way there today

For the **price/volume signals**, you *can* backtest immediately — price
history is available, so `evaluate.py --from-prices` reconstructs point-in-time
features from 2 years of history and measures their edge right now.

For the **news / Reddit / SEC signals**, you cannot. There is no reliable
historical archive of "what r/wallstreetbets sentiment for TSLA was on some
past Tuesday" that you can query. The only way to evaluate them honestly is to
**start recording them now**, point-in-time, and wait. That is exactly what the
daily job does: every run appends today's features for every ticker to
`data/history/features.jsonl`. In a few months that file *is* your dataset.

This is the single most important idea here: **the value compounds with time
because you're accumulating data nobody can reconstruct after the fact.**

## The month-by-month plan

### Month 0 (now)
1. Let the daily GitHub Action run. It logs a point-in-time snapshot every
   weekday and updates `data/daily_output.md`. Do nothing else yet.
2. Run the immediate price-signal backtest to get a first read:
   ```bash
   python -m pipeline.evaluate --from-prices --horizon 63 --limit 60
   ```
   Read `data/eval_report.md`. Note which price signals show a consistent, positive
   mean IC with |t-stat| ≥ 2. Those are your starting candidates.
3. **Paper-trade only.** Track the top-N list on paper (or a broker's paper
   account). Do not risk real money on month-0 hunches.

### Months 1–3 (accumulate + measure)
4. Each week, run `python -m pipeline.evaluate --from-store --horizon 63` and
   watch the per-signal IC table in `data/eval_report.md` stabilize as the sample
   grows. A signal that looked great on 3 dates and fades by 30 dates was
   noise — this is the process working.
5. Keep the signals with consistent IC; demote or drop the ones that don't
   clear |t-stat| ≥ 2. Re-tune `SCORE_WEIGHTS` in `pipeline/config.py` to lean
   on what's working (or let the model do it, next step).

### Months 3–6 (learn + validate)
6. Once you have ~40+ labeled dates, the walk-forward model
   (`pipeline/model.py`, run automatically by `evaluate.py`) trains on the past
   and predicts the strictly-future next block. Trust the **out-of-sample**
   AUC / IC / decile-spread numbers, never the in-sample ones.
7. Decision gate — go/no-go for real money, all must hold:
   - Composite or model **out-of-sample IC ≥ 0.03**, stable across folds.
   - Out-of-sample **top-minus-bottom decile spread** is positive and survives
     realistic costs (subtract ~0.1–0.3% round-trip per rebalance).
   - The edge persists across at least a couple of distinct market regimes
     (a calm stretch and a volatile one), not just one lucky quarter.
8. If it passes: start **small**, position-size by conviction and volatility,
   diversify across many names (the edge is statistical, not per-stock), and
   keep paper-trading the next iteration in parallel. If it fails: you've saved
   yourself real money and learned which ideas don't work — that's a win.

## The tactics that actually matter (ranked)

1. **No look-ahead leakage.** Every feature must use only information available
   at decision time. This is where ~all fake backtests die. The store and
   `features_asof()` are built to enforce it.
2. **Walk-forward, never shuffle.** Time-series data shuffled into a random
   train/test split leaks the future into the past. We only ever train on the
   past and test on the future.
3. **Cross-sectional IC, date by date.** Judge a signal by whether it ranks
   *that day's* names correctly, averaged over many days — not by one big
   pooled correlation (which mixes market-wide moves into the signal).
4. **Combine weak, decorrelated signals.** One signal won't do it. Price
   momentum + a filing catalyst + a sentiment shift that *disagree* with each
   other's noise but *agree* on a name is the edge.
5. **Cost realism.** Always subtract transaction costs and slippage. Many
   "profitable" strategies are just paying the spread to themselves.
6. **Regime awareness.** A signal that only works in a bull market isn't a
   signal, it's beta. Demand persistence across regimes.
7. **Position sizing & risk.** Even a real edge loses money if oversized. Bet
   small per name, cap exposure, and never bet money you can't lose.

## What "best" honestly looks like here

The best realistic outcome is **not** "the script told me which stock 5x'd." It
is: "after 4–6 months of leakage-free data, I have 2–3 signals with a small but
statistically real out-of-sample edge, a model that combines them, a track
record that survived costs and a couple of regimes, and the discipline to size
bets accordingly." That is what professional quant desks actually have. Anything
flashier than that, in a public tool built on free data, is a red flag.

See `RESEARCH.md` for the academic backdrop and `README.md` for how to run each
piece.
