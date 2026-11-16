import asyncio
import logging
from collections import Counter

import anyio
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import TypeAdapter
from starlette.types import Receive, Scope, Send

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
# copy of every torrent. Holding `raw` in _rendered_from keeps the identity
# check sound. Both are dropped _RENDER_TTL after that list was first
# rendered, so an idle dashboard does not keep the list and bodies in memory.
_RENDER_TTL = 1.0  # same as QBitClient._CACHE_TTL
_rendered_from: list | None = None
_rendered: dict[bool, bytes] = {}


def _drop_rendered(raw: list) -> None:
    global _rendered_from
    if _rendered_from is raw:
        _rendered_from = None
        _rendered.clear()


def _render_torrents(raw: list[dict], show_ratio: bool) -> bytes:
    global _rendered_from
    if _rendered_from is not raw:
        _rendered.clear()
        _rendered_from = raw
        asyncio.get_running_loop().call_later(_RENDER_TTL, _drop_rendered, raw)
    body = _rendered.get(show_ratio)
    if body is None:
        torrents = [TorrentInfo(**t) for t in raw]
        # Ratio is a monitor/admin privilege; withhold it, not just hide the column.
        if not show_ratio:
            for t in torrents:
                t.ratio = None
        body = _torrent_list.dump_json(torrents)
        _rendered[show_ratio] = body
    return body


# A client that stops reading must not pin a rendered body. Sent in one piece,
# the whole body sat in the socket's write buffer until the client read it
# (uvicorn has no write timeout), so a logged-in user could pin one full body
# per second for as long as they kept opening sockets. Instead the body goes
# out in chunks, so uvicorn's write flow control makes the send wait; a send
# still unfinished after _SEND_DEADLINE seconds is abandoned and the
# connection closed; and one account may have at most _MAX_SENDS_PER_USER
# multi-chunk sends in progress (more get 429). Memory held for slow clients
# is then bounded per account.
_CHUNK = 64 * 1024
_SEND_DEADLINE = 60.0
_MAX_SENDS_PER_USER = 4
_active_sends: Counter[int] = Counter()


class _SharedBodyResponse(Response):
    media_type = "application/json"

    def __init__(self, body: bytes, user_id: int):
        super().__init__(content=body)
        self._user_id = user_id

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        uid = self._user_id
        # A body that fits in one chunk never waits on flow control (it pins
        # no more than any other response), so only larger ones count against
        # the cap. That keeps a burst of small responses (several tabs served
        # by one shared fetch) from being refused. Checked here, not in the
        # endpoint, so every increment is paired with the decrement below.
        capped = len(self.body) > _CHUNK
        if capped:
            if _active_sends[uid] >= _MAX_SENDS_PER_USER:
                busy = JSONResponse({"detail": "Too many concurrent requests"}, status_code=429)
                await busy(scope, receive, send)
                return
            _active_sends[uid] += 1
        try:
            with anyio.move_on_after(_SEND_DEADLINE) as deadline:
                await send({"type": "http.response.start", "status": self.status_code, "headers": self.raw_headers})
                view = memoryview(self.body)
                for i in range(0, len(view), _CHUNK):
                    await send({"type": "http.response.body", "body": bytes(view[i:i + _CHUNK]), "more_body": True})
                await send({"type": "http.response.body", "body": b"", "more_body": False})
            if deadline.cancelled_caught:
                # Raising makes uvicorn close the connection; returning
                # would leave a response with a short body.
                raise ConnectionAbortedError(
                    f"/api/torrents client did not read its response within {_SEND_DEADLINE:.0f}s"
                )
        finally:
            if capped:
                _active_sends[uid] -= 1
                if _active_sends[uid] <= 0:
                    del _active_sends[uid]


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
    return _SharedBodyResponse(body, user.id)


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
