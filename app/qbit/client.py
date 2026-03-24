import logging

import httpx

logger = logging.getLogger(__name__)


class QBitClient:
    def __init__(self, host: str, username: str, password: str):
        self._host = host.rstrip("/")
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(base_url=self._host, timeout=10.0)
        self._authenticated = False

    async def _login(self):
        resp = await self._client.post(
            "/api/v2/auth/login",
            data={"username": self._username, "password": self._password},
        )
        if resp.status_code == 200 and resp.text.strip() == "Ok.":
            self._authenticated = True
            logger.info("Authenticated with qBittorrent")
        else:
            self._authenticated = False
            raise ConnectionError(f"qBittorrent login failed: {resp.text}")

    async def _request(self, path: str, params: dict | None = None) -> dict | list:
        if not self._authenticated:
            await self._login()

        resp = await self._client.get(path, params=params)

        # Re-auth on 403 (session expired)
        if resp.status_code == 403:
            self._authenticated = False
            await self._login()
            resp = await self._client.get(path, params=params)

        resp.raise_for_status()
        return resp.json()

    async def get_torrents(self) -> list[dict]:
        return await self._request("/api/v2/torrents/info")

    async def get_transfer_info(self) -> dict:
        return await self._request("/api/v2/transfer/info")

    async def close(self):
        await self._client.aclose()
