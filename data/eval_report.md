# Signal Evaluation — what actually works

_Generated: 2026-11-26T17:27:30.870289+00:00 · mode: from-store · horizon: 63d_

> 18674 feature snapshots across 95 dates → 9527 labeled examples at 63d horizon (pos rate 0.3135, 1237 tickers).

> ⚠️ Positive in-sample IC is easy to find by luck. Trust a signal only when the mean IC is **consistent across independent forward windows** (|t-stat| ≥ 2, which requires n_eff ≥ 2) AND the walk-forward out-of-sample numbers below hold up. While the archive is shorter than a couple of horizons, every t-stat reads `—` by design: a large |IC| with n_eff < 1 is a single overlapping observation, not a finding. Everything here is research, not advice.

## Per-signal edge (63d forward return)

IC = cross-sectional Spearman corr of signal vs forward return, averaged over dates. A consistent mean IC ≥ ~0.03 with |t-stat| ≥ 2 is a genuinely useful signal.

`n_eff` is the number of INDEPENDENT (non-overlapping) forward windows behind the IC series: dates / (horizon / sampling interval). Daily snapshots against a 63-day horizon overlap 63x, so 53 dates carry n_eff = 0.84 — less than one independent observation. Below n_eff = 2 no t-stat is computed (shown as `—`), because there are no degrees of freedom to test with; `IC ratio` is mean/std of the IC series, a descriptive ratio and *not* evidence of significance.

| Signal | mean IC | IC t-stat | IC ratio | n_eff | neut IC | dates | decile spread | top-quintile hit | turnover |
|--------|--------:|----------:|---------:|------:|--------:|------:|--------------:|-----------------:|---------:|
| pt_upside | -0.3366 | — | -4.19 | 0.49 | -0.4254 | 31 | 8.9% | 0.1250 | 0.6150 |
| annualized_vol | -0.2739 | — | -0.794 | 0.86 | -0.2495 | 54 | -0.5% | 0.1680 | 0.3930 |
| analyst_count | 0.2489 | — | 2.999 | 0.49 | 0.2414 | 31 | 5.6% | 0.3460 | 0.4490 |
| STD_20 | -0.2281 | — | -0.97 | 0.86 | -0.2301 | 54 | -4.8% | 0.2430 | 0.4050 |
| STD_10 | -0.2148 | — | -0.973 | 0.86 | -0.2015 | 54 | 8.7% | 0.2670 | 0.4350 |
| st_msg_count | -0.2110 | — | -1.912 | 0.65 | -0.1887 | 41 | -0.2% | 0.2200 | 0.3530 |
| STD_60 | -0.2027 | — | -0.707 | 0.86 | -0.2056 | 54 | -7.1% | 0.2240 | 0.3560 |
| MIN_20 | 0.1848 | — | 0.895 | 0.86 | 0.1974 | 54 | 5.0% | 0.3910 | 0.3310 |
| STD_5 | -0.1803 | — | -0.857 | 0.86 | -0.1605 | 54 | 9.6% | 0.2820 | 0.5240 |
| KLEN | -0.1799 | — | -0.778 | 0.86 | -0.1452 | 54 | 14.0% | 0.2750 | 0.7230 |
| MIN_10 | 0.1787 | — | 0.926 | 0.86 | 0.1572 | 54 | -0.9% | 0.3700 | 0.3890 |
| pct_off_52w_high | 0.1690 | — | 0.684 | 0.86 | 0.2396 | 54 | -15.7% | 0.3110 | 0.4330 |
| MIN_60 | 0.1550 | — | 0.982 | 0.86 | 0.1605 | 54 | 1.9% | 0.4010 | 0.2670 |
| CORR_60 | -0.1407 | — | -1.706 | 0.86 | -0.1237 | 54 | -9.9% | 0.2480 | 0.3930 |
| MIN_5 | 0.1393 | — | 0.656 | 0.86 | 0.1085 | 54 | -5.9% | 0.3560 | 0.4860 |
| MAX_60 | -0.1157 | — | -0.469 | 0.86 | -0.2141 | 54 | 0.4% | 0.2290 | 0.3520 |
| ret_63d | 0.1150 | — | 0.564 | 0.86 | 0.1773 | 54 | 7.9% | 0.3300 | 0.4570 |
| CORR_20 | -0.1127 | — | -1.047 | 0.86 | -0.0937 | 54 | -6.2% | 0.2610 | 0.4480 |
| KUP | -0.1115 | — | -0.681 | 0.86 | -0.0799 | 54 | 11.0% | 0.2790 | 0.7380 |
| SUMP_10 | -0.1097 | — | -0.789 | 0.86 | -0.0897 | 54 | -6.7% | 0.2540 | 0.5160 |
| eps_rev_vs_price | -0.1064 | — | -1.34 | 0.49 | -0.1210 | 31 | -8.9% | 0.0910 | 0.5500 |
| rsi_14 | -0.1029 | — | -0.711 | 0.65 | -0.0655 | 41 | -2.9% | 0.2420 | 0.5540 |
| ROC_10 | 0.1020 | — | 0.675 | 0.86 | 0.0536 | 54 | 10.6% | 0.3050 | 0.4150 |
| CNTP_60 | 0.0943 | — | 0.405 | 0.86 | 0.1154 | 54 | 5.2% | 0.3600 | 0.3820 |
| CNTP_10 | -0.0938 | — | -0.9 | 0.86 | -0.0724 | 54 | -13.6% | 0.2460 | 0.4770 |
| ROC_60 | -0.0928 | — | -0.472 | 0.86 | -0.1689 | 54 | -6.0% | 0.2050 | 0.3510 |
| SUMP_20 | -0.0895 | — | -0.709 | 0.86 | -0.0667 | 54 | -5.9% | 0.2770 | 0.4670 |
| MA_10 | 0.0882 | — | 0.527 | 0.86 | 0.0408 | 54 | -2.2% | 0.3080 | 0.4080 |
| SUMP_5 | -0.0841 | — | -0.517 | 0.86 | -0.0624 | 54 | 6.8% | 0.2740 | 0.5960 |
| ret_5d | -0.0829 | — | -0.426 | 0.86 | -0.0379 | 54 | 1.2% | 0.2410 | 0.6180 |
| ROC_5 | 0.0829 | — | 0.426 | 0.86 | 0.0389 | 54 | -1.2% | 0.3120 | 0.4640 |
| RSV_20 | -0.0797 | — | -0.533 | 0.86 | -0.0547 | 54 | -4.1% | 0.2670 | 0.6090 |
| MA_20 | 0.0790 | — | 0.491 | 0.86 | 0.0188 | 54 | -3.7% | 0.2890 | 0.3740 |
| CNTP_5 | -0.0789 | — | -0.606 | 0.86 | -0.0559 | 54 | 5.7% | 0.2520 | 0.5650 |
| RSV_10 | -0.0788 | — | -0.557 | 0.86 | -0.0499 | 54 | -4.8% | 0.2640 | 0.6900 |
| CORR_10 | -0.0694 | — | -0.69 | 0.86 | -0.0560 | 54 | -1.1% | 0.3010 | 0.5170 |
| KLOW | -0.0687 | — | -0.45 | 0.86 | -0.0632 | 54 | 13.5% | 0.2950 | 0.7760 |
| MA_5 | 0.0673 | — | 0.309 | 0.86 | 0.0364 | 54 | -12.1% | 0.2950 | 0.4990 |
| CORR_5 | -0.0660 | — | -0.519 | 0.86 | -0.0581 | 54 | 1.3% | 0.2820 | 0.6320 |
| news_sentiment | 0.0644 | — | 1.009 | 0.62 | 0.0625 | 39 | -2.8% | 0.3260 | 0.6130 |
| SUMP_60 | 0.0606 | — | 0.326 | 0.86 | 0.1086 | 54 | -0.4% | 0.3210 | 0.4150 |
| ROC_20 | 0.0599 | — | 0.478 | 0.86 | -0.0293 | 54 | 2.4% | 0.2770 | 0.3970 |
| RSV_5 | -0.0580 | — | -0.337 | 0.86 | -0.0327 | 54 | -4.2% | 0.2620 | 0.7440 |
| ret_21d | -0.0575 | — | -0.477 | 0.86 | — | 54 | 2.2% | 0.2450 | 0.4420 |
| news_count | -0.0564 | — | -0.685 | 0.62 | -0.0469 | 39 | -0.3% | 0.2770 | 0.5110 |
| MAX_20 | -0.0556 | — | -0.327 | 0.86 | -0.1832 | 54 | 7.4% | 0.2460 | 0.3930 |
| CNTP_20 | -0.0554 | — | -0.445 | 0.86 | -0.0294 | 54 | -4.8% | 0.2730 | 0.4340 |
| pct_above_52w_low | -0.0516 | — | -0.259 | 0.86 | -0.0155 | 54 | -4.4% | 0.3340 | 0.3990 |
| KMID | -0.0498 | — | -0.299 | 0.86 | -0.0233 | 54 | 13.4% | 0.2720 | 0.8530 |
| MAX_5 | -0.0476 | — | -0.24 | 0.86 | -0.0944 | 54 | 6.4% | 0.2810 | 0.4800 |
| KMID2 | -0.0475 | — | -0.311 | 0.86 | -0.0309 | 54 | -3.6% | 0.2870 | 0.8690 |
| MAX_10 | -0.0473 | — | -0.266 | 0.86 | -0.1188 | 54 | 3.9% | 0.2820 | 0.4130 |
| composite_score | 0.0440 | — | 0.503 | 0.65 | — | 41 | -8.5% | 0.2760 | 0.5510 |
| volume_spike_ratio | 0.0435 | — | 0.426 | 0.86 | 0.0584 | 54 | 3.2% | 0.3190 | 0.4830 |
| st_sentiment | -0.0434 | — | -0.441 | 0.65 | -0.0413 | 41 | 4.3% | 0.3100 | 0.6510 |
| st_trending | -0.0355 | — | -0.428 | 0.65 | -0.0020 | 41 | 2.6% | 0.2980 | 0.5260 |
| KSFT | -0.0266 | — | -0.158 | 0.86 | -0.0085 | 54 | 21.8% | 0.2770 | 0.8570 |
| RSV_60 | -0.0245 | — | -0.143 | 0.86 | 0.0201 | 54 | -3.3% | 0.3070 | 0.4980 |
| VMA_5 | 0.0190 | — | 0.177 | 0.86 | 0.0151 | 54 | 1.0% | 0.3300 | 0.6410 |
| eps_rev_breadth | 0.0180 | — | 0.127 | 0.49 | 0.0305 | 31 | 2.6% | 0.2060 | 0.6490 |
| MA_60 | 0.0156 | — | 0.09 | 0.86 | -0.0924 | 54 | 3.3% | 0.2710 | 0.3570 |
| VMA_60 | -0.0150 | — | -0.135 | 0.86 | -0.0264 | 54 | 1.2% | 0.3290 | 0.5580 |
| short_vol_ratio | -0.0127 | — | -0.171 | 0.86 | -0.0114 | 54 | 2.4% | 0.3430 | 0.6220 |
| VMA_20 | -0.0099 | — | -0.09 | 0.86 | -0.0178 | 54 | -3.6% | 0.3290 | 0.5760 |
| eps_rev_30d | 0.0094 | — | 0.092 | 0.49 | -0.0006 | 31 | -26.3% | 0.2080 | 0.5800 |
| VMA_10 | 0.0045 | — | 0.039 | 0.86 | -0.0029 | 54 | -5.1% | 0.3180 | 0.5960 |
| wiki_spike_ratio | 0.0018 | — | 0.026 | 0.86 | -0.0016 | 54 | -0.4% | 0.3030 | 0.6180 |
| wiki_views_7d | -0.0007 | — | -0.009 | 0.86 | 0.0269 | 54 | -5.0% | 0.3100 | 0.3280 |
| eps_rev_90d | 0.0001 | — | 0.001 | 0.49 | 0.0188 | 31 | -24.5% | 0.1460 | 0.5920 |
| reddit_mentions | — | — | — | — | — | 0 | -9.5% | 0.2500 | 0.3960 |
| reddit_sentiment | — | — | — | — | — | 0 | -9.5% | 0.2500 | 0.3960 |

## IC decay across horizons

How each signal's predictive power changes with holding period — a real signal usually decays smoothly; a leak or fluke jumps around.

| Signal | 21d IC | 63d IC | 126d IC |
|--------|-------:|-------:|-------:|
| ret_21d | -0.0165 | -0.0575 | 0.4516 |
| ROC_20 | 0.0233 | 0.0599 | -0.4383 |
| SUMP_20 | -0.0330 | -0.0895 | 0.4037 |
| MAX_20 | -0.0465 | -0.0556 | -0.3533 |
| pt_upside | -0.1500 | -0.3366 | — |
| MA_20 | 0.0252 | 0.0790 | -0.3353 |
| RSV_20 | -0.0230 | -0.0797 | 0.3141 |
| ROC_10 | 0.0217 | 0.1020 | -0.3043 |
| MAX_60 | -0.0454 | -0.1157 | -0.3021 |
| rsi_14 | -0.0131 | -0.1029 | 0.2771 |
| SUMP_10 | -0.0172 | -0.1097 | 0.2767 |
| CNTP_10 | 0.0089 | -0.0938 | 0.2761 |

## Walk-forward model (out-of-sample)

A model that learns the weights, evaluated strictly on future data it never trained on:

```
backend: sklearn-HGB
n_folds_used: 4
dead_features_max: 16
purged_rows: 33868
embargo_days: 2
n_oos: 1064
oos_auc: 0.4097
oos_ic: -0.2702
oos_top_quintile_hit_rate: 0.178
oos_decile_spread: -0.0762
feature_keys: ['ret_5d', 'ret_21d', 'ret_63d', 'volume_spike_ratio', 'rsi_14', 'pct_off_52w_high', 'pct_above_52w_low', 'annualized_vol', 'news_count', 'news_sentiment', 'reddit_mentions', 'reddit_sentiment', 'sec_form4_recent', 'sec_8k_recent', 'st_trending', 'st_msg_count', 'st_sentiment', 'wiki_views_7d', 'wiki_spike_ratio', 'short_vol_ratio', 'eps_rev_30d', 'eps_rev_90d', 'eps_rev_breadth', 'eps_rev_vs_price', 'analyst_count', 'pt_upside', 'KMID', 'KLEN', 'KMID2', 'KUP', 'KLOW', 'KSFT', 'ROC_5', 'ROC_10', 'ROC_20', 'ROC_60', 'MA_5', 'MA_10', 'MA_20', 'MA_60', 'STD_5', 'STD_10', 'STD_20', 'STD_60', 'MAX_5', 'MAX_10', 'MAX_20', 'MAX_60', 'MIN_5', 'MIN_10', 'MIN_20', 'MIN_60', 'RSV_5', 'RSV_10', 'RSV_20', 'RSV_60', 'CORR_5', 'CORR_10', 'CORR_20', 'CORR_60', 'CNTP_5', 'CNTP_10', 'CNTP_20', 'CNTP_60', 'SUMP_5', 'SUMP_10', 'SUMP_20', 'SUMP_60', 'VMA_5', 'VMA_10', 'VMA_20', 'VMA_60']
```
