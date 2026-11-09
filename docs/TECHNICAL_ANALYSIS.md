# Technical analysis conventions

MarketMitra calculates indicators from the chronologically ordered OHLC close
observations returned for the selected timeframe. Indicators are descriptive
historical analytics only; the application does not generate buy, sell, or hold
recommendations.

- SMA uses the arithmetic mean of the most recent `N` valid closes.
- EMA is seeded with the first `N`-observation SMA, then uses
  `EMA[t] = (close[t] - EMA[t-1]) * 2/(N+1) + EMA[t-1]`.
- RSI uses Wilder's smoothing. The initial average gain/loss is the arithmetic
  mean of the first `N` changes; subsequent values use `(previous * (N-1) +
  current) / N`. A flat series is reported as RSI 50.
- MACD is EMA(12) minus EMA(26), with a 9-period EMA of the MACD line as its
  signal and `MACD - signal` as its histogram.
- Bollinger Bands use an `N`-period SMA and population standard deviation
  (divide by `N`), with two standard deviations by default.

Periods are bounded to 2–200 and MACD fast must be less than slow. Warm-up
points are null and are never padded or repeated. A missing close resets the
contiguous calculation window, and the UI explains the exact minimum history
required when an indicator cannot be calculated.

The persistent interview demo currently contains four daily observations per
instrument. It therefore intentionally shows insufficient-history messages for
the default 14/20/26-period indicators. Longer deterministic sequences used by
unit tests are in frontend test fixtures only and are not ingested into
`marketmitra_demo`.
