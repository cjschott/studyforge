import hashlib
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import get_db
from app.main import app
from app.models import Base, SourceLibrary, User


def make_client(tmp_path, monkeypatch):
    monkeypatch.setenv("STUDYFORGE_SOURCE_ORIGINALS_DIR", str(tmp_path / "sources" / "originals"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        admin = User(
            username="admin",
            display_name="Administrator",
            password_hash=hash_password("changeme"),
            role="admin",
            is_active=True,
        )
        library = SourceLibrary(
            name="CompTIA",
            description="Security+ sources",
            category="certification",
        )
        db.add_all([admin, library])
        db.commit()
        library_id = library.id

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    return client, library_id, Path(tmp_path / "sources" / "originals")


def upload_source(client, library_id, filename, content, content_type="text/plain", title="Security+ Notes"):
    return client.post(
        "/api/source-materials/upload",
        data={
            "library_id": str(library_id),
            "title": title,
            "source_type": "txt",
            "authority_level": "4",
            "confidence": "reviewed",
            "verification_status": "needs_review",
            "copyright_status": "owned",
            "original_url": "https://example.test/source",
        },
        files={"file": (filename, content, content_type)},
    )


def test_upload_source_material_stores_safe_file_and_metadata(tmp_path, monkeypatch):
    client, library_id, upload_dir = make_client(tmp_path, monkeypatch)
    content = b"Security+ source text\nwith useful notes."

    response = upload_source(client, library_id, "../Security+ notes.txt", content)
    body = response.json()

    assert response.status_code == 201
    assert body["library_id"] == library_id
    assert body["title"] == "Security+ Notes"
    assert body["authority_level"] == 4
    assert body["confidence"] == "reviewed"
    assert body["verification_status"] == "needs_review"
    assert body["copyright_status"] == "owned"
    assert body["checksum"] == hashlib.sha256(content).hexdigest()
    assert body["chunk_count"] == 0
    assert body["extraction_status"] == "not_extracted"
    assert ".." not in body["original_filename"]
    assert ".." not in body["stored_path"]
    assert not Path(body["stored_path"]).is_absolute()
    assert (upload_dir / Path(body["stored_path"]).name).exists()


def test_duplicate_upload_returns_friendly_conflict(tmp_path, monkeypatch):
    client, library_id, _ = make_client(tmp_path, monkeypatch)
    content = b"same source bytes"

    first = upload_source(client, library_id, "notes.txt", content)
    duplicate = upload_source(client, library_id, "renamed.txt", content)

    assert first.status_code == 201
    assert duplicate.status_code == 409
    assert "duplicate" in duplicate.json()["detail"].lower()


def test_upload_rejects_unsupported_extension(tmp_path, monkeypatch):
    client, library_id, _ = make_client(tmp_path, monkeypatch)

    response = upload_source(
        client,
        library_id,
        "installer.exe",
        b"not a supported source",
        content_type="application/octet-stream",
    )

    assert response.status_code == 400
    assert "unsupported" in response.json()["detail"].lower()


def test_extract_text_source_creates_chunks_and_lists_them(tmp_path, monkeypatch):
    client, library_id, _ = make_client(tmp_path, monkeypatch)
    text = "# Identity controls\n\n" + ("Authentication, authorization, and accounting. " * 90)
    uploaded = upload_source(client, library_id, "identity.md", text.encode("utf-8"), "text/markdown")

    extraction = client.post(f"/api/source-materials/{uploaded.json()['id']}/extract")
    chunks = client.get(f"/api/source-materials/{uploaded.json()['id']}/chunks")

    assert extraction.status_code == 200
    assert extraction.json()["status"] == "completed"
    assert extraction.json()["chunks"] >= 2
    assert chunks.status_code == 200
    assert len(chunks.json()) == extraction.json()["chunks"]
    assert chunks.json()[0]["chunk_number"] == 1
    assert "Identity controls" in chunks.json()[0]["text"]
    assert len(chunks.json()[0]["checksum"]) == 64

    material = client.get(f"/api/source-materials/{uploaded.json()['id']}")
    assert material.status_code == 200
    assert material.json()["chunk_count"] == extraction.json()["chunks"]
    assert material.json()["extraction_status"] == "completed"
    assert "Extracted" in material.json()["extraction_message"]


def test_csv_extraction_reads_rows_as_text(tmp_path, monkeypatch):
    client, library_id, _ = make_client(tmp_path, monkeypatch)
    csv_body = "term,definition\nMFA,Multiple factors\nRBAC,Role based access\n"
    uploaded = upload_source(client, library_id, "terms.csv", csv_body.encode("utf-8"), "text/csv", title="CSV Terms")

    extraction = client.post(f"/api/source-materials/{uploaded.json()['id']}/extract")
    chunks = client.get(f"/api/source-materials/{uploaded.json()['id']}/chunks")

    assert extraction.status_code == 200
    assert chunks.json()[0]["text"].startswith("term definition")
    assert "MFA Multiple factors" in chunks.json()[0]["text"]


def test_admin_delete_source_material_removes_stored_original(tmp_path, monkeypatch):
    client, library_id, upload_dir = make_client(tmp_path, monkeypatch)
    uploaded = upload_source(client, library_id, "delete-me.txt", b"temporary source")
    stored_file = upload_dir / Path(uploaded.json()["stored_path"]).name

    response = client.delete(f"/api/source-materials/{uploaded.json()['id']}")
    fetched = client.get(f"/api/source-materials/{uploaded.json()['id']}")

    assert stored_file.exists() is False
    assert response.status_code == 200
    assert response.json()["ok"] is True
    assert fetched.status_code == 404
