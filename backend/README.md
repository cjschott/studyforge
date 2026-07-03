# StudyForge Backend

FastAPI backend foundation for StudyForge v0.5 alpha.

## Local Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export STUDYFORGE_ADMIN_PASSWORD='replace-default-password'
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Default admin:

- Username: `admin`
- Password: `changeme`

Change this before using the backend with real data.

## Environment Variables

- `STUDYFORGE_DATABASE_URL`: SQLAlchemy database URL. Defaults to `sqlite:///backend/studyforge.db`.
- `STUDYFORGE_SECRET_KEY`: JWT signing secret. Set this in production.
- `STUDYFORGE_ADMIN_PASSWORD`: password used when seeding the first admin.
- `STUDYFORGE_ENV`: environment label, for example `development` or `production`.
- `STUDYFORGE_SESSION_MINUTES`: session lifetime in minutes.
- `STUDYFORGE_COOKIE_SECURE`: set `true` when serving over HTTPS.
- `STUDYFORGE_CORS_ORIGINS`: comma-separated development origins. Same-origin nginx proxying does not require browser CORS.
- `STUDYFORGE_SOURCE_ORIGINALS_DIR`: backend-local directory for uploaded source files. Defaults to `backend/data/sources/originals`.

## Source Library

Authenticated users can create source libraries, upload PDF/DOCX/TXT/Markdown/CSV materials, extract text, and preview stored chunks.

Uploaded originals should stay outside the static frontend web root. The default backend-local path is ignored by git:

```text
backend/data/sources/originals/
```

Duplicate source uploads are blocked by SHA256 checksum. Extraction does not use OCR and does not call an AI provider.

## Concepts

Authenticated users can list, create, update, and review concepts. Source materials with extracted chunks can run rule-based concept extraction at:

```text
POST /api/source-materials/{id}/extract-concepts
```

Concept links preserve `source_id`, `source_chunk_id`, evidence text, confidence score, and extraction method. Delete requests are admin-only and mark concepts as `rejected` so source lineage remains intact.

v0.5 alpha.2 adds dedicated APIs for aliases, merge, evidence, and relationship management:

```text
GET    /api/concepts/{id}/aliases
POST   /api/concepts/{id}/aliases
DELETE /api/concepts/{id}/aliases/{alias_id}
POST   /api/concepts/{id}/merge
GET    /api/concepts/{id}/evidence
PUT    /api/concept-relationships/{relationship_id}
DELETE /api/concept-relationships/{relationship_id}
```

## Conflicts

v0.5 alpha.3 adds source and concept validation findings through authenticated conflict APIs:

```text
GET  /api/conflicts
GET  /api/conflicts/{id}
PUT  /api/conflicts/{id}
POST /api/conflicts/{id}/resolve
POST /api/source-materials/{id}/detect-conflicts
POST /api/concepts/{id}/detect-conflicts
```

Detection is rule-based only. It flags legacy Security+ exam references, low-authority or unverified source material, answer-key-like chunks without verified lineage, duplicate-looking concepts, missing source lineage, and verified concepts tied to weak evidence. Conflict evidence is stored as short snippets and source/concept lineage is preserved.

## Import Existing Static Course Data

From `backend/`:

```bash
python -m app.seed --import-static ../data/d413
```

SQLite is stored at `backend/studyforge.db` by default. Set `STUDYFORGE_DATABASE_URL` to override it for systemd or other deployment layouts.
