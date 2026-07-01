# StudyForge Architecture

StudyForge v0.3 keeps the static frontend and adds an optional backend.

## Frontend

- HTML/CSS/vanilla JS.
- Loads static JSON when the backend is unavailable.
- Checks `/api/admin/health` at startup.
- Requires login when the backend is available.
- Uses localStorage as the immediate UI cache.
- Syncs attempts, bookmarks, and mock exam results to the backend when authenticated.

## Backend

- FastAPI app in `backend/app`.
- SQLAlchemy ORM models in `backend/app/models.py`.
- SQLite database at `backend/studyforge.db` by default.
- JWT session token in an HTTP-only cookie.
- Import/export services preserve compatibility with static course packs.

## Data Flow

Static mode:

```text
data/*.json -> frontend -> localStorage
```

Backend mode:

```text
SQLite -> /api/export/{course_code} -> frontend cache -> /api/progress endpoints -> SQLite
```

## Design Constraint

The backend must be additive. If it is down, the current study experience still works from JSON files.
