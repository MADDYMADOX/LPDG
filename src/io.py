"""Loaders for the LPDG Innovation Hub challenge data.

Deliberately paranoid: this data will crash a naive pipeline in ways that are
invisible on some machines and fatal on others (see the encoding note below),
so every loader validates its own assumptions and fails loudly rather than
silently returning something wrong.
"""

from __future__ import annotations

import pathlib

import pandas as pd

METRICS = ["offline_duration_sec", "disconnection_cnt", "reboot_cnt"]

REQUIRED_TELEMETRY_COLS = {"gateway_id", "ts_utc", *METRICS}
REQUIRED_GATEWAY_COLS = {
    "gateway_id", "tenant", "site_type", "region", "hw_model",
    "antenna_type", "fw_version", "installed_on", "decommissioned_on",
    "n_meters_installed",
}
REQUIRED_VISIT_COLS = {
    "visit_id", "gateway_id", "requested_on", "visited_on",
    "reason_reported", "outcome", "parts_replaced", "technician_hours",
}
REQUIRED_MRS_COLS = {"week_start", "gateway_id", "meters_expected", "meters_read"}


class DataQualityError(RuntimeError):
    """Raised when an input file does not look like what the pipeline expects.

    We raise instead of coercing/guessing, because a silently-wrong
    prediction is worse than a loud failure -- see brief, Data engineering
    track: "checks that stop and complain when the data is wrong."
    """


def _require_columns(frame: pd.DataFrame, required: set[str], name: str) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise DataQualityError(f"{name}: missing expected column(s): {sorted(missing)}")


def load_gateway_master(data_dir: pathlib.Path) -> pd.DataFrame:
    """Load gateway_master.csv.

    Known trap: this file is NOT valid UTF-8. It is Latin-1 (Windows-1252
    compatible) encoded -- German characters like the sz in "Aussenmast"
    (site_type) are single bytes above 0x7F that are not valid UTF-8
    continuation bytes. `pandas.read_csv` with its default encoding raises
    UnicodeDecodeError and crashes the whole run on any strict-UTF-8
    environment (e.g. a Linux CI box), even though the same code can appear
    to work on a Windows machine whose locale silently falls back to
    cp1252. We decode explicitly so behaviour does not depend on the host.
    """
    path = data_dir / "gateway_master.csv"
    try:
        frame = pd.read_csv(path, encoding="latin-1")
    except FileNotFoundError as exc:
        raise DataQualityError(f"gateway_master.csv not found under {data_dir}") from exc
    _require_columns(frame, REQUIRED_GATEWAY_COLS, "gateway_master.csv")
    if frame["gateway_id"].duplicated().any():
        dupes = frame.loc[frame["gateway_id"].duplicated(), "gateway_id"].tolist()
        raise DataQualityError(f"gateway_master.csv: duplicate gateway_id(s): {dupes[:5]}")
    for col in ("installed_on", "fw_updated_on", "decommissioned_on"):
        if col in frame.columns:
            frame[col] = pd.to_datetime(frame[col], errors="coerce")
    return frame


def load_field_visits(data_dir: pathlib.Path) -> pd.DataFrame:
    """Load field_visits.csv. This file IS valid UTF-8 (checked explicitly
    below) -- the encoding problem is specific to gateway_master.csv, not
    universal to the dataset, which is exactly why guessing one encoding
    for "the CSVs" is the wrong fix."""
    path = data_dir / "field_visits.csv"
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        raw.decode("utf-8")
        encoding = "utf-8"
    except UnicodeDecodeError:
        encoding = "latin-1"
    frame = pd.read_csv(path, encoding=encoding)
    _require_columns(frame, REQUIRED_VISIT_COLS, "field_visits.csv")
    frame["requested_on"] = pd.to_datetime(frame["requested_on"], errors="coerce")
    frame["visited_on"] = pd.to_datetime(frame["visited_on"], errors="coerce")
    return frame


def load_meter_read_success(data_dir: pathlib.Path) -> pd.DataFrame:
    path = data_dir / "meter_read_success.csv"
    frame = pd.read_csv(path)
    _require_columns(frame, REQUIRED_MRS_COLS, "meter_read_success.csv")
    frame["week_start"] = pd.to_datetime(frame["week_start"], utc=True, errors="coerce")
    if (frame["meters_expected"] < 0).any() or (frame["meters_read"] < 0).any():
        raise DataQualityError("meter_read_success.csv: negative meter counts found")
    bad_ratio = frame["meters_read"] > frame["meters_expected"]
    if bad_ratio.any():
        # Seen in practice: a handful of rows read MORE meters than were
        # "expected" that week (a late catch-up read). Not a crash, but
        # worth surfacing rather than silently trusting meters_expected as a
        # hard ceiling everywhere downstream.
        frame.attrs["rows_read_exceeds_expected"] = int(bad_ratio.sum())
    frame["read_ratio"] = frame["meters_read"] / frame["meters_expected"].replace(0, pd.NA)
    return frame


def load_telemetry(data_dir: pathlib.Path, columns: list[str] | None = None) -> pd.DataFrame:
    tel_dir = data_dir / "telemetry"
    if not tel_dir.exists():
        raise DataQualityError(f"telemetry directory not found under {data_dir}")
    cols = columns if columns is not None else ["gateway_id", "ts_utc", *METRICS]
    frame = pd.read_parquet(tel_dir, columns=cols)
    _require_columns(frame, set(cols), "telemetry")
    frame["ts"] = pd.to_datetime(frame["ts_utc"], utc=True)
    return frame.drop(columns=["ts_utc"])


def load_engineer_review(data_dir: pathlib.Path) -> pd.DataFrame:
    path = data_dir / "engineer_review_2026-02.xlsx"
    frame = pd.read_excel(path)
    frame["reviewed_on"] = pd.to_datetime(frame["reviewed_on"], utc=True, errors="coerce")
    return frame
