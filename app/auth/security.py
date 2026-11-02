import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt

from app.config import settings

# bcrypt cost factor — pinned explicitly so library default drift doesn't
# silently change password hashing cost. 12 is the 2024+ OWASP baseline.
_BCRYPT_ROUNDS = 12

# bcrypt only uses the first 72 bytes of a password; bcrypt>=5 raises on more.
BCRYPT_MAX_BYTES = 72

# Pre-computed bcrypt hash used to prevent timing-based user enumeration.
# When a login attempt targets a non-existent username, verify_password()
# runs against this hash so response time is constant regardless.
_DUMMY_HASH: str = bcrypt.hashpw(b"dummy-timing-pad", bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def get_dummy_hash() -> str:
    return _DUMMY_HASH


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(password: str, hashed: str) -> bool:
    # Truncate like bcrypt<5 did, so over-long input is a normal mismatch
    # (and hashes created before bcrypt 5 keep working) instead of a 500.
    return bcrypt.checkpw(password.encode()[:BCRYPT_MAX_BYTES], hashed.encode())


def new_token_version() -> str:
    return secrets.token_hex(16)


def create_jwt(username: str, role: str, token_version: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": username,
        "role": role,
        "ver": token_version,
        # Per-token ID so logout can revoke this one session server-side.
        "jti": secrets.token_urlsafe(16),
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_EXPIRY_MINUTES),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def token_matches_user(payload: dict, token_version: str) -> bool:
    """A token is only valid for the user's current token_version, which is
    rotated on password change and unique per account (so a re-created
    username does not revive an old account's tokens)."""
    ver = payload.get("ver")
    return bool(token_version) and isinstance(ver, str) and hmac.compare_digest(ver, token_version)


def generate_csrf_token() -> str:
    return secrets.token_hex(32)
