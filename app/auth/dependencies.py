from fastapi import Depends, HTTPException, Request

from app.auth.models import User
from app.auth.security import token_matches_user, verify_jwt
from app.database import get_db


async def user_from_token(db, token: str | None) -> User | None:
    """Return the user a session JWT belongs to, or None if it is not valid.

    A token is valid only if its signature and expiry check out, it carries
    the user's current token_version (rotated on password change, unique per
    account) and its jti has not been revoked by logout. Used by both the API
    dependency and the page routes so the two can never disagree.
    """
    if not token:
        return None
    payload = verify_jwt(token)
    if not payload:
        return None
    cursor = await db.execute(
        "SELECT * FROM users WHERE username = ?", (payload.get("sub"),)
    )
    user = User.from_row(await cursor.fetchone())
    if not user or not token_matches_user(payload, user.token_version):
        return None
    jti = payload.get("jti")
    if not isinstance(jti, str) or not jti:
        return None
    cursor = await db.execute("SELECT 1 FROM revoked_tokens WHERE jti = ?", (jti,))
    if await cursor.fetchone() is not None:
        return None
    return user


async def get_current_user(
    request: Request,
    db=Depends(get_db),
) -> User:
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await user_from_token(db, token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return user


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
