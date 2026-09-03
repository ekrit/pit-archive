# Signal Evaluation — what actually works

_Generated: 2026-09-03T14:51:02.616153+00:00 · mode: from-store · horizon: 63d_

> 5462 feature snapshots across 35 dates → 0 labeled examples at 63d horizon (pos rate None, 0 tickers).

> ⚠️ Positive in-sample IC is easy to find by luck. Trust a signal only when the mean IC is **consistent across many dates** (|t-stat| ≥ 2) AND the walk-forward out-of-sample numbers below hold up. Everything here is research, not advice.

## Per-signal edge (63d forward return)

IC = cross-sectional Spearman corr of signal vs forward return, averaged over dates. A consistent mean IC ≥ ~0.03 with |t-stat| ≥ 2 is a genuinely useful signal.

| Signal | mean IC | IC t-stat | neut IC | dates | decile spread | top-quintile hit | turnover |
|--------|--------:|----------:|--------:|------:|--------------:|-----------------:|---------:|

## Walk-forward model (out-of-sample)

A model that learns the weights, evaluated strictly on future data it never trained on:

```
error: no examples
```
