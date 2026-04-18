import secrets
from datetime import datetime, timedelta, timezone

import jwt
import bcrypt

from app.config import settings

# bcrypt cost factor — pinned explicitly so library default drift doesn't
# silently change password hashing cost. 12 is the 2024+ OWASP baseline.
_BCRYPT_ROUNDS = 12

# Pre-computed bcrypt hash used to prevent timing-based user enumeration.
# When a login attempt targets a non-existent username, verify_password()
# runs against this hash so response time is constant regardless.
_DUMMY_HASH: str = bcrypt.hashpw(b"dummy-timing-pad", bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def get_dummy_hash() -> str:
    return _DUMMY_HASH


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


def create_jwt(username: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_EXPIRY_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def verify_jwt(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


def generate_csrf_token() -> str:
    return secrets.token_hex(32)
