# Security Policy

## Supported Versions

qBitRead is a rolling-release project. Security fixes land on `main` and are
published in the next tagged release. Only the latest release receives
security updates.

| Version        | Supported          |
|----------------|--------------------|
| Latest release | :white_check_mark: |
| Older releases | :x:                |

## Reporting a Vulnerability

Please **do not** report security issues in public GitHub issues.

Use GitHub's private vulnerability reporting:
1. Go to the [Security tab](https://github.com/JakeWard98/qbitread/security) on the repository.
2. Click **Report a vulnerability**.
3. Provide reproduction steps, affected versions, and impact.

You should receive an acknowledgement within 7 days. A fix or mitigation
timeline will follow once the report is triaged.

## Threat Model

qBitRead is designed to be a locked-down, read-only monitoring dashboard for a
single qBittorrent instance behind a trusted reverse proxy.

### What qBitRead defends against

- **Credential exposure to end users.** By default, qBittorrent credentials
  stay on the server — the browser never sees them. The one exception is the
  opt-in `ENABLE_BROWSER_AUTH` feature (default off); when enabled, the admin
  panel exposes the creds to the admin browser for IP-ban recovery.
- **Session hijacking.** JWTs live in `HttpOnly; SameSite=Strict` cookies. The
  `Secure` flag is applied when `SECURE_COOKIES=true` (i.e. behind HTTPS).
- **CSRF.** Double-submit cookie pattern on every mutating endpoint
  (`/api/auth/login`, `/api/auth/logout`, and `/api/auth/setup` are exempt by
  design; `setup` self-disables once any user exists).
- **Password brute force.** Login is rate-limited to `LOGIN_RATE_LIMIT`
  attempts per minute per IP (sliding window). Bcrypt hashing with a pinned
  cost factor of 12 protects against offline cracking if the DB leaks.
- **User enumeration.** Login response timing is constant whether the username
  exists or not (bcrypt verification always runs against a dummy hash).
- **SQL injection.** All SQL is parameterised via `aiosqlite`.
- **XSS in the dashboard.** All user-controlled strings are rendered via
  `textContent` or an `escHtml()` helper; CSP is `script-src 'self'`.
- **Clickjacking.** `X-Frame-Options: DENY` and CSP `frame-ancestors 'none'`.
- **Reverse-proxy header spoofing.** `X-Forwarded-For` is only trusted when
  the request comes from an IP listed in `TRUSTED_PROXIES`.

### What qBitRead does **not** defend against

- **A compromised qBittorrent instance.** If your qBit itself is malicious,
  qBitRead will faithfully display whatever it reports.
- **Container escape or host compromise.** qBitRead runs as non-root inside
  the container, but that only mitigates — not eliminates — container escape
  risks. Keep the host patched.
- **Operators who expose port 8000 directly.** Always front qBitRead with an
  HTTPS reverse proxy and set `SECURE_COOKIES=true`.
- **Stolen data volumes.** The SQLite DB is not encrypted at rest. Password
  hashes are bcrypt'd, but usernames and roles are readable if someone can
  read the volume. Protect the volume at the OS level.
- **Weak operator passwords.** The setup wizard enforces the password policy;
  `ADMIN_PASSWORD` bootstrapping only logs a warning if weak. Use strong
  passwords.
- **Denial of service via upstream.** qBitRead does its own circuit-breaking
  against qBit, but a DoS-capable attacker on the qBit side can still exhaust
  the connection.

## Operational recommendations

- Run behind an HTTPS reverse proxy (Caddy, Nginx, Traefik) and set
  `SECURE_COOKIES=true`.
- Leave `ENABLE_BROWSER_AUTH` at its default `false` unless you actively need
  IP-ban recovery from your browser's IP.
- Configure `TRUSTED_PROXIES` so rate limiting counts the real client IP.
- Back up the `/app/data` volume (contains `qbitread.db` and `.secret_key`)
  before upgrades.
- Rotate operator passwords periodically via the admin panel.
