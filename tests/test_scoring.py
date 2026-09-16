import datetime as dt

import pandas as pd
import pytest

from src.scoring import blended_scores_for_week, telemetry_flags_for_week, trailing_meter_risk


def _telemetry(rows):
    frame = pd.DataFrame(rows)
    frame["ts"] = pd.to_datetime(frame["ts"], utc=True)
    return frame


def test_telemetry_flags_never_uses_data_on_or_after_monday():
    """The core leak-free guarantee: nothing timestamped on/after `monday`
    may influence that week's flags. We plant an extreme outlier ON the
    Monday itself and assert it changes nothing about that week's score."""
    monday = dt.date(2026, 2, 2)
    baseline_rows = [
        {"gateway_id": "GW1", "ts": f"2026-01-{d:02d}T00:00:00Z",
         "offline_duration_sec": 10, "disconnection_cnt": 1, "reboot_cnt": 0}
        for d in range(5, 32)
    ]
    tel = _telemetry(baseline_rows)
    before = telemetry_flags_for_week(tel, monday)

    leak_row = _telemetry([{
        "gateway_id": "GW1", "ts": "2026-02-02T00:00:00Z",
        "offline_duration_sec": 999999, "disconnection_cnt": 999, "reboot_cnt": 999,
    }])
    tel_with_leak = pd.concat([tel, leak_row], ignore_index=True)
    after = telemetry_flags_for_week(tel_with_leak, monday)

    pd.testing.assert_frame_equal(
        before.sort_values("gateway_id").reset_index(drop=True),
        after.sort_values("gateway_id").reset_index(drop=True),
    )


def test_trailing_meter_risk_excludes_target_week():
    mrs = pd.DataFrame({
        "gateway_id": ["GW1", "GW1", "GW1"],
        "week_start": pd.to_datetime(
            ["2026-01-12", "2026-01-19", "2026-02-02"], utc=True
        ),
        "meters_expected": [100, 100, 100],
        "meters_read": [90, 95, 0],  # the Feb-2 row is a total outage
    })
    mrs["read_ratio"] = mrs["meters_read"] / mrs["meters_expected"]
    risk = trailing_meter_risk(mrs, dt.date(2026, 2, 2))
    # Should average only the two January weeks (0.10, 0.05 read-risk),
    # NOT be pulled toward 1.0 by the same-week outage.
    assert risk["GW1"] == pytest.approx(1 - (0.90 + 0.95) / 2)


def test_tied_scores_are_broken_deterministically_by_gateway_id():
    """FAQ 3.6: two runs that disagree about the order of tied rows is a bug.
    Three gateways with identical telemetry must tie on score and come back in
    gateway_id order -- not in whatever order the dataframe library produced,
    which is not stable across pandas versions."""
    monday = dt.date(2026, 2, 2)
    rows = [
        {"gateway_id": gw, "ts": f"2026-01-{d:02d}T00:00:00Z",
         "offline_duration_sec": 10 + d, "disconnection_cnt": 1, "reboot_cnt": 0}
        # deliberately not in sorted order, so a stable sort alone would not
        # be enough to produce the expected answer
        for gw in ("GW_C", "GW_A", "GW_B")
        for d in range(5, 32)
    ]
    empty_mrs = pd.DataFrame(columns=["gateway_id", "week_start", "read_ratio"])
    scored = blended_scores_for_week(_telemetry(rows), empty_mrs, monday)

    assert scored["blended_score"].nunique() == 1, "fixture should produce a tie"
    assert list(scored["gateway_id"]) == ["GW_A", "GW_B", "GW_C"]


def test_blended_scores_handle_gateway_with_no_meter_history():
    """A gateway absent from meter_read_success.csv must not crash the
    pipeline or silently score as 'perfectly healthy' (risk=0 would be an
    unearned claim); it should fall back to the fleet-median risk."""
    monday = dt.date(2026, 2, 2)
    rows = [
        {"gateway_id": "GW_NO_METER_DATA", "ts": f"2026-01-{d:02d}T00:00:00Z",
         "offline_duration_sec": 10 + d, "disconnection_cnt": 1, "reboot_cnt": 0}
        for d in range(5, 32)
    ]
    tel = _telemetry(rows)
    empty_mrs = pd.DataFrame(columns=["gateway_id", "week_start", "read_ratio"])
    scored = blended_scores_for_week(tel, empty_mrs, monday)
    assert not scored.empty
    assert scored["meter_risk"].notna().all()
