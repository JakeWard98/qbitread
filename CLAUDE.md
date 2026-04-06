# CLAUDE.md

## Project Overview

qBitRead is a lightweight, read-only Docker web application that monitors a qBittorrent instance. It provides a dark, minimal dashboard showing all torrents with live speeds, progress, ETA, and ratios. The app is **read-only by design** — it only monitors torrents; it never modifies, adds, or deletes them.

### Why This App Exists

Self-hosted qBittorrent users need a simple, secure way to glance at torrent status without exposing the full qBittorrent Web UI. qBitRead provides a locked-down, multi-user dashboard that proxies all communication through a backend, keeping qBittorrent credentials completely hidden from the browser.

## Tech Stack

- **Backend**: Python 3.12, FastAPI, Uvicorn (ASGI)
- **Frontend**: Vanilla JavaScript, HTML5, CSS3 (no frameworks)
- **Database**: SQLite via SQLAlchemy (async) + aiosqlite
- **HTTP Client**: httpx (async) for qBittorrent API calls
- **Auth**: JWT (PyJWT) + bcrypt password hashing
- **Container**: Docker (multi-stage build, non-root user)
- **CI/CD**: GitHub Actions -> GitHub Container Registry (GHCR)

## Project Structure

```
app/                    # Backend (FastAPI)
  main.py               # App entry point, lifespan, page routes
  config.py             # Pydantic Settings (env var config)
  database.py           # SQLAlchemy async engine, DB init
  middleware.py          # Security headers, CSRF, rate limiting
  auth/                 # Authentication module
    models.py           # User SQLAlchemy model
    security.py         # JWT creation/verification, password hashing
    router.py           # Auth API endpoints
    schemas.py          # Pydantic request/response models
    dependencies.py     # FastAPI dependencies (get_current_user, require_admin)
  qbit/                 # qBittorrent integration
    client.py           # QBitClient with circuit breaker pattern
    router.py           # /api/torrents, /api/transfer endpoints
    schemas.py          # Torrent/transfer Pydantic schemas
templates/              # HTML pages (index, login, setup, admin)
static/
  js/                   # Vanilla JS (app.js, auth.js, setup.js, admin.js)
  css/style.css         # Dark theme with CSS variables
Dockerfile              # Multi-stage build
docker-compose.yml      # Production compose
.env.example            # Environment variable template
requirements.txt        # Python dependencies (pinned)
```

## Build & Run

```bash
# Development (no Docker)
pip install -r requirements.txt
export QBIT_PASSWORD=changeme ADMIN_PASSWORD=admin SECURE_COOKIES=false
uvicorn app.main:app --reload --port 8000

# Production (Docker)
cp .env.example .env    # Edit with your qBittorrent details
docker compose up -d    # Access at http://localhost:8112
```

## Architecture & Design Preferences

### Backend-as-Proxy

The backend is the **only** component that talks to qBittorrent. The browser never communicates with qBittorrent directly. All qBit API calls go through FastAPI endpoints that require authentication. This is the most critical architectural decision in the app.

```
Browser  -->  FastAPI (auth + proxy)  -->  qBittorrent API
              credentials here only
```

### Design Principles

- **Read-only**: The app monitors torrents. It does not add, pause, resume, or delete them. Do not add write operations to the qBittorrent API surface.
- **Vanilla JS frontend**: No React, Vue, or other frameworks. Keep it simple — plain JavaScript with fetch() calls. No build step for frontend assets.
- **Async everywhere**: All backend I/O is async (httpx, aiosqlite, SQLAlchemy async sessions). Do not introduce synchronous blocking calls.
- **Dark minimal UI**: The interface uses CSS variables for theming. The design is intentionally sparse — no unnecessary visual complexity.
- **Single-page feel**: Each page (dashboard, login, setup, admin) is a separate HTML template served by FastAPI, with JS handling dynamic behavior. Not a true SPA — no client-side routing.
- **Pydantic for all validation**: Request/response schemas use Pydantic models. Config uses pydantic-settings.
- **Circuit breaker on qBit client**: The `QBitClient` (`app/qbit/client.py`) uses exponential backoff (10s to 300s) on failed logins and detects IP bans (15-minute pause). Respect this pattern when modifying the client.

## Security Requirements

**These are non-negotiable. Every change must preserve these guarantees.**

### Credential Isolation

- qBittorrent credentials (`QBIT_HOST`, `QBIT_USERNAME`, `QBIT_PASSWORD`) exist **only** on the backend. They must **never** appear in API responses, HTML templates, JavaScript, or any data sent to the browser.
- The `SECRET_KEY` is auto-generated and persisted to `/app/data/.secret_key` with `0o600` permissions. It must never be logged or exposed.

### Authentication & Session Security

- JWT tokens are stored in **HTTP-only, SameSite=Strict** cookies. Never move tokens to localStorage, sessionStorage, or response bodies.
- When `SECURE_COOKIES=true`, cookies get the Secure flag (required behind HTTPS reverse proxy).
- JWT expiry is 12 hours by default (`JWT_EXPIRY_MINUTES=720`).
- Passwords are hashed with **bcrypt** (with salt). Never store or compare plaintext passwords.

### CSRF Protection

- Double-submit cookie pattern: CSRF token in cookie + `X-CSRF-Token` header on mutating requests.
- Exempt paths: `/api/auth/login`, `/api/auth/logout`, `/api/auth/setup` only.
- Do not add CSRF exemptions without careful consideration.

### Rate Limiting

- Login endpoint is rate-limited to 5 attempts per minute per IP (sliding window).
- Respects `X-Forwarded-For` for clients behind a reverse proxy.

### Security Headers

Applied via `SecurityHeadersMiddleware` in `app/middleware.py`:
- `Content-Security-Policy: default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; img-src 'self' data:; connect-src 'self'`
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

### Same-Origin Only

- No CORS headers are set. The app only accepts same-origin requests. Do not add CORS middleware unless explicitly required.

### Docker Security

- Container runs as non-root `appuser` (no login shell).
- Multi-stage build minimizes attack surface.
- SQLite database and secret key persisted in `/app/data/` volume.

## Code Style & Patterns

- **No test framework** currently in the project.
- **Middleware order matters**: SecurityHeaders -> RateLimiting -> CSRF (applied in reverse in `main.py`).
- **Error handling**: qBit client returns structured error responses; frontend shows connection status indicator with error messages.
- **Frontend polling**: Dashboard polls `/api/torrents` and `/api/transfer` every 5 seconds with automatic backoff on errors.
- **Dependencies are pinned** in `requirements.txt`. Update versions deliberately.

## Environment Variables

All configuration is via environment variables. See `.env.example` for the full list with defaults. Key variables:

| Variable | Required | Description |
|----------|----------|-------------|
| `QBIT_PASSWORD` | Yes | qBittorrent password (server-side only) |
| `QBIT_HOST` | No | qBittorrent URL (default: `http://localhost:8080`) |
| `SECRET_KEY` | No | JWT signing key (auto-generated if not set) |
| `ADMIN_PASSWORD` | Recommended | Bootstrap admin password (setup wizard if omitted) |
| `SECURE_COOKIES` | No | Set `true` behind HTTPS proxy |

## CI/CD

GitHub Actions workflow (`.github/workflows/docker-release.yml`):
- Triggers on GitHub release publication
- Multi-platform builds: `linux/amd64`, `linux/arm64`
- Pushes to GitHub Container Registry (GHCR)
- Semantic version tags: `1.2.3`, `1.2`, `1`, `latest` (or `beta` for pre-releases)
