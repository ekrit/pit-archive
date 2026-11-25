# Signal Evaluation — what actually works

_Generated: 2026-11-25T00:36:36.689378+00:00 · mode: from-store · horizon: 63d_

> 18365 feature snapshots across 94 dates → 9313 labeled examples at 63d horizon (pos rate 0.313, 1220 tickers).

> ⚠️ Positive in-sample IC is easy to find by luck. Trust a signal only when the mean IC is **consistent across independent forward windows** (|t-stat| ≥ 2, which requires n_eff ≥ 2) AND the walk-forward out-of-sample numbers below hold up. While the archive is shorter than a couple of horizons, every t-stat reads `—` by design: a large |IC| with n_eff < 1 is a single overlapping observation, not a finding. Everything here is research, not advice.

## Per-signal edge (63d forward return)

IC = cross-sectional Spearman corr of signal vs forward return, averaged over dates. A consistent mean IC ≥ ~0.03 with |t-stat| ≥ 2 is a genuinely useful signal.

`n_eff` is the number of INDEPENDENT (non-overlapping) forward windows behind the IC series: dates / (horizon / sampling interval). Daily snapshots against a 63-day horizon overlap 63x, so 53 dates carry n_eff = 0.84 — less than one independent observation. Below n_eff = 2 no t-stat is computed (shown as `—`), because there are no degrees of freedom to test with; `IC ratio` is mean/std of the IC series, a descriptive ratio and *not* evidence of significance.

| Signal | mean IC | IC t-stat | IC ratio | n_eff | neut IC | dates | decile spread | top-quintile hit | turnover |
|--------|--------:|----------:|---------:|------:|--------:|------:|--------------:|-----------------:|---------:|
| pt_upside | -0.3434 | — | -4.671 | 0.48 | -0.4219 | 30 | 9.3% | 0.1260 | 0.6150 |
| annualized_vol | -0.2661 | — | -0.774 | 0.84 | -0.2433 | 53 | 0.6% | 0.1690 | 0.3910 |
| analyst_count | 0.2533 | — | 3.047 | 0.48 | 0.2457 | 30 | 5.5% | 0.3460 | 0.4520 |
| STD_20 | -0.2259 | — | -0.955 | 0.84 | -0.2276 | 53 | -4.3% | 0.2440 | 0.4010 |
| STD_10 | -0.2113 | — | -0.954 | 0.84 | -0.1988 | 53 | 9.4% | 0.2680 | 0.4330 |
| st_msg_count | -0.2083 | — | -1.888 | 0.63 | -0.1885 | 40 | 0.8% | 0.2170 | 0.3530 |
| STD_60 | -0.1993 | — | -0.691 | 0.84 | -0.2004 | 53 | -7.0% | 0.2250 | 0.3530 |
| STD_5 | -0.1796 | — | -0.845 | 0.84 | -0.1597 | 53 | 10.2% | 0.2810 | 0.5210 |
| MIN_20 | 0.1781 | — | 0.876 | 0.84 | 0.1943 | 53 | 4.3% | 0.3830 | 0.3300 |
| KLEN | -0.1771 | — | -0.762 | 0.84 | -0.1451 | 53 | 14.8% | 0.2760 | 0.7200 |
| MIN_10 | 0.1732 | — | 0.906 | 0.84 | 0.1553 | 53 | -1.7% | 0.3670 | 0.3880 |
| pct_off_52w_high | 0.1688 | — | 0.677 | 0.84 | 0.2359 | 53 | -16.2% | 0.3120 | 0.4330 |
| MIN_60 | 0.1481 | — | 0.977 | 0.84 | 0.1577 | 53 | 0.9% | 0.3930 | 0.2660 |
| CORR_60 | -0.1384 | — | -1.689 | 0.84 | -0.1248 | 53 | -9.8% | 0.2460 | 0.3900 |
| MIN_5 | 0.1380 | — | 0.646 | 0.84 | 0.1109 | 53 | -6.2% | 0.3540 | 0.4890 |
| MAX_60 | -0.1175 | — | -0.472 | 0.84 | -0.2088 | 53 | 0.3% | 0.2280 | 0.3490 |
| ret_63d | 0.1143 | — | 0.555 | 0.84 | 0.1731 | 53 | 7.8% | 0.3300 | 0.4570 |
| CORR_20 | -0.1103 | — | -1.027 | 0.84 | -0.0944 | 53 | -5.7% | 0.2610 | 0.4470 |
| KUP | -0.1099 | — | -0.667 | 0.84 | -0.0808 | 53 | 11.6% | 0.2800 | 0.7360 |
| SUMP_10 | -0.1024 | — | -0.78 | 0.84 | -0.0857 | 53 | -5.8% | 0.2560 | 0.5180 |
| eps_rev_vs_price | -0.1018 | — | -1.297 | 0.48 | -0.1127 | 30 | -8.9% | 0.0920 | 0.5480 |
| rsi_14 | -0.0956 | — | -0.686 | 0.63 | -0.0648 | 40 | -2.0% | 0.2410 | 0.5560 |
| CNTP_60 | 0.0954 | — | 0.406 | 0.84 | 0.1147 | 53 | -0.9% | 0.3610 | 0.3810 |
| ROC_10 | 0.0946 | — | 0.656 | 0.84 | 0.0496 | 53 | 9.8% | 0.2990 | 0.4130 |
| ROC_60 | -0.0945 | — | -0.478 | 0.84 | -0.1655 | 53 | -6.2% | 0.2070 | 0.3480 |
| CNTP_10 | -0.0880 | — | -0.892 | 0.84 | -0.0702 | 53 | -4.9% | 0.2520 | 0.4790 |
| MA_10 | 0.0851 | — | 0.51 | 0.84 | 0.0434 | 53 | -2.5% | 0.3030 | 0.4060 |
| SUMP_5 | -0.0844 | — | -0.521 | 0.84 | -0.0662 | 53 | 6.6% | 0.2730 | 0.5970 |
| ret_5d | -0.0837 | — | -0.432 | 0.84 | -0.0440 | 53 | 0.9% | 0.2420 | 0.6170 |
| ROC_5 | 0.0837 | — | 0.432 | 0.84 | 0.0448 | 53 | -0.9% | 0.3150 | 0.4640 |
| SUMP_20 | -0.0814 | — | -0.705 | 0.84 | -0.0634 | 53 | -5.6% | 0.2800 | 0.4660 |
| CNTP_5 | -0.0798 | — | -0.623 | 0.84 | -0.0597 | 53 | 5.1% | 0.2520 | 0.5670 |
| RSV_10 | -0.0742 | — | -0.532 | 0.84 | -0.0487 | 53 | -4.4% | 0.2640 | 0.6920 |
| RSV_20 | -0.0733 | — | -0.507 | 0.84 | -0.0521 | 53 | -3.4% | 0.2700 | 0.6110 |
| MA_20 | 0.0731 | — | 0.465 | 0.84 | 0.0198 | 53 | -4.2% | 0.2860 | 0.3720 |
| CORR_10 | -0.0707 | — | -0.707 | 0.84 | -0.0587 | 53 | -1.0% | 0.2990 | 0.5150 |
| KLOW | -0.0677 | — | -0.44 | 0.84 | -0.0619 | 53 | 13.8% | 0.2960 | 0.7740 |
| MA_5 | 0.0677 | — | 0.309 | 0.84 | 0.0414 | 53 | -12.3% | 0.2940 | 0.5000 |
| news_sentiment | 0.0660 | — | 1.048 | 0.6 | 0.0639 | 38 | -3.0% | 0.3220 | 0.6130 |
| CORR_5 | -0.0654 | — | -0.511 | 0.84 | -0.0596 | 53 | 1.5% | 0.2780 | 0.6320 |
| SUMP_60 | 0.0642 | — | 0.345 | 0.84 | 0.1085 | 53 | 0.0% | 0.3210 | 0.4150 |
| MAX_20 | -0.0592 | — | -0.349 | 0.84 | -0.1803 | 53 | 7.5% | 0.2440 | 0.3890 |
| RSV_5 | -0.0574 | — | -0.332 | 0.84 | -0.0350 | 53 | -4.2% | 0.2620 | 0.7450 |
| news_count | -0.0531 | — | -0.656 | 0.6 | -0.0444 | 38 | 0.2% | 0.2740 | 0.5110 |
| ROC_20 | 0.0524 | — | 0.448 | 0.84 | -0.0297 | 53 | 2.1% | 0.2710 | 0.3950 |
| KMID | -0.0520 | — | -0.311 | 0.84 | -0.0274 | 53 | 13.7% | 0.2730 | 0.8520 |
| KMID2 | -0.0498 | — | -0.327 | 0.84 | -0.0344 | 53 | -3.8% | 0.2850 | 0.8670 |
| CNTP_20 | -0.0497 | — | -0.415 | 0.84 | -0.0275 | 53 | -3.4% | 0.2800 | 0.4360 |
| ret_21d | -0.0496 | — | -0.446 | 0.84 | — | 53 | 2.8% | 0.2470 | 0.4400 |
| MAX_10 | -0.0491 | — | -0.275 | 0.84 | -0.1163 | 53 | 4.0% | 0.2800 | 0.4100 |
| MAX_5 | -0.0465 | — | -0.234 | 0.84 | -0.0892 | 53 | 6.7% | 0.2810 | 0.4800 |
| composite_score | 0.0463 | — | 0.529 | 0.63 | — | 40 | -8.4% | 0.2740 | 0.5520 |
| pct_above_52w_low | -0.0440 | — | -0.227 | 0.84 | -0.0147 | 53 | -3.2% | 0.3370 | 0.3970 |
| st_sentiment | -0.0431 | — | -0.429 | 0.63 | -0.0421 | 40 | 4.5% | 0.3100 | 0.6510 |
| volume_spike_ratio | 0.0379 | — | 0.399 | 0.84 | 0.0540 | 53 | 2.9% | 0.3140 | 0.4790 |
| st_trending | -0.0362 | — | -0.437 | 0.63 | 0.0051 | 40 | 1.1% | 0.3120 | 0.5320 |
| KSFT | -0.0294 | — | -0.174 | 0.84 | -0.0124 | 53 | 22.1% | 0.2790 | 0.8570 |
| eps_rev_breadth | 0.0256 | — | 0.186 | 0.48 | 0.0333 | 30 | 2.6% | 0.1970 | 0.6490 |
| VMA_5 | 0.0197 | — | 0.183 | 0.84 | 0.0161 | 53 | 0.8% | 0.3250 | 0.6390 |
| RSV_60 | -0.0183 | — | -0.109 | 0.84 | 0.0218 | 53 | -2.9% | 0.3090 | 0.4990 |
| short_vol_ratio | -0.0123 | — | -0.163 | 0.84 | -0.0113 | 53 | 2.4% | 0.3390 | 0.6220 |
| eps_rev_30d | 0.0120 | — | 0.116 | 0.48 | 0.0043 | 30 | -27.0% | 0.1990 | 0.5820 |
| VMA_60 | -0.0103 | — | -0.096 | 0.84 | -0.0225 | 53 | 1.1% | 0.3250 | 0.5590 |
| MA_60 | 0.0097 | — | 0.057 | 0.84 | -0.0892 | 53 | 3.1% | 0.2680 | 0.3530 |
| eps_rev_90d | 0.0092 | — | 0.073 | 0.48 | 0.0248 | 30 | -24.9% | 0.1460 | 0.5960 |
| VMA_10 | 0.0076 | — | 0.066 | 0.84 | -0.0005 | 53 | -5.3% | 0.3150 | 0.5950 |
| VMA_20 | -0.0067 | — | -0.062 | 0.84 | -0.0161 | 53 | -3.9% | 0.3300 | 0.5760 |
| wiki_spike_ratio | 0.0027 | — | 0.039 | 0.84 | -0.0033 | 53 | -0.1% | 0.3040 | 0.6150 |
| wiki_views_7d | 0.0006 | — | 0.007 | 0.84 | 0.0245 | 53 | -10.6% | 0.3090 | 0.3250 |
| reddit_mentions | — | — | — | — | — | 0 | -10.0% | 0.2270 | 0.4000 |
| reddit_sentiment | — | — | — | — | — | 0 | -10.0% | 0.2270 | 0.4000 |

## IC decay across horizons

How each signal's predictive power changes with holding period — a real signal usually decays smoothly; a leak or fluke jumps around.

| Signal | 21d IC | 63d IC | 126d IC |
|--------|-------:|-------:|-------:|
| ret_21d | -0.0223 | -0.0496 | 0.4527 |
| ROC_20 | 0.0281 | 0.0524 | -0.4346 |
| SUMP_20 | -0.0365 | -0.0814 | 0.3989 |
| pt_upside | -0.1425 | -0.3434 | — |
| MAX_20 | -0.0429 | -0.0592 | -0.3379 |
| MA_20 | 0.0262 | 0.0731 | -0.3170 |
| MAX_60 | -0.0392 | -0.1175 | -0.2943 |
| RSV_20 | -0.0225 | -0.0733 | 0.2925 |
| ROC_10 | 0.0243 | 0.0946 | -0.2860 |
| rsi_14 | -0.0122 | -0.0956 | 0.2788 |
| CORR_20 | -0.0076 | -0.1103 | -0.2767 |
| CNTP_10 | 0.0090 | -0.0880 | 0.2676 |

## Walk-forward model (out-of-sample)

A model that learns the weights, evaluated strictly on future data it never trained on:

```
backend: sklearn-HGB
n_folds_used: 4
dead_features_max: 16
purged_rows: 34041
embargo_days: 2
n_oos: 852
oos_auc: 0.4335
oos_ic: -0.2434
oos_top_quintile_hit_rate: 0.176
oos_decile_spread: -0.043
feature_keys: ['ret_5d', 'ret_21d', 'ret_63d', 'volume_spike_ratio', 'rsi_14', 'pct_off_52w_high', 'pct_above_52w_low', 'annualized_vol', 'news_count', 'news_sentiment', 'reddit_mentions', 'reddit_sentiment', 'sec_form4_recent', 'sec_8k_recent', 'st_trending', 'st_msg_count', 'st_sentiment', 'wiki_views_7d', 'wiki_spike_ratio', 'short_vol_ratio', 'eps_rev_30d', 'eps_rev_90d', 'eps_rev_breadth', 'eps_rev_vs_price', 'analyst_count', 'pt_upside', 'KMID', 'KLEN', 'KMID2', 'KUP', 'KLOW', 'KSFT', 'ROC_5', 'ROC_10', 'ROC_20', 'ROC_60', 'MA_5', 'MA_10', 'MA_20', 'MA_60', 'STD_5', 'STD_10', 'STD_20', 'STD_60', 'MAX_5', 'MAX_10', 'MAX_20', 'MAX_60', 'MIN_5', 'MIN_10', 'MIN_20', 'MIN_60', 'RSV_5', 'RSV_10', 'RSV_20', 'RSV_60', 'CORR_5', 'CORR_10', 'CORR_20', 'CORR_60', 'CNTP_5', 'CNTP_10', 'CNTP_20', 'CNTP_60', 'SUMP_5', 'SUMP_10', 'SUMP_20', 'SUMP_60', 'VMA_5', 'VMA_10', 'VMA_20', 'VMA_60']
```
