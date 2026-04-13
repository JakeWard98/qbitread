import logging
import os
import secrets

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


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

    # Trusted reverse proxy IPs (only trust X-Forwarded-For from these)
    TRUSTED_PROXIES: list[str] = []

    # Cookie security (disable Secure flag for local dev without HTTPS)
    SECURE_COOKIES: bool = False

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode="after")
    def _ensure_secret_key(self) -> "Settings":
        if self.SECRET_KEY:
            return self

        data_dir = os.path.dirname(self.DATABASE_PATH)
        key_file = os.path.join(data_dir, ".secret_key")

        try:
            os.makedirs(data_dir, exist_ok=True)

            if os.path.exists(key_file):
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
            # Fall back to an ephemeral key (lost on restart)
            self.SECRET_KEY = secrets.token_hex(32)
            logger.warning(
                "Could not persist SECRET_KEY to %s (%s); using ephemeral key",
                key_file,
                exc,
            )

        return self


settings = Settings()

if not settings.SECURE_COOKIES:
    logger.warning(
        "SECURE_COOKIES is False — cookies will not have the Secure flag. "
        "Set SECURE_COOKIES=true in production behind HTTPS."
    )
