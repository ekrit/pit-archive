# Signal Evaluation — what actually works

_Generated: 2026-11-25T17:48:25.804446+00:00 · mode: from-store · horizon: 63d_

> 18442 feature snapshots across 94 dates → 9527 labeled examples at 63d horizon (pos rate 0.3113, 1237 tickers).

> ⚠️ Positive in-sample IC is easy to find by luck. Trust a signal only when the mean IC is **consistent across independent forward windows** (|t-stat| ≥ 2, which requires n_eff ≥ 2) AND the walk-forward out-of-sample numbers below hold up. While the archive is shorter than a couple of horizons, every t-stat reads `—` by design: a large |IC| with n_eff < 1 is a single overlapping observation, not a finding. Everything here is research, not advice.

## Per-signal edge (63d forward return)

IC = cross-sectional Spearman corr of signal vs forward return, averaged over dates. A consistent mean IC ≥ ~0.03 with |t-stat| ≥ 2 is a genuinely useful signal.

`n_eff` is the number of INDEPENDENT (non-overlapping) forward windows behind the IC series: dates / (horizon / sampling interval). Daily snapshots against a 63-day horizon overlap 63x, so 53 dates carry n_eff = 0.84 — less than one independent observation. Below n_eff = 2 no t-stat is computed (shown as `—`), because there are no degrees of freedom to test with; `IC ratio` is mean/std of the IC series, a descriptive ratio and *not* evidence of significance.

| Signal | mean IC | IC t-stat | IC ratio | n_eff | neut IC | dates | decile spread | top-quintile hit | turnover |
|--------|--------:|----------:|---------:|------:|--------:|------:|--------------:|-----------------:|---------:|
| pt_upside | -0.3374 | — | -4.265 | 0.49 | -0.4267 | 31 | 8.6% | 0.1250 | 0.6150 |
| annualized_vol | -0.2753 | — | -0.795 | 0.86 | -0.2508 | 54 | -0.8% | 0.1670 | 0.3930 |
| analyst_count | 0.2482 | — | 2.982 | 0.49 | 0.2407 | 31 | 5.5% | 0.3410 | 0.4490 |
| STD_20 | -0.2283 | — | -0.971 | 0.86 | -0.2305 | 54 | -5.0% | 0.2410 | 0.4050 |
| STD_10 | -0.2155 | — | -0.974 | 0.86 | -0.2022 | 54 | 8.6% | 0.2660 | 0.4350 |
| st_msg_count | -0.2120 | — | -1.916 | 0.65 | -0.1897 | 41 | -0.5% | 0.2140 | 0.3530 |
| STD_60 | -0.2034 | — | -0.709 | 0.86 | -0.2064 | 54 | -7.1% | 0.2230 | 0.3560 |
| MIN_20 | 0.1855 | — | 0.895 | 0.86 | 0.1983 | 54 | 5.0% | 0.3860 | 0.3310 |
| STD_5 | -0.1809 | — | -0.857 | 0.86 | -0.1610 | 54 | 9.5% | 0.2800 | 0.5240 |
| KLEN | -0.1805 | — | -0.78 | 0.86 | -0.1456 | 54 | 13.8% | 0.2720 | 0.7230 |
| MIN_10 | 0.1795 | — | 0.926 | 0.86 | 0.1581 | 54 | -0.8% | 0.3670 | 0.3890 |
| pct_off_52w_high | 0.1696 | — | 0.686 | 0.86 | 0.2404 | 54 | -15.6% | 0.3090 | 0.4330 |
| MIN_60 | 0.1553 | — | 0.981 | 0.86 | 0.1608 | 54 | 2.0% | 0.3970 | 0.2670 |
| CORR_60 | -0.1413 | — | -1.698 | 0.86 | -0.1243 | 54 | -10.0% | 0.2460 | 0.3930 |
| MIN_5 | 0.1399 | — | 0.657 | 0.86 | 0.1090 | 54 | -5.8% | 0.3540 | 0.4860 |
| MAX_60 | -0.1160 | — | -0.47 | 0.86 | -0.2149 | 54 | 0.3% | 0.2280 | 0.3520 |
| ret_63d | 0.1155 | — | 0.566 | 0.86 | 0.1779 | 54 | 8.0% | 0.3290 | 0.4570 |
| CORR_20 | -0.1131 | — | -1.044 | 0.86 | -0.0940 | 54 | -6.2% | 0.2580 | 0.4480 |
| KUP | -0.1120 | — | -0.682 | 0.86 | -0.0803 | 54 | 10.9% | 0.2770 | 0.7380 |
| SUMP_10 | -0.1106 | — | -0.787 | 0.86 | -0.0907 | 54 | -6.9% | 0.2510 | 0.5160 |
| eps_rev_vs_price | -0.1068 | — | -1.337 | 0.49 | -0.1218 | 31 | -9.0% | 0.0910 | 0.5500 |
| rsi_14 | -0.1038 | — | -0.71 | 0.65 | -0.0667 | 41 | -2.8% | 0.2410 | 0.5540 |
| ROC_10 | 0.1026 | — | 0.676 | 0.86 | 0.0543 | 54 | 10.7% | 0.3000 | 0.4150 |
| CNTP_10 | -0.0947 | — | -0.897 | 0.86 | -0.0735 | 54 | -13.5% | 0.2440 | 0.4770 |
| CNTP_60 | 0.0945 | — | 0.406 | 0.86 | 0.1157 | 54 | 5.5% | 0.3570 | 0.3820 |
| ROC_60 | -0.0933 | — | -0.475 | 0.86 | -0.1696 | 54 | -6.0% | 0.2050 | 0.3510 |
| SUMP_20 | -0.0899 | — | -0.708 | 0.86 | -0.0672 | 54 | -5.8% | 0.2760 | 0.4670 |
| MA_10 | 0.0887 | — | 0.527 | 0.86 | 0.0411 | 54 | -2.1% | 0.3030 | 0.4080 |
| SUMP_5 | -0.0848 | — | -0.517 | 0.86 | -0.0630 | 54 | 6.5% | 0.2710 | 0.5960 |
| ret_5d | -0.0833 | — | -0.425 | 0.86 | -0.0382 | 54 | 1.1% | 0.2400 | 0.6180 |
| ROC_5 | 0.0833 | — | 0.425 | 0.86 | 0.0392 | 54 | -1.1% | 0.3080 | 0.4640 |
| RSV_20 | -0.0803 | — | -0.534 | 0.86 | -0.0555 | 54 | -4.0% | 0.2670 | 0.6090 |
| CNTP_5 | -0.0797 | — | -0.608 | 0.86 | -0.0568 | 54 | 5.7% | 0.2480 | 0.5650 |
| MA_20 | 0.0795 | — | 0.492 | 0.86 | 0.0193 | 54 | -3.7% | 0.2840 | 0.3740 |
| RSV_10 | -0.0795 | — | -0.558 | 0.86 | -0.0507 | 54 | -4.9% | 0.2620 | 0.6900 |
| CORR_10 | -0.0695 | — | -0.686 | 0.86 | -0.0560 | 54 | -1.1% | 0.2980 | 0.5170 |
| KLOW | -0.0694 | — | -0.453 | 0.86 | -0.0640 | 54 | 13.3% | 0.2930 | 0.7760 |
| MA_5 | 0.0674 | — | 0.308 | 0.86 | 0.0363 | 54 | -12.1% | 0.2920 | 0.4990 |
| CORR_5 | -0.0659 | — | -0.517 | 0.86 | -0.0579 | 54 | 1.3% | 0.2800 | 0.6320 |
| news_sentiment | 0.0640 | — | 0.997 | 0.62 | 0.0622 | 39 | -2.7% | 0.3250 | 0.6130 |
| SUMP_60 | 0.0610 | — | 0.328 | 0.86 | 0.1091 | 54 | -0.3% | 0.3200 | 0.4150 |
| ROC_20 | 0.0600 | — | 0.478 | 0.86 | -0.0292 | 54 | 2.4% | 0.2720 | 0.3970 |
| RSV_5 | -0.0583 | — | -0.338 | 0.86 | -0.0330 | 54 | -4.2% | 0.2610 | 0.7440 |
| ret_21d | -0.0576 | — | -0.477 | 0.86 | — | 54 | 2.3% | 0.2440 | 0.4420 |
| news_count | -0.0572 | — | -0.685 | 0.62 | -0.0478 | 39 | -0.1% | 0.2730 | 0.5110 |
| CNTP_20 | -0.0560 | — | -0.447 | 0.86 | -0.0303 | 54 | -4.6% | 0.2720 | 0.4340 |
| MAX_20 | -0.0553 | — | -0.325 | 0.86 | -0.1833 | 54 | 7.4% | 0.2430 | 0.3930 |
| pct_above_52w_low | -0.0523 | — | -0.262 | 0.86 | -0.0164 | 54 | -4.4% | 0.3320 | 0.3990 |
| KMID | -0.0498 | — | -0.299 | 0.86 | -0.0232 | 54 | 13.4% | 0.2700 | 0.8530 |
| MAX_5 | -0.0478 | — | -0.241 | 0.86 | -0.0947 | 54 | 6.3% | 0.2780 | 0.4800 |
| KMID2 | -0.0474 | — | -0.311 | 0.86 | -0.0309 | 54 | -3.5% | 0.2850 | 0.8690 |
| MAX_10 | -0.0470 | — | -0.264 | 0.86 | -0.1188 | 54 | 3.9% | 0.2790 | 0.4130 |
| composite_score | 0.0441 | — | 0.503 | 0.65 | — | 41 | -8.6% | 0.2760 | 0.5510 |
| volume_spike_ratio | 0.0441 | — | 0.426 | 0.86 | 0.0588 | 54 | 3.0% | 0.3170 | 0.4830 |
| st_sentiment | -0.0436 | — | -0.439 | 0.65 | -0.0415 | 41 | 4.2% | 0.3070 | 0.6510 |
| st_trending | -0.0357 | — | -0.431 | 0.65 | -0.0017 | 41 | 2.5% | 0.2970 | 0.5260 |
| KSFT | -0.0267 | — | -0.158 | 0.86 | -0.0086 | 54 | 21.8% | 0.2750 | 0.8570 |
| RSV_60 | -0.0247 | — | -0.143 | 0.86 | 0.0201 | 54 | -3.2% | 0.3060 | 0.4980 |
| VMA_5 | 0.0188 | — | 0.175 | 0.86 | 0.0150 | 54 | 0.7% | 0.3280 | 0.6410 |
| eps_rev_breadth | 0.0182 | — | 0.129 | 0.49 | 0.0308 | 31 | 2.4% | 0.2040 | 0.6490 |
| MA_60 | 0.0157 | — | 0.091 | 0.86 | -0.0927 | 54 | 3.3% | 0.2670 | 0.3570 |
| VMA_60 | -0.0156 | — | -0.139 | 0.86 | -0.0270 | 54 | 1.1% | 0.3270 | 0.5580 |
| short_vol_ratio | -0.0134 | — | -0.179 | 0.86 | -0.0121 | 54 | 2.3% | 0.3380 | 0.6220 |
| VMA_20 | -0.0103 | — | -0.093 | 0.86 | -0.0182 | 54 | -3.8% | 0.3260 | 0.5760 |
| eps_rev_30d | 0.0081 | — | 0.078 | 0.49 | -0.0017 | 31 | -26.5% | 0.2060 | 0.5800 |
| VMA_10 | 0.0041 | — | 0.036 | 0.86 | -0.0032 | 54 | -5.3% | 0.3140 | 0.5960 |
| wiki_spike_ratio | 0.0015 | — | 0.022 | 0.86 | -0.0020 | 54 | -0.4% | 0.3010 | 0.6180 |
| wiki_views_7d | -0.0010 | — | -0.013 | 0.86 | 0.0267 | 54 | -5.1% | 0.3070 | 0.3280 |
| eps_rev_90d | -0.0004 | — | -0.003 | 0.49 | 0.0184 | 31 | -24.5% | 0.1450 | 0.5920 |
| reddit_mentions | — | — | — | — | — | 0 | -11.3% | 0.2360 | 0.3960 |
| reddit_sentiment | — | — | — | — | — | 0 | -11.3% | 0.2360 | 0.3960 |

## IC decay across horizons

How each signal's predictive power changes with holding period — a real signal usually decays smoothly; a leak or fluke jumps around.

| Signal | 21d IC | 63d IC | 126d IC |
|--------|-------:|-------:|-------:|
| ret_21d | -0.0111 | -0.0576 | 0.4682 |
| ROC_20 | 0.0180 | 0.0600 | -0.4526 |
| SUMP_20 | -0.0284 | -0.0899 | 0.4188 |
| MAX_20 | -0.0514 | -0.0553 | -0.3650 |
| MA_20 | 0.0210 | 0.0795 | -0.3430 |
| pt_upside | -0.1568 | -0.3374 | — |
| RSV_20 | -0.0197 | -0.0803 | 0.3231 |
| MAX_60 | -0.0503 | -0.1160 | -0.3219 |
| ROC_10 | 0.0182 | 0.1026 | -0.3125 |
| MA_60 | 0.0271 | 0.0157 | -0.2934 |
| CNTP_10 | 0.0099 | -0.0947 | 0.2871 |
| CNTP_20 | -0.0031 | -0.0560 | 0.2852 |

## Walk-forward model (out-of-sample)

A model that learns the weights, evaluated strictly on future data it never trained on:

```
backend: sklearn-HGB
n_folds_used: 4
dead_features_max: 16
purged_rows: 33868
embargo_days: 2
n_oos: 1064
oos_auc: 0.407
oos_ic: -0.2798
oos_top_quintile_hit_rate: 0.164
oos_decile_spread: -0.0921
feature_keys: ['ret_5d', 'ret_21d', 'ret_63d', 'volume_spike_ratio', 'rsi_14', 'pct_off_52w_high', 'pct_above_52w_low', 'annualized_vol', 'news_count', 'news_sentiment', 'reddit_mentions', 'reddit_sentiment', 'sec_form4_recent', 'sec_8k_recent', 'st_trending', 'st_msg_count', 'st_sentiment', 'wiki_views_7d', 'wiki_spike_ratio', 'short_vol_ratio', 'eps_rev_30d', 'eps_rev_90d', 'eps_rev_breadth', 'eps_rev_vs_price', 'analyst_count', 'pt_upside', 'KMID', 'KLEN', 'KMID2', 'KUP', 'KLOW', 'KSFT', 'ROC_5', 'ROC_10', 'ROC_20', 'ROC_60', 'MA_5', 'MA_10', 'MA_20', 'MA_60', 'STD_5', 'STD_10', 'STD_20', 'STD_60', 'MAX_5', 'MAX_10', 'MAX_20', 'MAX_60', 'MIN_5', 'MIN_10', 'MIN_20', 'MIN_60', 'RSV_5', 'RSV_10', 'RSV_20', 'RSV_60', 'CORR_5', 'CORR_10', 'CORR_20', 'CORR_60', 'CNTP_5', 'CNTP_10', 'CNTP_20', 'CNTP_60', 'SUMP_5', 'SUMP_10', 'SUMP_20', 'SUMP_60', 'VMA_5', 'VMA_10', 'VMA_20', 'VMA_60']
```
