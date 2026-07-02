from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.auth import hash_password
from app.database import get_db
from app.main import app
from app.models import Base, User


def make_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(engine)

    with Session(engine) as db:
        db.add_all([
            User(
                username="admin",
                display_name="Administrator",
                password_hash=hash_password("changeme"),
                role="admin",
                is_active=True,
            ),
            User(
                username="student",
                display_name="Student",
                password_hash=hash_password("changeme"),
                role="student",
                is_active=True,
            ),
        ])
        db.commit()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def login(client, username="admin"):
    response = client.post("/api/auth/login", json={"username": username, "password": "changeme"})
    assert response.status_code == 200


def test_source_libraries_require_authentication():
    client = make_client()

    response = client.get("/api/source-libraries")

    assert response.status_code == 401


def test_authenticated_user_can_crud_source_library_except_delete():
    client = make_client()
    login(client, "student")

    created = client.post(
        "/api/source-libraries",
        json={
            "name": "CompTIA",
            "description": "Security+ sources",
            "category": "certification",
        },
    )
    listed = client.get("/api/source-libraries")
    fetched = client.get(f"/api/source-libraries/{created.json()['id']}")
    updated = client.put(
        f"/api/source-libraries/{created.json()['id']}",
        json={"description": "Security+ and Network+ sources", "category": "security"},
    )
    deleted = client.delete(f"/api/source-libraries/{created.json()['id']}")

    assert created.status_code == 201
    assert created.json()["name"] == "CompTIA"
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "CompTIA"
    assert fetched.status_code == 200
    assert fetched.json()["category"] == "certification"
    assert updated.status_code == 200
    assert updated.json()["description"] == "Security+ and Network+ sources"
    assert updated.json()["category"] == "security"
    assert deleted.status_code == 403


def test_admin_can_delete_source_library():
    client = make_client()
    login(client, "admin")

    created = client.post("/api/source-libraries", json={"name": "Temporary"})
    deleted = client.delete(f"/api/source-libraries/{created.json()['id']}")
    listed = client.get("/api/source-libraries")

    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
    assert listed.json() == []
