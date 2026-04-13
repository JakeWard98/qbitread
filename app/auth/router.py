import sqlite3
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.auth.schemas import LoginRequest, PasswordUpdate, RefreshRateUpdate, RoleUpdate, UserCreate, UserOut, password_meets_policy
from app.auth.security import create_jwt, generate_csrf_token, get_dummy_hash, hash_password, verify_password
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db=Depends(get_db),
):
    cursor = await db.execute(
        "SELECT * FROM users WHERE username = ?", (body.username,)
    )
    row = await cursor.fetchone()
    user = User.from_row(row)
    # Always run bcrypt comparison to prevent timing-based user enumeration
    password_hash = user.password if user else get_dummy_hash()
    password_valid = verify_password(body.password, password_hash)
    if not user or not password_valid:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    meets_policy = password_meets_policy(body.password)
    if user.password_meets_policy != meets_policy:
        await db.execute(
            "UPDATE users SET password_meets_policy = ? WHERE id = ?",
            (meets_policy, user.id),
        )
        await db.commit()

    token = create_jwt(user.username, user.role)
    csrf_token = generate_csrf_token()

    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=settings.SECURE_COOKIES,
        samesite="strict",
        max_age=settings.JWT_EXPIRY_MINUTES * 60,
    )
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=False,
        secure=settings.SECURE_COOKIES,
        samesite="strict",
        max_age=settings.JWT_EXPIRY_MINUTES * 60,
    )
    return {
        "message": "OK",
        "is_admin": user.is_admin,
        "role": user.role,
        "username": user.username,
        "password_weak": not meets_policy,
    }


@router.post("/setup", status_code=201)
async def initial_setup(
    body: UserCreate,
    db=Depends(get_db),
):
    cursor = await db.execute("SELECT * FROM users LIMIT 1")
    if await cursor.fetchone() is not None:
        raise HTTPException(status_code=403, detail="Setup already completed")

    now = datetime.now(timezone.utc).isoformat()
    try:
        await db.execute(
            "INSERT INTO users (username, password, role, created_at, password_meets_policy) "
            "VALUES (?, ?, ?, ?, ?)",
            (body.username, hash_password(body.password), "admin", now, True),
        )
        await db.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=409, detail="Setup already completed")
    return {"message": "Admin account created. Please log in."}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("access_token")
    response.delete_cookie("csrf_token")
    return {"message": "OK"}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _: User = Depends(require_admin),
    db=Depends(get_db),
):
    cursor = await db.execute("SELECT * FROM users ORDER BY created_at")
    rows = await cursor.fetchall()
    return [User.from_row(r) for r in rows]


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    _: User = Depends(require_admin),
    db=Depends(get_db),
):
    cursor = await db.execute(
        "SELECT * FROM users WHERE username = ?", (body.username,)
    )
    if await cursor.fetchone():
        raise HTTPException(status_code=409, detail="Username already exists")

    now = datetime.now(timezone.utc).isoformat()
    hashed = hash_password(body.password)
    cursor = await db.execute(
        "INSERT INTO users (username, password, role, created_at, password_meets_policy) "
        "VALUES (?, ?, ?, ?, ?)",
        (body.username, hashed, body.role, now, True),
    )
    await db.commit()

    return User(
        id=cursor.lastrowid,
        username=body.username,
        password=hashed,
        role=body.role,
        created_at=datetime.fromisoformat(now),
        password_meets_policy=True,
    )


@router.put("/users/{user_id}/password", status_code=200)
async def change_user_password(
    user_id: int,
    body: PasswordUpdate,
    _: User = Depends(require_admin),
    db=Depends(get_db),
):
    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = await cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")

    await db.execute(
        "UPDATE users SET password = ?, password_meets_policy = ? WHERE id = ?",
        (hash_password(body.password), True, user_id),
    )
    await db.commit()
    return {"message": "Password updated"}


@router.put("/users/{user_id}/role", status_code=200)
async def change_user_role(
    user_id: int,
    body: RoleUpdate,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role")

    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    await db.execute(
        "UPDATE users SET role = ? WHERE id = ?",
        (body.role, user_id),
    )
    await db.commit()
    return {"message": "Role updated"}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db=Depends(get_db),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    cursor = await db.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    if not await cursor.fetchone():
        raise HTTPException(status_code=404, detail="User not found")

    await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    await db.commit()


@router.get("/settings/refresh-rate")
async def get_refresh_rate(_: User = Depends(get_current_user), db=Depends(get_db)):
    cursor = await db.execute("SELECT value FROM app_settings WHERE key = 'refresh_rate'")
    row = await cursor.fetchone()
    return {"refresh_rate": int(row["value"]) if row else 5}


@router.put("/settings/refresh-rate")
async def set_refresh_rate(
    body: RefreshRateUpdate,
    _: User = Depends(require_admin),
    db=Depends(get_db),
):
    await db.execute(
        "INSERT OR REPLACE INTO app_settings (key, value) VALUES ('refresh_rate', ?)",
        (str(body.refresh_rate),),
    )
    await db.commit()
    return {"refresh_rate": body.refresh_rate}
