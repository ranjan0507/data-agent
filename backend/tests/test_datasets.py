from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.security import create_access_token
from backend.app.core.config import settings
from backend.app.db.database import Base, get_db
from backend.app.db.models import User
from backend.app.main import app
from backend.app.services import storage_services


@pytest.fixture
def dataset_test_context(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    storage_dir = tmp_path / "storage"
    monkeypatch.setattr(settings, "storage_dir", str(storage_dir))

    def override_get_db():
        with TestingSession() as db:
            yield db

    old_overrides = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = override_get_db

    try:
        with TestClient(app) as client:
            yield client, TestingSession, storage_dir
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(old_overrides)
        Base.metadata.drop_all(engine)
        engine.dispose()


def auth_headers(session_factory, email: str) -> dict[str, str]:
    with session_factory() as db:
        user = User(
            email=email,
            hashed_password="unused-in-this-test",
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        token = create_access_token(user.id)

    return {"Authorization": f"Bearer {token}"}


def test_upload_list_and_get_dataset(dataset_test_context):
    client, session_factory, storage_dir = dataset_test_context
    headers = auth_headers(session_factory, "owner@example.com")
    csv_content = b"month,total\nJan,12\n"

    response = client.post(
        "/datasets",
        headers=headers,
        files={"file": ("sales.csv", csv_content, "text/csv")},
    )

    assert response.status_code == 201
    dataset = response.json()
    assert dataset["original_filename"] == "sales.csv"
    assert dataset["file_size"] == len(csv_content)

    saved_files = list(Path(storage_dir).glob("*.csv"))
    assert len(saved_files) == 1

    listed = client.get("/datasets", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == dataset["id"]

    retrieved = client.get(f"/datasets/{dataset['id']}", headers=headers)
    assert retrieved.status_code == 200
    assert retrieved.json()["id"] == dataset["id"]


def test_upload_requires_authentication(dataset_test_context):
    client, _, _ = dataset_test_context

    response = client.post(
        "/datasets",
        files={"file": ("sales.csv", b"month,total\nJan,12\n", "text/csv")},
    )

    assert response.status_code == 401


def test_upload_rejects_invalid_files(dataset_test_context):
    client, session_factory, _ = dataset_test_context
    headers = auth_headers(session_factory, "uploader@example.com")

    wrong_extension = client.post(
        "/datasets",
        headers=headers,
        files={"file": ("sales.txt", b"not csv", "text/plain")},
    )
    assert wrong_extension.status_code == 400

    malformed_csv = client.post(
        "/datasets",
        headers=headers,
        files={"file": ("sales.csv", b"a,b\n1\n", "text/csv")},
    )
    assert malformed_csv.status_code == 400


def test_upload_rejects_files_over_limit(dataset_test_context, monkeypatch):
    client, session_factory, storage_dir = dataset_test_context
    headers = auth_headers(session_factory, "large-upload@example.com")
    monkeypatch.setattr(storage_services, "MAX_UPLOAD_SIZE", 5)

    response = client.post(
        "/datasets",
        headers=headers,
        files={"file": ("sales.csv", b"a,b\n1,12\n", "text/csv")},
    )

    assert response.status_code == 413
    assert list(Path(storage_dir).glob("*.csv")) == []
    assert list(Path(storage_dir).glob("*.tmp")) == []


def test_dataset_is_private_and_delete_removes_file(dataset_test_context):
    client, session_factory, storage_dir = dataset_test_context
    owner_headers = auth_headers(session_factory, "owner2@example.com")
    other_headers = auth_headers(session_factory, "other@example.com")

    upload = client.post(
        "/datasets",
        headers=owner_headers,
        files={"file": ("sales.csv", b"month,total\nJan,12\n", "text/csv")},
    )
    assert upload.status_code == 201

    dataset_id = upload.json()["id"]
    saved_file = next(Path(storage_dir).glob("*.csv"))

    assert client.get(
        f"/datasets/{dataset_id}", headers=other_headers
    ).status_code == 404
    assert client.delete(
        f"/datasets/{dataset_id}", headers=other_headers
    ).status_code == 404
    assert saved_file.exists()

    deleted = client.delete(f"/datasets/{dataset_id}", headers=owner_headers)
    assert deleted.status_code == 204
    assert not saved_file.exists()
    assert client.get(
        f"/datasets/{dataset_id}", headers=owner_headers
    ).status_code == 404