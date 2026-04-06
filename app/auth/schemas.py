from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=50, pattern=r"^[a-zA-Z0-9_]+$")
    password: str = Field(min_length=6, max_length=128)
    role: Literal["user", "manager", "admin"] = "user"


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    @computed_field
    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    model_config = {"from_attributes": True}
