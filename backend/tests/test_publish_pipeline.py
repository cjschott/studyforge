from app.models import PublishedQuestionLineage, Question, QuestionPublishHistory, SourceConflict, SourceMaterial

from test_question_drafts import create_material_with_chunks, make_client, warning_codes


def publishable_draft_payload(material_id=None, chunk_id=None):
    payload = {
        "course_code": "SY0-701",
        "source_id": material_id,
        "source_chunk_id": chunk_id,
        "question_type": "single_choice",
        "stem": "What does TLS provide?",
        "choices": ["Encryption", "Routing"],
        "correct_answer": "Encryption",
        "explanation_json": {
            "correct": "Encryption is correct because TLS protects traffic.",
            "incorrect": {"Routing": "Routing is wrong because TLS does not route packets."},
        },
        "difficulty": 2,
        "oa_probability": 4,
    }
    return {key: value for key, value in payload.items() if value is not None}


def create_publishable_draft(client, session_factory, library_id, user_id):
    material_id, [chunk_id] = create_material_with_chunks(
        session_factory,
        library_id,
        user_id,
        [{"text": "TLS encrypts traffic and does not route packets."}],
        title="Security+ Official Notes",
        source_type="official_course_material",
        confidence="verified",
        verification_status="verified",
    )
    response = client.post("/api/question-drafts", json=publishable_draft_payload(material_id, chunk_id))
    assert response.status_code == 201
    return response.json(), material_id, chunk_id


def test_publish_creates_history_and_lineage_snapshot(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    draft, material_id, chunk_id = create_publishable_draft(client, session_factory, library_id, user_id)

    published = client.post(f"/api/question-drafts/{draft['id']}/publish")

    assert published.status_code == 200
    question_id = published.json()["published_question_id"]
    with session_factory() as db:
        history = db.query(QuestionPublishHistory).one()
        snapshot = db.query(PublishedQuestionLineage).one()
        assert history.draft_id == draft["id"]
        assert history.question_id == question_id
        assert history.course_code == "SY0-701"
        assert history.action == "published"
        assert history.previous_status is None
        assert history.new_status == "verified"
        assert history.published_by == user_id
        assert snapshot.question_id == question_id
        assert snapshot.source_id == material_id
        assert snapshot.source_chunk_id == chunk_id
        assert snapshot.source_title == "Security+ Official Notes"
        assert snapshot.source_type == "official_course_material"
        assert snapshot.source_confidence == "verified"
        assert snapshot.source_verification_status == "verified"
        assert "TLS encrypts traffic" in snapshot.evidence_text


def test_republish_updates_same_question_and_records_republished_history(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    draft, _, _ = create_publishable_draft(client, session_factory, library_id, user_id)
    first = client.post(f"/api/question-drafts/{draft['id']}/publish")
    question_id = first.json()["published_question_id"]

    client.put(f"/api/question-drafts/{draft['id']}", json={"stem": "What security property does TLS provide?"})
    second = client.post(f"/api/question-drafts/{draft['id']}/publish")

    assert second.status_code == 200
    assert second.json()["published_question_id"] == question_id
    with session_factory() as db:
        actions = [row.action for row in db.query(QuestionPublishHistory).order_by(QuestionPublishHistory.id)]
        question = db.get(Question, question_id)
        assert actions == ["published", "republished"]
        assert question.question_text == "What security property does TLS provide?"
        assert db.query(PublishedQuestionLineage).filter_by(question_id=question_id).count() == 1


def test_lineage_snapshot_preserves_source_metadata_after_source_changes(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    draft, material_id, _ = create_publishable_draft(client, session_factory, library_id, user_id)

    published = client.post(f"/api/question-drafts/{draft['id']}/publish")
    with session_factory() as db:
        material = db.get(SourceMaterial, material_id)
        material.title = "Renamed Source After Publish"
        material.verification_status = "rejected"
        db.add(material)
        db.commit()

    lineage = client.get(f"/api/questions/{published.json()['published_question_id']}/lineage")

    assert lineage.status_code == 200
    assert lineage.json()[0]["source_title"] == "Security+ Official Notes"
    assert lineage.json()[0]["source_verification_status"] == "verified"


def test_retire_hides_question_from_practice_and_restore_returns_it(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    draft, _, _ = create_publishable_draft(client, session_factory, library_id, user_id)
    question_id = client.post(f"/api/question-drafts/{draft['id']}/publish").json()["published_question_id"]

    retired = client.post(f"/api/questions/{question_id}/retire")
    practice_hidden = client.get("/api/courses/SY0-701/questions")
    admin_visible = client.get("/api/questions?status=retired")
    restored = client.post(f"/api/questions/{question_id}/restore")
    practice_visible = client.get("/api/courses/SY0-701/questions")

    assert retired.status_code == 200
    assert retired.json()["status"] == "retired"
    assert practice_hidden.json() == []
    assert admin_visible.json()[0]["id"] == f"SY0-701-draft-{draft['id']}"
    assert restored.status_code == 200
    assert restored.json()["status"] == "verified"
    assert practice_visible.json()[0]["id"] == f"SY0-701-draft-{draft['id']}"


def test_export_excludes_retired_by_default_and_includes_lineage_when_requested(tmp_path, monkeypatch):
    client, session_factory, library_id, user_id, _ = make_client(tmp_path, monkeypatch)
    draft, _, _ = create_publishable_draft(client, session_factory, library_id, user_id)
    question_id = client.post(f"/api/question-drafts/{draft['id']}/publish").json()["published_question_id"]
    client.post(f"/api/questions/{question_id}/retire")

    default_export = client.get("/api/export/SY0-701")
    full_export = client.get(
        "/api/export/SY0-701?include_retired=true&include_lineage=true&include_review_metadata=true"
    )

    assert default_export.status_code == 200
    assert default_export.json()["questions"] == []
    question = full_export.json()["questions"][0]
    assert question["status"] == "retired"
    assert question["explanationJson"]["correct"].startswith("Encryption is correct")
    assert question["publishedLineage"][0]["source_title"] == "Security+ Official Notes"
    assert question["publishHistory"][-1]["action"] == "retired"
    assert "stored_path" not in str(full_export.json()).lower()


def test_export_validation_detects_missing_lineage_and_high_conflicts(tmp_path, monkeypatch):
    client, session_factory, _, _, course_id = make_client(tmp_path, monkeypatch)
    with session_factory() as db:
        question = Question(
            course_id=course_id,
            legacy_id="missing-lineage",
            question_text="Question without lineage?",
            choices_json=["A", "B"],
            answer_json="A",
            explanation="A is correct. B is wrong.",
            status="verified",
            confidence=9,
            lineage_json={},
        )
        conflict = SourceConflict(
            conflict_type="unsupported_claim",
            summary="High unresolved conflict.",
            severity="high",
            status="needs_review",
            detection_method="manual",
        )
        db.add_all([question, conflict])
        db.commit()

    response = client.get("/api/export/SY0-701/validate")

    assert response.status_code == 200
    codes = warning_codes(response.json()["warnings"])
    assert "missing_question_lineage" in codes
    assert "unresolved_high_severity_conflict" in codes
