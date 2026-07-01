from pathlib import Path

from app.models import Course, Flashcard, GlossaryTerm, Question, CheatSheet
from app.services.course_importer import import_static_course_pack

from test_auth_and_progress import make_client
from test_import_export_validation import make_session


def login_admin(client):
    client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})


def test_question_status_transitions_and_review_lists():
    client = make_client()
    login_admin(client)

    generated = client.post("/api/questions/sample-q1/generated")
    reviewed = client.post("/api/questions/sample-q1/review")
    verified = client.post("/api/questions/sample-q1/verify")
    retired = client.post("/api/questions/sample-q1/retire")
    status_list = client.get("/api/questions?status=retired")
    counts = client.get("/api/questions/status-counts")
    low_confidence = client.get("/api/questions/low-confidence?threshold=10")
    warnings = client.get("/api/questions/validation-warnings")

    assert generated.status_code == 200
    assert reviewed.json()["status"] == "reviewed"
    assert verified.json()["status"] == "verified"
    assert retired.json()["status"] == "retired"
    assert status_list.status_code == 200
    assert status_list.json()[0]["id"] == "sample-q1"
    assert counts.status_code == 200
    assert counts.json()["retired"] == 1
    assert any(item["id"] == "sample-q1" for item in low_confidence.json())
    assert warnings.status_code == 200


def test_secplus_static_pack_imports_expected_alpha2_counts():
    db = make_session()
    pack_path = Path(__file__).resolve().parents[2] / "data" / "secplus"

    result = import_static_course_pack(db, pack_path)
    course = db.query(Course).filter_by(course_code="secplus").one()

    assert result["questions"] == 50
    assert db.query(Question).filter_by(course_id=course.id).count() == 50
    assert db.query(Flashcard).filter_by(course_id=course.id).count() == 20
    assert db.query(GlossaryTerm).filter_by(course_id=course.id).count() == 30
    assert db.query(CheatSheet).filter_by(course_id=course.id).count() == 5
    assert {question.status for question in db.query(Question).filter_by(course_id=course.id)} <= {"generated", "reviewed"}
