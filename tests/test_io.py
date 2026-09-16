import pytest

from src.io import DataQualityError, load_gateway_master, load_field_visits

from .conftest import DATA, requires_dataset


@requires_dataset
def test_gateway_master_loads_despite_latin1_encoding():
    """Regression test for the bug we actually hit: gateway_master.csv is
    Latin-1, not UTF-8. A naive pd.read_csv(path) raises UnicodeDecodeError
    on any strict-UTF-8 host. This must not happen."""
    frame = load_gateway_master(DATA)
    assert len(frame) > 0
    # If the encoding were wrong we'd see mojibake ('Au�enmast') or a
    # raised exception before we ever got here. Confirm real German text.
    assert "Außenmast" in frame["site_type"].unique()


def test_gateway_master_missing_file_raises_data_quality_error(tmp_path):
    with pytest.raises(DataQualityError):
        load_gateway_master(tmp_path)


@requires_dataset
def test_gateway_master_no_duplicate_gateways():
    frame = load_gateway_master(DATA)
    assert not frame["gateway_id"].duplicated().any()


@requires_dataset
def test_field_visits_loads_and_parses_dates():
    frame = load_field_visits(DATA)
    assert frame["requested_on"].notna().all()
    assert (frame["visited_on"] >= frame["requested_on"]).all()
