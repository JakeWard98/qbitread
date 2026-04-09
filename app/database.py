import logging
import os
from contextlib import asynccontextmanager

import aiosqlite

from app.config import settings

logger = logging.getLogger(__name__)

db_path = settings.DATABASE_PATH
os.makedirs(os.path.dirname(db_path), mode=0o700, exist_ok=True)

CREATE_USERS_TABLE = """\
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(128) NOT NULL,
    role VARCHAR(20) NOT NULL DEFAULT 'user',
    created_at DATETIME,
    password_meets_policy BOOLEAN NOT NULL DEFAULT 1
)
"""

CREATE_APP_SETTINGS_TABLE = """\
CREATE TABLE IF NOT EXISTS app_settings (
    key VARCHAR(50) PRIMARY KEY,
    value TEXT NOT NULL
)
"""


@asynccontextmanager
async def get_connection():
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


async def get_db():
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        yield conn


async def _migrate_is_admin_to_role(conn):
    """Migrate old is_admin boolean column to role string column via table rebuild."""
    cursor = await conn.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in await cursor.fetchall()}

    if "is_admin" not in columns or "role" in columns:
        return

    logger.info("Migrating users table: is_admin -> role")
    await conn.execute(
        "CREATE TABLE users_new ("
        "  id INTEGER PRIMARY KEY,"
        "  username VARCHAR(50) NOT NULL UNIQUE,"
        "  password VARCHAR(128) NOT NULL,"
        "  role VARCHAR(20) NOT NULL DEFAULT 'user',"
        "  created_at DATETIME"
        ")"
    )
    await conn.execute(
        "INSERT INTO users_new (id, username, password, role, created_at) "
        "SELECT id, username, password, "
        "  CASE WHEN is_admin = 1 THEN 'admin' ELSE 'user' END, "
        "  created_at "
        "FROM users"
    )
    await conn.execute("DROP TABLE users")
    await conn.execute("ALTER TABLE users_new RENAME TO users")
    logger.info("Users table migration complete")


async def _migrate_manager_to_monitor(conn):
    """Rename legacy 'manager' role to 'monitor'."""
    cursor = await conn.execute("SELECT COUNT(*) FROM users WHERE role='manager'")
    count = (await cursor.fetchone())[0]
    if count == 0:
        return
    logger.info("Migrating %d user(s) from role 'manager' to 'monitor'", count)
    await conn.execute("UPDATE users SET role='monitor' WHERE role='manager'")


async def _migrate_add_password_meets_policy(conn):
    """Add password_meets_policy column to existing users table."""
    cursor = await conn.execute("PRAGMA table_info(users)")
    columns = {row[1] for row in await cursor.fetchall()}

    if "password_meets_policy" in columns:
        return

    logger.info("Adding password_meets_policy column to users table")
    await conn.execute(
        "ALTER TABLE users ADD COLUMN password_meets_policy BOOLEAN NOT NULL DEFAULT 0"
    )
    logger.info("password_meets_policy column added (existing users default to 0)")


async def _migrate_add_app_settings(conn):
    """Create app_settings table and seed refresh_rate from env/default on first run."""
    await conn.execute(CREATE_APP_SETTINGS_TABLE)
    await conn.execute(
        "INSERT OR IGNORE INTO app_settings (key, value) VALUES ('refresh_rate', ?)",
        (str(settings.REFRESH_RATE),),
    )


async def init_db():
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        # Check if users table exists before running migrations
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
        )
        if await cursor.fetchone() is not None:
            await _migrate_is_admin_to_role(conn)
            await _migrate_add_password_meets_policy(conn)
            await _migrate_manager_to_monitor(conn)
        await conn.execute(CREATE_USERS_TABLE)
        await _migrate_add_app_settings(conn)
        await conn.commit()
