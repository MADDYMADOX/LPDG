#!/usr/bin/env python3
"""Render the three charts for REPORT.md from scripts/backtest_results.csv.

Style: restrained, one message per chart, no dual axes, direct labels over
legends where there are only two series. Palette: categorical slot 1 (blue,
#2a78d6) for the given baseline, slot 2 (orange, #eb6834) for our method --
validated as an adjacent-safe CVD pair.
"""
import pathlib

import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def wrap(text, width):
    return "\n".join(textwrap.wrap(text, width))

HERE = pathlib.Path(__file__).resolve().parent.parent
FIG_DIR = HERE / "report" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

BLUE = "#2a78d6"
ORANGE = "#eb6834"
INK = "#0b0b0b"
SECONDARY_INK = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.size": 11,
    "text.color": INK,
    "axes.edgecolor": GRID,
    "axes.labelcolor": SECONDARY_INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "savefig.facecolor": SURFACE,
})

res = pd.read_csv(HERE / "scripts" / "backtest_results.csv")

# ---------- Chart 1: precision@15 by threshold, baseline vs ours ----------
thresholds = sorted(res["bad_ratio_threshold"].unique())
sigma_prec = [res.loc[res.bad_ratio_threshold == t, "sigma_hits"].mean() / 15 for t in thresholds]
blend_prec = [res.loc[res.bad_ratio_threshold == t, "blend_hits"].mean() / 15 for t in thresholds]

fig, ax = plt.subplots(figsize=(7, 4.2))
x = np.arange(len(thresholds))
w = 0.32
b1 = ax.bar(x - w/2, sigma_prec, w, color=BLUE, label="Given baseline (3-sigma)")
b2 = ax.bar(x + w/2, blend_prec, w, color=ORANGE, label="Our method (telemetry + meter trend)")
for bars, vals in ((b1, sigma_prec), (b2, blend_prec)):
    for rect, v in zip(bars, vals):
        ax.text(rect.get_x() + rect.get_width()/2, v + 0.015, f"{v:.0%}",
                 ha="center", va="bottom", fontsize=9.5, color=INK)
ax.set_xticks(x)
ax.set_xticklabels([f"< {int(t*100)}% of\nmeters read" for t in thresholds])
ax.set_ylabel(wrap("Precision@15 (share of the 15 visited that actually had a problem that week)", 28))
ax.set_ylim(0, 1.08)
ax.spines[["top", "right"]].set_visible(False)
ax.yaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc="upper left", fontsize=9.5)
ax.set_title(wrap("The blend beats the baseline under every definition of “needs a visit” we tested", 62),
             fontsize=12.5, color=INK, pad=14, loc="left")
fig.tight_layout()
fig.savefig(FIG_DIR / "precision_by_threshold.png", dpi=160)
plt.close(fig)

# ---------- Chart 2: weekly cost, 21 backtested weeks, threshold=0.7 ----------
sub = res[res.bad_ratio_threshold == 0.7].copy()
sub["week"] = pd.to_datetime(sub["week"])
sub = sub.sort_values("week")

fig, ax = plt.subplots(figsize=(8.5, 4.2))
ax.plot(sub["week"], sub["sigma_cost"], color=BLUE, linewidth=2, marker="o", markersize=4,
        label="Given baseline (3-sigma)")
ax.plot(sub["week"], sub["blend_cost"], color=ORANGE, linewidth=2, marker="o", markersize=4,
        label="Our method")
ax.fill_between(sub["week"], sub["blend_cost"], sub["sigma_cost"],
                 where=(sub["sigma_cost"] >= sub["blend_cost"]), color=ORANGE, alpha=0.08)
ax.set_ylabel(wrap("Weekly cost (EUR): wasted visits x EUR380 + missed problems x EUR600", 30))
ax.spines[["top", "right"]].set_visible(False)
ax.yaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.legend(frameon=False, loc="upper right", fontsize=9.5)
fig.autofmt_xdate()
ax.set_title(wrap("Our method costs less almost every single week, using “<70% meters read” as the definition", 68),
             fontsize=11.5, color=INK, pad=14, loc="left")
fig.tight_layout()
fig.savefig(FIG_DIR / "weekly_cost.png", dpi=160)
plt.close(fig)

# ---------- Chart 3: saving with bootstrap CI, by threshold ----------
def bootstrap_ci(values, n_boot=5000, seed=0):
    rng = np.random.default_rng(seed)
    n = len(values)
    means = np.array([rng.choice(values, size=n, replace=True).mean() for _ in range(n_boot)])
    return np.percentile(means, 2.5), values.mean(), np.percentile(means, 97.5)

rows = []
for t in thresholds:
    sub = res[res.bad_ratio_threshold == t]
    saving = (sub["sigma_cost"] - sub["blend_cost"]).to_numpy()
    lo, mid, hi = bootstrap_ci(saving)
    rows.append((t, lo, mid, hi))

fig, ax = plt.subplots(figsize=(7, 4.2))
x = np.arange(len(rows))
mids = [r[2] for r in rows]
los = [r[2]-r[1] for r in rows]
his = [r[3]-r[2] for r in rows]
ax.bar(x, mids, color=ORANGE, width=0.5)
ax.errorbar(x, mids, yerr=[los, his], fmt="none", ecolor=INK, elinewidth=1.4, capsize=5)
for i, (t, lo, mid, hi) in enumerate(rows):
    ax.text(i, hi + 90, f"EUR{mid:,.0f}", ha="center", va="bottom", fontsize=9.5, color=INK)
ax.axhline(0, color=MUTED, linewidth=1)
ax.set_xticks(x)
ax.set_xticklabels([f"< {int(t*100)}%" for t, *_ in rows])
ax.set_xlabel("Definition of “needs a visit” (meters-read threshold)")
ax.set_ylabel(wrap("Mean weekly saving vs. baseline (EUR) with 95% bootstrap interval", 28))
ax.set_ylim(0, max(hi for *_ , hi in rows) * 1.18)
ax.spines[["top", "right"]].set_visible(False)
ax.yaxis.grid(True, color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.set_title(wrap("The saving holds regardless of exactly where we draw that line", 62),
             fontsize=12.5, color=INK, pad=14, loc="left")
fig.tight_layout()
fig.savefig(FIG_DIR / "saving_by_threshold.png", dpi=160)
plt.close(fig)

print("wrote:")
for p in sorted(FIG_DIR.glob("*.png")):
    print(" ", p)
