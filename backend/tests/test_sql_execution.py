from pathlib import Path

import pytest

from backend.app.analytics.duckdb_engine import (
    MAX_RESULT_ROWS,
    SQLExecutionError,
    run_sql,
)
from backend.app.core.config import settings
from backend.app.db.models import Dataset


def make_dataset(path: Path) -> Dataset:
    return Dataset(
        id=1,
        owner_id=1,
        original_filename="data.csv",
        stored_filename=path.name,
        file_size=path.stat().st_size,
        content_type="text/csv",
    )


def test_average_uses_all_dataset_rows(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    path = tmp_path / f"{'a' * 32}.csv"
    ages = list(range(1, 1502))
    path.write_text(
        "age\n" + "\n".join(map(str, ages)) + "\n",
        encoding="utf-8",
    )

    result = run_sql(
        make_dataset(path),
        'SELECT AVG("age") AS average_age FROM _dataset',
    )

    assert result["rows"] == [[751.0]]
    assert result["returned_row_count"] == 1
    assert result["truncated"] is False


@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1; SELECT 2",
        "DROP TABLE _dataset",
        "SELECT * FROM another_dataset",
        "SELECT * FROM read_csv('C:/private.csv')",
        "SELECT query('SELECT 1')",
    ],
)
def test_rejects_unsafe_sql(tmp_path, monkeypatch, query):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    path = tmp_path / f"{'b' * 32}.csv"
    path.write_text("age\n21\n", encoding="utf-8")

    with pytest.raises(SQLExecutionError):
        run_sql(make_dataset(path), query)


def test_caps_returned_rows_and_marks_truncation(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "storage_dir", str(tmp_path))
    path = tmp_path / f"{'c' * 32}.csv"
    path.write_text(
        "age\n" + "\n".join(str(age) for age in range(MAX_RESULT_ROWS + 1)),
        encoding="utf-8",
    )

    result = run_sql(make_dataset(path), "SELECT age FROM _dataset")

    assert result["returned_row_count"] == MAX_RESULT_ROWS
    assert len(result["rows"]) == MAX_RESULT_ROWS
    assert result["truncated"] is True