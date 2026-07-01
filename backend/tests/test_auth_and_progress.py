from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session, sessionmaker
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import get_db
from app.main import app
from app.models import Base, Course, Question, User


def make_client():
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
        course = Course(
            course_code="sample",
            name="Sample Course",
            short_name="SAMPLE",
            description="Sample",
            version="1.0",
            exam_type="professional_certification",
            provider="StudyForge",
            topics_json=["Identity"],
            is_active=True,
        )
        db.add_all([admin, course])
        db.flush()
        db.add(
            Question(
                course_id=course.id,
                legacy_id="sample-q1",
                question_type="single_choice",
                topic="Identity",
                subtopic="AAA",
                difficulty=3,
                oa_probability=5,
                question_text="Which AAA function decides allowed access?",
                choices_json=["Authentication", "Authorization", "Accounting", "Attestation"],
                answer_json="Authorization",
                explanation="Authorization determines allowed access.",
                status="verified",
                confidence=9,
                lineage_json={"sourceTags": ["Practice Test"]},
            )
        )
        db.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def test_admin_login_sets_cookie_and_me_returns_user():
    client = make_client()

    login = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "changeme"},
    )

    assert login.status_code == 200
    assert "studyforge_session" in login.cookies
    assert login.json()["user"]["role"] == "admin"

    me = client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


def test_admin_can_create_student_user():
    client = make_client()
    client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})

    response = client.post(
        "/api/users",
        json={
            "username": "student1",
            "display_name": "Student One",
            "password": "learnit",
            "role": "student",
        },
    )

    assert response.status_code == 201
    assert response.json()["username"] == "student1"
    assert response.json()["role"] == "student"


def test_attempts_bookmarks_and_progress_round_trip():
    client = make_client()
    client.post("/api/auth/login", json={"username": "admin", "password": "changeme"})

    attempt = client.post(
        "/api/questions/sample-q1/attempt",
        json={"selected_answer": "Authorization", "mode": "practice", "time_spent_seconds": 12},
    )
    assert attempt.status_code == 201
    assert attempt.json()["is_correct"] is True

    bookmark = client.post("/api/questions/sample-q1/bookmark")
    assert bookmark.status_code == 201

    progress = client.get("/api/courses/sample/progress")
    assert progress.status_code == 200
    body = progress.json()
    assert body["answered"]["sample-q1"]["attempts"] == 1
    assert body["answered"]["sample-q1"]["correct"] == 1
    assert body["topicStats"]["Identity"]["answered"] == 1
    assert body["bookmarks"]["sample-q1"]["id"] == "sample-q1"
