import time
from collections import defaultdict

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        csp = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "script-src 'self'; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
        browser_host = settings.QBIT_BROWSER_HOST
        if browser_host:
            # Lock form/frame targets to self + configured browser host
            csp += f"; form-action 'self' {browser_host}"
            csp += f"; frame-src 'self' {browser_host}"
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

    def _get_client_ip(self, request: Request) -> str:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _clean(self, ip: str, now: float):
        cutoff = now - self.window
        self._hits[ip] = [t for t in self._hits[ip] if t > cutoff]

    async def dispatch(self, request: Request, call_next):
        if request.url.path == self.path and request.method == "POST":
            ip = self._get_client_ip(request)
            now = time.time()
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

        if not cookie_token or not header_token or cookie_token != header_token:
            return Response(
                content='{"detail":"CSRF validation failed"}',
                status_code=403,
                media_type="application/json",
            )

        return await call_next(request)
