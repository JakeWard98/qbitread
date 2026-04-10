from dataclasses import dataclass
from datetime import datetime


VALID_ROLES = ("user", "monitor", "admin")


@dataclass
class User:
    id: int
    username: str
    password: str
    role: str = "user"
    created_at: datetime | None = None
    password_meets_policy: bool = True

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @classmethod
    def from_row(cls, row) -> "User":
        if row is None:
            return None
        return cls(
            id=row["id"],
            username=row["username"],
            password=row["password"],
            role=row["role"],
            created_at=datetime.fromisoformat(row["created_at"]) if row["created_at"] else None,
            password_meets_policy=bool(row["password_meets_policy"]),
        )
