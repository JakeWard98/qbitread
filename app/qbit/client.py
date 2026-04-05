import logging
import time

import httpx

logger = logging.getLogger(__name__)


class QBitClient:
    def __init__(self, host: str, username: str, password: str):
        self._host = host.rstrip("/")
        self._username = username
        self._password = password
        self._client = httpx.AsyncClient(base_url=self._host, timeout=10.0)
        self._authenticated = False
        self._login_cooldown = 0
        self._last_login_failure = 0.0
        self._MAX_COOLDOWN = 300
        self._BAN_COOLDOWN = 900  # 15 minutes for IP ban

    async def _login(self):
        # Circuit breaker: skip login if in cooldown
        now = time.monotonic()
        elapsed = now - self._last_login_failure
        if self._login_cooldown > 0 and elapsed < self._login_cooldown:
            remaining = int(self._login_cooldown - elapsed)
            raise ConnectionError(
                f"Login on cooldown ({remaining}s remaining). "
                f"Not contacting qBittorrent to avoid IP ban."
            )

        try:
            resp = await self._client.post(
                "/api/v2/auth/login",
                data={"username": self._username, "password": self._password},
            )
        except Exception as exc:
            self._record_login_failure()
            raise ConnectionError(f"qBittorrent unreachable: {exc}") from exc

        if resp.status_code == 200 and resp.text.strip() == "Ok.":
            self._authenticated = True
            self._login_cooldown = 0
            logger.info("Authenticated with qBittorrent")
        else:
            self._authenticated = False
            # Detect IP ban (403 with "banned" in response text)
            if resp.status_code == 403 and "banned" in resp.text.lower():
                self._record_login_failure(ban=True)
                raise ConnectionError(
                    f"IP banned by qBittorrent. Pausing login attempts for 15 minutes."
                )
            self._record_login_failure()
            raise ConnectionError(f"qBittorrent login failed: {resp.text}")

    def _record_login_failure(self, ban: bool = False):
        self._last_login_failure = time.monotonic()
        if ban:
            self._login_cooldown = self._BAN_COOLDOWN
            logger.warning(
                "IP banned by qBittorrent. Next login attempt in %ds.",
                self._login_cooldown,
            )
        else:
            if self._login_cooldown == 0:
                self._login_cooldown = 10
            else:
                self._login_cooldown = min(
                    self._login_cooldown * 2, self._MAX_COOLDOWN
                )
            logger.warning(
                "Login failed. Next attempt in %ds.", self._login_cooldown
            )

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
