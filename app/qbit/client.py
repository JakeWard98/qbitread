import asyncio
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
        self._BAN_MAX_DURATION = 900  # 15 minutes total ban window
        self._BAN_PROBE_INTERVAL = 60  # retry every 60s during ban
        self._ban_detected_at = 0.0  # when ban was first detected
        self._login_lock = asyncio.Lock()

    async def _login(self):
        async with self._login_lock:
            if self._authenticated:
                return  # Another coroutine already logged in while we waited
            await self._do_login()

    async def _do_login(self):
        # Circuit breaker: skip login if in cooldown
        now = time.monotonic()
        elapsed = now - self._last_login_failure

        # If banned and total ban window has elapsed, clear cooldown and retry
        if self._ban_detected_at > 0:
            ban_elapsed = now - self._ban_detected_at
            if ban_elapsed >= self._BAN_MAX_DURATION:
                logger.info(
                    "Ban window (%ds) expired. Retrying login.",
                    self._BAN_MAX_DURATION,
                )
                self._login_cooldown = 0
                self._ban_detected_at = 0.0

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
            self._ban_detected_at = 0.0
            logger.info("Authenticated with qBittorrent")
        else:
            self._authenticated = False
            # Detect IP ban (403 with "banned" in response text)
            if resp.status_code == 403 and "banned" in resp.text.lower():
                self._record_login_failure(ban=True)
                raise ConnectionError(
                    f"IP banned by qBittorrent. Will probe every 60s until ban lifts."
                )
            self._record_login_failure()
            raise ConnectionError(f"qBittorrent login failed: {resp.text}")

    def _record_login_failure(self, ban: bool = False):
        self._last_login_failure = time.monotonic()
        if ban:
            if self._ban_detected_at == 0.0:
                self._ban_detected_at = time.monotonic()
            self._login_cooldown = self._BAN_PROBE_INTERVAL
            ban_elapsed = int(time.monotonic() - self._ban_detected_at)
            logger.warning(
                "IP banned by qBittorrent. Next probe in %ds (ban detected %ds ago).",
                self._login_cooldown,
                ban_elapsed,
            )
        else:
            self._ban_detected_at = 0.0
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

        # Handle 403: distinguish IP ban from session expiry
        if resp.status_code == 403:
            if "banned" in resp.text.lower():
                self._record_login_failure(ban=True)
                raise ConnectionError(
                    "IP banned by qBittorrent. Will probe every 60s until ban lifts."
                )
            self._authenticated = False
            await self._login()
            resp = await self._client.get(path, params=params)

        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "application/json" not in content_type:
            raise ConnectionError(
                f"Unexpected Content-Type from qBittorrent: {content_type}"
            )
        return resp.json()

    def get_status(self) -> dict:
        now = time.monotonic()
        cooldown_remaining = 0
        if self._login_cooldown > 0 and self._last_login_failure > 0:
            elapsed = now - self._last_login_failure
            cooldown_remaining = max(0, int(self._login_cooldown - elapsed))

        ban_seconds_remaining = 0
        if self._ban_detected_at > 0:
            ban_elapsed = now - self._ban_detected_at
            ban_seconds_remaining = max(0, int(self._BAN_MAX_DURATION - ban_elapsed))

        return {
            "authenticated": self._authenticated,
            "ban_detected": self._ban_detected_at > 0,
            "cooldown_remaining": cooldown_remaining,
            "ban_seconds_remaining": ban_seconds_remaining,
        }

    def reset_circuit_breaker(self):
        self._login_cooldown = 0
        self._ban_detected_at = 0.0
        self._last_login_failure = 0.0
        self._authenticated = False
        logger.info("Circuit breaker reset by admin")

    async def force_login(self):
        self.reset_circuit_breaker()
        await self._login()

    async def get_torrents(self) -> list[dict]:
        return await self._request("/api/v2/torrents/info")

    async def get_transfer_info(self) -> dict:
        return await self._request("/api/v2/transfer/info")

    async def close(self):
        await self._client.aclose()
