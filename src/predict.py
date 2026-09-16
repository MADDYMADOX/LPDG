#!/usr/bin/env python3
"""Build predictions.csv for the LPDG Innovation Hub challenge.

Usage:
    python -m src.predict --data data --out predictions.csv

Method: see src/scoring.py docstring. In one line -- rank gateways each
Monday by a leak-free blend of a 3-sigma telemetry-anomaly signal and a
lagged meter-read-success trend, take the top 15.
"""

from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import sys

import pandas as pd

from .io import DataQualityError, load_meter_read_success, load_telemetry
from .scoring import blended_scores_for_week, build_reason

VISITS_PER_WEEK = 15

# The submission window fixed by the challenge: eight Mondays, 2026-02-02 to
# 2026-03-23. validate_submission.py hard-codes these same dates, so the
# default run must produce exactly them. The window is a parameter rather than
# a constant in the loop because the live session drops in a new month and asks
# the pipeline to run on it -- see --auto-window below.
SUBMISSION_START = dt.date(2026, 2, 2)
SUBMISSION_N_WEEKS = 8


def week_starts(start: dt.date, n_weeks: int) -> list[dt.date]:
    return [start + dt.timedelta(days=7 * i) for i in range(n_weeks)]


def latest_scorable_monday(telemetry: pd.DataFrame) -> dt.date:
    """The most recent Monday that has telemetry before it.

    Used by --auto-window so a new monthly partition is picked up without
    editing code. Scoring a Monday only ever reads data strictly before it,
    so the last Monday at or before the final timestamp is the latest one we
    can score with a full trailing window behind it.
    """
    last = telemetry["ts"].max()
    if pd.isna(last):
        raise DataQualityError("telemetry contains no usable timestamps")
    last_date = last.date()
    return last_date - dt.timedelta(days=last_date.weekday())


def build_predictions(
    data_dir: pathlib.Path,
    start: dt.date = SUBMISSION_START,
    n_weeks: int = SUBMISSION_N_WEEKS,
    auto_window: bool = False,
) -> pd.DataFrame:
    telemetry = load_telemetry(data_dir)
    meter = load_meter_read_success(data_dir)

    newest_monday = latest_scorable_monday(telemetry)
    if auto_window:
        start = newest_monday - dt.timedelta(days=7 * (n_weeks - 1))
    scored_weeks = week_starts(start, n_weeks)

    # Do not let a newer partition sit in data/ unnoticed. Silently ignoring a
    # month someone just dropped in is the failure mode the brief warns about,
    # so say it out loud and name the flag that scores it.
    if newest_monday > scored_weeks[-1]:
        print(
            f"note: telemetry runs to {telemetry['ts'].max().date()}, past the end of the "
            f"scored window ({scored_weeks[-1]}). Scoring the fixed submission window. "
            f"Use --auto-window to score the most recent {n_weeks} weeks instead.",
            file=sys.stderr,
        )

    rows = []
    for monday in scored_weeks:
        scored = blended_scores_for_week(telemetry, meter, monday)
        if len(scored) < VISITS_PER_WEEK:
            raise DataQualityError(
                f"only {len(scored)} gateways have telemetry before {monday}; "
                f"cannot fill {VISITS_PER_WEEK} visit slots"
            )
        top = scored.head(VISITS_PER_WEEK)
        for rank, (_, row) in enumerate(top.iterrows(), 1):
            rows.append(
                {
                    "week_start": monday.isoformat(),
                    "rank": rank,
                    "gateway_id": row["gateway_id"],
                    "score": round(float(row["blended_score"]), 6),
                    "reason": build_reason(row),
                }
            )
    return pd.DataFrame(rows)


def main(argv: list[str] | None = None) -> int:
    here = pathlib.Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=pathlib.Path, default=here / "data")
    parser.add_argument("--out", type=pathlib.Path, default=here / "predictions.csv")
    parser.add_argument(
        "--start",
        type=dt.date.fromisoformat,
        default=SUBMISSION_START,
        help="Monday the scored window starts on (default: the submission window)",
    )
    parser.add_argument(
        "--weeks", type=int, default=SUBMISSION_N_WEEKS, help="how many weeks to score"
    )
    parser.add_argument(
        "--auto-window",
        action="store_true",
        help="score the most recent --weeks Mondays the data supports instead of "
        "the fixed submission window; use this when a newer month has been added",
    )
    args = parser.parse_args(argv)

    try:
        predictions = build_predictions(
            args.data, start=args.start, n_weeks=args.weeks, auto_window=args.auto_window
        )
    except DataQualityError as exc:
        print(f"data quality problem, refusing to write predictions: {exc}", file=sys.stderr)
        return 1

    # Write through a temporary file so a failure never leaves a half-written
    # predictions.csv behind, and pin the line terminator so the bytes are the
    # same whether this runs on Windows or in the Linux container.
    tmp = args.out.with_suffix(args.out.suffix + ".tmp")
    predictions.to_csv(tmp, index=False, lineterminator="\n")
    tmp.replace(args.out)
    print(f"wrote {args.out} -- {len(predictions)} rows over {predictions.week_start.nunique()} weeks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
