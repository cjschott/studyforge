from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import get_db
from app.main import app
from app.models import Base, Concept, SourceChunk, SourceConflict, SourceLibrary, SourceMaterial, User


def make_client(tmp_path, monkeypatch, login=True, role="admin"):
    monkeypatch.setenv("STUDYFORGE_SOURCE_ORIGINALS_DIR", str(tmp_path / "sources" / "originals"))
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        user = User(
            username="admin",
            display_name="Administrator",
            password_hash=hash_password("changeme"),
            role=role,
            is_active=True,
        )
        library = SourceLibrary(name="CompTIA", description="Security+ sources", category="certification")
        db.add_all([user, library])
        db.commit()
        user_id = user.id
        library_id = library.id

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    if login:
        client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})
    return client, TestingSessionLocal, library_id, user_id


def create_material_with_chunks(session_factory, library_id, user_id, chunks, **fields):
    with session_factory() as db:
        material = SourceMaterial(
            library_id=library_id,
            title=fields.get("title", "Security+ Source"),
            source_type=fields.get("source_type", "markdown"),
            authority_level=fields.get("authority_level", 4),
            confidence=fields.get("confidence", "reviewed"),
            verification_status=fields.get("verification_status", "needs_review"),
            copyright_status="owned",
            original_filename="source.md",
            stored_path=str(Path("source.md")),
            original_url="",
            checksum=fields.get("checksum", ("b" * 63) + str(library_id)),
            uploaded_by=user_id,
        )
        db.add(material)
        db.flush()
        for index, item in enumerate(chunks, start=1):
            db.add(
                SourceChunk(
                    source_id=material.id,
                    chunk_number=index,
                    page_number=item.get("page_number"),
                    heading=item.get("heading", ""),
                    text=item["text"],
                    checksum=(str(index) * 64)[:64],
                )
            )
        db.commit()
        return material.id


def create_concept(session_factory, name, **fields):
    with session_factory() as db:
        concept = Concept(
            name=name,
            normalized_name=fields.get("normalized_name") or name.lower(),
            description=fields.get("description", ""),
            course_code=fields.get("course_code", "SY0-701"),
            status=fields.get("status", "generated"),
            confidence=fields.get("confidence", "generated"),
        )
        db.add(concept)
        db.commit()
        return concept.id


def create_conflict(session_factory, **fields):
    with session_factory() as db:
        conflict = SourceConflict(
            concept_id=fields.get("concept_id"),
            source_id_a=fields.get("source_id_a"),
            source_chunk_id_a=fields.get("source_chunk_id_a"),
            source_id_b=fields.get("source_id_b"),
            source_chunk_id_b=fields.get("source_chunk_id_b"),
            conflict_type=fields.get("conflict_type", "unsupported_claim"),
            summary=fields.get("summary", "A generated conflict needs review."),
            evidence_a=fields.get("evidence_a", "Evidence A"),
            evidence_b=fields.get("evidence_b", ""),
            severity=fields.get("severity", "medium"),
            status=fields.get("status", "generated"),
            detection_method=fields.get("detection_method", "manual"),
        )
        db.add(conflict)
        db.commit()
        return conflict.id


def test_conflict_endpoints_require_authentication(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id = make_client(tmp_path, monkeypatch, login=False)
    material_id = create_material_with_chunks(session_factory, library_id, user_id, [{"text": "SY0-601 notes."}])
    concept_id = create_concept(session_factory, "Firewall", normalized_name="firewall")
    conflict_id = create_conflict(session_factory, concept_id=concept_id, source_id_a=material_id)

    requests = [
        client.get("/api/conflicts"),
        client.get(f"/api/conflicts/{conflict_id}"),
        client.put(f"/api/conflicts/{conflict_id}", json={"status": "reviewed"}),
        client.post(f"/api/conflicts/{conflict_id}/resolve"),
        client.post(f"/api/source-materials/{material_id}/detect-conflicts"),
        client.post(f"/api/concepts/{concept_id}/detect-conflicts"),
    ]

    assert [response.status_code for response in requests] == [401, 401, 401, 401, 401, 401]


def test_conflict_model_persists_correctly(tmp_path, monkeypatch):
    _, session_factory, library_id, user_id = make_client(tmp_path, monkeypatch)
    material_id = create_material_with_chunks(session_factory, library_id, user_id, [{"text": "SY0-601 notes."}])
    concept_id = create_concept(session_factory, "Firewall", normalized_name="firewall")

    conflict_id = create_conflict(
        session_factory,
        concept_id=concept_id,
        source_id_a=material_id,
        conflict_type="outdated_reference",
        severity="high",
        status="needs_review",
        detection_method="rule_based",
    )

    with session_factory() as db:
        conflict = db.get(SourceConflict, conflict_id)
        assert conflict.concept_id == concept_id
        assert conflict.source_id_a == material_id
        assert conflict.conflict_type == "outdated_reference"
        assert conflict.severity == "high"
        assert conflict.status == "needs_review"
        assert conflict.detection_method == "rule_based"


def test_conflict_list_hides_resolved_by_default(tmp_path, monkeypatch):
    client, session_factory, _, _ = make_client(tmp_path, monkeypatch)
    create_conflict(session_factory, summary="Open conflict", status="needs_review")
    create_conflict(session_factory, summary="Resolved conflict", status="resolved")

    default_response = client.get("/api/conflicts")
    include_response = client.get("/api/conflicts?include_resolved=true")

    assert default_response.status_code == 200
    assert [item["summary"] for item in default_response.json()] == ["Open conflict"]
    assert {item["summary"] for item in include_response.json()} == {"Open conflict", "Resolved conflict"}


def test_source_conflict_detection_creates_outdated_exam_version_conflict(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id = make_client(tmp_path, monkeypatch)
    material_id = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [{"heading": "Legacy objectives", "text": "This note references CompTIA Security+ SY0-601 domains."}],
    )

    response = client.post(f"/api/source-materials/{material_id}/detect-conflicts")

    assert response.status_code == 200
    conflicts = response.json()["conflicts"]
    assert any(item["conflict_type"] == "outdated_reference" for item in conflicts)
    outdated = next(item for item in conflicts if item["conflict_type"] == "outdated_reference")
    assert outdated["source_id_a"] == material_id
    assert outdated["severity"] == "high"
    assert "SY0-601" in outdated["evidence_a"]


def test_duplicate_concept_conflict_can_be_detected(tmp_path, monkeypatch):
    client, session_factory, _, _ = make_client(tmp_path, monkeypatch)
    concept_id = create_concept(session_factory, "Firewall", normalized_name="firewall")
    duplicate_id = create_concept(session_factory, "Fire wall", normalized_name="firewall")

    response = client.post(f"/api/concepts/{concept_id}/detect-conflicts")

    assert response.status_code == 200
    duplicate_conflicts = [item for item in response.json()["conflicts"] if item["conflict_type"] == "duplicate_concept"]
    assert duplicate_conflicts
    assert duplicate_conflicts[0]["concept_id"] == concept_id
    assert str(duplicate_id) in duplicate_conflicts[0]["evidence_b"]


def test_conflict_can_be_reviewed_resolved_and_rejected(tmp_path, monkeypatch):
    client, session_factory, _, _ = make_client(tmp_path, monkeypatch)
    conflict_id = create_conflict(session_factory, status="needs_review")
    rejected_id = create_conflict(session_factory, status="needs_review")

    reviewed = client.put(f"/api/conflicts/{conflict_id}", json={"status": "reviewed"})
    resolved = client.post(f"/api/conflicts/{conflict_id}/resolve")
    rejected = client.put(f"/api/conflicts/{rejected_id}", json={"status": "rejected"})

    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"
    assert resolved.status_code == 200
    assert resolved.json()["status"] == "resolved"
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_source_material_stats_include_unresolved_conflict_count(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id = make_client(tmp_path, monkeypatch)
    material_id = create_material_with_chunks(session_factory, library_id, user_id, [{"text": "Source text."}])
    create_conflict(session_factory, source_id_a=material_id, status="needs_review")
    create_conflict(session_factory, source_id_a=material_id, status="resolved")

    response = client.get(f"/api/source-materials/{material_id}")

    assert response.status_code == 200
    assert response.json()["conflict_count"] == 2
    assert response.json()["unresolved_conflict_count"] == 1
