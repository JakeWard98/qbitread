import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field, field_validator


def _check_password_policy(password: str) -> str:
    """Validate password meets security policy. Returns password or raises ValueError."""
    errors = []
    if len(password) < 8:
        errors.append("at least 8 characters")
    if not re.search(r"[A-Z]", password):
        errors.append("at least 1 uppercase letter")
    if not re.search(r"[a-z]", password):
        errors.append("at least 1 lowercase letter")
    if not re.search(r"\d", password):
        errors.append("at least 1 number")
    if not re.search(r"[^a-zA-Z0-9]", password):
        errors.append("at least 1 special character")
    if errors:
        raise ValueError("Password must contain: " + ", ".join(errors))
    return password


def password_meets_policy(password: str) -> bool:
    """Check if a password meets the current policy without raising."""
    try:
        _check_password_policy(password)
        return True
    except ValueError:
        return False


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=8, max_length=128)
    role: Literal["user", "manager", "admin"] = "user"

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _check_password_policy(v)


class PasswordUpdate(BaseModel):
    password: str = Field(min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return _check_password_policy(v)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime
    password_meets_policy: bool

    @computed_field
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    model_config = {"from_attributes": True}
