# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security
- **2026-07-20 dependency re-audit — 7 advisories closed (1 High/7.5, 1 High/7.4, 4 Moderate, 1 Low).**
  Scheduled routine `pip-audit` against a fresh venv of the pinned set surfaced
  **9 records / 6 distinct GHSAs** across `PyJWT 2.12.1` and `pydantic-settings
  2.14.1` (as previously recorded in the still-open #62/#63/#64/#65/#66/#67).
  Manual GHSA / NVD / OSV cross-check additionally identified **GHSA-82w8-qh3p-5jfq
  / CVE-2026-54283** (Starlette `request.form()` DoS, High, CVSS 7.5, published
  2026-06-12, fixed 1.3.1) — pip-audit missed it because the resolver already
  picked `starlette 1.3.1` under the previous `>=1.1.0` floor, but the loose
  floor left a regression window. Floor tightened to `>=1.3.1`. All fixes applied:
    - `PyJWT 2.12.1 → 2.13.0`
    - `pydantic-settings 2.14.1 → 2.14.2`
    - `starlette>=1.1.0 → starlette>=1.3.1`

  Post-bump `pip-audit -r requirements.txt` returns **0 known vulnerabilities**
  against the resolved set (`starlette 1.3.1`, `PyJWT 2.13.0`, `pydantic-settings
  2.14.2`).

  | Advisory | Package | Severity / CVSS | Fixed in | Reachable in qBitRead? |
  |---|---|---|---|---|
  | GHSA-82w8-qh3p-5jfq / CVE-2026-54283 | starlette | **High, 7.5** | 1.3.1 | **No** — no `Form()` / `request.form()` usage; all endpoints consume JSON via Pydantic. Floor bump is defence-in-depth against regression. |
  | GHSA-xgmm-8j9v-c9wx / CVE-2026-48526 | PyJWT | **High, 7.4** | 2.13.0 | **No** — `verify_jwt()` pins `algorithms=[settings.JWT_ALGORITHM]` to a single symmetric `HS256` with static `SECRET_KEY`; no asymmetric alg to pivot through. |
  | GHSA-jq35-7prp-9v3f / CVE-2026-48523 | PyJWT | Moderate, 5.4 | 2.13.0 | **No** — no `PyJWK` / `PyJWKClient` usage. |
  | GHSA-w7vc-732c-9m39 / CVE-2026-48525 | PyJWT | Moderate, 5.3 | 2.13.0 | **No** — no detached-JWS (`b64=false`) path. |
  | GHSA-993g-76c3-p5m4 / CVE-2026-48522 | PyJWT | Moderate, 4.2 | 2.13.0 | **No** — no `PyJWKClient` usage. |
  | GHSA-fhv5-28vv-h8m8 / CVE-2026-48524 | PyJWT | Low, 3.7 | 2.13.0 | **No** — no `PyJWKClient` usage. |
  | GHSA-4xgf-cpjx-pc3j | pydantic-settings | Moderate, 5.3 | 2.14.2 | **No** — `app/config.py` uses `BaseSettings` with `SettingsConfigDict(env_file=".env")`; `NestedSecretsSettingsSource` is never instantiated. |

  Reviewed every other direct dep (`fastapi 0.136.1`, `uvicorn 0.47.0`,
  `httpx 0.28.1`, `bcrypt 5.0.0`, `aiosqlite 0.22.1`) and notable transitive
  (`anyio 4.14.2`, `certifi 2026.6.17`, `h11 0.16.0`, `httpcore 1.0.9`,
  `pydantic 2.13.4`, `pydantic-core 2.46.4`, `typing-inspection 0.4.2`,
  `python-dotenv 1.2.2`, `idna 3.18`, `urllib3 2.7.0`) against GHSA / NVD /
  OSV — no additional advisories since the 2026-07-13 re-audit tracked by #67.

  Highest CVSS in this batch is **7.5** (Starlette form DoS), which does not
  clear the routine's `>7.5` auto-merge threshold — PR left for human review.

### Dependencies
- Bumped `PyJWT 2.12.1 → 2.13.0` (see 2026-07-20 Security entry above).
- Bumped `pydantic-settings 2.14.1 → 2.14.2` (see 2026-07-20 Security entry above).
- Bumped `starlette` floor `>=1.1.0 → >=1.3.1` (see 2026-07-20 Security entry above).

- **2026-06-01 dependency re-audit — clean.** Fresh `pip-audit` against a
  clean venv of the pinned set (`fastapi 0.136.1`, `starlette>=1.1.0`
  resolved to `1.1.0`, `uvicorn 0.47.0`, `httpx 0.28.1`, `PyJWT 2.12.1`,
  `bcrypt 5.0.0`, `aiosqlite 0.22.1`, `pydantic-settings 2.14.1`)
  returned **0 known vulnerabilities** at Critical/High/Moderate/Low.
  Manual GHSA / NVD cross-check across every direct and notable
  transitive dep (`anyio 4.13.0`, `certifi 2026.4.22`, `h11 0.16.0`,
  `httpcore 1.0.9`, `pydantic 2.13.4`, `pydantic-core 2.46.4`,
  `typing-inspection 0.4.2`, `python-dotenv 1.2.2`) returned no new
  advisories in the five days since the 2026-05-27 re-audit. No GitHub
  Security advisories or Dependabot alerts open against the repo.
  Confirmed still patched:
  - `starlette>=1.1.0` still closes GHSA-86qp-5c8j-p5mr / CVE-2026-48710
    (BadHost — Host-header path poisoning, Moderate),
    GHSA-wqp7-x3pw-xc5r (StaticFiles UNC-path SSRF, High) and
    GHSA-x746-7m8f-x49c (HTTPEndpoint getattr dispatch, Moderate).
  - `starlette>=1.1.0` still closes CVE-2025-62727 (FileResponse
    Range-header O(n²) DoS, High) and CVE-2025-54121 (multipart-parsing
    event-loop block, Moderate).
  - `PyJWT 2.12.1` still closes CVE-2026-32597 (`crit` header parameter
    not validated, High).
  No code or dependency-version changes required.
- **2026-06-08 dependency re-audit — clean.** `pip-audit` against a fresh
  venv of the pinned set (`fastapi 0.136.1`, `starlette>=1.1.0` → resolved
  `1.2.1`, `uvicorn 0.47.0`, `httpx 0.28.1`, `PyJWT 2.12.1`, `bcrypt 5.0.0`,
  `aiosqlite 0.22.1`, `pydantic-settings 2.14.1`) returned **0 known
  vulnerabilities** at Critical/High/Moderate/Low. Manual GHSA / NVD /
  OSV cross-check across every direct dep and notable transitive returned
  no new advisories in the week since the 2026-06-01 entry. No GitHub
  Security advisories or Dependabot alerts open against the repo. Confirmed
  still patched:
  - `starlette>=1.1.0` continues to close GHSA-86qp-5c8j-p5mr /
    CVE-2026-48710 (BadHost — Host-header `request.url.path` poisoning,
    Moderate, CVSS 6.5; fixed 1.0.1), GHSA-wqp7-x3pw-xc5r (StaticFiles
    UNC-path SSRF on Windows, High, CVSS 7.5; fixed 1.1.0),
    GHSA-x746-7m8f-x49c (HTTPEndpoint `getattr` dispatch, Moderate,
    CVSS 5.3; fixed 1.1.0), CVE-2025-62727 (FileResponse Range-header
    O(n²) DoS, High) and CVE-2025-54121 (multipart-parsing event-loop
    block, Moderate). Latest PyPI is `starlette 1.2.1` (released
    2026-05-31); the resolver already picks it under the existing floor,
    so no requirements.txt bump is required.
  - `PyJWT 2.12.1` continues to close CVE-2026-32597 (`crit` header
    parameter not validated, High, CVSS 7.5; fixed 2.12.0). `PyJWT 2.13.0`
    is available but only adds an `InsecureKeyLengthWarning` quality
    enhancement — no new CVE forces the bump.
  - `fastapi 0.136.3` is the latest PyPI release (2026-05-23) but is
    documentation-only over `0.136.1`; no new CVE forces the bump.
  No code or dependency-version changes required — pure documentation.
- **2026-05-27 dependency re-audit — three new Starlette advisories fixed.**
  `pip-audit` against a fresh venv resolved the pinned set to
  `starlette 1.1.0` (latest) and reported **0 known vulnerabilities**, but a
  manual GHSA / NVD cross-check found three advisories published 2026-05-21…23
  — *after* the 2026-05-18 audit — affecting Starlette versions the previous
  `>=0.49.1` floor still permitted. Only one (the Host-header issue) had a
  `PYSEC`/OSV record at audit time, so the automated scan alone would have
  missed the other two:
  - **GHSA-86qp-5c8j-p5mr / CVE-2026-48710** — missing `Host` header
    validation poisons `request.url.path`, bypassing path-based security
    checks (Moderate, CVSS 6.5; fixed 1.0.1). **Reachable here:** both
    `RateLimitMiddleware` (login limiter) and `CSRFMiddleware` (exempt-path
    and `/api/` enforcement) keyed their decisions off `request.url.path`.
  - **GHSA-wqp7-x3pw-xc5r** — `StaticFiles` resolves UNC paths on Windows,
    enabling SSRF / NTLM-credential theft via forced SMB auth (High, CVSS
    7.5; fixed 1.1.0). qBitRead mounts `StaticFiles`, but the official
    deployment is Linux/Docker, where UNC paths are not absolute — not
    exploitable there; the floor bump closes it for any Windows dev host.
  - **GHSA-x746-7m8f-x49c** — `HTTPEndpoint` dispatches the client method via
    `getattr`, exposing non-handler attributes (Moderate, CVSS 5.3; fixed
    1.1.0). Not applicable: qBitRead uses FastAPI function routes, no
    `HTTPEndpoint` subclasses. Closed by the upgrade regardless.
  Raised the `starlette` floor `>=0.49.1` → **`>=1.1.0`** (highest fix) to
  guarantee the patched framework, and hardened both middleware to read the
  raw ASGI `scope["path"]` instead of `request.url.path` so path-based
  security checks match the path the router actually dispatches even if a
  vulnerable Starlette is ever resolved. All other pinned deps
  (`fastapi 0.136.1`, `uvicorn 0.47.0`, `httpx 0.28.1`, `PyJWT 2.12.1`,
  `bcrypt 5.0.0`, `aiosqlite 0.22.1`, `pydantic-settings 2.14.1`) and
  transitives remain clean. Smoke-tested in a clean venv: imports OK,
  `pip-audit` clean, `/login` 200, CSRF still blocks a token-less `/api/`
  POST sent with a crafted `Host` header, login stays CSRF-exempt, and the
  login rate limiter still trips at the configured threshold.
- **2026-05-18 dependency re-audit.** Fourth consecutive clean run.
  `pip-audit` against a fresh venv of the (now-bumped) pinned set
  (`fastapi 0.136.1`, `starlette>=0.49.1` → resolved `1.0.0`,
  `uvicorn 0.47.0`, `httpx 0.28.1`, `PyJWT 2.12.1`, `bcrypt 5.0.0`,
  `aiosqlite 0.22.1`, `pydantic-settings 2.14.1`) returned **0 known
  vulnerabilities** at Critical/High/Moderate/Low. Manual GHSA / NVD
  cross-check across every direct and transitive dep (`anyio 4.13.0`,
  `certifi 2026.4.22`, `h11 0.16.0`, `httpcore 1.0.9`,
  `pydantic 2.13.4`, `pydantic-core 2.46.4`, `typing-inspection 0.4.2`,
  `python-dotenv 1.2.2`) returned no new advisories in the two weeks
  since the 2026-05-04 re-audit. No GitHub Security advisories or
  Dependabot alerts open against the repo. Confirmed:
  - `starlette>=0.49.1` still closes CVE-2025-62727 (FileResponse
    Range-header O(n²) DoS, High) and CVE-2025-54121 (multipart-parsing
    event-loop block on rollover-to-disk, Moderate).
  - `PyJWT 2.12.1` still closes CVE-2026-32597 (`crit` header parameter
    not validated, High).
  Only safe maintenance bumps applied — see Dependencies below.
- **2026-05-04 dependency re-audit.** Third consecutive clean run.
  Manual GHSA / NVD cross-check across every pinned dep in
  `requirements.txt` (`fastapi 0.136.0`, `starlette>=0.49.1`,
  `uvicorn 0.44.0`, `httpx 0.28.1`, `PyJWT 2.12.1`, `bcrypt 5.0.0`,
  `aiosqlite 0.22.1`, `pydantic-settings 2.13.1`) returned **0 known
  vulnerabilities** at Critical/High/Moderate/Low. No new advisories
  affecting any pinned dep have been published in the week since the
  2026-04-27 re-audit. Confirmed:
  - `starlette>=0.49.1` still closes CVE-2025-62727 (FileResponse
    Range-header O(n²) DoS, High) and CVE-2025-54121 (multipart-parsing
    event-loop block on rollover-to-disk, Moderate; fixed upstream in
    0.47.2).
  - `PyJWT 2.12.1` still closes CVE-2026-32597 (`crit` header parameter
    not validated, High; fixed upstream in 2.12.0).
  No code changes required.
- **2026-04-27 dependency re-audit.** Second consecutive clean run of
  `pip-audit` and a manual GHSA cross-check across every pinned dep in
  `requirements.txt` (`fastapi 0.136.0`, `starlette>=0.49.1`,
  `uvicorn 0.44.0`, `httpx 0.28.1`, `PyJWT 2.12.1`, `bcrypt 5.0.0`,
  `aiosqlite 0.22.1`, `pydantic-settings 2.13.1`) — **0 known
  vulnerabilities** at Critical/High/Moderate/Low. No code changes
  required. Confirmed:
  - `starlette>=0.49.1` still closes CVE-2025-62727 (FileResponse
    Range-header O(n²) DoS).
  - `PyJWT 2.12.1` includes the fix for CVE-2026-32597 (`crit` header
    parameter not validated, High, fixed upstream in 2.12.0).
- **2026-04-20 dependency re-audit.** `pip-audit` (PyPI advisory service) and
  a manual GHSA cross-check of every pinned dep in `requirements.txt`
  (`fastapi 0.136.0`, `starlette>=0.49.1`, `uvicorn 0.44.0`, `httpx 0.28.1`,
  `PyJWT 2.12.1`, `bcrypt 5.0.0`, `aiosqlite 0.22.1`, `pydantic-settings
  2.13.1`) returned **0 known vulnerabilities** at Critical/High/Moderate/Low.
  No code changes required.
- Pinned `starlette>=0.49.1` to close CVE-2025-62727 (O(n²) DoS via `Range`
  header merging in `FileResponse`). qBitRead serves HTML templates via
  `FileResponse`, so the path was reachable.
- `/api/qbit/browser-auth-creds` is now gated behind the new
  `ENABLE_BROWSER_AUTH` environment variable (default `false`). When disabled,
  the endpoint returns 404 and the admin panel hides the Browser Auth form.
  Previously, any admin session could retrieve the qBit username + password
  in plaintext JSON — this silently contradicted the project's "credentials
  never leave the server" guarantee. Operators who need the feature for
  IP-ban recovery must now opt in explicitly.
- Fail-fast if `SECRET_KEY` cannot be persisted to disk. Previously, a
  filesystem or permission error caused silent fallback to an ephemeral
  in-memory key, invalidating every existing JWT on the next container
  restart with no operator signal.
- Pinned bcrypt work factor to `rounds=12` in both `hash_password()` and the
  timing-attack dummy hash. Prevents library default drift from silently
  changing the hashing cost.
- Disabled the OpenAPI schema endpoint (`/openapi.json`). `/docs` and `/redoc`
  were already disabled, but the underlying schema — which enumerates every
  admin-only endpoint — remained publicly readable.

### Added
- `ENABLE_BROWSER_AUTH` environment variable (see README env-var table).
- Docker Compose healthcheck probing `/login` — container now reports
  `healthy` / `unhealthy` via `docker inspect`. Also added to
  `docker-compose.hardcoded.yml`.
- `SECURITY.md` — supported versions, private disclosure process, threat
  model, operational recommendations.
- `CHANGELOG.md` — this file.

### Dependencies
- **2026-05-27 security bump.** `starlette` floor `>=0.49.1` → **`>=1.1.0`**
  to close GHSA-86qp-5c8j-p5mr / CVE-2026-48710, GHSA-wqp7-x3pw-xc5r and
  GHSA-x746-7m8f-x49c (see Security above). The resolver already picked
  `starlette 1.1.0` under the old floor, so this is a guarantee — not a
  runtime change. FastAPI 0.136.1 (declares `starlette>=0.46.0`) resolves
  cleanly against the new floor. All other pins unchanged.
- **2026-05-18 dependency refresh.** Safe maintenance bumps to current
  PyPI latest. Resolver still picks `starlette 1.0.0` transitively under
  the existing `>=0.49.1` floor. Smoke test in clean venv: imports OK,
  `pip-audit` clean, uvicorn boots, JWT + CSRF cookie issuance unchanged,
  bcrypt `$2b$12$` hash prefix preserved.
  - uvicorn 0.46.0 → **0.47.0**
  - pydantic-settings 2.14.0 → **2.14.1**
  - fastapi, starlette, httpx, PyJWT, bcrypt, aiosqlite already at latest
- **2026-05-04 dependency refresh.** Bumped pinned deps to current PyPI
  latest. Resolver picks `starlette 1.0.0` transitively under the existing
  `>=0.49.1` floor (FastAPI 0.136.1 declares `starlette>=0.46.0`). Smoke
  test in clean venv: imports OK, uvicorn boots, `/login` returns 200,
  `/api/auth/login` issues JWT + CSRF cookies and emits all security
  headers, `/api/auth/me` round-trips with the cookie, `/api/torrents`
  returns the expected structured 502 when qBit is unreachable (circuit
  breaker path executes cleanly).
  - fastapi 0.136.0 → **0.136.1**
  - uvicorn 0.44.0 → **0.46.0**
  - pydantic-settings 2.13.1 → **2.14.0** (pulls in `typing-inspection>=0.4.0`)
  - starlette, httpx, PyJWT, bcrypt, aiosqlite already at latest
- fastapi 0.135.3 → **0.136.0**
- uvicorn 0.34.2 → **0.44.0**
- bcrypt 4.3.0 → **5.0.0** (API-compatible; `$2b$12$` hash prefix preserved)
- aiosqlite 0.20.0 → **0.22.1**
- pydantic-settings 2.7.1 → **2.13.1**
- httpx, PyJWT unchanged (already at latest)
- Smoke-tested: bcrypt roundtrip, JWT roundtrip, schema validation, SQLite
  roundtrip, full uvicorn boot, and endpoint/header checks all pass.

### Changed
- `app/middleware.py`: `RateLimitMiddleware` and `CSRFMiddleware` now read the
  raw ASGI `scope["path"]` rather than `request.url.path` for their
  security-relevant path checks, matching the path the router dispatches and
  removing any dependence on Host-header parsing (defense-in-depth for
  CVE-2026-48710).
- `CLAUDE.md`: Security Headers section now documents the actual CSP emitted
  by `app/middleware.py` (including `frame-ancestors 'none'` and the
  dynamically-added `form-action` / `frame-src` for `QBIT_BROWSER_HOST`), plus
  `X-XSS-Protection: 0` and the `Strict-Transport-Security` header that is
  only emitted when `SECURE_COOKIES=true`.
- `README.md`: credential-isolation bullet now notes the opt-in
  `ENABLE_BROWSER_AUTH` exception; IP-ban troubleshooting references the flag.
- `app/qbit/router.py`: the log line emitted when an admin retrieves
  browser-auth creds no longer includes the admin's username.
