# StudyForge Backend

FastAPI backend foundation for StudyForge v0.3 alpha.

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

## Import Existing Static Course Data

From `backend/`:

```bash
python -m app.seed --import-static ../data/d413
```

SQLite is stored at `backend/studyforge.db` by default. Set `STUDYFORGE_DATABASE_URL` to override it for systemd or other deployment layouts.
