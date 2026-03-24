# qBitRead

A lightweight Docker web app that monitors your qBittorrent instance. Dark, minimal dashboard showing all torrents with live speeds, progress, and ETA.

## Features

- Real-time torrent monitoring (5s polling)
- Filter by status: All / Downloading / Seeding / Stalled / Paused
- Sortable columns, search
- User authentication with admin role
- Admin panel to create/delete users
- Security: CSRF protection, rate-limited login, security headers, HTTP-only JWT cookies
- qBittorrent credentials never exposed to the browser

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your qBittorrent details and a random SECRET_KEY

# Build and run
docker compose up -d

# Open http://localhost:8000
# Login with the ADMIN_USERNAME / ADMIN_PASSWORD from your .env
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QBIT_HOST` | No | `http://localhost:8080` | qBittorrent Web UI URL |
| `QBIT_USERNAME` | No | `admin` | qBittorrent username |
| `QBIT_PASSWORD` | Yes | — | qBittorrent password |
| `SECRET_KEY` | Yes | — | Random string for JWT signing (generate with `python -c "import secrets; print(secrets.token_hex(32))"`) |
| `ADMIN_USERNAME` | No | `admin` | Bootstrap admin username |
| `ADMIN_PASSWORD` | Yes | — | Bootstrap admin password |
| `SECURE_COOKIES` | No | `true` | Set to `false` for local dev without HTTPS |

## Production: HTTPS with Reverse Proxy

Do not expose port 8000 directly. Use a reverse proxy for TLS termination.

**Caddy** (recommended — automatic HTTPS):

```
qbit.yourdomain.com {
    reverse_proxy qbitread:8000
}
```

**Nginx:**

```nginx
server {
    listen 443 ssl;
    server_name qbit.yourdomain.com;

    ssl_certificate     /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Security

- JWT tokens stored in HTTP-only, Secure, SameSite=Strict cookies
- CSRF double-submit cookie protection on all mutating API requests
- Login rate limiting (5 attempts/min per IP)
- Security headers: CSP, X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy
- qBittorrent credentials stay server-side only
- Container runs as non-root user
- SQLite database persisted in Docker volume

## Development

```bash
# Without Docker
pip install -r requirements.txt
export SECRET_KEY=dev-secret ADMIN_PASSWORD=admin SECURE_COOKIES=false
uvicorn app.main:app --reload --port 8000
```
