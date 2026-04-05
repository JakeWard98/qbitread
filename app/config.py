from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # qBittorrent connection
    QBIT_HOST: str = "http://localhost:8080"
    QBIT_USERNAME: str = "admin"
    QBIT_PASSWORD: str

    # App security
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRY_MINUTES: int = 720  # 12 hours

    # Database
    DATABASE_PATH: str = "/app/data/qbitread.db"

    # Admin bootstrap
    ADMIN_USERNAME: str = "admin"
    ADMIN_PASSWORD: str

    # Rate limiting
    LOGIN_RATE_LIMIT: int = 5  # attempts per minute

    # Cookie security (disable Secure flag for local dev without HTTPS)
    SECURE_COOKIES: bool = True

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
