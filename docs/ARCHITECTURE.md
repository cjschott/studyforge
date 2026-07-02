# StudyForge Architecture

StudyForge v0.4 keeps the static frontend and optional backend, then adds a backend-only Source Library foundation for future AI ingestion.

## Frontend

- HTML/CSS/vanilla JS.
- Loads static JSON when the backend is unavailable.
- Checks `/api/admin/health` at startup.
- Requires login when the backend is available.
- Uses localStorage as the immediate UI cache.
- Syncs attempts, bookmarks, and mock exam results to the backend when authenticated.
- Shows Source Library only after backend login.

## Backend

- FastAPI app in `backend/app`.
- SQLAlchemy ORM models in `backend/app/models.py`.
- SQLite database at `backend/studyforge.db` by default.
- JWT session token in an HTTP-only cookie.
- Import/export services preserve compatibility with static course packs.
- Source Library stores source libraries, source material metadata, extracted chunks, and import job status in SQLite.
- Uploaded original source files are stored under `backend/data/sources/originals/` by default, outside the static frontend deployment path.
- `backend/app/ai` contains disabled provider and agent placeholders so future AI integrations can plug in without changing the Source Library data model.

## Data Flow

Static mode:

```text
data/*.json -> frontend -> localStorage
```

Backend mode:

```text
SQLite -> /api/export/{course_code} -> frontend cache -> /api/progress endpoints -> SQLite
```

Source Library:

```text
browser upload -> /api/source-materials/upload -> backend file storage + SQLite metadata
stored source -> /api/source-materials/{id}/extract -> extraction service -> source_chunks
```

## Design Constraint

The backend must be additive. If it is down, the current study experience still works from JSON files.

Source Library is backend-only. Static mode does not upload or extract files.
