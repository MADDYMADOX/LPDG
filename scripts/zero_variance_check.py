#!/usr/bin/env python3
"""Quantify the blind spot in the given baseline_3sigma.py method.

The baseline flags an hour when a metric exceeds its gateway's own 28-day mean
by 3 standard deviations. Where a gateway's reboot_cnt never varies over that
window, the standard deviation is 0, the z-score is undefined, and no value --
however extreme -- can ever cross the threshold. That gateway is invisible on
that metric.

How many gateways this affects depends on which 28-day window you look at, so
this prints the figure per window rather than quoting one number as if it were
a constant. Run:

    python scripts/zero_variance_check.py
"""

from __future__ import annotations

import datetime as dt
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.io import METRICS, load_telemetry  # noqa: E402
from src.predict import SUBMISSION_N_WEEKS, SUBMISSION_START, week_starts  # noqa: E402
from src.scoring import BASELINE_DAYS  # noqa: E402

# A few earlier Mondays for contrast, so the spread over time is visible rather
# than implied.
HISTORICAL_MONDAYS = [dt.date(2025, 10, 6), dt.date(2025, 12, 1), dt.date(2026, 1, 5)]


def zero_variance_share(telemetry: pd.DataFrame, monday: dt.date, metric: str) -> tuple[int, int]:
    """(gateways with no variance in `metric`, gateways with any data) for the
    28-day window strictly before `monday` -- the same window the baseline and
    our own scorer use."""
    end = pd.Timestamp(monday, tz="UTC")
    window = telemetry[
        (telemetry["ts"] >= end - dt.timedelta(days=BASELINE_DAYS)) & (telemetry["ts"] < end)
    ]
    std = window.groupby("gateway_id")[metric].std()
    if std.empty:
        return 0, 0
    # A NaN std means a single observation: also unflaggable, same blind spot.
    return int((std.fillna(0) == 0).sum()), int(len(std))


def main() -> int:
    data_dir = pathlib.Path(__file__).resolve().parent.parent / "data"
    telemetry = load_telemetry(data_dir)

    scored = week_starts(SUBMISSION_START, SUBMISSION_N_WEEKS)
    mondays = HISTORICAL_MONDAYS + scored

    print(f"Gateways that cannot be flagged, per {BASELINE_DAYS}-day baseline window")
    print(f"(zero or undefined variance => no z-score => never exceeds {3} sigma)\n")
    header = f"{'window before':<14}{'gateways':>9}" + "".join(f"{m:>22}" for m in METRICS)
    print(header)
    print("-" * len(header))

    shares: dict[str, list[float]] = {m: [] for m in METRICS}
    for monday in mondays:
        marker = "*" if monday in scored else " "
        cells, total = "", 0
        for metric in METRICS:
            blind, total = zero_variance_share(telemetry, monday, metric)
            pct = 100 * blind / total if total else 0.0
            if monday in scored:
                shares[metric].append(pct)
            cells += f"{f'{blind} ({pct:.1f}%)':>22}"
        print(f"{monday.isoformat()}{marker:<3}{total:>9}{cells}")

    print("\n* = one of the eight scored Mondays\n")
    for metric in METRICS:
        lo, hi = min(shares[metric]), max(shares[metric])
        mean = sum(shares[metric]) / len(shares[metric])
        print(f"across the scored window, {metric:<22} {mean:5.1f}% blind  ({lo:.1f}-{hi:.1f}%)")

    print(
        "\nThis is why the ranking does not rest on reboot_cnt alone: the metric with\n"
        "the largest blind spot is also the one the given baseline leans on hardest."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
