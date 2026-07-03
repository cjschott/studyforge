import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.config import get_settings


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = f"sqlite:///{BACKEND_DIR / 'studyforge.db'}"
DATABASE_URL = os.getenv("STUDYFORGE_DATABASE_URL", get_settings().database_url)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def _migrate_sqlite_concepts(bind_engine):
    if bind_engine.dialect.name != "sqlite":
        return

    raw = bind_engine.raw_connection()
    cursor = raw.cursor()
    try:
        cursor.execute("PRAGMA table_info(concepts)")
        rows = cursor.fetchall()
        if not rows:
            return
        columns = {row[1]: {"type": row[2], "notnull": row[3]} for row in rows}
        required = {
            "normalized_name",
            "description",
            "course_code",
            "status",
            "updated_at",
        }
        needs_rebuild = bool(required - set(columns)) or columns.get("course_id", {}).get("notnull") == 1
        if not needs_rebuild:
            if "normalized_name" in columns:
                cursor.execute("CREATE INDEX IF NOT EXISTS ix_concepts_normalized_name ON concepts (normalized_name)")
                raw.commit()
            return

        def existing(name: str, fallback: str) -> str:
            return name if name in columns else fallback

        normalized_expr = (
            "COALESCE(NULLIF(normalized_name, ''), lower(trim(name)))"
            if "normalized_name" in columns
            else "lower(trim(name))"
        )
        course_code_expr = (
            "course_code"
            if "course_code" in columns
            else "(SELECT course_code FROM courses WHERE courses.id = concepts.course_id)"
        )
        status_expr = existing("status", "'reviewed'")
        confidence_expr = (
            """CASE
                WHEN confidence IN ('generated', 'reviewed', 'verified', 'unverified') THEN confidence
                WHEN CAST(confidence AS INTEGER) >= 9 THEN 'verified'
                WHEN CAST(confidence AS INTEGER) >= 6 THEN 'reviewed'
                WHEN CAST(confidence AS INTEGER) > 0 THEN 'generated'
                ELSE 'unverified'
            END"""
            if "confidence" in columns
            else "'unverified'"
        )

        cursor.execute("PRAGMA foreign_keys=OFF")
        cursor.execute(
            """
            CREATE TABLE concepts_new (
                id INTEGER NOT NULL PRIMARY KEY,
                course_id INTEGER,
                name VARCHAR(255) NOT NULL,
                normalized_name VARCHAR(255),
                description TEXT NOT NULL DEFAULT '',
                course_code VARCHAR(80),
                status VARCHAR(40) NOT NULL DEFAULT 'generated',
                topic VARCHAR(160) NOT NULL DEFAULT '',
                subtopic VARCHAR(160) NOT NULL DEFAULT '',
                aliases_json JSON NOT NULL DEFAULT '[]',
                related_concepts_json JSON NOT NULL DEFAULT '[]',
                confidence VARCHAR(40) NOT NULL DEFAULT 'unverified',
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL,
                FOREIGN KEY(course_id) REFERENCES courses (id),
                CONSTRAINT uq_concept_course_name UNIQUE (course_id, name)
            )
            """
        )
        cursor.execute(
            f"""
            INSERT INTO concepts_new (
                id,
                course_id,
                name,
                normalized_name,
                description,
                course_code,
                status,
                topic,
                subtopic,
                aliases_json,
                related_concepts_json,
                confidence,
                created_at,
                updated_at
            )
            SELECT
                id,
                course_id,
                name,
                {normalized_expr},
                {existing("description", "''")},
                {course_code_expr},
                {status_expr},
                {existing("topic", "''")},
                {existing("subtopic", "''")},
                {existing("aliases_json", "'[]'")},
                {existing("related_concepts_json", "'[]'")},
                {confidence_expr},
                {existing("created_at", "CURRENT_TIMESTAMP")},
                {existing("updated_at", "CURRENT_TIMESTAMP")}
            FROM concepts
            """
        )
        cursor.execute("DROP TABLE concepts")
        cursor.execute("ALTER TABLE concepts_new RENAME TO concepts")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_concepts_normalized_name ON concepts (normalized_name)")
        cursor.execute("PRAGMA foreign_keys=ON")
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        cursor.close()
        raw.close()


def init_db(bind_engine=None):
    from app import models  # noqa: F401

    target_engine = bind_engine or engine
    Base.metadata.create_all(bind=target_engine)
    _migrate_sqlite_concepts(target_engine)



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
