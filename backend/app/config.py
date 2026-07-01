import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    env: str
    database_url: str
    secret_key: str
    admin_password: str
    session_minutes: int
    cookie_secure: bool
    cors_origins: list[str]


def get_settings() -> Settings:
    env = os.getenv("STUDYFORGE_ENV", "development")
    origins = os.getenv(
        "STUDYFORGE_CORS_ORIGINS",
        "http://127.0.0.1:8080,http://localhost:8080,http://127.0.0.1:8000,http://localhost:8000",
    )
    return Settings(
        env=env,
        database_url=os.getenv("STUDYFORGE_DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'studyforge.db'}"),
        secret_key=os.getenv("STUDYFORGE_SECRET_KEY", "change-this-dev-secret"),
        admin_password=os.getenv("STUDYFORGE_ADMIN_PASSWORD", "changeme"),
        session_minutes=int(os.getenv("STUDYFORGE_SESSION_MINUTES", "10080")),
        cookie_secure=os.getenv("STUDYFORGE_COOKIE_SECURE", "false").lower() == "true",
        cors_origins=[origin.strip() for origin in origins.split(",") if origin.strip()],
    )
