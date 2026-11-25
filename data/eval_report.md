# Signal Evaluation — what actually works

_Generated: 2026-11-25T00:06:34.600247+00:00 · mode: from-store · horizon: 63d_

> 18147 feature snapshots across 93 dates → 9313 labeled examples at 63d horizon (pos rate 0.3133, 1220 tickers).

> ⚠️ Positive in-sample IC is easy to find by luck. Trust a signal only when the mean IC is **consistent across independent forward windows** (|t-stat| ≥ 2, which requires n_eff ≥ 2) AND the walk-forward out-of-sample numbers below hold up. While the archive is shorter than a couple of horizons, every t-stat reads `—` by design: a large |IC| with n_eff < 1 is a single overlapping observation, not a finding. Everything here is research, not advice.

## Per-signal edge (63d forward return)

IC = cross-sectional Spearman corr of signal vs forward return, averaged over dates. A consistent mean IC ≥ ~0.03 with |t-stat| ≥ 2 is a genuinely useful signal.

`n_eff` is the number of INDEPENDENT (non-overlapping) forward windows behind the IC series: dates / (horizon / sampling interval). Daily snapshots against a 63-day horizon overlap 63x, so 53 dates carry n_eff = 0.84 — less than one independent observation. Below n_eff = 2 no t-stat is computed (shown as `—`), because there are no degrees of freedom to test with; `IC ratio` is mean/std of the IC series, a descriptive ratio and *not* evidence of significance.

| Signal | mean IC | IC t-stat | IC ratio | n_eff | neut IC | dates | decile spread | top-quintile hit | turnover |
|--------|--------:|----------:|---------:|------:|--------:|------:|--------------:|-----------------:|---------:|
| pt_upside | -0.3430 | — | -4.617 | 0.48 | -0.4214 | 30 | 9.4% | 0.1260 | 0.6150 |
| annualized_vol | -0.2656 | — | -0.773 | 0.84 | -0.2427 | 53 | 0.7% | 0.1700 | 0.3910 |
| analyst_count | 0.2526 | — | 3.034 | 0.48 | 0.2450 | 30 | 5.4% | 0.3510 | 0.4520 |
| STD_20 | -0.2250 | — | -0.953 | 0.84 | -0.2268 | 53 | -4.3% | 0.2450 | 0.4010 |
| STD_10 | -0.2107 | — | -0.952 | 0.84 | -0.1982 | 53 | 9.5% | 0.2680 | 0.4330 |
| st_msg_count | -0.2076 | — | -1.887 | 0.63 | -0.1879 | 40 | 0.8% | 0.2190 | 0.3530 |
| STD_60 | -0.1986 | — | -0.69 | 0.84 | -0.1997 | 53 | -6.9% | 0.2250 | 0.3530 |
| STD_5 | -0.1791 | — | -0.843 | 0.84 | -0.1592 | 53 | 10.3% | 0.2810 | 0.5210 |
| MIN_20 | 0.1779 | — | 0.876 | 0.84 | 0.1937 | 53 | 4.3% | 0.3830 | 0.3300 |
| KLEN | -0.1765 | — | -0.76 | 0.84 | -0.1444 | 53 | 14.9% | 0.2770 | 0.7200 |
| MIN_10 | 0.1730 | — | 0.906 | 0.84 | 0.1548 | 53 | -1.7% | 0.3670 | 0.3880 |
| pct_off_52w_high | 0.1687 | — | 0.676 | 0.84 | 0.2356 | 53 | -16.2% | 0.3130 | 0.4330 |
| MIN_60 | 0.1479 | — | 0.977 | 0.84 | 0.1572 | 53 | 0.8% | 0.3940 | 0.2660 |
| CORR_60 | -0.1384 | — | -1.692 | 0.84 | -0.1249 | 53 | -9.8% | 0.2460 | 0.3900 |
| MIN_5 | 0.1379 | — | 0.645 | 0.84 | 0.1105 | 53 | -6.2% | 0.3540 | 0.4890 |
| MAX_60 | -0.1173 | — | -0.472 | 0.84 | -0.2082 | 53 | 0.4% | 0.2280 | 0.3490 |
| ret_63d | 0.1145 | — | 0.556 | 0.84 | 0.1735 | 53 | 7.8% | 0.3320 | 0.4570 |
| CORR_20 | -0.1102 | — | -1.027 | 0.84 | -0.0943 | 53 | -5.7% | 0.2640 | 0.4470 |
| KUP | -0.1095 | — | -0.666 | 0.84 | -0.0805 | 53 | 11.6% | 0.2800 | 0.7360 |
| eps_rev_vs_price | -0.1022 | — | -1.297 | 0.48 | -0.1131 | 30 | -8.9% | 0.0920 | 0.5480 |
| SUMP_10 | -0.1021 | — | -0.78 | 0.84 | -0.0855 | 53 | -5.7% | 0.2560 | 0.5180 |
| CNTP_60 | 0.0956 | — | 0.407 | 0.84 | 0.1149 | 53 | -0.9% | 0.3630 | 0.3810 |
| rsi_14 | -0.0953 | — | -0.686 | 0.63 | -0.0646 | 40 | -2.0% | 0.2420 | 0.5560 |
| ROC_60 | -0.0947 | — | -0.479 | 0.84 | -0.1658 | 53 | -6.2% | 0.2070 | 0.3480 |
| ROC_10 | 0.0944 | — | 0.655 | 0.84 | 0.0494 | 53 | 9.8% | 0.2990 | 0.4130 |
| CNTP_10 | -0.0881 | — | -0.892 | 0.84 | -0.0703 | 53 | -4.9% | 0.2520 | 0.4790 |
| MA_10 | 0.0849 | — | 0.51 | 0.84 | 0.0433 | 53 | -2.5% | 0.3040 | 0.4060 |
| SUMP_5 | -0.0845 | — | -0.521 | 0.84 | -0.0665 | 53 | 6.6% | 0.2730 | 0.5970 |
| ret_5d | -0.0838 | — | -0.431 | 0.84 | -0.0440 | 53 | 0.9% | 0.2420 | 0.6170 |
| ROC_5 | 0.0838 | — | 0.431 | 0.84 | 0.0450 | 53 | -0.9% | 0.3160 | 0.4640 |
| SUMP_20 | -0.0815 | — | -0.706 | 0.84 | -0.0638 | 53 | -5.6% | 0.2810 | 0.4660 |
| CNTP_5 | -0.0800 | — | -0.622 | 0.84 | -0.0599 | 53 | 5.0% | 0.2520 | 0.5670 |
| RSV_10 | -0.0742 | — | -0.532 | 0.84 | -0.0488 | 53 | -4.4% | 0.2640 | 0.6920 |
| RSV_20 | -0.0732 | — | -0.507 | 0.84 | -0.0521 | 53 | -3.4% | 0.2700 | 0.6110 |
| MA_20 | 0.0730 | — | 0.465 | 0.84 | 0.0199 | 53 | -4.2% | 0.2860 | 0.3720 |
| CORR_10 | -0.0703 | — | -0.706 | 0.84 | -0.0583 | 53 | -0.9% | 0.3000 | 0.5150 |
| KLOW | -0.0677 | — | -0.44 | 0.84 | -0.0618 | 53 | 13.9% | 0.2970 | 0.7740 |
| MA_5 | 0.0676 | — | 0.309 | 0.84 | 0.0414 | 53 | -12.3% | 0.2950 | 0.5000 |
| news_sentiment | 0.0658 | — | 1.038 | 0.6 | 0.0637 | 38 | -3.0% | 0.3220 | 0.6130 |
| CORR_5 | -0.0655 | — | -0.511 | 0.84 | -0.0597 | 53 | 1.5% | 0.2780 | 0.6320 |
| SUMP_60 | 0.0644 | — | 0.347 | 0.84 | 0.1088 | 53 | 0.0% | 0.3230 | 0.4150 |
| MAX_20 | -0.0590 | — | -0.348 | 0.84 | -0.1796 | 53 | 7.6% | 0.2450 | 0.3890 |
| RSV_5 | -0.0575 | — | -0.333 | 0.84 | -0.0352 | 53 | -4.2% | 0.2620 | 0.7450 |
| news_count | -0.0526 | — | -0.655 | 0.6 | -0.0440 | 38 | 0.1% | 0.2760 | 0.5110 |
| ROC_20 | 0.0526 | — | 0.449 | 0.84 | -0.0289 | 53 | 2.2% | 0.2720 | 0.3950 |
| KMID | -0.0517 | — | -0.309 | 0.84 | -0.0271 | 53 | 13.7% | 0.2730 | 0.8520 |
| CNTP_20 | -0.0499 | — | -0.417 | 0.84 | -0.0279 | 53 | -3.5% | 0.2800 | 0.4360 |
| ret_21d | -0.0497 | — | -0.446 | 0.84 | — | 53 | 2.7% | 0.2480 | 0.4400 |
| KMID2 | -0.0496 | — | -0.326 | 0.84 | -0.0343 | 53 | -3.8% | 0.2860 | 0.8670 |
| MAX_10 | -0.0490 | — | -0.274 | 0.84 | -0.1159 | 53 | 4.0% | 0.2810 | 0.4100 |
| composite_score | 0.0465 | — | 0.534 | 0.63 | — | 40 | -8.3% | 0.2780 | 0.5520 |
| MAX_5 | -0.0462 | — | -0.233 | 0.84 | -0.0886 | 53 | 6.8% | 0.2820 | 0.4800 |
| pct_above_52w_low | -0.0437 | — | -0.226 | 0.84 | -0.0142 | 53 | -3.2% | 0.3370 | 0.3970 |
| st_sentiment | -0.0432 | — | -0.431 | 0.63 | -0.0422 | 40 | 4.4% | 0.3100 | 0.6510 |
| volume_spike_ratio | 0.0378 | — | 0.398 | 0.84 | 0.0538 | 53 | 2.9% | 0.3150 | 0.4790 |
| st_trending | -0.0362 | — | -0.436 | 0.63 | 0.0052 | 40 | 1.1% | 0.3130 | 0.5320 |
| KSFT | -0.0292 | — | -0.173 | 0.84 | -0.0122 | 53 | 22.1% | 0.2800 | 0.8570 |
| eps_rev_breadth | 0.0249 | — | 0.18 | 0.48 | 0.0327 | 30 | 2.6% | 0.1970 | 0.6490 |
| VMA_5 | 0.0191 | — | 0.177 | 0.84 | 0.0155 | 53 | 0.8% | 0.3250 | 0.6390 |
| RSV_60 | -0.0182 | — | -0.108 | 0.84 | 0.0218 | 53 | -2.9% | 0.3100 | 0.4990 |
| short_vol_ratio | -0.0123 | — | -0.164 | 0.84 | -0.0114 | 53 | 2.3% | 0.3390 | 0.6220 |
| eps_rev_30d | 0.0119 | — | 0.115 | 0.48 | 0.0044 | 30 | -27.0% | 0.2010 | 0.5820 |
| VMA_60 | -0.0107 | — | -0.098 | 0.84 | -0.0228 | 53 | 1.1% | 0.3260 | 0.5590 |
| MA_60 | 0.0098 | — | 0.058 | 0.84 | -0.0892 | 53 | 3.1% | 0.2690 | 0.3530 |
| eps_rev_90d | 0.0089 | — | 0.071 | 0.48 | 0.0244 | 30 | -24.9% | 0.1470 | 0.5960 |
| VMA_10 | 0.0071 | — | 0.061 | 0.84 | -0.0010 | 53 | -5.3% | 0.3160 | 0.5950 |
| VMA_20 | -0.0071 | — | -0.065 | 0.84 | -0.0165 | 53 | -3.9% | 0.3310 | 0.5760 |
| wiki_spike_ratio | 0.0031 | — | 0.045 | 0.84 | -0.0029 | 53 | -0.2% | 0.3050 | 0.6150 |
| wiki_views_7d | 0.0006 | — | 0.008 | 0.84 | 0.0246 | 53 | -10.6% | 0.3110 | 0.3250 |
| reddit_mentions | — | — | — | — | — | 0 | -9.6% | 0.2290 | 0.4000 |
| reddit_sentiment | — | — | — | — | — | 0 | -9.6% | 0.2290 | 0.4000 |

## IC decay across horizons

How each signal's predictive power changes with holding period — a real signal usually decays smoothly; a leak or fluke jumps around.

| Signal | 21d IC | 63d IC | 126d IC |
|--------|-------:|-------:|-------:|
| ret_21d | -0.0222 | -0.0497 | 0.4581 |
| ROC_20 | 0.0279 | 0.0526 | -0.4411 |
| SUMP_20 | -0.0365 | -0.0815 | 0.4054 |
| pt_upside | -0.1425 | -0.3430 | — |
| MAX_20 | -0.0429 | -0.0590 | -0.3385 |
| MA_20 | 0.0261 | 0.0730 | -0.3213 |
| RSV_20 | -0.0226 | -0.0732 | 0.2990 |
| MAX_60 | -0.0391 | -0.1173 | -0.2916 |
| ROC_10 | 0.0245 | 0.0944 | -0.2887 |
| CORR_20 | -0.0078 | -0.1102 | -0.2814 |
| rsi_14 | -0.0124 | -0.0953 | 0.2810 |
| CNTP_10 | 0.0089 | -0.0881 | 0.2704 |

## Walk-forward model (out-of-sample)

A model that learns the weights, evaluated strictly on future data it never trained on:

```
backend: sklearn-HGB
n_folds_used: 4
dead_features_max: 16
purged_rows: 34041
embargo_days: 2
n_oos: 852
oos_auc: 0.4334
oos_ic: -0.2388
oos_top_quintile_hit_rate: 0.182
oos_decile_spread: -0.0381
feature_keys: ['ret_5d', 'ret_21d', 'ret_63d', 'volume_spike_ratio', 'rsi_14', 'pct_off_52w_high', 'pct_above_52w_low', 'annualized_vol', 'news_count', 'news_sentiment', 'reddit_mentions', 'reddit_sentiment', 'sec_form4_recent', 'sec_8k_recent', 'st_trending', 'st_msg_count', 'st_sentiment', 'wiki_views_7d', 'wiki_spike_ratio', 'short_vol_ratio', 'eps_rev_30d', 'eps_rev_90d', 'eps_rev_breadth', 'eps_rev_vs_price', 'analyst_count', 'pt_upside', 'KMID', 'KLEN', 'KMID2', 'KUP', 'KLOW', 'KSFT', 'ROC_5', 'ROC_10', 'ROC_20', 'ROC_60', 'MA_5', 'MA_10', 'MA_20', 'MA_60', 'STD_5', 'STD_10', 'STD_20', 'STD_60', 'MAX_5', 'MAX_10', 'MAX_20', 'MAX_60', 'MIN_5', 'MIN_10', 'MIN_20', 'MIN_60', 'RSV_5', 'RSV_10', 'RSV_20', 'RSV_60', 'CORR_5', 'CORR_10', 'CORR_20', 'CORR_60', 'CNTP_5', 'CNTP_10', 'CNTP_20', 'CNTP_60', 'SUMP_5', 'SUMP_10', 'SUMP_20', 'SUMP_60', 'VMA_5', 'VMA_10', 'VMA_20', 'VMA_60']
```
