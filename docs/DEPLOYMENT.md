# Deployment

Target: Ubuntu CT `schweb2`.

- Frontend path: `/var/www/html/studyforge`
- Backend path: `/opt/studyforge/backend`
- API bind: `http://127.0.0.1:8000`
- nginx frontend URL: `/studyforge/`
- nginx API proxy: `/api/`

## Install Files

```bash
sudo mkdir -p /opt/studyforge /var/www/html/studyforge /opt/backups
sudo chown -R "$USER":"$USER" /opt/studyforge
cd /opt/studyforge
git clone https://github.com/cjschott/studyforge.git .
```

## Backend Setup

```bash
cd /opt/studyforge/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export STUDYFORGE_ADMIN_PASSWORD='replace-default-password'
python -m app.seed --import-static ../data/d413
python -m app.seed --import-static ../data/secplus
```

## Systemd

Edit `deploy/systemd/studyforge-api.service` and replace `change-this-secret` and `replace-default-password`, then install:

```bash
sudo cp /opt/studyforge/deploy/systemd/studyforge-api.service /etc/systemd/system/studyforge-api.service
sudo systemctl daemon-reload
sudo systemctl enable --now studyforge-api
sudo systemctl status studyforge-api
```

## Frontend

```bash
sudo rsync -a --delete \
  /opt/studyforge/index.html \
  /opt/studyforge/css \
  /opt/studyforge/js \
  /opt/studyforge/data \
  /var/www/html/studyforge/
```

## Nginx

```bash
sudo cp /opt/studyforge/deploy/nginx/studyforge.conf /etc/nginx/sites-available/studyforge.conf
sudo ln -sf /etc/nginx/sites-available/studyforge.conf /etc/nginx/sites-enabled/studyforge.conf
sudo nginx -t
sudo systemctl reload nginx
```

Open:

```text
http://schweb2/studyforge/
```

## Backups

```bash
sqlite3 /opt/studyforge/backend/studyforge.db ".backup '/opt/backups/studyforge-$(date +%F).db'"
```

Back up static course packs and the SQLite database.

Export course packs from the API:

```bash
curl -b cookies.txt http://127.0.0.1:8000/api/export/d413 > d413-export.json
curl -b cookies.txt http://127.0.0.1:8000/api/export/secplus > secplus-export.json
```
