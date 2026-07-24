# Predicting Stock Price Direction: Research Summary

## 1. The hard constraint: markets are mostly efficient

Before picking a method, it's worth being clear-eyed about the ceiling. Under the
weak-form Efficient Market Hypothesis, current prices already reflect past price
and volume information, so mechanically predicting direction from price history
alone has a low and shrinking edge as markets get more efficient and more
participants compete for the same signal. Empirically, papers that claim high
accuracy at predicting *price levels* are usually predicting a value that is
99% "yesterday's price plus noise," which looks accurate on standard error
metrics (MSE/MAE) but is close to useless for predicting *direction* — the
thing that actually matters for a trading decision. Any approach below should
be evaluated on directional/trading metrics (hit rate, Sharpe, PnL after costs),
not price-fit metrics.

Sources:
- [The Efficient Market Hypothesis: A Survey (RBA)](https://www.rba.gov.au/publications/rdp/2000/pdf/rdp2000-01.pdf)
- [Machine learning, stock market forecasting, and market efficiency: a comparative study (Springer)](https://link.springer.com/article/10.1007/s41060-025-00854-4)
- [A Comprehensive Study of Market Prediction from EMH to Intelligent Market Prediction (Springer)](https://link.springer.com/article/10.1007/s10614-022-10283-1)

## 2. Approaches, roughly in order of what practitioners actually rely on

### a) Classical statistical / econometric models
ARIMA, GARCH, and factor models (Fama-French style) remain the baseline. They're
cheap, interpretable, and hard to beat out-of-sample on pure price series
despite being "simpler" than deep learning.

### b) Tree-based ML on engineered features (most robust for tabular signal)
Gradient boosting (XGBoost/LightGBM) and Random Forests on engineered features
(technical indicators, fundamentals, cross-sectional ranks) are the workhorse
in industry because they handle noisy, non-stationary tabular data well and are
resistant to overfitting relative to deep nets, given proper cross-validation.
Reported accuracy numbers above ~90% in papers almost always indicate data
leakage (e.g., using same-day features to predict same-day direction) rather
than genuine skill — treat such claims skeptically.

### c) Deep learning on sequences (LSTM / Transformer)
- **LSTM**: still a reasonable balance of performance vs. compute; struggles
  because there isn't enough non-redundant historical data to justify very
  deep architectures — bigger isn't automatically better here.
- **Transformers**: can outperform LSTM given enough data and compute, but
  the self-attention mechanism lacks the inductive bias for seasonality/trend
  that time series has, needs large datasets to avoid unstable predictions,
  and is expensive to train/serve. Hybrid LSTM+Transformer architectures are
  an active research area trying to get the best of both.
- Across the board: overfitting to a specific asset/regime is the dominant
  failure mode, not underfitting.

Sources:
- [Comparing Different Transformer Model Structures for Stock Prediction (arXiv)](https://arxiv.org/pdf/2504.16361)
- [Integrating deep learning and econometrics for stock price prediction (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S2666827025001136)
- [Transformers vs. LSTM for Stock Price Time Series Prediction](https://medium.com/@mskmay66/transformers-vs-lstm-for-stock-price-time-series-prediction-3a26fcc1a782)

### d) Sentiment analysis & alternative data (where real edge tends to live)
This is where quant funds report genuine, if decaying, alpha:
- NLP sentiment from news/social media (e.g., a sudden spike in negative
  sentiment has been correlated with ~2.5% underperformance over the
  following month in some studies).
- Alternative data: credit-card transaction data, web traffic, satellite
  imagery (parking lots, shipping), and job postings can lead traditional
  earnings forecasts by 2-3 weeks.
- LLM-generated "formulaic alpha" combined with transformers is an emerging
  2025/2026 research direction combining sentiment + structured signals.

The edge here comes from *information asymmetry / speed*, not from a
better curve-fitting algorithm — which is a fundamentally different (and more
defensible) source of predictive power than price-history modeling alone.

Sources:
- [Sentiment-Aware Stock Price Prediction with Transformer and LLM-Generated Formulaic Alpha (arXiv)](https://arxiv.org/pdf/2508.04975)
- [5 Best Alternative Data Sources for Hedge Funds (ExtractAlpha)](https://extractalpha.com/2025/07/07/5-best-alternative-data-sources-for-hedge-funds/)
- [How Quant Hedge Funds Actually Build and Vet Trading Signals](https://youngandcalculated.substack.com/p/how-quant-hedge-funds-actually-build)

### e) Ensembles / hybrid models
Combining multiple weak, decorrelated signals (price-based ML + sentiment +
fundamentals) via ensembling or stacking consistently outperforms any single
model class in both papers and practice. This mirrors how real quant funds
operate: many small, independent signals blended together, rather than one
model expected to "solve" prediction.

## 3. Practical recommendations if building a predictor

1. **Predict direction/return over a horizon, not price level.** Frame as
   classification (up/down/flat) or return regression, evaluated with
   precision/recall and realistic trading metrics, not RMSE on price.
2. **Guard against leakage.** No feature should use information not available
   at decision time (survivorship bias, restated fundamentals, same-bar data).
3. **Walk-forward validation**, not random train/test splits — time series
   requires expanding-window backtests to avoid look-ahead bias.
4. **Include transaction costs and slippage** in any backtest; many "profitable"
   models evaporate once costs are included.
5. **Prefer an ensemble of simple, decorrelated signals** (technical + fundamental
   + sentiment) over a single complex deep model — this is both more robust
   and matches what production quant systems actually do.
6. **Treat headline accuracy claims (>90%) with suspicion** — they are the
   single biggest red flag for data leakage in this literature.

## 4. Bottom line

There is no model that reliably predicts *when* a stock will go up in an
absolute sense — if one existed and worked at scale, the act of trading on it
would arbitrage the edge away. The realistic, defensible approach is: combine
diverse, decorrelated signals (price/technical ML, fundamentals, sentiment/
alternative data), validate with strict walk-forward/no-leakage methodology,
size positions for uncertainty, and expect a small, decaying statistical edge
rather than high-confidence per-stock predictions.
