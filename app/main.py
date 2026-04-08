import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response as StarletteResponse

from app.auth.models import User
from app.auth.router import router as auth_router
from app.auth.schemas import password_meets_policy
from app.auth.security import hash_password, verify_jwt
from app.config import settings
from app.database import get_connection, init_db
from app.middleware import CSRFMiddleware, RateLimitMiddleware, SecurityHeadersMiddleware
from app.qbit.client import QBitClient
from app.qbit.router import router as qbit_router

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await init_db()
    await bootstrap_admin()
    app.state.qbit_client = QBitClient(
        host=settings.QBIT_HOST,
        username=settings.QBIT_USERNAME,
        password=settings.QBIT_PASSWORD,
    )
    logger.info("qBitRead started — qBit target: %s", settings.QBIT_HOST)
    try:
        await app.state.qbit_client._login()
        logger.info("Initial qBittorrent login successful")
    except ConnectionError as e:
        logger.warning("Initial qBittorrent login failed (will retry on first request): %s", e)
    yield
    # Shutdown
    await app.state.qbit_client.close()


async def bootstrap_admin():
    if not settings.ADMIN_PASSWORD:
        logger.info("No ADMIN_PASSWORD set — setup wizard will be available on first visit")
        return

    if not password_meets_policy(settings.ADMIN_PASSWORD):
        logger.warning(
            "ADMIN_PASSWORD does not meet password policy "
            "(8+ chars, uppercase, lowercase, digit, special). "
            "Consider setting a stronger password."
        )

    async with get_connection() as db:
        cursor = await db.execute(
            "SELECT * FROM users WHERE username = ?", (settings.ADMIN_USERNAME,)
        )
        admin = await cursor.fetchone()
        if admin is None:
            now = datetime.now(timezone.utc).isoformat()
            await db.execute(
                "INSERT INTO users (username, password, role, created_at, password_meets_policy) "
                "VALUES (?, ?, ?, ?, ?)",
                (settings.ADMIN_USERNAME, hash_password(settings.ADMIN_PASSWORD), "admin", now,
             password_meets_policy(settings.ADMIN_PASSWORD)),
            )
            await db.commit()
            logger.info("Admin user '%s' created", settings.ADMIN_USERNAME)
        else:
            logger.info("Admin user '%s' already exists", settings.ADMIN_USERNAME)


async def _has_users() -> bool:
    async with get_connection() as db:
        cursor = await db.execute("SELECT 1 FROM users LIMIT 1")
        return await cursor.fetchone() is not None


app = FastAPI(title="qBitRead", docs_url=None, redoc_url=None, lifespan=lifespan)

# Middleware (applied in reverse order)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Static files
class NoCacheStaticFiles(StaticFiles):
    """StaticFiles wrapper that forces revalidation on JS/CSS assets.

    Without this, browsers and CDN edges (e.g. Cloudflare) cache app.js / style.css
    and continue serving stale versions after a container update — producing
    "$(...) is null" errors when stale JS runs against newer HTML.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if isinstance(response, StarletteResponse) and path.endswith((".js", ".css")):
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
        return response


app.mount("/static", NoCacheStaticFiles(directory="static"), name="static")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return FileResponse("static/favicon.ico", media_type="image/x-icon")


# API routers
app.include_router(auth_router)
app.include_router(qbit_router)


# Page routes
@app.get("/setup")
async def setup_page():
    if await _has_users():
        return RedirectResponse("/login")
    return FileResponse("templates/setup.html")


@app.get("/login")
async def login_page():
    if not await _has_users():
        return RedirectResponse("/setup")
    return FileResponse("templates/login.html")


@app.get("/admin")
async def admin_page(request: Request):
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    payload = verify_jwt(token)
    if not payload or payload.get("role") != "admin":
        return RedirectResponse("/")
    return FileResponse("templates/admin.html")


@app.get("/")
async def index_page(request: Request):
    if not await _has_users():
        return RedirectResponse("/setup")
    token = request.cookies.get("access_token")
    if not token:
        return RedirectResponse("/login")
    payload = verify_jwt(token)
    if not payload:
        return RedirectResponse("/login")
    return FileResponse("templates/index.html")
