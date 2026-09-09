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
SCORED_WEEKS = [dt.date(2026, 2, 2) + dt.timedelta(days=7 * i) for i in range(8)]


def build_predictions(data_dir: pathlib.Path) -> pd.DataFrame:
    telemetry = load_telemetry(data_dir)
    meter = load_meter_read_success(data_dir)

    rows = []
    for monday in SCORED_WEEKS:
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
    args = parser.parse_args(argv)

    try:
        predictions = build_predictions(args.data)
    except DataQualityError as exc:
        print(f"data quality problem, refusing to write predictions: {exc}", file=sys.stderr)
        return 1

    predictions.to_csv(args.out, index=False)
    print(f"wrote {args.out} -- {len(predictions)} rows over {predictions.week_start.nunique()} weeks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
