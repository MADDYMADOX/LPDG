"""End-to-end test: build_predictions() against the real data directory must
produce a file validate_submission.py accepts with zero problems, and must
be idempotent (running twice gives the same ranking).

The window tests at the bottom build their own telemetry and run without the
dataset, because "the pipeline follows the data forward" is the behaviour the
live session exercises and it should not need 105 MB to check.
"""

import datetime as dt
import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.predict import SUBMISSION_START, latest_scorable_monday, build_predictions  # noqa: E402
from validate_submission import validate  # noqa: E402

from .conftest import DATA, requires_dataset  # noqa: E402


@requires_dataset
def test_predictions_pass_the_official_validator(tmp_path):
    predictions = build_predictions(DATA)
    out = tmp_path / "predictions.csv"
    predictions.to_csv(out, index=False)
    problems = validate(out)
    assert problems == [], f"validator found problems: {problems}"


@requires_dataset
def test_predictions_are_deterministic():
    first = build_predictions(DATA)
    second = build_predictions(DATA)
    pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))


@requires_dataset
def test_every_reason_is_under_300_chars():
    predictions = build_predictions(DATA)
    assert (predictions["reason"].str.len() <= 300).all()


@requires_dataset
def test_default_window_is_the_eight_submission_weeks():
    """The validator hard-codes these dates, so the default run must not drift
    off them however much data is present."""
    weeks = sorted(build_predictions(DATA)["week_start"].unique())
    assert len(weeks) == 8
    assert weeks[0] == SUBMISSION_START.isoformat()
    assert weeks[-1] == (SUBMISSION_START + dt.timedelta(days=49)).isoformat()


def test_latest_scorable_monday_follows_the_data_forward():
    """Regression test for the hard-coded-window trap: when a new month is
    dropped into data/, the pipeline must be able to find it rather than
    staying pinned to March 2026."""
    telemetry = pd.DataFrame(
        {"ts": pd.to_datetime(["2026-04-28T13:00:00Z", "2026-04-30T17:00:00Z"], utc=True)}
    )
    # 2026-04-30 is a Thursday; the Monday of that week is 2026-04-27.
    assert latest_scorable_monday(telemetry) == dt.date(2026, 4, 27)
