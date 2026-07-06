from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import hash_password
from app.database import get_db
from app.main import app
from app.models import Base, Concept, Course, Question, SourceChunk, SourceConcept, SourceConflict, SourceLibrary, SourceMaterial, User


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
        course = Course(course_code="SY0-701", name="Security+", short_name="Sec+")
        library = SourceLibrary(name="CompTIA", description="Security+ sources", category="certification")
        db.add_all([user, course, library])
        db.commit()
        user_id = user.id
        library_id = library.id
        course_id = course.id

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
    return client, TestingSessionLocal, library_id, user_id, course_id


def create_material_with_chunks(session_factory, library_id, user_id, chunks, **fields):
    with session_factory() as db:
        material = SourceMaterial(
            library_id=library_id,
            title=fields.get("title", "Security+ Practice"),
            source_type=fields.get("source_type", "practice_assessment"),
            authority_level=fields.get("authority_level", 4),
            confidence=fields.get("confidence", "reviewed"),
            verification_status=fields.get("verification_status", "needs_review"),
            copyright_status="owned",
            original_filename="practice.md",
            stored_path=str(Path("practice.md")),
            original_url="",
            checksum=fields.get("checksum", ("q" * 63) + str(library_id)),
            uploaded_by=user_id,
        )
        db.add(material)
        db.flush()
        chunk_ids = []
        for index, item in enumerate(chunks, start=1):
            chunk = SourceChunk(
                source_id=material.id,
                chunk_number=index,
                page_number=item.get("page_number"),
                heading=item.get("heading", ""),
                text=item["text"],
                checksum=(str(index) * 64)[:64],
            )
            db.add(chunk)
            db.flush()
            chunk_ids.append(chunk.id)
        db.commit()
        return material.id, chunk_ids


def create_concept_with_lineage(session_factory, material_id, chunk_id, **fields):
    with session_factory() as db:
        concept = Concept(
            name=fields.get("name", "Firewall"),
            normalized_name=fields.get("normalized_name", "firewall"),
            description=fields.get("description", "A control that filters network traffic."),
            course_code=fields.get("course_code", "SY0-701"),
            status=fields.get("status", "verified"),
            confidence=fields.get("confidence", "verified"),
        )
        db.add(concept)
        db.flush()
        db.add(
            SourceConcept(
                source_id=material_id,
                source_chunk_id=chunk_id,
                concept_id=concept.id,
                evidence_text="A firewall filters packets based on rules.",
                confidence_score=0.9,
                extraction_method="manual",
            )
        )
        db.commit()
        return concept.id


def warning_codes(warnings):
    return {warning["code"] for warning in warnings}


def create_conflict(session_factory, **fields):
    with session_factory() as db:
        conflict = SourceConflict(
            concept_id=fields.get("concept_id"),
            source_id_a=fields.get("source_id_a"),
            source_chunk_id_a=fields.get("source_chunk_id_a"),
            conflict_type=fields.get("conflict_type", "unsupported_claim"),
            summary=fields.get("summary", "High severity conflict."),
            evidence_a=fields.get("evidence_a", "Evidence"),
            evidence_b="",
            severity=fields.get("severity", "high"),
            status=fields.get("status", "needs_review"),
            detection_method="manual",
        )
        db.add(conflict)
        db.commit()
        return conflict.id


def test_unauthenticated_question_draft_endpoints_return_401(tmp_path, monkeypatch):
    client, _, _, _, _ = make_client(tmp_path, monkeypatch, login=False)

    endpoints = [
        ("GET", "/api/question-drafts", None),
        ("POST", "/api/question-drafts", {"course_code": "SY0-701", "stem": "Draft?"}),
        ("GET", "/api/question-drafts/1", None),
        ("PUT", "/api/question-drafts/1", {"stem": "Updated?"}),
        ("POST", "/api/question-drafts/1/review", None),
        ("POST", "/api/question-drafts/1/verify", None),
        ("POST", "/api/question-drafts/1/reject", None),
        ("POST", "/api/question-drafts/1/publish", None),
        ("GET", "/api/question-drafts/1/warnings", None),
        ("POST", "/api/question-drafts/1/validate", None),
        ("POST", "/api/source-materials/1/draft-questions", {"course_code": "SY0-701"}),
        ("POST", "/api/concepts/1/draft-questions", {"course_code": "SY0-701"}),
        ("POST", "/api/course-builder/draft-questions", {"course_code": "SY0-701", "source_material_ids": [1]}),
    ]

    for method, path, payload in endpoints:
        response = client.request(method, path, json=payload)
        assert response.status_code == 401


def test_draft_can_be_created_manually_with_defaults(tmp_path, monkeypatch):
    client, _, _, _, _ = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/question-drafts",
        json={
            "course_code": "SY0-701",
            "question_type": "single_choice",
            "stem": "Which port is used by HTTPS?",
            "choices": ["80", "443", "53", "22"],
            "correct_answer": "443",
        },
    )

    assert response.status_code == 201
    draft = response.json()
    assert draft["status"] == "needs_review"
    assert draft["confidence"] == "generated"
    assert draft["generation_method"] == "manual"
    assert draft["stem"] == "Which port is used by HTTPS?"


def test_missing_lineage_creates_validation_warning(tmp_path, monkeypatch):
    client, _, _, _, _ = make_client(tmp_path, monkeypatch)

    response = client.post(
        "/api/question-drafts",
        json={
            "course_code": "SY0-701",
            "stem": "Which statement is true?",
            "choices": ["Needs review", "Needs review"],
            "correct_answer": [],
        },
    )

    assert response.status_code == 201
    warnings = response.json()["warnings"]
    assert "missing_lineage" in warning_codes(warnings)
    assert "missing_answer" in warning_codes(warnings)
    assert "missing_explanation" in warning_codes(warnings)
    assert any(item["severity"] == "high" for item in warnings)


def test_validation_detects_missing_wrong_answer_explanations(tmp_path, monkeypatch):
    client, _, _, _, _ = make_client(tmp_path, monkeypatch)
    draft_id = client.post(
        "/api/question-drafts",
        json={
            "course_code": "SY0-701",
            "stem": "What does TLS provide?",
            "choices": ["Encryption", "Routing", "Addressing"],
            "correct_answer": "Encryption",
            "explanation": "TLS provides encryption.",
            "lineage": [{"lineage_reason": "manual", "evidence_text": "TLS encrypts traffic."}],
        },
    ).json()["id"]

    response = client.post(f"/api/question-drafts/{draft_id}/validate")

    assert response.status_code == 200
    assert "missing_wrong_answer_explanations" in warning_codes(response.json()["warnings"])


def test_source_draft_endpoint_creates_drafts_with_lineage(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    material_id, [chunk_id] = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [
            {
                "text": (
                    "Question: Which protocol provides encrypted web traffic?\n"
                    "A. HTTP\nB. HTTPS\nC. FTP\nD. Telnet\n"
                    "Answer: B\nExplanation: HTTPS uses TLS to encrypt web traffic."
                )
            }
        ],
    )

    response = client.post(f"/api/source-materials/{material_id}/draft-questions", json={"course_code": "SY0-701"})

    assert response.status_code == 200
    result = response.json()
    assert result["drafts_created"] == 1
    draft = result["drafts"][0]
    assert draft["source_id"] == material_id
    assert draft["source_chunk_id"] == chunk_id
    assert draft["stem"] == "Which protocol provides encrypted web traffic?"
    assert draft["choices"] == ["HTTP", "HTTPS", "FTP", "Telnet"]
    assert draft["correct_answer"] == "HTTPS"
    assert draft["status"] == "needs_review"
    assert draft["generation_method"] == "rule_based"
    assert draft["lineage"][0]["source_chunk_id"] == chunk_id


def test_concept_draft_endpoint_creates_draft_with_lineage(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    material_id, [chunk_id] = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [{"text": "A firewall filters packets based on rules."}],
    )
    concept_id = create_concept_with_lineage(session_factory, material_id, chunk_id)

    response = client.post(f"/api/concepts/{concept_id}/draft-questions", json={"course_code": "SY0-701"})

    assert response.status_code == 200
    draft = response.json()["drafts"][0]
    assert draft["concept_id"] == concept_id
    assert draft["source_id"] == material_id
    assert draft["source_chunk_id"] == chunk_id
    assert "Which statement best describes Firewall?" in draft["stem"]
    assert draft["lineage"][0]["concept_id"] == concept_id
    assert draft["warnings"]


def test_high_severity_warning_blocks_verify_and_publish(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    material_id, [chunk_id] = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [{"text": "TLS encrypts web traffic."}],
        verification_status="verified",
    )
    create_conflict(session_factory, source_id_a=material_id, source_chunk_id_a=chunk_id, severity="high")
    draft = client.post(
        "/api/question-drafts",
        json={
            "course_code": "SY0-701",
            "source_id": material_id,
            "source_chunk_id": chunk_id,
            "stem": "What does TLS provide?",
            "choices": ["Encryption", "Routing"],
            "correct_answer": "Encryption",
            "explanation_json": {
                "correct": "Encryption is correct because TLS protects traffic confidentiality.",
                "incorrect": {"Routing": "Routing is wrong because TLS does not choose packet paths."},
            },
        },
    ).json()

    verify = client.post(f"/api/question-drafts/{draft['id']}/verify")
    publish = client.post(f"/api/question-drafts/{draft['id']}/publish")

    assert "unresolved_high_severity_conflict" in warning_codes(draft["warnings"])
    assert verify.status_code == 400
    assert publish.status_code == 400


def test_course_builder_draft_endpoint_creates_source_drafts_and_source_filter_lists_them(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    material_id, _ = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [{"text": "Question: What does a firewall inspect?\nA. Packets\nB. Desk height\nAnswer: A"}],
    )

    response = client.post(
        "/api/course-builder/draft-questions",
        json={"course_code": "SY0-701", "source_material_ids": [material_id]},
    )
    source_list = client.get(f"/api/question-drafts?source_id={material_id}&include_rejected=true")

    assert response.status_code == 200
    assert response.json()["target_type"] == "course_builder"
    assert response.json()["drafts_created"] == 1
    assert source_list.status_code == 200
    assert [item["source_id"] for item in source_list.json()] == [material_id]


def test_draft_can_be_reviewed_verified_and_rejected(tmp_path, monkeypatch):
    client, _, _, _, _ = make_client(tmp_path, monkeypatch)
    draft_id = client.post(
        "/api/question-drafts",
        json={"course_code": "SY0-701", "stem": "Review me?", "correct_answer": []},
    ).json()["id"]

    reviewed = client.post(f"/api/question-drafts/{draft_id}/review")
    rejected = client.post(f"/api/question-drafts/{draft_id}/reject")

    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"
    assert "missing_answer" in warning_codes(reviewed.json()["warnings"])
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"


def test_duplicate_question_warning_is_created(tmp_path, monkeypatch):
    client, _, _, _, _ = make_client(tmp_path, monkeypatch)
    payload = {
        "course_code": "SY0-701",
        "concept_id": 77,
        "stem": "What does a firewall inspect?",
        "choices": ["Packets", "Desk height"],
        "correct_answer": "Packets",
        "explanation": "Packets is correct. Desk height is wrong.",
        "lineage": [{"concept_id": 77, "lineage_reason": "manual", "evidence_text": "Firewall evidence."}],
    }
    client.post("/api/question-drafts", json=payload)

    response = client.post("/api/question-drafts", json={**payload, "stem": "What does the firewall inspect?"})

    assert response.status_code == 201
    assert "duplicate_question" in warning_codes(response.json()["warnings"])


def test_warnings_refresh_after_draft_update(tmp_path, monkeypatch):
    client, _, _, _, _ = make_client(tmp_path, monkeypatch)
    draft_id = client.post(
        "/api/question-drafts",
        json={
            "course_code": "SY0-701",
            "stem": "What does TLS provide?",
            "choices": ["Encryption", "Routing"],
            "correct_answer": "Encryption",
            "lineage": [{"lineage_reason": "manual", "evidence_text": "TLS encrypts traffic."}],
        },
    ).json()["id"]

    before = client.get(f"/api/question-drafts/{draft_id}/warnings")
    after = client.put(
        f"/api/question-drafts/{draft_id}",
        json={
            "explanation_json": {
                "correct": "Encryption is correct because TLS protects traffic.",
                "incorrect": {"Routing": "Routing is wrong because TLS does not route traffic."},
            }
        },
    )

    assert "missing_explanation" in warning_codes(before.json())
    assert "missing_explanation" not in warning_codes(after.json()["warnings"])
    assert "missing_wrong_answer_explanations" not in warning_codes(after.json()["warnings"])


def test_rejected_drafts_hidden_by_default(tmp_path, monkeypatch):
    client, _, _, _, _ = make_client(tmp_path, monkeypatch)
    kept = client.post("/api/question-drafts", json={"course_code": "SY0-701", "stem": "Keep?", "correct_answer": []}).json()
    rejected = client.post("/api/question-drafts", json={"course_code": "SY0-701", "stem": "Reject?", "correct_answer": []}).json()
    client.post(f"/api/question-drafts/{rejected['id']}/reject")

    default_response = client.get("/api/question-drafts")
    include_response = client.get("/api/question-drafts?include_rejected=true")

    assert [item["id"] for item in default_response.json()] == [kept["id"]]
    assert {item["id"] for item in include_response.json()} == {kept["id"], rejected["id"]}


def test_publish_creates_then_updates_same_real_question(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    material_id, [chunk_id] = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [{"text": "Question: What does TLS provide?\nA. Encryption\nB. Routing\nAnswer: A"}],
        verification_status="verified",
    )
    draft_id = client.post(
        "/api/question-drafts",
        json={
            "course_code": "SY0-701",
            "source_id": material_id,
            "source_chunk_id": chunk_id,
            "question_type": "single_choice",
            "stem": "What does TLS provide?",
            "choices": ["Encryption", "Routing"],
            "correct_answer": "Encryption",
            "explanation_json": {
                "correct": "Encryption is correct because TLS encrypts traffic.",
                "incorrect": {"Routing": "Routing is wrong because TLS does not route packets."},
            },
            "difficulty": 2,
            "oa_probability": 4,
        },
    ).json()["id"]

    first_publish = client.post(f"/api/question-drafts/{draft_id}/publish")
    second_publish = client.put(f"/api/question-drafts/{draft_id}", json={"stem": "What security property does TLS provide?"})
    second_publish = client.post(f"/api/question-drafts/{draft_id}/publish")

    assert first_publish.status_code == 200
    assert second_publish.status_code == 200
    first_question_id = first_publish.json()["published_question_id"]
    assert second_publish.json()["published_question_id"] == first_question_id
    assert second_publish.json()["status"] == "published"

    with session_factory() as db:
        questions = db.query(Question).all()
        assert len(questions) == 1
        assert questions[0].id == first_question_id
        assert questions[0].question_text == "What security property does TLS provide?"
        assert questions[0].status == "verified"
        assert questions[0].why_wrong_json == {"Routing": "Routing is wrong because TLS does not route packets."}
        assert questions[0].lineage_json["draftId"] == draft_id
        assert questions[0].lineage_json["sourceMaterialId"] == material_id
        assert questions[0].lineage_json["sourceChunkId"] == chunk_id


def test_publish_succeeds_when_high_severity_warnings_are_resolved(tmp_path, monkeypatch):
    client, _, _, _, _ = make_client(tmp_path, monkeypatch)
    draft_id = client.post(
        "/api/question-drafts",
        json={
            "course_code": "SY0-701",
            "stem": "What does TLS provide?",
            "choices": ["Encryption", "Routing"],
            "correct_answer": "Encryption",
            "explanation_json": {
                "correct": "Encryption is correct because TLS protects traffic.",
                "incorrect": {"Routing": "Routing is wrong because TLS does not route traffic."},
            },
        },
    ).json()["id"]

    blocked = client.post(f"/api/question-drafts/{draft_id}/publish")
    updated = client.put(
        f"/api/question-drafts/{draft_id}",
        json={"lineage": [{"lineage_reason": "manual", "evidence_text": "TLS encrypts traffic."}]},
    )
    published = client.post(f"/api/question-drafts/{draft_id}/publish")

    assert blocked.status_code == 400
    assert "missing_lineage" in warning_codes(blocked.json()["warnings"])
    assert "missing_lineage" not in warning_codes(updated.json()["warnings"])
    assert published.status_code == 200
    assert published.json()["status"] == "published"
