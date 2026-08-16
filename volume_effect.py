"""
volume_effect.py — Isolate the effect of volume on next-bar price movement.

Single question: does today's volume tell you anything about tomorrow's return?

Two approaches, both pure PyTorch:
  1. torch.linalg.lstsq — closed-form, exact coefficients
  2. torch.optim.SGD    — gradient descent (same answer, iterative)

Usage:
    python volume_effect.py AAPL
    python volume_effect.py AAPL TSLA MSFT
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

# Volume features — everything derivable from price × volume
FEATURE_COLS = [
    "vol_chg_pct",        # raw volume % change vs prior day
    "vol_chg_sign",       # +1 if volume went up, -1 if down
    "rel_volume",         # today's volume / 20-day average
    "vol_x_range",        # volume × intraday range (effort)
    "vol_x_abs_chg",      # volume × absolute close change (force)
    "price_up",           # was today's return positive? (interaction term)
    "vol_x_direction",    # volume_chg × sign(return) — confirms or contradicts
]
TARGET_COL = "target"      # next bar's return %
TRAIN_RATIO = 0.80


# ── Data ──────────────────────────────────────────────────────────────────

def load_bars(ticker: str) -> pd.DataFrame:
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


def build_volume_features(df: pd.DataFrame) -> pd.DataFrame:
    """Engineer volume-centric features from raw OHLCV bars."""
    df = df.copy()

    c = df["Close"]
    o = df["Open"]
    h = df["High"]
    l = df["Low"]
    v = df["Volume"]

    prev_c = c.shift(1)
    prev_v = v.shift(1)

    # Daily return
    ret = (c - prev_c) / prev_c * 100

    # Volume change %
    df["vol_chg_pct"] = ((v - prev_v) / prev_v * 100).round(4)

    # Volume direction
    df["vol_chg_sign"] = np.where(df["vol_chg_pct"] >= 0, 1.0, -1.0)

    # Relative volume (today / 20-day average)
    df["rel_volume"] = (v / v.rolling(20).mean()).round(4)

    # Volume × range — "effort": how much volume drove the intraday swing
    df["vol_x_range"] = (v * (h - l) / l).round(4)

    # Volume × absolute close change — "force": volume-weighted price impact
    df["vol_x_abs_chg"] = (v * (c - prev_c).abs() / prev_c).round(4)

    # Interaction: was today up?
    df["price_up"] = np.where(ret >= 0, 1.0, -1.0)

    # Volume direction × price direction — confirms (+1) or contradicts (-1)
    df["vol_x_direction"] = df["vol_chg_sign"] * df["price_up"]

    # Target
    df[TARGET_COL] = ret.shift(-1)

    return df


# ── Prepare tensors ───────────────────────────────────────────────────────

def prepare_tensors(df: pd.DataFrame):
    cols = FEATURE_COLS + [TARGET_COL]
    clean = df[cols].dropna()

    X_np = clean[FEATURE_COLS].values.astype(np.float32)
    y_np = clean[TARGET_COL].values.astype(np.float32).reshape(-1, 1)

    # Standardise
    X_mean = X_np.mean(axis=0, keepdims=True)
    X_std = X_np.std(axis=0, keepdims=True)
    X_std[X_std == 0] = 1.0
    X_np = (X_np - X_mean) / X_std

    split = int(len(X_np) * TRAIN_RATIO)
    return (
        torch.tensor(X_np[:split]), torch.tensor(y_np[:split]),
        torch.tensor(X_np[split:]), torch.tensor(y_np[split:]),
        X_mean, X_std, clean,
    )


# ── Approach 1: Closed-form ───────────────────────────────────────────────

def solve_closed(X: torch.Tensor, y: torch.Tensor) -> torch.Tensor:
    """β = (XᵀX)⁻¹Xᵀy via SVD."""
    return torch.linalg.lstsq(X, y).solution


# ── Approach 2: Gradient descent ──────────────────────────────────────────

class VolumeModel(nn.Module):
    def __init__(self, n: int):
        super().__init__()
        self.beta = nn.Parameter(torch.zeros(n, 1))

    def forward(self, x):
        return x @ self.beta


def train_gd(X, y, epochs=800, lr=0.05):
    model = VolumeModel(X.shape[1])
    opt = torch.optim.SGD(model.parameters(), lr=lr)
    loss_fn = nn.MSELoss()
    history = []
    for e in range(epochs):
        opt.zero_grad()
        loss = loss_fn(model(X), y)
        loss.backward()
        opt.step()
        history.append(loss.item())
    return model.beta.detach().numpy(), history


# ── Display ────────────────────────────────────────────────────────────────

def report(ticker: str, beta: np.ndarray, X_test: torch.Tensor,
           y_test: torch.Tensor, gd_history: list[float] | None = None):
    """Print coefficients, metrics, and interpretation."""
    pred = (X_test @ torch.tensor(beta)).numpy()
    actual = y_test.numpy()

    ss_res = ((actual - pred) ** 2).sum()
    ss_tot = ((actual - actual.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    dir_acc = np.mean(np.sign(pred) == np.sign(actual))

    beta_flat = beta.flatten()

    print(f"\n{'='*64}")
    print(f"  {ticker} — Volume → Price Effect")
    print(f"{'='*64}")
    print(f"  R² = {float(r2):.4f}     (fraction of next-day return explained by volume)")
    print(f"  Directional accuracy = {float(dir_acc):.2%}")
    print(f"  Test bars = {len(X_test)}")
    if gd_history:
        print(f"  GD final loss = {gd_history[-1]:.6f}")

    # Ranked coefficients
    pairs = sorted(zip(FEATURE_COLS, beta_flat), key=lambda x: abs(x[1]), reverse=True)
    print(f"\n  {'Feature':>22s}  {'β':>10s}   Interpretation")
    print(f"  {'-'*60}")
    for name, coef in pairs:
        s = "+" if coef >= 0 else "-"
        interp = _interpret(name, coef)
        print(f"  {name:>22s}  {s}{abs(coef):.6f}   {interp}")

    # Volume buckets — does the effect concentrate at extremes?
    print(f"\n  ── Prediction by volume regime ──")
    vol_chg = X_test[:, 0].numpy()  # first feature = vol_chg_pct (standardised)
    regimes = [
        ("Volume crash  (< -2σ)",  vol_chg < -2),
        ("Volume low     (-2σ..-1σ)", (vol_chg >= -2) & (vol_chg < -1)),
        ("Volume normal  (-1σ..+1σ)", (vol_chg >= -1) & (vol_chg <= 1)),
        ("Volume high    (+1σ..+2σ)", (vol_chg > 1) & (vol_chg <= 2)),
        ("Volume surge   (> +2σ)",  vol_chg > 2),
    ]
    for label, mask in regimes:
        n = mask.sum()
        if n > 0:
            avg_pred = float(pred[mask].mean())
            avg_act = float(actual[mask].mean())
            hit = np.mean(np.sign(pred[mask]) == np.sign(actual[mask]))
            print(f"  {label:>28s}  n={n:>4d}  "
                  f"pred={avg_pred:>+.4f}%  actual={avg_act:>+.4f}%  "
                  f"hit={hit:.1%}")

    print()


def _interpret(name: str, coef: float) -> str:
    """Human-readable interpretation of each coefficient."""
    sign = "higher" if coef >= 0 else "lower"
    maps = {
        "vol_chg_pct":     f"{sign} next return — {'momentum' if coef >= 0 else 'reversal'} signal",
        "vol_chg_sign":    f"rising volume → {sign} return",
        "rel_volume":      f"volume relative to average → {sign} return",
        "vol_x_range":     f"effort (vol×range) → {sign} return",
        "vol_x_abs_chg":   f"force (vol×|chg|) → {sign} return",
        "price_up":        f"up days → {sign} return next day",
        "vol_x_direction": f"volume confirms price → {sign} return",
    }
    return maps.get(name, "")


# ── Main ──────────────────────────────────────────────────────────────────

def run(ticker: str):
    raw = load_bars(ticker)
    df = build_volume_features(raw)
    X_tr, y_tr, X_te, y_te, _, _, _ = prepare_tensors(df)

    print(f"\n  {ticker}: {len(raw)} bars → "
          f"{len(X_tr)} train / {len(X_te)} test  "
          f"({len(FEATURE_COLS)} volume features)")

    # Closed-form
    beta_cf = solve_closed(X_tr, y_tr).numpy()
    report(ticker, beta_cf, X_te, y_te)


if __name__ == "__main__":
    tickers = sys.argv[1:] if len(sys.argv) > 1 else ["AAPL"]
    for t in tickers:
        try:
            run(t)
        except FileNotFoundError as e:
            print(f"  SKIP {t}: {e}")
