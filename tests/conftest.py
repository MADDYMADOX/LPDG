"""Shared test fixtures.

The 105 MB dataset is not ours to ship, so it is git-ignored and absent from a
fresh clone. Tests that genuinely need it are marked `requires_dataset` and
skip cleanly rather than erroring; the scoring tests build their own synthetic
fixtures and run anywhere.
"""

import pathlib

import pytest

DATA = pathlib.Path(__file__).resolve().parent.parent / "data"

requires_dataset = pytest.mark.skipif(
    not DATA.exists(),
    reason="full dataset not present -- put the provided data/ folder at the repo root",
)
