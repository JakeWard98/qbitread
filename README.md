# qBitRead

A lightweight Docker web app that monitors your qBittorrent instance. Dark, minimal dashboard showing all torrents with live speeds, progress, and ETA.

## Features

- Real-time torrent monitoring (5s polling)
- Filter by status: All / Downloading / Seeding / Stalled / Paused
- Sortable columns, search
- User authentication with admin role
- Admin panel to create/delete users and change passwords
- Password policy enforcement (8+ chars, uppercase, lowercase, digit, special character)
- Weak password detection — existing users with grandfathered passwords see a dashboard banner
- First-run setup wizard (no config file editing required)
- Security: CSRF protection, rate-limited login, security headers, HTTP-only JWT cookies
- qBittorrent credentials never exposed to the browser

## Quick Start

```bash
# Clone and configure
cp .env.example .env
# Edit .env with your qBittorrent details

# (Recommended) Set admin credentials in .env:
#   ADMIN_USERNAME=admin
#   ADMIN_PASSWORD=your-password
#
# Or skip them — a setup wizard will guide you on first visit.

# Build and run
docker compose up -d

# Open http://localhost:8112
```

## Docker Image Tags

The image is published to GitHub Container Registry at `ghcr.io/jakeward98/qbitread` and supports both `linux/amd64` and `linux/arm64` platforms.

```bash
docker pull ghcr.io/jakeward98/qbitread:latest
```

**Stable releases** (e.g. GitHub release `v1.2.3`) produce these tags:

| Tag | Description |
|-----|-------------|
| `1.2.3` | Exact version — pinned, never changes |
| `1.2` | Latest patch within the `1.2.x` line |
| `1` | Latest minor + patch within the `1.x.x` line |
| `latest` | Most recent stable release |

**Pre-releases** (e.g. GitHub release `v1.2.3-beta.1`) produce these tags:

| Tag | Description |
|-----|-------------|
| `1.2.3-beta.1` | Exact pre-release version |
| `beta` | Most recent pre-release |

Pre-releases do **not** update `latest`, so stable users are unaffected.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `QBIT_HOST` | No | `http://localhost:8080` | qBittorrent Web UI URL |
| `QBIT_USERNAME` | No | `admin` | qBittorrent username |
| `QBIT_PASSWORD` | Yes | — | qBittorrent password |
| `SECRET_KEY` | No | auto-generated | Random string for JWT signing. Auto-generated and persisted to the data volume if not set. |
| `ADMIN_USERNAME` | No | `admin` | **Recommended.** Bootstrap admin username. |
| `ADMIN_PASSWORD` | No | — | **Recommended.** Bootstrap admin password (must meet password policy: 8+ chars, uppercase, lowercase, digit, special char). If omitted, a setup wizard is shown on first run. |
| `SECURE_COOKIES` | No | `false` | Set to `true` if behind an HTTPS reverse proxy |

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

When using HTTPS, set `SECURE_COOKIES=true` in your environment.

## Security

- JWT tokens stored in HTTP-only, SameSite=Strict cookies (Secure flag when `SECURE_COOKIES=true`)
- CSRF double-submit cookie protection on all mutating API requests
- Login rate limiting (5 attempts/min per IP)
- Password policy: 8+ characters, uppercase, lowercase, digit, and special character required
- Grandfathered weak passwords are flagged at login; admins can update them from the admin panel
- Security headers: CSP, X-Frame-Options DENY, X-Content-Type-Options, Referrer-Policy
- qBittorrent credentials stay server-side only
- Container runs as non-root user
- SQLite database persisted in Docker volume
- SECRET_KEY auto-generated and persisted if not provided

## Development

```bash
# Without Docker
pip install -r requirements.txt
export QBIT_PASSWORD=changeme ADMIN_PASSWORD=admin SECURE_COOKIES=false
uvicorn app.main:app --reload --port 8000
# SECRET_KEY is auto-generated if not set
```
