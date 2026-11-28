# Signal Evaluation — what actually works

_Generated: 2026-11-28T13:51:38.524732+00:00 · mode: from-store · horizon: 63d_

> 18954 feature snapshots across 96 dates → 9962 labeled examples at 63d horizon (pos rate 0.3159, 1282 tickers).

> ⚠️ Positive in-sample IC is easy to find by luck. Trust a signal only when the mean IC is **consistent across independent forward windows** (|t-stat| ≥ 2, which requires n_eff ≥ 2) AND the walk-forward out-of-sample numbers below hold up. While the archive is shorter than a couple of horizons, every t-stat reads `—` by design: a large |IC| with n_eff < 1 is a single overlapping observation, not a finding. Everything here is research, not advice.

## Per-signal edge (63d forward return)

IC = cross-sectional Spearman corr of signal vs forward return, averaged over dates. A consistent mean IC ≥ ~0.03 with |t-stat| ≥ 2 is a genuinely useful signal.

`n_eff` is the number of INDEPENDENT (non-overlapping) forward windows behind the IC series: dates / (horizon / sampling interval). Daily snapshots against a 63-day horizon overlap 63x, so 53 dates carry n_eff = 0.84 — less than one independent observation. Below n_eff = 2 no t-stat is computed (shown as `—`), because there are no degrees of freedom to test with; `IC ratio` is mean/std of the IC series, a descriptive ratio and *not* evidence of significance.

| Signal | mean IC | IC t-stat | IC ratio | n_eff | neut IC | dates | decile spread | top-quintile hit | turnover |
|--------|--------:|----------:|---------:|------:|--------:|------:|--------------:|-----------------:|---------:|
| pt_upside | -0.3309 | — | -4.041 | 0.52 | -0.4374 | 33 | 7.2% | 0.1240 | 0.6100 |
| annualized_vol | -0.2839 | — | -0.828 | 0.89 | -0.2540 | 56 | -2.2% | 0.1660 | 0.4010 |
| analyst_count | 0.2435 | — | 2.931 | 0.52 | 0.2369 | 33 | 7.3% | 0.3540 | 0.4430 |
| STD_20 | -0.2310 | — | -0.999 | 0.89 | -0.2408 | 56 | -5.6% | 0.2410 | 0.4100 |
| st_msg_count | -0.2157 | — | -1.948 | 0.68 | -0.1902 | 43 | -0.5% | 0.2240 | 0.3600 |
| STD_10 | -0.2155 | — | -0.994 | 0.89 | -0.2105 | 56 | 7.7% | 0.2630 | 0.4420 |
| STD_60 | -0.2067 | — | -0.733 | 0.89 | -0.2147 | 56 | -7.4% | 0.2260 | 0.3620 |
| MIN_20 | 0.1899 | — | 0.928 | 0.89 | 0.1969 | 56 | 5.9% | 0.3980 | 0.3340 |
| KLEN | -0.1792 | — | -0.788 | 0.89 | -0.1425 | 56 | 13.2% | 0.2780 | 0.7290 |
| MIN_10 | 0.1783 | — | 0.939 | 0.89 | 0.1494 | 56 | -0.4% | 0.3730 | 0.3930 |
| STD_5 | -0.1763 | — | -0.849 | 0.89 | -0.1676 | 56 | 8.8% | 0.2800 | 0.5300 |
| pct_off_52w_high | 0.1728 | — | 0.709 | 0.89 | 0.2472 | 56 | -14.3% | 0.3150 | 0.4350 |
| MIN_60 | 0.1594 | — | 1.019 | 0.89 | 0.1596 | 56 | 3.0% | 0.4030 | 0.2660 |
| CORR_60 | -0.1391 | — | -1.72 | 0.89 | -0.1192 | 56 | -9.7% | 0.2490 | 0.4040 |
| MIN_5 | 0.1349 | — | 0.641 | 0.89 | 0.0966 | 56 | -5.7% | 0.3550 | 0.4900 |
| SUMP_10 | -0.1158 | — | -0.824 | 0.89 | -0.0895 | 56 | -7.6% | 0.2500 | 0.5150 |
| ret_63d | 0.1157 | — | 0.578 | 0.89 | 0.1840 | 56 | 7.6% | 0.3310 | 0.4600 |
| MAX_60 | -0.1153 | — | -0.476 | 0.89 | -0.2286 | 56 | -0.1% | 0.2290 | 0.3550 |
| eps_rev_vs_price | -0.1148 | — | -1.386 | 0.52 | -0.1325 | 33 | -8.9% | 0.0950 | 0.5490 |
| CORR_20 | -0.1096 | — | -1.004 | 0.89 | -0.0879 | 56 | -6.4% | 0.2640 | 0.4620 |
| KUP | -0.1094 | — | -0.678 | 0.89 | -0.0783 | 56 | 10.7% | 0.2830 | 0.7410 |
| rsi_14 | -0.1088 | — | -0.756 | 0.68 | -0.0613 | 43 | -4.4% | 0.2430 | 0.5540 |
| ROC_10 | 0.1070 | — | 0.708 | 0.89 | 0.0369 | 56 | 10.7% | 0.3040 | 0.4190 |
| SUMP_20 | -0.1004 | — | -0.735 | 0.89 | -0.0711 | 56 | -7.0% | 0.2710 | 0.4680 |
| CNTP_10 | -0.1003 | — | -0.931 | 0.89 | -0.0747 | 56 | -7.8% | 0.2360 | 0.4770 |
| CNTP_60 | 0.0935 | — | 0.409 | 0.89 | 0.1172 | 56 | 5.7% | 0.3660 | 0.3850 |
| ROC_60 | -0.0933 | — | -0.484 | 0.89 | -0.1797 | 56 | -6.1% | 0.2060 | 0.3540 |
| MA_10 | 0.0851 | — | 0.512 | 0.89 | 0.0223 | 56 | -1.9% | 0.3030 | 0.4100 |
| RSV_20 | -0.0848 | — | -0.567 | 0.89 | -0.0534 | 56 | -4.5% | 0.2660 | 0.6090 |
| MA_20 | 0.0831 | — | 0.52 | 0.89 | 0.0006 | 56 | -3.4% | 0.2910 | 0.3750 |
| SUMP_5 | -0.0796 | — | -0.491 | 0.89 | -0.0527 | 56 | 6.7% | 0.2800 | 0.5960 |
| ret_5d | -0.0793 | — | -0.412 | 0.89 | -0.0216 | 56 | 0.9% | 0.2450 | 0.6200 |
| ROC_5 | 0.0793 | — | 0.412 | 0.89 | 0.0209 | 56 | -0.9% | 0.3100 | 0.4650 |
| RSV_10 | -0.0784 | — | -0.561 | 0.89 | -0.0438 | 56 | -4.6% | 0.2700 | 0.6930 |
| CNTP_5 | -0.0770 | — | -0.6 | 0.89 | -0.0505 | 56 | -6.5% | 0.2640 | 0.5670 |
| KLOW | -0.0751 | — | -0.484 | 0.89 | -0.0697 | 56 | 12.3% | 0.2900 | 0.7790 |
| ROC_20 | 0.0704 | — | 0.523 | 0.89 | -0.0451 | 56 | 3.2% | 0.2790 | 0.4000 |
| ret_21d | -0.0695 | — | -0.52 | 0.89 | — | 56 | 1.1% | 0.2370 | 0.4430 |
| CORR_5 | -0.0666 | — | -0.53 | 0.89 | -0.0567 | 56 | 1.0% | 0.2860 | 0.6440 |
| CNTP_20 | -0.0658 | — | -0.493 | 0.89 | -0.0353 | 56 | -6.9% | 0.2770 | 0.4350 |
| CORR_10 | -0.0654 | — | -0.647 | 0.89 | -0.0518 | 56 | -1.6% | 0.3060 | 0.5230 |
| MA_5 | 0.0628 | — | 0.291 | 0.89 | 0.0191 | 56 | -11.5% | 0.2950 | 0.5040 |
| SUMP_60 | 0.0604 | — | 0.332 | 0.89 | 0.1131 | 56 | -0.7% | 0.3250 | 0.4190 |
| news_sentiment | 0.0587 | — | 0.875 | 0.65 | 0.0574 | 41 | -3.0% | 0.3300 | 0.6140 |
| news_count | -0.0580 | — | -0.725 | 0.65 | -0.0485 | 41 | -0.6% | 0.2860 | 0.5110 |
| pct_above_52w_low | -0.0566 | — | -0.287 | 0.89 | -0.0130 | 56 | -4.8% | 0.3280 | 0.4030 |
| RSV_5 | -0.0534 | — | -0.311 | 0.89 | -0.0238 | 56 | -4.1% | 0.2660 | 0.7490 |
| MAX_5 | -0.0521 | — | -0.265 | 0.89 | -0.1072 | 56 | 5.6% | 0.2820 | 0.4820 |
| MAX_20 | -0.0508 | — | -0.302 | 0.89 | -0.1983 | 56 | 6.9% | 0.2460 | 0.3970 |
| volume_spike_ratio | 0.0504 | — | 0.472 | 0.89 | 0.0706 | 56 | 3.9% | 0.3250 | 0.4880 |
| MAX_10 | -0.0479 | — | -0.274 | 0.89 | -0.1328 | 56 | 3.5% | 0.2810 | 0.4170 |
| st_sentiment | -0.0459 | — | -0.475 | 0.68 | -0.0413 | 43 | 4.3% | 0.3160 | 0.6470 |
| KMID | -0.0441 | — | -0.261 | 0.89 | -0.0146 | 56 | 12.4% | 0.2760 | 0.8560 |
| KMID2 | -0.0405 | — | -0.26 | 0.89 | -0.0217 | 56 | -3.1% | 0.2980 | 0.8680 |
| composite_score | 0.0383 | — | 0.425 | 0.68 | — | 43 | -8.4% | 0.2750 | 0.5490 |
| st_trending | -0.0359 | — | -0.44 | 0.68 | -0.0025 | 43 | 13.5% | 0.2860 | 0.5350 |
| RSV_60 | -0.0285 | — | -0.168 | 0.89 | 0.0223 | 56 | -3.9% | 0.3070 | 0.5030 |
| KSFT | -0.0254 | — | -0.149 | 0.89 | -0.0037 | 56 | 20.5% | 0.2790 | 0.8610 |
| VMA_60 | -0.0201 | — | -0.177 | 0.89 | -0.0306 | 56 | 0.5% | 0.3260 | 0.5640 |
| MA_60 | 0.0198 | — | 0.116 | 0.89 | -0.1073 | 56 | -2.9% | 0.2730 | 0.3610 |
| eps_rev_90d | -0.0172 | — | -0.119 | 0.52 | 0.0088 | 33 | -23.6% | 0.1390 | 0.5870 |
| VMA_5 | 0.0169 | — | 0.159 | 0.89 | 0.0187 | 56 | 0.5% | 0.3330 | 0.6450 |
| short_vol_ratio | -0.0141 | — | -0.191 | 0.89 | -0.0109 | 56 | 2.1% | 0.3460 | 0.6230 |
| VMA_20 | -0.0141 | — | -0.128 | 0.89 | -0.0203 | 56 | -4.7% | 0.3340 | 0.5850 |
| eps_rev_30d | -0.0041 | — | -0.037 | 0.52 | -0.0095 | 33 | -24.9% | 0.2000 | 0.5760 |
| eps_rev_breadth | 0.0039 | — | 0.026 | 0.52 | 0.0237 | 33 | -1.8% | 0.1840 | 0.6550 |
| wiki_spike_ratio | 0.0020 | — | 0.029 | 0.89 | -0.0001 | 56 | -0.8% | 0.3020 | 0.6210 |
| wiki_views_7d | -0.0014 | — | -0.018 | 0.89 | 0.0276 | 56 | -2.7% | 0.3190 | 0.3320 |
| VMA_10 | 0.0007 | — | 0.006 | 0.89 | -0.0035 | 56 | -5.6% | 0.3210 | 0.6030 |
| reddit_mentions | — | — | — | — | — | 0 | -8.0% | 0.2850 | 0.4090 |
| reddit_sentiment | — | — | — | — | — | 0 | -8.0% | 0.2850 | 0.4090 |

## IC decay across horizons

How each signal's predictive power changes with holding period — a real signal usually decays smoothly; a leak or fluke jumps around.

| Signal | 21d IC | 63d IC | 126d IC |
|--------|-------:|-------:|-------:|
| ret_21d | -0.0099 | -0.0695 | 0.4509 |
| ROC_20 | 0.0173 | 0.0704 | -0.4335 |
| SUMP_20 | -0.0285 | -0.1004 | 0.3994 |
| MAX_20 | -0.0524 | -0.0508 | -0.3411 |
| MA_20 | 0.0193 | 0.0831 | -0.3322 |
| pt_upside | -0.1580 | -0.3309 | — |
| RSV_20 | -0.0187 | -0.0848 | 0.3071 |
| MAX_60 | -0.0520 | -0.1153 | -0.3039 |
| MA_60 | 0.0239 | 0.0198 | -0.2911 |
| annualized_vol | -0.1987 | -0.2839 | -0.2308 |
| CNTP_20 | -0.0059 | -0.0658 | 0.2754 |
| rsi_14 | -0.0097 | -0.1088 | 0.2653 |

## Walk-forward model (out-of-sample)

A model that learns the weights, evaluated strictly on future data it never trained on:

```
backend: sklearn-HGB
n_folds_used: 4
dead_features_max: 16
purged_rows: 34404
embargo_days: 2
n_oos: 1500
oos_auc: 0.4062
oos_ic: -0.2846
oos_top_quintile_hit_rate: 0.153
oos_decile_spread: -0.1197
feature_keys: ['ret_5d', 'ret_21d', 'ret_63d', 'volume_spike_ratio', 'rsi_14', 'pct_off_52w_high', 'pct_above_52w_low', 'annualized_vol', 'news_count', 'news_sentiment', 'reddit_mentions', 'reddit_sentiment', 'sec_form4_recent', 'sec_8k_recent', 'st_trending', 'st_msg_count', 'st_sentiment', 'wiki_views_7d', 'wiki_spike_ratio', 'short_vol_ratio', 'eps_rev_30d', 'eps_rev_90d', 'eps_rev_breadth', 'eps_rev_vs_price', 'analyst_count', 'pt_upside', 'KMID', 'KLEN', 'KMID2', 'KUP', 'KLOW', 'KSFT', 'ROC_5', 'ROC_10', 'ROC_20', 'ROC_60', 'MA_5', 'MA_10', 'MA_20', 'MA_60', 'STD_5', 'STD_10', 'STD_20', 'STD_60', 'MAX_5', 'MAX_10', 'MAX_20', 'MAX_60', 'MIN_5', 'MIN_10', 'MIN_20', 'MIN_60', 'RSV_5', 'RSV_10', 'RSV_20', 'RSV_60', 'CORR_5', 'CORR_10', 'CORR_20', 'CORR_60', 'CNTP_5', 'CNTP_10', 'CNTP_20', 'CNTP_60', 'SUMP_5', 'SUMP_10', 'SUMP_20', 'SUMP_60', 'VMA_5', 'VMA_10', 'VMA_20', 'VMA_60']
```
