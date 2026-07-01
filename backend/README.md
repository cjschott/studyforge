# StudyForge Backend

FastAPI backend foundation for StudyForge v0.3.

## Local Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Default admin:

- Username: `admin`
- Password: `changeme`

Change this before using the backend with real data.

## Import Existing Static Course Data

From `backend/`:

```bash
python -m app.seed --import-static ../data/d413
```

SQLite is stored at `backend/studyforge.db` by default. Set `STUDYFORGE_DATABASE_URL` to override it.
