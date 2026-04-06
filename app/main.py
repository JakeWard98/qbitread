import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.auth.models import User
from app.auth.router import router as auth_router
from app.auth.security import hash_password, verify_jwt
from app.config import settings
from app.database import async_session, init_db
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

    async with async_session() as db:
        result = await db.execute(
            select(User).where(User.username == settings.ADMIN_USERNAME)
        )
        admin = result.scalar_one_or_none()
        if admin is None:
            admin = User(
                username=settings.ADMIN_USERNAME,
                password=hash_password(settings.ADMIN_PASSWORD),
                role="admin",
            )
            db.add(admin)
            await db.commit()
            logger.info("Admin user '%s' created", settings.ADMIN_USERNAME)
        else:
            logger.info("Admin user '%s' already exists", settings.ADMIN_USERNAME)


async def _has_users() -> bool:
    async with async_session() as db:
        result = await db.execute(select(User).limit(1))
        return result.scalar_one_or_none() is not None


app = FastAPI(title="qBitRead", docs_url=None, redoc_url=None, lifespan=lifespan)

# Middleware (applied in reverse order)
app.add_middleware(CSRFMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

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
