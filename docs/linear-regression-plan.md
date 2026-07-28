# Linear Regression Price Prediction — Design Plan

## Goal

Train a linear model on the enriched OHLCV columns (from `price_diff.py`) to
predict the **next bar's close-to-close return** and use the prediction to
drive buy/sell decisions in the backtest engine.

---

## Why Linear Regression

| Reason | Detail |
|--------|--------|
| **Interpretable** | Every coefficient has a sign and magnitude you can read — no black box |
| **Fast** | Trains in milliseconds on 5 years of daily data; no GPU needed |
| **Low overfit risk** | With ~13 features and 1,250 rows per ticker, a linear model is well-constrained |
| **Baseline** | Before reaching for XGBoost or LSTM, establish what a simple model can do |
| **Stats built-in** | p-values, t-stats, R² come for free — you know which features actually matter |

---

## Data Pipeline

```
stock_data/{area}/{TICKER}.txt
        │
        ▼
price_diff.compute_diffs(interval=1)    ← 18 columns
        │
        ▼
build_features(df)                       ← lagged diffs, rolling stats
        │
        ▼
train/test split                         ← 80% train, 20% test (time-aware)
        │
        ▼
LinearRegression / Ridge / Lasso
        │
        ▼
evaluate → predict → feed backtest
```

---

## Feature Engineering

### Target

| Target | Column | Description |
|--------|--------|-------------|
| `target` | `pct_chg.shift(-1)` | Next bar's close-to-close return % |

### Features (what the model sees)

All features use **only data available at time t** — no look-ahead.

| # | Feature | Source | Description |
|---|---------|--------|-------------|
| 1 | `pct_chg` | diff column | Today's return |
| 2 | `gap_pct` | diff column | Today's overnight gap |
| 3 | `range_pct` | diff column | Today's intraday range |
| 4 | `co_pct` | diff column | Today's close-vs-open drift |
| 5 | `vol_chg_pct` | diff column | Today's volume change |
| 6 | `drawdown_pct` | diff column | Current drawdown from max |
| 7 | `pct_chg_lag1` | `pct_chg.shift(1)` | Yesterday's return |
| 8 | `pct_chg_lag2` | `pct_chg.shift(2)` | Return 2 days ago |
| 9 | `pct_chg_5d` | rolling sum | 5-day cumulative return |
| 10 | `range_5d_mean` | rolling mean | 5-day average intraday range |
| 11 | `vol_5d_mean` | rolling mean | 5-day average volume |
| 12 | `gap_5d_std` | rolling std | 5-day gap volatility |
| 13 | `direction` | `sign(pct_chg)` | +1 if up, −1 if down |

Total: **13 features**, all computable from the columns already produced by
`price_diff.py`.

---

## Model Variants

### 1. Ordinary Least Squares (baseline)

```python
from sklearn.linear_model import LinearRegression

model = LinearRegression()
model.fit(X_train, y_train)
```

- Fastest, most interpretable
- Every coefficient = "1 unit change in feature → β% change in predicted return"
- R² tells you how much variance is captured

### 2. Ridge Regression (regularised)

```python
from sklearn.linear_model import RidgeCV

model = RidgeCV(alphas=[0.01, 0.1, 1.0, 10.0, 100.0])
model.fit(X_train, y_train)
```

- Shrinks coefficients toward zero — better on noisy financial data
- Cross-validated alpha selection
- Same interpretability as OLS

### 3. Lasso (feature selection)

```python
from sklearn.linear_model import LassoCV

model = LassoCV(cv=5, max_iter=5000)
model.fit(X_train, y_train)
```

- Drives irrelevant feature coefficients to exactly zero
- Tells you which features actually matter
- Useful discovery tool even if you don't deploy it

---

## Evaluation Metrics

| Metric | What it measures | Target |
|--------|-----------------|--------|
| **R²** | % of variance explained | > 0.02 is meaningful in finance |
| **Directional accuracy** | % of times sign(pred) == sign(actual) | > 52% beats coin flip |
| **Mean absolute error (MAE)** | Average |pred − actual| in % | Compare to naive (predict 0) |
| **RMSE** | Root mean squared error % | Lower than naive std |
| **Sharpe of predictions** | If you traded every prediction, what Sharpe? | > 0.5 is decent |
| **Hit rate at extremes** | Accuracy when |prediction| > threshold | Higher confidence → higher accuracy? |

---

## Training Strategy

### Per-ticker vs pooled

| Approach | Pros | Cons |
|----------|------|------|
| **Per-ticker** — one model per stock | Captures ticker-specific patterns | Needs 1,250+ bars each; 4,000 models |
| **Pooled** — one model across all tickers | Massive training set; generalises | Ignores ticker idiosyncrasies |
| **Hybrid** — pooled with ticker embedding | Best of both | More complex |

**Recommendation:** Start with **per-ticker** (each stock gets its own model).
The `price_diff.py` batch output already has 1,250 rows per ticker — enough
for a 13-feature linear model.  Pooled is the natural v2.

### Time-aware split

```
[ 2019-07 ... 2025-01-01 | 2025-01-02 ... 2026-07 ]
          train 80%                    test 20%
```

No shuffling — financial data is a time series.  The model must predict on
data it has never seen temporally.

---

## Integration Points

### 1. With `price_diff.py`

```python
from price_diff import compute_diffs, batch_process
from linreg_model import build_features, train_model, predict

# Load enriched data
df = compute_diffs(raw_bars, interval=1)

# Build features + target
X, y = build_features(df)

# Train
model, metrics = train_model(X, y, method="ridge")
print(f"R²={metrics['r2']:.4f}  dir_acc={metrics['dir_acc']:.2%}")
```

### 2. With the backtest server

Add a new endpoint:

```
POST /api/{area}/{ticker}/predict
    Body: {}  (uses latest bar)
    Response: {"ticker":"AAPL","predicted_return_pct":0.34,"confidence":0.62}
```

The backtest server loads the trained model and predicts on the most
recent bar.

### 3. With the alert engine

```
price_diff batch → model predicts AAPL +1.2% tomorrow
                         │
                         ▼
                  WatchlistMonitor writes:
                  AAPL --cross-prediction 0.5   (threshold on prediction)
                         │
                         ▼
                  AlertEngine fires if prediction > threshold
                         │
                         ▼
                  Callback places order via ib_paper
```

### 4. With `random_algorithm.py`

Replace the "buy after 5% drop" heuristic with "buy when predicted return >
threshold":

```python
# Old: if pct_chg < -0.05 → buy
# New: if model.predict(features) > 0.5 → buy
```

---

## File Structure (proposed)

```
library/
├── linreg_model/
│   ├── __init__.py
│   ├── features.py          # build_features(), feature names, target
│   ├── train.py             # train_model(), cross-validate
│   ├── evaluate.py          # metrics, residual plots, coefficient table
│   ├── predict.py           # load model, predict on new bar
│   └── cli.py               # "python -m linreg_model train AAPL"
├── models/                  # serialised models
│   └── AAPL_ridge_2026-07.pkl
└── docs/
    └── linear-regression-plan.md   # this file
```

---

## Deliverables (in order)

| Phase | What | Effort |
|-------|------|--------|
| **1. Core** | `features.py` — `build_features(df)` → X, y | Small |
| **2. Train** | `train.py` — OLS + Ridge, per-ticker, metrics | Small |
| **3. Evaluate** | Coefficient table, residual diagnostics, directional accuracy | Small |
| **4. CLI** | `python -m linreg_model train AAPL --method ridge` | Small |
| **5. Predict** | `predict.py` — load model, score latest bar | Small |
| **6. Backtest** | Walk-forward: retrain every N bars, simulate P&L | Medium |
| **7. Server** | `POST /api/{ticker}/predict` endpoint | Medium |
| **8. Alert** | WatchlistMonitor supports prediction thresholds | Medium |

---

## First-cut expectations

Financial returns are notoriously hard to predict with linear models.
Realistic expectations for a per-ticker Ridge model:

| Metric | Realistic range | Notes |
|--------|----------------|-------|
| R² | 0.01 – 0.05 | Low but meaningful in finance |
| Directional accuracy | 50% – 55% | Every % above 50 is edge |
| MAE vs naive | 0.95× – 1.0× | Slightly better than "predict zero" |
| Sharpe (long-only on +pred) | 0.2 – 0.8 | Depends on market regime |
| Most important feature | `pct_chg_lag1` | Autocorrelation is usually strongest |

If the model achieves R² < 0 and directional accuracy < 50%, the features
don't carry a linear signal — next step is non-linear (XGBoost) or
regime-switching models.
