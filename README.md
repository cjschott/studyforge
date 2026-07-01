# StudyForge

StudyForge is a self-hosted learning platform that still works as a static HTML/CSS/vanilla JS app. Version `0.3.0-alpha` adds a FastAPI + SQLite backend foundation for accounts, DB-backed course data, progress sync, administration, and course import/export.

The existing static app is preserved. If the backend is not running, StudyForge loads JSON course packs from `data/` and stores progress in browser `localStorage`.

## Modes

Static mode:

- Serve the repo over HTTP.
- Course data loads from `data/courses.json` and course folders.
- Progress stays in browser `localStorage` under `studyforge:v1`.
- The sidebar shows `Local Mode`.

Backend mode:

- Run the FastAPI app from `backend/`.
- The frontend checks `/api/admin/health`.
- If the backend is available, users sign in.
- Courses load from SQLite exports.
- Attempts, bookmarks, and mock results sync to the backend.
- LocalStorage remains an immediate frontend cache so the UI stays responsive.

## Local Static Run

```powershell
python -m http.server 8080
```

Open:

```text
http://127.0.0.1:8080/
```

Stop the backend to test fallback mode. The app should show `Local Mode` and still load D413 and Security+ from `data/`.

## Backend Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Windows PowerShell:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

SQLite database:

```text
backend/studyforge.db
```

Override with:

```bash
export STUDYFORGE_DATABASE_URL=sqlite:////opt/studyforge/studyforge.db
```

## Default Admin

Seed creates:

- Username: `admin`
- Password: `changeme`
- Role: `admin`

Change this before deployment. The default password is only for local bootstrap.

## Import Existing D413 Data

From `backend/`:

```bash
python -m app.seed --import-static ../data/d413
```

You can also import from the Administration screen after logging in as an admin.

## Add Security+

Security+ starter data is under:

```text
data/secplus/
```

It is registered in `data/courses.json`. These are original StudyForge starter examples, not official exam questions. To import into SQLite:

```bash
cd backend
python -m app.seed --import-static ../data/secplus
```

## Export A Course Pack

Backend API:

```text
GET /api/export/{course_code}
```

Frontend:

- Backend mode: Administration -> Export Active DB Course.
- Static mode: Settings -> Export Current Course Pack.

## Ubuntu / Nginx Deployment

Install backend:

```bash
cd /opt/studyforge/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed --import-static ../data/d413
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Serve frontend from:

```text
/var/www/html/studyforge
```

Proxy `/api` to:

```text
http://127.0.0.1:8000
```

Examples:

- `deploy/nginx/studyforge.conf`
- `deploy/systemd/studyforge-api.service`

## SQLite Backup

Stop writes or run during low activity, then copy the DB:

```bash
sqlite3 /opt/studyforge/backend/studyforge.db ".backup '/opt/backups/studyforge-$(date +%F).db'"
```

Also keep static course packs under version control.

## Project Layout

```text
backend/                 FastAPI app, SQLite models, import/export services
css/                     Static frontend styles
data/                    Static course packs
docs/                    Architecture and deployment docs
js/                      Vanilla JS frontend modules
tools/coursepack-builder Course Builder prompts, templates, examples
```

## Tests

```bash
python -m pytest backend/tests -q
```
