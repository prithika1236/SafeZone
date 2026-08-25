"""FastAPI dependencies for transactional database sessions."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.database.session import async_session_factory


async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session and roll back unfinished work when a request fails."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
