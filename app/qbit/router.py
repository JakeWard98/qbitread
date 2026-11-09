import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import TypeAdapter

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.config import settings
from app.qbit.schemas import TorrentInfo, TransferInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["qbit"])

_torrent_list = TypeAdapter(list[TorrentInfo])
# Rendered /api/torrents bodies, one per ratio visibility, for the raw list the
# qBit client is currently sharing (see QBitClient._shared_get). Concurrent
# requests then share one serialised body instead of each building its own
# copy of every torrent. Holding `raw` keeps the identity check sound.
_rendered: dict[bool, tuple[list, bytes]] = {}


def _render_torrents(raw: list[dict], show_ratio: bool) -> bytes:
    hit = _rendered.get(show_ratio)
    if hit is not None and hit[0] is raw:
        return hit[1]
    torrents = [TorrentInfo(**t) for t in raw]
    # Ratio is a monitor/admin privilege; withhold it, not just hide the column.
    if not show_ratio:
        for t in torrents:
            t.ratio = None
    body = _torrent_list.dump_json(torrents)
    _rendered[show_ratio] = (raw, body)
    return body


@router.get("/torrents", response_model=list[TorrentInfo])
async def get_torrents(
    request: Request,
    user: User = Depends(get_current_user),
):
    client = request.app.state.qbit_client
    try:
        raw = await client.get_torrents()
    except Exception as e:
        logger.error("Failed to fetch torrents: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with qBittorrent")
    body = _render_torrents(raw, show_ratio=user.role in ("admin", "monitor"))
    return Response(content=body, media_type="application/json")


@router.get("/transfer", response_model=TransferInfo)
async def get_transfer(
    request: Request,
    _: User = Depends(get_current_user),
):
    client = request.app.state.qbit_client
    try:
        raw = await client.get_transfer_info()
    except Exception as e:
        logger.error("Failed to fetch transfer info: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with qBittorrent")
    return TransferInfo(**raw)


@router.get("/qbit/connection-info")
async def connection_info(
    request: Request,
    user: User = Depends(require_admin),
):
    client = request.app.state.qbit_client
    status = client.get_status()
    status["browser_host"] = settings.QBIT_BROWSER_HOST
    # The qBit username is a credential: only the opt-in browser-auth flow may see it.
    status["qbit_username"] = settings.QBIT_USERNAME if settings.ENABLE_BROWSER_AUTH else ""
    status["browser_auth_enabled"] = settings.ENABLE_BROWSER_AUTH
    return status


@router.post("/qbit/retry-login")
async def retry_login(
    request: Request,
    user: User = Depends(require_admin),
):
    logger.info("Admin '%s' triggered manual retry login", user.username)
    client = request.app.state.qbit_client
    try:
        await client.force_login()
        return {"success": True, "message": "Successfully authenticated with qBittorrent"}
    except ConnectionError:
        logger.exception("retry-login failed for admin '%s'", user.username)
        return {"success": False, "message": "Failed to authenticate with qBittorrent. Check server logs for details."}


@router.get("/qbit/browser-auth-creds")
async def browser_auth_creds(
    request: Request,
    user: User = Depends(require_admin),
):
    # Off by default: returning qBit credentials to the browser breaks the
    # "credentials stay on the server" model. Operators who need this for
    # IP-ban recovery must opt in via ENABLE_BROWSER_AUTH=true.
    if not settings.ENABLE_BROWSER_AUTH:
        raise HTTPException(status_code=404, detail="Not found")
    logger.info("Browser-auth credentials served to an admin session")
    return JSONResponse(
        content={
            "url": settings.QBIT_BROWSER_HOST,
            "username": settings.QBIT_USERNAME,
            "password": settings.QBIT_PASSWORD,
        },
        headers={"Cache-Control": "no-store"},
    )
