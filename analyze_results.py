"""
analyze_results.py — Read backtest results JSON and generate matplotlib charts.

Usage:
    python analyze_results.py                          # latest results file
    python analyze_results.py results_20260721.json    # specific file
    python analyze_results.py --csv results.csv        # read CSV instead

Output:
    backtest_results/analysis_<stamp>.png   — multi-panel chart figure
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

# ── Config ────────────────────────────────────────────────────────────────

RESULTS_DIR = Path("backtest_results")
FIGURE_DPI = 150
FIGURE_SIZE = (18, 22)

# ── Palette (from validated reference) ────────────────────────────────────

SURFACE = "#fcfcfb"
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"

BLUE_RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef",
             "#6da7ec", "#5598e7", "#3987e5", "#2a78d6",
             "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"]

GREEN_GOOD = "#0ca30c"
RED_CRITICAL = "#d03b3b"
ORANGE = "#eb6834"
MAGENTA = "#e87ba4"

# ── Data loading ──────────────────────────────────────────────────────────

def load_latest_results() -> dict:
    """Load the most recent results JSON from RESULTS_DIR."""
    json_files = sorted(RESULTS_DIR.glob("results_*.json"))
    if not json_files:
        # Try CSV
        csv_files = sorted(RESULTS_DIR.glob("results_*.csv"))
        if csv_files:
            return _load_from_csv(csv_files[-1])
        raise FileNotFoundError(f"No results files found in {RESULTS_DIR}")

    path = json_files[-1]
    print(f"Loading: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def load_specific(path: str) -> dict:
    """Load a specific results file (JSON or CSV)."""
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"File not found: {path}")
    if p.suffix == ".csv":
        return _load_from_csv(p)
    print(f"Loading: {p}")
    return json.loads(p.read_text(encoding="utf-8"))


def _load_from_csv(path: Path) -> dict:
    """Wrap a CSV results file into the same shape as JSON."""
    print(f"Loading: {path}")
    df = pd.read_csv(path)
    tickers = []
    for _, row in df.iterrows():
        d = row.to_dict()
        # Convert NaN to None
        for k, v in d.items():
            if isinstance(v, float) and np.isnan(v):
                d[k] = None
        tickers.append(d)
    return {"tickers": tickers, "summary": {}, "config": {}}


def to_dataframe(data: dict) -> pd.DataFrame:
    """Extract the tickers list into a clean DataFrame, dropping errors."""
    rows = []
    for t in data.get("tickers", []):
        if t.get("error"):
            continue
        rows.append({
            "ticker": t["ticker"],
            "total_trades": t.get("total_trades", 0),
            "winning_trades": t.get("winning_trades", 0),
            "losing_trades": t.get("losing_trades", 0),
            "win_rate": t.get("win_rate", 0.0),
            "avg_gain_per_day_pct": t.get("avg_gain_per_day_pct", 0.0),
            "total_return_pct": t.get("total_return_pct", 0.0),
            "max_drawdown_pct": t.get("max_drawdown_pct", 0.0),
            "total_commission": t.get("total_commission", 0.0),
            "gross_pnl": t.get("gross_pnl", 0.0),
            "net_pnl": t.get("net_pnl", 0.0),
            "signal_count": t.get("signal_count", 0),
            "bar_count": t.get("bar_count", 0),
        })
    df = pd.DataFrame(rows)
    return df[df["total_trades"] > 0].copy()


# ── Styling helpers ───────────────────────────────────────────────────────

def style_axes(ax, xlabel="", ylabel="", title=""):
    """Apply the house style to a matplotlib Axes."""
    ax.set_facecolor(SURFACE)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(BASELINE)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(colors=INK_MUTED, labelsize=8)
    ax.xaxis.label.set_color(INK_SECONDARY)
    ax.yaxis.label.set_color(INK_SECONDARY)
    ax.title.set_color(INK_PRIMARY)
    ax.title.set_fontweight("bold")
    ax.title.set_fontsize(11)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=9)
    if title:
        ax.set_title(title, pad=10)
    ax.grid(axis="y", color=GRIDLINE, linewidth=0.5, alpha=0.7)
    ax.set_axisbelow(True)


def save_figure(fig, stamp: str) -> Path:
    """Save figure to disk and return path."""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out = RESULTS_DIR / f"analysis_{stamp}.png"
    fig.savefig(out, dpi=FIGURE_DPI, bbox_inches="tight",
                facecolor=SURFACE, edgecolor="none")
    print(f"Saved: {out}")
    return out


# ── Chart builders ────────────────────────────────────────────────────────

def histogram(ax, values, bins=40, title="", xlabel="", ylabel="Count",
              color=BLUE_RAMP[5], edge_color=SURFACE):
    """Plot a styled histogram."""
    ax.hist(values, bins=bins, color=color, edgecolor=edge_color,
            linewidth=0.5, alpha=0.88)
    style_axes(ax, xlabel=xlabel, ylabel=ylabel, title=title)

    # Add a thin median line
    if len(values) > 0:
        median = np.median(values)
        ylim = ax.get_ylim()
        ax.axvline(median, color=INK_PRIMARY, linewidth=1.2, linestyle="--", alpha=0.7)
        ax.text(median, ylim[1] * 0.95, f"  median={median:.2f}",
                fontsize=7, color=INK_SECONDARY, va="top")


def scatter(ax, x, y, c=None, title="", xlabel="", ylabel="",
            cmap_name="", alpha=0.55, s=14):
    """Plot a styled scatter plot."""
    if c is not None and len(c) > 0:
        points = ax.scatter(x, y, c=c, cmap=cmap_name, alpha=alpha,
                            s=s, edgecolors="none")
        cbar = plt.colorbar(points, ax=ax, shrink=0.82, pad=0.02)
        cbar.outline.set_visible(False)
        cbar.ax.tick_params(labelsize=7, colors=INK_MUTED)
    else:
        ax.scatter(x, y, color=BLUE_RAMP[5], alpha=alpha, s=s,
                   edgecolors="none")

    # Reference lines
    if title and "return" in title.lower():
        ax.axhline(0, color=BASELINE, linewidth=0.8, linestyle="-")
        ax.axvline(0.5, color=BASELINE, linewidth=0.8, linestyle="-")

    style_axes(ax, xlabel=xlabel, ylabel=ylabel, title=title)


def barh(ax, labels, values, title="", xlabel="", colors=None):
    """Plot a styled horizontal bar chart."""
    n = len(labels)
    if colors is None:
        colors = [BLUE_RAMP[5]] * n
    bars = ax.barh(range(n), values, height=0.62, color=colors,
                   edgecolor=SURFACE, linewidth=0.5)
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=7.5, color=INK_SECONDARY)
    style_axes(ax, xlabel=xlabel, title=title)

    # Direct-label each bar
    for i, (bar, val) in enumerate(zip(bars, values)):
        x_pos = bar.get_width()
        if val >= 0:
            label_x = x_pos + (max(values) * 0.01)
            ha = "left"
        else:
            label_x = x_pos - (max(abs(v) for v in values) * 0.01)
            ha = "right"
        ax.text(label_x, bar.get_y() + bar.get_height() / 2,
                f"${val:,.0f}", fontsize=7, color=INK_SECONDARY,
                va="center", ha=ha)


# ── Main figure ───────────────────────────────────────────────────────────

def build_figure(df: pd.DataFrame) -> plt.Figure:
    """Construct the full multi-panel analysis figure."""
    fig = plt.figure(figsize=FIGURE_SIZE, facecolor=SURFACE)
    fig.suptitle("Drop-Rebound Strategy — Backtest Analysis",
                 fontsize=15, fontweight="bold", color=INK_PRIMARY, y=0.985)

    # Subplot grid: 4 rows x 3 cols
    gs = fig.add_gridspec(4, 3, hspace=0.45, wspace=0.35,
                          top=0.95, bottom=0.03, left=0.06, right=0.97)

    # Config text in top-right
    ax_info = fig.add_subplot(gs[0, 2])
    ax_info.axis("off")
    info_lines = [
        f"Tickers traded: {len(df)}",
        f"Total trades:   {df['total_trades'].sum():,}",
        f"Win rate (mean): {df['win_rate'].mean():.1%}",
        f"Net P&L (sum):  ${df['net_pnl'].sum():,.0f}",
        f"Return (mean):  {df['total_return_pct'].mean():.2f}%",
        f"Return (med):   {df['total_return_pct'].median():.2f}%",
        f"Gain/day (mean):{df['avg_gain_per_day_pct'].mean():.3f}%",
        f"Positive return: {(df['total_return_pct'] > 0).sum()}/{len(df)}",
    ]
    for i, line in enumerate(info_lines):
        ax_info.text(0.05, 0.92 - i * 0.11, line, transform=ax_info.transAxes,
                     fontsize=9, color=INK_SECONDARY, fontfamily="monospace",
                     va="top")

    # ── Row 0: histograms ──────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0, 0])
    histogram(ax1, df["total_return_pct"], bins=50,
              title="Distribution of Total Return (%)",
              xlabel="Total return (%)",
              color=BLUE_RAMP[5])

    ax2 = fig.add_subplot(gs[0, 1])
    histogram(ax2, df["win_rate"] * 100, bins=30,
              title="Distribution of Win Rate (%)",
              xlabel="Win rate (%)",
              color=BLUE_RAMP[5])

    # ── Row 1: more distributions ──────────────────────────────────────
    ax3 = fig.add_subplot(gs[1, 0])
    net = df["net_pnl"]
    counts, bins_net = np.histogram(net, bins=50)
    bin_colors = [GREEN_GOOD if (bins_net[i] + bins_net[i+1]) / 2 >= 0
                  else RED_CRITICAL for i in range(len(counts))]
    ax3.bar(bins_net[:-1], counts, width=np.diff(bins_net),
            color=bin_colors, edgecolor=SURFACE, linewidth=0.5,
            alpha=0.85, align="edge")
    ax3.axvline(0, color=INK_PRIMARY, linewidth=0.8, linestyle="-")
    style_axes(ax3, xlabel="Net P&L ($)", ylabel="Count",
               title="Distribution of Net P&L ($)")

    ax4 = fig.add_subplot(gs[1, 1])
    histogram(ax4, df["avg_gain_per_day_pct"], bins=50,
              title="Distribution of Avg Gain / Day (%)",
              xlabel="Avg gain per day (%)",
              color=BLUE_RAMP[5])

    ax5 = fig.add_subplot(gs[1, 2])
    histogram(ax5, df["max_drawdown_pct"], bins=40,
              title="Distribution of Max Drawdown (%)",
              xlabel="Max drawdown (%)",
              color=ORANGE)

    # ── Row 2: scatter plots ───────────────────────────────────────────
    ax6 = fig.add_subplot(gs[2, 0])
    scatter(ax6, df["win_rate"] * 100, df["total_return_pct"],
            c=df["total_trades"], cmap_name="Blues",
            title="Win Rate vs Total Return",
            xlabel="Win rate (%)", ylabel="Total return (%)")

    ax7 = fig.add_subplot(gs[2, 1])
    scatter(ax7, df["total_trades"], df["net_pnl"],
            c=df["win_rate"] * 100, cmap_name="Blues",
            title="Trade Count vs Net P&L",
            xlabel="Number of trades", ylabel="Net P&L ($)")

    ax8 = fig.add_subplot(gs[2, 2])
    scatter(ax8, df["avg_gain_per_day_pct"], df["total_return_pct"],
            c=df["win_rate"] * 100, cmap_name="Blues",
            title="Gain/Day vs Total Return",
            xlabel="Avg gain/day (%)", ylabel="Total return (%)")

    # ── Row 3: top & bottom bar charts ──────────────────────────────────
    # Top 10 by net P&L
    ax9 = fig.add_subplot(gs[3, 0:2])
    top10 = df.nlargest(10, "net_pnl")
    bottom5 = df.nsmallest(5, "net_pnl")
    combined = pd.concat([top10, bottom5]).drop_duplicates()

    labels = [f"{r.ticker}  ({r.total_trades}t)" for _, r in combined.iterrows()]
    values = combined["net_pnl"].values
    bar_colors = [GREEN_GOOD if v >= 0 else RED_CRITICAL for v in values]
    barh(ax9, labels, values,
         title="Top 10 + Bottom 5 by Net P&L ($)",
         xlabel="Net P&L ($)",
         colors=bar_colors)

    # Trade count distribution (small)
    ax10 = fig.add_subplot(gs[3, 2])
    histogram(ax10, df["total_trades"], bins=40,
              title="Distribution of Trade Count",
              xlabel="Number of trades",
              color=BLUE_RAMP[4])

    return fig


# ── Entry point ───────────────────────────────────────────────────────────

def main():
    # Parse args
    if len(sys.argv) > 1:
        if sys.argv[1] == "--csv" and len(sys.argv) > 2:
            data = load_specific(sys.argv[2])
        else:
            data = load_specific(sys.argv[1])
    else:
        data = load_latest_results()

    df = to_dataframe(data)

    if df.empty:
        print("No tickers with trades found — nothing to plot.")
        sys.exit(1)

    print(f"Plotting {len(df)} tickers "
          f"(total {df['total_trades'].sum():,} trades, "
          f"net P&L ${df['net_pnl'].sum():,.0f})")

    fig = build_figure(df)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = save_figure(fig, stamp)
    plt.close(fig)
    print(f"Done.  Open: {out_path}")


if __name__ == "__main__":
    main()
