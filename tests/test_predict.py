"""End-to-end test: build_predictions() against the real data directory must
produce a file validate_submission.py accepts with zero problems, and must
be idempotent (running twice gives the same ranking)."""

import pathlib
import sys

import pandas as pd

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from src.predict import build_predictions  # noqa: E402
from validate_submission import validate  # noqa: E402

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"


def test_predictions_pass_the_official_validator(tmp_path):
    predictions = build_predictions(DATA)
    out = tmp_path / "predictions.csv"
    predictions.to_csv(out, index=False)
    problems = validate(out)
    assert problems == [], f"validator found problems: {problems}"


def test_predictions_are_deterministic():
    first = build_predictions(DATA)
    second = build_predictions(DATA)
    pd.testing.assert_frame_equal(first.reset_index(drop=True), second.reset_index(drop=True))


def test_every_reason_is_under_300_chars():
    predictions = build_predictions(DATA)
    assert (predictions["reason"].str.len() <= 300).all()
