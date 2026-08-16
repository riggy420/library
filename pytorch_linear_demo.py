"""
pytorch_linear_demo.py — Linear regression with PyTorch for stock prediction.

Two approaches, same math:
  1. torch.linalg.lstsq  — closed-form (Normal Equation via SVD)
  2. torch.optim.SGD     — gradient descent, iterative

Predicts next-bar return from enriched OHLCV diff columns.

Usage:
    python pytorch_linear_demo.py AAPL
    python pytorch_linear_demo.py AAPL --epochs 2000 --lr 0.01
    python pytorch_linear_demo.py AAPL TSLA MSFT
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn


# ── Config ────────────────────────────────────────────────────────────────

DATA_DIR = Path("stock_data")
AREA = "America"
FEATURE_COLS = [
    "pct_chg",          # today's return
    "gap_pct",          # overnight gap
    "range_pct",        # intraday range
    "co_pct",           # close-vs-open drift
    "vol_chg_pct",      # volume change
    "drawdown_pct",     # drawdown from max
    "pct_chg_lag1",     # yesterday's return
    "pct_chg_lag2",     # return 2 days ago
    "pct_chg_5d",       # 5-day cumulative return
    "range_5d_mean",    # 5-day average range
    "vol_5d_mean",      # 5-day average volume
    "gap_5d_std",       # 5-day gap volatility
    "direction",        # +1 if up, -1 if down
]
TARGET_COL = "target"    # next-bar return %
TRAIN_RATIO = 0.80


# ── Data loading ──────────────────────────────────────────────────────────

def load_raw_bars(ticker: str) -> pd.DataFrame:
    """Read a scraper-format CSV into a clean DataFrame."""
    import csv

    path = DATA_DIR / AREA / f"{ticker}.txt"
    if not path.exists():
        raise FileNotFoundError(f"No data for {ticker} at {path}")

    df = pd.read_csv(
        path, header=None,
        names=["Date", "Close", "High", "Low", "Open", "Volume"],
        quoting=csv.QUOTE_NONNUMERIC, on_bad_lines="skip",
    )
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
    df = df.dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return df


def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """Compute diff columns and engineer features for the model."""
    # Use compute_diffs from price_diff if available, else inline
    try:
        from price_diff import compute_diffs
        df = compute_diffs(df.rename(columns={
            "Date": "date", "Close": "close", "High": "high",
            "Low": "low", "Open": "open", "Volume": "volume",
        }))
    except ImportError:
        df = _compute_diffs_inline(df)

    # Lagged returns
    df["pct_chg_lag1"] = df["pct_chg"].shift(1)
    df["pct_chg_lag2"] = df["pct_chg"].shift(2)

    # 5-day rolling stats
    df["pct_chg_5d"] = df["pct_chg"].rolling(5).sum()
    df["range_5d_mean"] = df["range_pct"].rolling(5).mean()
    df["vol_5d_mean"] = df["volume"].rolling(5).mean()
    df["gap_5d_std"] = df["gap_pct"].rolling(5).std()

    # Direction dummy
    df["direction"] = np.where(df["pct_chg"] >= 0, 1.0, -1.0)

    # Target: next bar's return
    df[TARGET_COL] = df["pct_chg"].shift(-1)

    return df


def _compute_diffs_inline(df: pd.DataFrame) -> pd.DataFrame:
    """Fallback diff computation when price_diff is not importable."""
    df = df.copy()
    cols = {c.lower(): c for c in df.columns}
    c = cols.get("close", "Close")
    o = cols.get("open", "Open")
    h = cols.get("high", "High")
    l = cols.get("low", "Low")
    v = cols.get("volume", "Volume")

    prev_c = df[c].shift(1)
    prev_v = df[v].shift(1)

    df["pct_chg"] = ((df[c] - prev_c) / prev_c * 100).round(4)
    df["gap_pct"] = ((df[o] - prev_c) / prev_c * 100).round(4)
    df["range_pct"] = ((df[h] - df[l]) / df[l] * 100).round(4)
    df["co_pct"] = ((df[c] - df[o]) / df[o] * 100).round(4)
    df["vol_chg_pct"] = ((df[v] - prev_v) / prev_v * 100).round(4)

    cummax = df[c].cummax()
    df["drawdown_pct"] = ((df[c] - cummax) / cummax * 100).round(4)
    return df


# ── Prepare tensors ───────────────────────────────────────────────────────

def prepare_data(df: pd.DataFrame) -> tuple[torch.Tensor, ...]:
    """Drop rows with NaN (rolling windows + lagged shifts) and split."""
    cols = FEATURE_COLS + [TARGET_COL]
    available = [c for c in cols if c in df.columns]
    clean = df[available].dropna()

    X_np = clean[FEATURE_COLS].values.astype(np.float32)
    y_np = clean[TARGET_COL].values.astype(np.float32).reshape(-1, 1)

    # Standardise features (zero mean, unit variance)
    X_mean = X_np.mean(axis=0, keepdims=True)
    X_std = X_np.std(axis=0, keepdims=True)
    X_std[X_std == 0] = 1.0
    X_np = (X_np - X_mean) / X_std

    # Time-aware split
    split = int(len(X_np) * TRAIN_RATIO)
    X_train = torch.tensor(X_np[:split])
    y_train = torch.tensor(y_np[:split])
    X_test = torch.tensor(X_np[split:])
    y_test = torch.tensor(y_np[split:])

    return X_train, y_train, X_test, y_test, X_mean, X_std, clean


# ── Approach 1: Closed-form via torch.linalg.lstsq ───────────────────────

def solve_normal_equation(X: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """β = argmin ‖Xβ − y‖²  via least-squares (SVD internally)."""
    return torch.linalg.lstsq(X, y).solution


# ── Approach 2: Gradient descent via torch.optim ──────────────────────────

class LinearModel(nn.Module):
    """y = X @ β   (no bias — we standardised and it acts as an implicit intercept)."""
    def __init__(self, n_features: int):
        super().__init__()
        self.beta = nn.Parameter(torch.randn(n_features, 1) * 0.01)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x @ self.beta


def train_gradient_descent(
    X: torch.Tensor, y: torch.Tensor,
    epochs: int = 1000,
    lr: float = 0.01,
    quiet: bool = False,
) -> tuple[LinearModel, list[float]]:
    """Train a linear model with SGD and return the trained model + loss history."""
    model = LinearModel(X.shape[1])
    optimiser = torch.optim.SGD(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    history: list[float] = []

    for epoch in range(epochs):
        optimiser.zero_grad()
        pred = model(X)
        loss = loss_fn(pred, y)
        loss.backward()
        optimiser.step()
        history.append(loss.item())

        if not quiet and epoch % (epochs // 10) == 0:
            print(f"  epoch {epoch:>5d}/{epochs}  loss={loss.item():.6f}")

    return model, history


# ── Evaluation ────────────────────────────────────────────────────────────

def evaluate(beta: torch.Tensor, X: torch.Tensor, y: torch.Tensor,
             X_mean: np.ndarray, X_std: np.ndarray) -> dict:
    """Compute R², directional accuracy, and MAE."""
    pred = (X @ beta).numpy()
    actual = y.numpy()

    ss_res = ((actual - pred) ** 2).sum()
    ss_tot = ((actual - actual.mean()) ** 2).sum()
    r2 = float(1 - ss_res / ss_tot) if ss_tot > 0 else 0.0

    dir_acc = float(np.mean(np.sign(pred) == np.sign(actual)))
    mae = float(np.mean(np.abs(pred - actual)))

    return {"r2": round(r2, 4), "dir_acc": round(dir_acc, 4), "mae": round(mae, 4)}


def print_coefficients(beta: np.ndarray) -> None:
    """Print a ranked table of feature coefficients."""
    pairs = sorted(
        zip(FEATURE_COLS, beta.flatten()),
        key=lambda x: abs(x[1]), reverse=True,
    )
    print(f"\n{'Feature':>22s}  {'Coefficient':>10s}  ")
    print("-" * 38)
    for name, coef in pairs:
        direction = "+" if coef > 0 else "-"
        print(f"  {name:>20s}  {direction}{abs(coef):.6f}")


# ── Main ──────────────────────────────────────────────────────────────────

def run(ticker: str, epochs: int = 1000, lr: float = 0.01) -> None:
    print(f"\n{'='*60}")
    print(f"  {ticker}")
    print(f"{'='*60}")

    # 1. Load data
    raw = load_raw_bars(ticker)
    df = build_features(raw)
    X_train, y_train, X_test, y_test, X_mean, X_std, clean = prepare_data(df)

    n_train = len(X_train)
    n_test = len(X_test)
    n_feat = X_train.shape[1]
    print(f"  bars: {len(raw)} total  |  train={n_train}  test={n_test}  "
          f"features={n_feat}")

    # 2. Approach 1 — Normal Equation (closed-form)
    print(f"\n  ── Normal Equation (torch.linalg.lstsq) ──")
    beta_lstsq = solve_normal_equation(X_train, y_train)
    metrics_lstsq = evaluate(beta_lstsq, X_test, y_test, X_mean, X_std)
    print(f"  R²={metrics_lstsq['r2']:.4f}  "
          f"dir_acc={metrics_lstsq['dir_acc']:.2%}  "
          f"MAE={metrics_lstsq['mae']:.4f}")

    # 3. Approach 2 — Gradient Descent
    print(f"\n  ── Gradient Descent (lr={lr}, epochs={epochs}) ──")
    model, history = train_gradient_descent(X_train, y_train, epochs=epochs, lr=lr)
    beta_sgd = model.beta.detach().numpy()
    metrics_sgd = evaluate(torch.tensor(beta_sgd), X_test, y_test, X_mean, X_std)
    print(f"  final loss={history[-1]:.6f}")
    print(f"  R²={metrics_sgd['r2']:.4f}  "
          f"dir_acc={metrics_sgd['dir_acc']:.2%}  "
          f"MAE={metrics_sgd['mae']:.4f}")

    # 4. Print coefficients (from the exact solution)
    print(f"\n  ── Feature coefficients ──")
    print_coefficients(beta_lstsq.numpy())

    # 5. Show a few predictions on test data
    print(f"\n  ── Sample predictions (test set) ──")
    pred_test = (X_test @ beta_lstsq).numpy().flatten()
    actual_test = y_test.numpy().flatten()
    indices = np.argsort(np.abs(actual_test))[-8:]  # 8 most volatile
    print(f"  {'Actual':>8s}  {'Pred':>8s}  {'Hit?':>6s}")
    print(f"  {'-'*26}")
    for i in sorted(indices):
        hit = "✓" if np.sign(pred_test[i]) == np.sign(actual_test[i]) else "✗"
        print(f"  {actual_test[i]:>8.4f}  {pred_test[i]:>8.4f}  {hit:>6s}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PyTorch linear regression for stocks")
    parser.add_argument("tickers", nargs="*", default=["AAPL"],
                        help="Ticker(s) to train on")
    parser.add_argument("--epochs", type=int, default=1000,
                        help="Gradient descent iterations (default: 1000)")
    parser.add_argument("--lr", type=float, default=0.01,
                        help="Learning rate (default: 0.01)")
    args = parser.parse_args()

    tickers = args.tickers if args.tickers else ["AAPL"]

    for t in tickers:
        try:
            run(t, epochs=args.epochs, lr=args.lr)
        except FileNotFoundError as e:
            print(f"  SKIP {t}: {e}")
