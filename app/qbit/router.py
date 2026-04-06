import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.config import settings
from app.qbit.schemas import TorrentInfo, TransferInfo

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["qbit"])


@router.get("/torrents", response_model=list[TorrentInfo])
async def get_torrents(
    request: Request,
    _: User = Depends(get_current_user),
):
    client = request.app.state.qbit_client
    try:
        raw = await client.get_torrents()
    except Exception as e:
        logger.error("Failed to fetch torrents: %s", e)
        raise HTTPException(status_code=502, detail="Failed to communicate with qBittorrent")
    return [TorrentInfo(**t) for t in raw]


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
    status["qbit_username"] = settings.QBIT_USERNAME
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
    except ConnectionError as e:
        return {"success": False, "message": str(e)}


@router.get("/qbit/browser-auth-creds")
async def browser_auth_creds(
    request: Request,
    user: User = Depends(require_admin),
):
    logger.warning("Admin '%s' requested qBit credentials for browser auth", user.username)
    return JSONResponse(
        content={
            "url": settings.QBIT_BROWSER_HOST,
            "username": settings.QBIT_USERNAME,
            "password": settings.QBIT_PASSWORD,
        },
        headers={"Cache-Control": "no-store"},
    )
