# Deployment Skill

> systemd + Nginx + Certbot (no Docker for this build)

This build runs as two plain processes on a Linux host - a `uvicorn`
process managed by systemd, and a static frontend build served by Nginx.
There is no Dockerfile, no `docker-compose.yml`, and no CI pipeline for this
build.

---

## Layout on the server

```
/opt/<app>/backend/     # synced app/ + requirements.txt, its own .venv, .env
/opt/<app>/output/      # OUTPUT_DIR - uploaded sources + generated clips
/var/www/<app>/         # built frontend static files (npm run build output)
```

Serve the frontend from `/var/www/...`, not from inside the backend's home
directory - a systemd service's home dir is typically `0750`, which blocks
Nginx (running as `www-data`) from traversing into it to read the static
files.

---

## systemd unit

```ini
# /etc/systemd/system/<app>-backend.service
[Unit]
Description=<App> backend
After=network.target

[Service]
Type=simple
User=<app>
Group=<app>
WorkingDirectory=/opt/<app>/backend
Environment=HOME=/opt/<app>
Environment=HF_HOME=/opt/<app>/hf-cache
ExecStart=/opt/<app>/backend/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010 --workers 1
Restart=on-failure
RestartSec=5
# Optional, if this host runs other CPU-hungry services (e.g. Docker
# containers) that would otherwise starve Whisper/ffmpeg under contention:
CPUWeight=400
Nice=-5

[Install]
WantedBy=multi-user.target
```

`--workers 1` matters here: `faster-whisper`'s model is cached in a
module-level global per process, so a single worker means every request
after the first reuses the already-loaded model instead of reloading it.

```bash
systemctl daemon-reload
systemctl enable --now <app>-backend
journalctl -u <app>-backend -f   # tail logs
```

---

## Nginx site

```nginx
server {
    listen 80;
    server_name <domain>;

    client_max_body_size 1600m;   # must exceed the backend's MAX_UPLOAD_BYTES

    root /var/www/<app>;
    index index.html;

    location /api/ {
        proxy_pass http://127.0.0.1:8010/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 300;
        proxy_send_timeout 300;
    }

    location /output/ {
        proxy_pass http://127.0.0.1:8010/output/;
        proxy_set_header Host $host;
    }

    location / {
        try_files $uri /index.html;   # SPA fallback for react-router
    }
}
```

```bash
ln -sf /etc/nginx/sites-available/<domain> /etc/nginx/sites-enabled/<domain>
nginx -t && systemctl reload nginx

# TLS - run once DNS for <domain> already resolves to this host
certbot --nginx -d <domain> --non-interactive --agree-tos -m <email> --redirect
```

Certbot rewrites the site file in place to add the `listen 443 ssl`
block and an HTTP->HTTPS redirect, and installs its own renewal timer.

---

## Environment File

```env
# backend/.env
DATABASE_URL=sqlite:////opt/<app>/backend/app.db   # absolute path under systemd
SECRET_KEY=<random, e.g. `python -c "import secrets; print(secrets.token_hex(32))"`>
ALLOWED_ORIGINS=["https://<domain>"]
OUTPUT_DIR=/opt/<app>/output
MAX_VIDEO_DURATION_SECONDS=1800
```

Frontend build reads `VITE_API_URL` at **build time** (baked into the
bundle) - set it to the bare origin, e.g. `VITE_API_URL=https://<domain>`,
since the frontend appends `/api` and `/output` itself.

---

## Deploy / redeploy

```bash
# Backend: sync code, install deps, restart
rsync -az backend/ <host>:/opt/<app>/backend/   # or tar | ssh ... | tar -x
ssh <host> "cd /opt/<app>/backend && .venv/bin/pip install -r requirements.txt && systemctl restart <app>-backend"

# Frontend: rebuild, copy static output
ssh <host> "cd /opt/<app>/frontend && npm ci && npm run build && cp -r dist/. /var/www/<app>/"
```

No `docker-compose build`/`down` step for this build - a redeploy is just a
code sync + `systemctl restart` (backend) or a rebuild + copy (frontend).

---

## Best Practices (this build)

- Run the backend as a dedicated non-root system user, home dir separate from where Nginx needs to read static files.
- `OUTPUT_DIR` and `DATABASE_URL` should be **absolute paths** once running under systemd - a relative path resolves against `WorkingDirectory`, which is easy to get wrong.
- Set `client_max_body_size` in Nginx to comfortably exceed the backend's own `MAX_UPLOAD_BYTES`, or large uploads fail at the proxy before ever reaching the app.
- If the host runs other CPU-bound services, use `CPUWeight`/`Nice` on the backend's systemd unit rather than trying to hard-reserve cores - it's a fair-share priority boost, not a reservation, so it doesn't starve the other services outright.
- `faster-whisper` downloads its model to `HF_HOME` on first use - point that somewhere writable and persistent (not the service's ephemeral working directory) so it isn't re-downloaded on every restart.
