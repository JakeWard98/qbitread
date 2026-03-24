import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from app.auth.dependencies import get_current_user
from app.auth.models import User
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
        raise HTTPException(status_code=502, detail="Cannot reach qBittorrent")
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
        raise HTTPException(status_code=502, detail="Cannot reach qBittorrent")
    return TransferInfo(**raw)
