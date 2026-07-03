# StudyForge

StudyForge is a self-hosted learning platform that still works as a static HTML/CSS/vanilla JS app. Version `0.5.0-alpha.3` adds rule-based conflict detection and source validation review on top of Source Library chunks and concept review.

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
- Source Library uploads, extraction, and chunks are available after login.
- Concepts can be extracted from source chunks, reviewed, verified, rejected/restored, merged, aliased, related to other concepts, and traced back to source evidence.
- Conflicts can be detected from source materials and concepts, reviewed, resolved, rejected, and traced back to source/concept evidence.
- Course Builder can select extracted source materials and preview source, chunk, concept, verified concept, rejected concept, relationship, and unresolved conflict counts.
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

Backend environment variables:

```bash
export STUDYFORGE_DATABASE_URL=sqlite:////opt/studyforge/studyforge.db
export STUDYFORGE_SECRET_KEY='replace-with-a-long-random-secret'
export STUDYFORGE_ADMIN_PASSWORD='replace-default-password'
export STUDYFORGE_ENV=production
export STUDYFORGE_SOURCE_ORIGINALS_DIR=/opt/studyforge/backend/data/sources/originals
```

## Default Admin

Seed creates:

- Username: `admin`
- Password: `changeme`
- Role: `admin`

Set `STUDYFORGE_ADMIN_PASSWORD` before seeding on a deployed host. The default password is only for local bootstrap.

## Import Existing D413 Data

From `backend/`:

```bash
python -m app.seed --import-static ../data/d413
```

You can also import from the Administration screen after logging in as an admin.

## Source Library

Backend mode includes a Source Library section in the sidebar after login.

Supported initial uploads:

- PDF
- DOCX
- TXT
- Markdown
- CSV

Original files are stored under the backend service directory by default:

```text
backend/data/sources/originals/
```

Set `STUDYFORGE_SOURCE_ORIGINALS_DIR` to move this directory. Keep it outside the static frontend web root. Uploaded files are checksumed with SHA256 and duplicate uploads are rejected with a friendly conflict message.

Source text extraction support is practical but intentionally simple:

- TXT and Markdown are read directly.
- CSV rows are joined into readable text.
- DOCX uses `python-docx`.
- PDF uses `pypdf`.
- OCR, PPTX, Anki, vector search, and LLM generation are not part of v0.5.

## Concepts

Backend mode includes a Concepts section in the sidebar after login. Concepts are extracted from existing `source_chunks` with a rule-based extractor only:

- source headings
- glossary-looking lines such as `Term: definition`
- repeated capitalized technical terms
- a small Security+/networking keyword seed list

Extracted concepts are stored as `generated` with `generated` confidence and are linked back to source chunks through short evidence snippets. Rejected concepts remain in SQLite for lineage but are hidden from the concept list by default.

The Concepts screen supports:

- review, verify, reject, and restore actions
- editing name, description, and course code
- aliases with normalized duplicate prevention
- evidence views with source title, source type, source confidence, verification status, chunk number, page number, and evidence text
- relationship creation and status review
- admin merge controls that move aliases, source links, and relationships into the target concept without hard-deleting the source concept

## Conflicts

Backend mode includes a Conflicts section in the sidebar after login. Conflict detection is rule-based only and stores short evidence snippets rather than logging full source chunks.

The first validation checks flag:

- legacy Security+ exam references such as `SY0-501` or `SY0-601`
- answer-key-like text in unverified source chunks
- low-authority, unverified, or community-derived source material
- duplicate-looking concept names
- concepts with missing source lineage
- verified concepts linked to weak source evidence

Conflicts can be filtered by severity, status, type, and search text. Reviewers can mark conflicts reviewed, resolved, or rejected. No conflict action hard-deletes concepts, sources, chunks, or lineage.

## Course Builder Source Selection

Backend mode Course Builder can load source libraries, select source materials, and summarize the selected context by source count, chunk count, concept count, verified concept count, rejected concept count, relationship count, unresolved conflict count, extraction readiness, and source type. Concept Extraction is shown as active only when selected sources already have extracted concepts. A high-severity conflict warning appears when selected context has unresolved high-severity findings. This remains a preparation stage; it does not generate questions, flashcards, or course packs.

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

## Ubuntu / Nginx Deployment For schweb2

Deployment target:

- Frontend: `/var/www/html/studyforge`
- Backend: `/opt/studyforge/backend`
- API: `http://127.0.0.1:8000`
- nginx: `/studyforge/` serves the frontend and `/api/` proxies to FastAPI

Install:

```bash
sudo mkdir -p /opt/studyforge /var/www/html/studyforge /opt/backups
cd /opt/studyforge
git clone https://github.com/cjschott/studyforge.git .
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export STUDYFORGE_ADMIN_PASSWORD='replace-default-password'
export STUDYFORGE_SOURCE_ORIGINALS_DIR=/opt/studyforge/backend/data/sources/originals
python -m app.seed --import-static ../data/d413
python -m app.seed --import-static ../data/secplus
sudo cp -r ../index.html ../css ../js ../data /var/www/html/studyforge/
```

Install service and nginx config:

```bash
sudo cp ../deploy/systemd/studyforge-api.service /etc/systemd/system/studyforge-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now studyforge-api
sudo cp ../deploy/nginx/studyforge.conf /etc/nginx/sites-available/studyforge.conf
sudo ln -sf /etc/nginx/sites-available/studyforge.conf /etc/nginx/sites-enabled/studyforge.conf
sudo nginx -t
sudo systemctl reload nginx
```

## SQLite Backup

Stop writes or run during low activity, then copy the DB:

```bash
sqlite3 /opt/studyforge/backend/studyforge.db ".backup '/opt/backups/studyforge-$(date +%F).db'"
```

Also keep static course packs under version control.

## Known Limitations

- v0.5 remains an alpha: permissions are intentionally simple and not full RBAC.
- PBQ questions are manual-check placeholders unless a simplified answer is configured.
- Diagram questions render images and choices but do not support clickable regions yet.
- Course Builder files are prompt/template scaffolding, not an automated source-ingestion UI.
- Security+ content is generated/example starter material, not official exam content and not verified.
- Source Library extraction does not OCR scans and does not create questions automatically.
- Concept extraction is rule-based and review-oriented; it does not use a real LLM, embeddings, vector search, or question generation.
- The AI provider is intentionally disabled until a local LLM provider is configured in a later release.

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
node --test js/dashboard.admin.test.mjs js/sourceLibrary.test.mjs js/courseBuilder.test.mjs js/concepts.test.mjs
```
