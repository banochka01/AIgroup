from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy import select

from jarvis_multiagent.agents.schema import DEFAULT_PROFILES
from jarvis_multiagent.db.models import Agent, Base
from jarvis_multiagent.core.config import settings

engine = create_async_engine(settings.database_url, future=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_agents()


async def seed_agents() -> None:
    async with SessionLocal() as session:
        for profile in DEFAULT_PROFILES:
            agent = await session.scalar(select(Agent).where(Agent.name == profile.name))
            if agent is None:
                session.add(
                    Agent(
                        name=profile.name,
                        role=profile.role,
                        token_env=profile.token_env,
                        system_prompt=profile.system_prompt,
                        status="idle",
                    )
                )
                continue
            agent.role = profile.role
            agent.token_env = profile.token_env
            agent.system_prompt = profile.system_prompt
        await session.commit()
