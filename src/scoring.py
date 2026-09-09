"""The ranking method: a transparent blend of a 3-sigma telemetry signal and
a lagged meter-read-success trend.

Design goals, in order:
  1. Leak-free by construction -- every input to a Monday's score is dated
     strictly before that Monday. No feature ever looks at the target week.
  2. Explainable in one sentence, because the live-session round makes you
     change this in front of people. There is no black box to defend.
  3. Beats the given baseline (baseline_3sigma.py) on total cost, backed by
     a leak-free historical backtest -- see scripts/backtest.py.

Method
------
For a given Monday `monday`:

  telemetry signal (fully live through the scored window):
    - trailing 28 days of telemetry strictly before `monday`
    - per gateway, mean/std of offline_duration_sec, disconnection_cnt,
      reboot_cnt over that window
    - count hours in the trailing 7 days where any metric exceeds its own
      gateway's mean by more than SIGMA standard deviations
    -> `flagged_hours`, min-max normalised across that week's gateways

  meter-trend signal (NOTE: only live through 2026-01-26, see LIMITATIONS.md):
    - mean of the two most recent meter_read_success weeks strictly before
      `monday`
    - expressed as a risk score: 1 - trailing_read_ratio (0 = healthy)
    -> `meter_risk`

  blended_score = W_TELEMETRY * flagged_hours_norm + W_METER * meter_risk

Weights were chosen by a leak-free backtest across 21 historical weeks,
not tuned against the scored window: see scripts/backtest.py and
REPORT.md.
"""

from __future__ import annotations

import datetime as dt

import numpy as np
import pandas as pd

from .io import METRICS

SIGMA = 3.0
BASELINE_DAYS = 28
RECENT_DAYS = 7
W_TELEMETRY = 0.7
W_METER = 0.3
TRAILING_METER_WEEKS = 2


def telemetry_flags_for_week(telemetry: pd.DataFrame, monday: dt.date) -> pd.DataFrame:
    """Hours flagged >SIGMA over a gateway's own 28-day baseline, in the
    trailing 7 days before `monday`. Returns one row per gateway that had
    any telemetry in the baseline window (gateways with none are simply
    absent -- callers must decide how to treat "no recent data" explicitly,
    rather than have it silently default to a score of zero)."""
    end = pd.Timestamp(monday)
    end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
    window = telemetry[
        (telemetry["ts"] >= end - dt.timedelta(days=BASELINE_DAYS)) & (telemetry["ts"] < end)
    ]
    if window.empty:
        return pd.DataFrame(columns=["gateway_id", "flagged_hours", "worst_metric"])

    stats = window.groupby("gateway_id")[METRICS].agg(["mean", "std"])
    recent = window[window["ts"] >= end - dt.timedelta(days=RECENT_DAYS)].copy()

    flags = pd.Series(0, index=recent.index, dtype=int)
    worst = pd.Series("", index=recent.index, dtype=object)
    for metric in METRICS:
        mean = recent["gateway_id"].map(stats[(metric, "mean")])
        std = recent["gateway_id"].map(stats[(metric, "std")]).replace(0, np.nan)
        exceeded = ((recent[metric] - mean) > SIGMA * std).fillna(False)
        flags = flags + exceeded.astype(int)
        worst = worst.where(~exceeded | (worst != ""), metric)

    recent["flagged"] = flags
    recent["worst_metric"] = worst
    grouped = recent.groupby("gateway_id").agg(
        flagged_hours=("flagged", "sum"),
        worst_metric=("worst_metric", lambda s: next((v for v in s if v), "")),
    )
    return grouped.reset_index()


def trailing_meter_risk(meter_read_success: pd.DataFrame, monday: dt.date) -> pd.Series:
    """Mean read_ratio of the most recent TRAILING_METER_WEEKS weeks
    strictly before `monday`, expressed as a risk score (higher = worse).
    Returns an empty Series if no qualifying data exists before `monday`
    (this is expected for every scored week after 2026-01-26 stops being
    "recent" -- see LIMITATIONS.md: the feature freezes at its last known
    value rather than silently vanishing or leaking)."""
    end = pd.Timestamp(monday)
    end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
    prior = meter_read_success[meter_read_success["week_start"] < end].copy()
    if prior.empty:
        return pd.Series(dtype=float, name="meter_risk")
    prior = prior.sort_values("week_start")
    recent_weeks = prior["week_start"].drop_duplicates().tail(TRAILING_METER_WEEKS)
    prior = prior[prior["week_start"].isin(recent_weeks)]
    trailing_ratio = prior.groupby("gateway_id")["read_ratio"].mean()
    return (1 - trailing_ratio).clip(lower=0).rename("meter_risk")


def blended_scores_for_week(
    telemetry: pd.DataFrame,
    meter_read_success: pd.DataFrame,
    monday: dt.date,
    w_telemetry: float = W_TELEMETRY,
    w_meter: float = W_METER,
) -> pd.DataFrame:
    """The score used both by the backtest and by predict.py. Returns
    gateway_id, flagged_hours, worst_metric, meter_risk, blended_score."""
    flagged = telemetry_flags_for_week(telemetry, monday)
    if flagged.empty:
        return flagged.assign(meter_risk=pd.Series(dtype=float), blended_score=pd.Series(dtype=float))

    risk = trailing_meter_risk(meter_read_success, monday)
    flagged = flagged.set_index("gateway_id")
    flagged["meter_risk"] = risk.reindex(flagged.index)
    # A gateway with no meter history at all (rare, not every gateway
    # appears in meter_read_success.csv) gets the fleet-median risk rather
    # than 0 -- 0 would assert "known healthy," which is not something we
    # know.
    flagged["meter_risk"] = flagged["meter_risk"].fillna(flagged["meter_risk"].median())
    flagged["meter_risk"] = flagged["meter_risk"].fillna(0.0)

    fh = flagged["flagged_hours"].astype(float)
    span = fh.max() - fh.min()
    fh_norm = (fh - fh.min()) / span if span > 0 else fh * 0
    flagged["flagged_hours_norm"] = fh_norm
    flagged["blended_score"] = w_telemetry * fh_norm + w_meter * flagged["meter_risk"]
    return flagged.reset_index().sort_values("blended_score", ascending=False)


def build_reason(row: pd.Series) -> str:
    metric_label = {
        "offline_duration_sec": "time spent offline",
        "disconnection_cnt": "backhaul disconnections",
        "reboot_cnt": "reboots",
    }.get(row["worst_metric"], "no single metric over 3σ")
    meter_note = ""
    if row["meter_risk"] > 0.3:
        meter_note = f"; recent meter-read success also below plan (risk {row['meter_risk']:.2f})"
    reason = (
        f"{int(row['flagged_hours'])}h beyond 3σ of its own 28-day baseline in the last 7 days "
        f"(worst: {metric_label}){meter_note}."
    )
    return reason[:300]
