from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, require_admin
from app.auth.models import User
from app.auth.schemas import LoginRequest, PasswordUpdate, UserCreate, UserOut, password_meets_policy
from app.auth.security import create_jwt, generate_csrf_token, hash_password, verify_password
from app.config import settings
from app.database import get_db

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login")
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    # Rate limiting is handled by middleware
    result = await db.execute(select(User).where(User.username == body.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(body.password, user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Check password against current policy and update flag
    meets_policy = password_meets_policy(body.password)
    if user.password_meets_policy != meets_policy:
        user.password_meets_policy = meets_policy
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
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).limit(1))
    if result.scalar_one_or_none() is not None:
        raise HTTPException(status_code=403, detail="Setup already completed")

    user = User(
        username=body.username,
        password=hash_password(body.password),
        role="admin",
        password_meets_policy=True,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
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
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).order_by(User.created_at))
    return result.scalars().all()


@router.post("/users", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    existing = await db.execute(select(User).where(User.username == body.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Username already exists")

    user = User(
        username=body.username,
        password=hash_password(body.password),
        role=body.role,
        password_meets_policy=True,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


@router.put("/users/{user_id}/password", status_code=200)
async def change_user_password(
    user_id: int,
    body: PasswordUpdate,
    _: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    user.password = hash_password(body.password)
    user.password_meets_policy = True
    await db.commit()
    return {"message": "Password updated"}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: int,
    current_user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
):
    if current_user.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    await db.delete(user)
    await db.commit()
