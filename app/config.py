import json
import logging
import os
import secrets
from typing import Annotated

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

logger = logging.getLogger(__name__)


def _restrict_mode(path: str, mode: int) -> None:
    """Best-effort: drop group/other permission bits on a secret file. A file
    we cannot chmod (e.g. owned by another user on a bind mount) is left alone
    with a warning rather than failing startup."""
    try:
        current = os.stat(path).st_mode & 0o777
        if current & ~mode:
            os.chmod(path, mode)
            logger.warning("Tightened permissions on %s from %o to %o", path, current, mode)
    except OSError as exc:
        logger.warning("Could not restrict permissions on %s: %s", path, exc)


class Settings(BaseSettings):
    # qBittorrent connection
    QBIT_HOST: str
    QBIT_USERNAME: str = "admin"
    QBIT_PASSWORD: str
    QBIT_BROWSER_HOST: str = ""  # Browser-accessible qBit URL (optional)

    # App security
    SECRET_KEY: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 720  # 12 hours

    # Database
    DATABASE_PATH: str = "/app/data/qbitread.db"

    # Admin bootstrap (optional — setup wizard used if omitted)
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str = ""

    # Dashboard polling interval — seeds app_settings on first run; overridden by admin panel
    REFRESH_RATE: int = 5  # seconds

    # Rate limiting
    LOGIN_RATE_LIMIT: int = 5  # attempts per minute

    # Trusted reverse proxy IPs/CIDRs (only trust X-Forwarded-For from these).
    # Accepts a comma-separated list or a JSON array; empty means none.
    TRUSTED_PROXIES: Annotated[list[str], NoDecode] = []

    # Cookie security (disable Secure flag for local dev without HTTPS)
    SECURE_COOKIES: bool = False

    # Admin-only feature that returns qBit credentials to the browser so the
    # admin can trigger a qBit login from their own IP (useful for IP-ban
    # recovery). Off by default because it breaks the "credentials stay on
    # the server" model. Enable only if you understand the trade-off.
    ENABLE_BROWSER_AUTH: bool = False

    # hide_input_in_errors: a validation error would otherwise echo the raw
    # settings dict (truncated head and tail), which can include
    # ADMIN_PASSWORD, QBIT_PASSWORD or SECRET_KEY, into the startup log.
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", hide_input_in_errors=True)

    @field_validator("TRUSTED_PROXIES", mode="before")
    @classmethod
    def _parse_trusted_proxies(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("["):
                return json.loads(v)
            return [p.strip() for p in v.split(",") if p.strip()]
        return v

    @model_validator(mode="after")
    def _ensure_secret_key(self) -> "Settings":
        if self.SECRET_KEY:
            if self.SECRET_KEY.lower().startswith("change-me"):
                raise ValueError(
                    "SECRET_KEY is still the documented placeholder. Remove it to "
                    "auto-generate one, or set it to the output of "
                    "`python -c \"import secrets; print(secrets.token_hex(32))\"`."
                )
            if len(self.SECRET_KEY.encode()) < 32:
                logger.warning(
                    "SECRET_KEY is shorter than 32 bytes; JWTs signed with it can be "
                    "brute-forced offline. Use a random 64-hex-character key."
                )
            return self

        data_dir = os.path.dirname(self.DATABASE_PATH)
        key_file = os.path.join(data_dir, ".secret_key")

        try:
            # 0700 to match database.py; this runs first, so it decides the
            # mode a newly created data dir gets.
            os.makedirs(data_dir, mode=0o700, exist_ok=True)

            if os.path.exists(key_file):
                _restrict_mode(key_file, 0o600)
                with open(key_file) as f:
                    self.SECRET_KEY = f.read().strip()
                if self.SECRET_KEY:
                    logger.info("SECRET_KEY loaded from %s", key_file)
                    return self

            self.SECRET_KEY = secrets.token_hex(32)
            fd = os.open(key_file, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600)
            try:
                os.write(fd, self.SECRET_KEY.encode())
            finally:
                os.close(fd)
            logger.info("SECRET_KEY auto-generated and saved to %s", key_file)
        except OSError as exc:
            raise RuntimeError(
                f"Cannot persist SECRET_KEY to {key_file}: {exc}. "
                "Set SECRET_KEY in env or fix data volume permissions."
            ) from exc

        return self


settings = Settings()

if not settings.SECURE_COOKIES:
    logger.warning(
        "SECURE_COOKIES is False — cookies will not have the Secure flag. "
        "Set SECURE_COOKIES=true in production behind HTTPS."
    )
