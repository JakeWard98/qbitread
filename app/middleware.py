import asyncio
import hmac
import ipaddress
import logging
import re
import time
from collections import defaultdict
from urllib.parse import urlparse

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings

logger = logging.getLogger(__name__)

# Regex to validate CSP source values: scheme://host[:port] only
_CSP_ORIGIN_RE = re.compile(r"^https?://[a-zA-Z0-9\-._~:]+$")


def _sanitize_csp_origin(value: str) -> str | None:
    """Validate that a value is safe for inclusion in a CSP directive.

    Returns the origin (scheme://host[:port]) if valid, None otherwise.
    This prevents CSP injection via crafted QBIT_BROWSER_HOST values.
    """
    value = value.strip()
    if not value:
        return None
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ("http", "https"):
            return None
        if not parsed.hostname:
            return None
        origin = f"{parsed.scheme}://{parsed.hostname}"
        if parsed.port:
            origin += f":{parsed.port}"
        if _CSP_ORIGIN_RE.match(origin):
            return origin
    except Exception:
        pass
    logger.warning("QBIT_BROWSER_HOST value rejected for CSP: %r", value)
    return None


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "0"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        if settings.SECURE_COOKIES:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        # NOTE: 'unsafe-inline' is required for style-src because templates and JS
        # use inline style attributes extensively. Removing it requires migrating
        # all inline styles to CSS classes — tracked as a future improvement.
        # NOTE: script-src 'self' intentionally blocks proxy-injected inline scripts
        # (e.g. Cloudflare Rocket Loader). Templates use data-cfasync="false" and
        # DOMContentLoaded in JS to stay resilient when behind such proxies.
        csp = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'"
        )
        browser_origin = _sanitize_csp_origin(settings.QBIT_BROWSER_HOST)
        if browser_origin:
            csp += f"; form-action 'self' {browser_origin}"
            csp += f"; frame-src 'self' {browser_origin}"
        response.headers["Content-Security-Policy"] = csp
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Sliding window rate limiter for the login endpoint."""

    def __init__(self, app, path: str = "/api/auth/login", limit: int | None = None, window: int = 60):
        super().__init__(app)
        self.path = path
        self.limit = limit if limit is not None else settings.LOGIN_RATE_LIMIT
        self.window = window
        self._hits: dict[str, list[float]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        client_ip = request.client.host if request.client else "unknown"
        if forwarded and self._is_trusted_proxy(client_ip):
            return forwarded.split(",")[0].strip()
        return client_ip

    @staticmethod
    def _is_trusted_proxy(ip: str) -> bool:
        if not settings.TRUSTED_PROXIES:
            return False  # Do not trust X-Forwarded-For unless proxies are explicitly configured
        try:
            addr = ipaddress.ip_address(ip)
            for proxy in settings.TRUSTED_PROXIES:
                if "/" in proxy:
                    if addr in ipaddress.ip_network(proxy, strict=False):
                        return True
                elif ip == proxy:
                    return True
        except ValueError:
            pass
        return False

    def _clean(self, ip: str, now: float):
        cutoff = now - self.window
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]

    async def dispatch(self, request: Request, call_next):
        if request.url.path == self.path and request.method == "POST":
            ip = self._get_client_ip(request)
            now = time.time()

            async with self._lock:
                self._clean(ip, now)
                if len(self._hits[ip]) >= self.limit:
                    return Response(
                        content='{"detail":"Too many login attempts. Try again later."}',
                        status_code=429,
                        media_type="application/json",
                    )
                self._hits[ip].append(now)

        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """Double-submit cookie CSRF protection for mutating requests."""

    SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
    EXEMPT_PATHS = {"/api/auth/login", "/api/auth/logout", "/api/auth/setup"}

    async def dispatch(self, request: Request, call_next):
        if request.method in self.SAFE_METHODS:
            return await call_next(request)

        if request.url.path in self.EXEMPT_PATHS:
            return await call_next(request)

        # Only enforce CSRF on authenticated API endpoints
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        cookie_token = request.cookies.get("csrf_token")
        header_token = request.headers.get("x-csrf-token")

        if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
            return Response(
                content='{"detail":"CSRF validation failed"}',
                status_code=403,
                media_type="application/json",
            )

        return await call_next(request)
