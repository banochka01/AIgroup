from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from jarvis_multiagent.core.config import settings
from jarvis_multiagent.db.models import Base

engine = create_async_engine(settings.database_url, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
