# Prediction-algorithm plan: the model ladder

The dataset (66 features/ticker/day, dense price labels, `rel_ret` targets)
feeds this ladder. Climb it **in order** — each rung must beat the one below it
out-of-sample or you stop and keep the simpler model. Complexity you can't
justify with OOS evidence is negative value: it overfits, it hides bugs, and
it makes failure diagnosis impossible.

## Rung 0 — baselines (already running)

Composite heuristic score + per-signal IC tables. Purpose: a floor, and a
sanity check that the data plumbing works. Any learned model that can't beat
the naive composite score's IC is telling you something important.

## Rung 1 — regularized linear (already implemented: `model.py`)

Standardized L2 logistic regression on all features, purged/embargoed
walk-forward, target = top-quintile `rel_ret`. Linear models answer the key
early question — *is there any combinable signal at all?* — with minimal
variance. Expected timeline: meaningful after ~40 collection dates.

**Gate to rung 2:** OOS IC ≥ 0.02 sustained across folds, else collect more
data / better features rather than adding model capacity.

## Rung 2 — gradient-boosted trees (auto-enabled when sklearn present)

HistGradientBoosting (or LightGBM) captures interactions and nonlinearity
(e.g. "volume spike matters only when short_vol_ratio is high"). Trees are
the industry workhorse for tabular cross-sectional ranking — use max_depth
3-4, heavy regularization, early stopping on a time-ordered validation slice.

Additions at this rung:
- **Feature neutralization**: residualize each candidate signal against
  momentum + volatility before the IC table, so "new" signals must show
  *incremental* IC, not repackaged momentum.
- **Feature pruning**: drop features whose neutralized |IC t-stat| < 1 across
  3+ months; fewer, cleaner features beat kitchen sinks at this data size.

**Gate to rung 3:** trees beat linear OOS by a margin that survives costs
(decile spread net of ~0.2%/side), across ≥ 2 market regimes.

## Rung 3 — ensemble + calibrated ranking

Blend rungs 1-2 with rank-averaging (robust to scale drift), calibrate
probabilities (isotonic on OOS folds), and produce a **daily top-K list with
confidence bands**. Position sizing derives from calibrated probability ×
inverse volatility, never from raw scores.

## Rung 4 — only if the data earns it

Sequence models (temporal transformer over the daily feature history) and
cross-sectional attention (rank a day's universe jointly). Requires: ≥ 1 year
of snapshots, rung 2/3 edge already proven, and a GPU budget. FinRL-style RL
execution is a *strategy* layer on top, not a predictor — consider it last.

## Targets: what "predict the next big riser" becomes, concretely

| Target | Definition | Why |
|---|---|---|
| Primary | P(rel_ret in top quintile) at 63d | Peer-relative, dense labels, well-calibrated |
| Secondary | P(fwd_ret > +30%) at 126d | Closest honest proxy for "big riser" — rare-event, needs the full-market archive |
| Diagnostic | 21d rel_ret regression | Fast feedback on feature drift |

The "next 10 big rises" question maps to the secondary target: a ranked
shortlist by P(large move), refreshed daily, with calibration curves showing
how often the model's "20%" actually happens. It will be a probabilistic
shortlist, not a prophecy — that's what the math can honestly deliver, and a
well-calibrated shortlist is genuinely valuable.

## Evaluation contract (all rungs)

- Purged + embargoed walk-forward only; no shuffled splits, ever.
- Report: OOS IC, decile spread net of costs, top-quintile hit rate,
  calibration error, turnover. All in `EVALUATION.md`, tracked over time.
- A model is promoted only on OOS evidence from data it never touched.
