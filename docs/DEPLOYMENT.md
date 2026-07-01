# Deployment

## Backend

```bash
cd /opt/studyforge/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed --import-static ../data/d413
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Use systemd for long-running service. See:

```text
deploy/systemd/studyforge-api.service
```

## Frontend

Copy the static files to:

```text
/var/www/html/studyforge
```

Use nginx to serve the frontend and proxy `/api` to FastAPI. See:

```text
deploy/nginx/studyforge.conf
```

## Backups

```bash
sqlite3 /opt/studyforge/backend/studyforge.db ".backup '/opt/backups/studyforge-$(date +%F).db'"
```

Back up static course packs and the SQLite database.
