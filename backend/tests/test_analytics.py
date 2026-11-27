from pathlib import Path

import pytest

from backend.app.core.config import settings
from backend.app.db.models import Dataset
from backend.app.analytics.dataset_profile import (
    DatasetProfileError,
    get_dataset_profile,
)


def make_dataset(path: Path) -> Dataset:
    return Dataset(
        id=1,
        owner_id=1,
        original_filename="data.csv",
        stored_filename=path.name,
        file_size=path.stat().st_size,
        content_type="text/csv",
    )


def test_profile_reports_schema_missing_values_duplicates_and_summaries(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    csv_path = tmp_path / f"{'a' * 32}.csv"
    csv_path.write_text(
        "name,score,flag\nAlice,10,true\n,20,false\nNA,,true\nNA,,true\n",
        encoding="utf-8",
    )

    profile = get_dataset_profile(make_dataset(csv_path))

    assert profile["row_count"] == 4
    assert profile["column_count"] == 3
    assert profile["duplicate_row_count"] == 1
    assert profile["columns"][0]["missing_count"] == 1
    assert profile["columns"][0]["top_values"][0] == {
        "value": "NA",
        "count": 2,
    }
    assert profile["columns"][1]["missing_count"] == 2
    assert profile["columns"][1]["numeric_summary"]["mean"] == 15.0
    assert len(profile["preview"]) == 4


def test_profile_bounds_rows_columns_and_categorical_values(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    csv_path = tmp_path / f"{'b' * 32}.csv"

    columns = ["category"] + [f"column_{index}" for index in range(50)]
    rows = [
        [f"value-{row % 11}"] + [str(row + index) for index in range(50)]
        for row in range(105)
    ]
    csv_path.write_text(
        ",".join(columns)
        + "\n"
        + "\n".join(",".join(row) for row in rows)
        + "\n",
        encoding="utf-8",
    )

    profile = get_dataset_profile(make_dataset(csv_path))

    assert profile["row_count"] == 105
    assert profile["column_count"] == 51
    assert profile["columns_truncated"] is True
    assert len(profile["columns"]) == 50
    assert len(profile["columns"][0]["top_values"]) == 10
    assert len(profile["preview"]) == 100
    assert profile["preview_truncated"] is True


def test_profile_rejects_missing_dataset_file(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    missing_path = tmp_path / f"{'c' * 32}.csv"
    dataset = Dataset(
        id=1,
        owner_id=1,
        original_filename="missing.csv",
        stored_filename=missing_path.name,
        file_size=0,
        content_type="text/csv",
    )

    with pytest.raises(DatasetProfileError, match="not found"):
        get_dataset_profile(dataset)


def test_profile_rejects_invalid_stored_filename(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    dataset = Dataset(
        id=1,
        owner_id=1,
        original_filename="data.csv",
        stored_filename="..\\outside.csv",
        file_size=0,
        content_type="text/csv",
    )

    with pytest.raises(DatasetProfileError, match="invalid stored filename"):
        get_dataset_profile(dataset)
        