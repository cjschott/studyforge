import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


BACKEND_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DATABASE_URL = f"sqlite:///{BACKEND_DIR / 'studyforge.db'}"
DATABASE_URL = os.getenv("STUDYFORGE_DATABASE_URL", DEFAULT_DATABASE_URL)

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def init_db(bind_engine=None):
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=bind_engine or engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
