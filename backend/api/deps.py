"""
AIClipper API Dependencies

FastAPI dependency-injection callables used across route modules.
"""

from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database.crud import get_or_create_default_user
from backend.database.engine import get_session
from backend.database.models import User
from backend.utils.config import Settings, get_settings


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session, committing on success and rolling back on error."""
    async for session in get_session():
        yield session


async def get_current_user(
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Resolve the current user.

    In single-user / local-dev mode this returns (or creates) the default
    'admin' user.  When auth is added later, this dependency will be swapped
    out for a real token-based resolver.
    """
    return await get_or_create_default_user(db)


def get_config() -> Settings:
    """Return the cached application settings singleton."""
    return get_settings()
