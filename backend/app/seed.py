import argparse
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_settings
from app.auth import hash_password
from app.database import SessionLocal, init_db
from app.models import User
from app.services.course_importer import import_static_course_pack


def resolve_static_path(raw_path: str) -> Path:
    requested = Path(raw_path)
    candidates = [
        requested,
        Path.cwd() / requested,
        Path(__file__).resolve().parents[2] / "data" / requested.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return requested.resolve()


def ensure_admin(
    db: Session,
    username: str = "admin",
    password: str = "changeme",
    display_name: str = "Administrator",
    role: str = "admin",
):
    user = db.query(User).filter_by(username=username).one_or_none()
    if user:
        return {"created": False, "username": username}
    user = User(
        username=username,
        display_name=display_name,
        role=role,
        is_active=True,
        password_hash=hash_password(password),
    )
    db.add(user)
    db.commit()
    return {"created": True, "username": username}


def main():
    parser = argparse.ArgumentParser(description="Seed StudyForge backend data.")
    parser.add_argument("--import-static", help="Path to an existing static course folder, such as ../../data/d413.")
    parser.add_argument("--admin-username", default="admin")
    parser.add_argument("--admin-password", default="changeme")
    parser.add_argument("--admin-display-name", default="Administrator")
    args = parser.parse_args()

    settings = get_settings()
    admin_password = args.admin_password if args.admin_password != "changeme" else settings.admin_password
    init_db()
    with SessionLocal() as db:
        admin_result = ensure_admin(
            db,
            username=args.admin_username,
            password=admin_password,
            display_name=args.admin_display_name,
        )
        print(f"Admin user: {admin_result['username']} ({'created' if admin_result['created'] else 'exists'})")
        if args.import_static:
            result = import_static_course_pack(db, resolve_static_path(args.import_static))
            print(f"Imported {result['course_code']}: {result['questions']} questions, {result['flashcards']} flashcards")
        elif admin_result["created"] and admin_password == "changeme":
            print("WARNING: default admin password is changeme. Change it before deployment.")


if __name__ == "__main__":
    main()
