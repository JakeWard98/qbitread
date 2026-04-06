import logging
import os

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.config import settings

logger = logging.getLogger(__name__)

db_path = settings.DATABASE_PATH
os.makedirs(os.path.dirname(db_path), exist_ok=True)

engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def _migrate_is_admin_to_role(conn):
    """Migrate old is_admin boolean column to role string column via table rebuild."""
    result = await conn.execute(text("PRAGMA table_info(users)"))
    columns = {row[1] for row in result.fetchall()}

    if "is_admin" not in columns or "role" in columns:
        return  # No migration needed

    logger.info("Migrating users table: is_admin -> role")
    await conn.execute(text(
        "CREATE TABLE users_new ("
        "  id INTEGER PRIMARY KEY,"
        "  username VARCHAR(50) NOT NULL UNIQUE,"
        "  password VARCHAR(128) NOT NULL,"
        "  role VARCHAR(20) NOT NULL DEFAULT 'user',"
        "  created_at DATETIME"
        ")"
    ))
    await conn.execute(text(
        "INSERT INTO users_new (id, username, password, role, created_at) "
        "SELECT id, username, password, "
        "  CASE WHEN is_admin = 1 THEN 'admin' ELSE 'user' END, "
        "  created_at "
        "FROM users"
    ))
    await conn.execute(text("DROP TABLE users"))
    await conn.execute(text("ALTER TABLE users_new RENAME TO users"))
    logger.info("Users table migration complete")


async def _migrate_add_password_meets_policy(conn):
    """Add password_meets_policy column to existing users table."""
    result = await conn.execute(text("PRAGMA table_info(users)"))
    columns = {row[1] for row in result.fetchall()}

    if "password_meets_policy" in columns:
        return  # Already migrated

    logger.info("Adding password_meets_policy column to users table")
    await conn.execute(text(
        "ALTER TABLE users ADD COLUMN password_meets_policy BOOLEAN NOT NULL DEFAULT 0"
    ))
    logger.info("password_meets_policy column added (existing users default to 0)")


async def init_db():
    from app.auth.models import User  # noqa: F401
    async with engine.begin() as conn:
        # Run migrations before create_all (so create_all sees the new schema)
        await _migrate_is_admin_to_role(conn)
        await _migrate_add_password_meets_policy(conn)
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
