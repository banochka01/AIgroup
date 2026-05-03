from __future__ import annotations

from sqlalchemy import select

from jarvis_multiagent.db.models import Agent, Delegation, Memory, Message, Stat, Subtask, Task
from jarvis_multiagent.db.session import SessionLocal


class TaskService:
    async def create_task(self, public_id: str, user_id: int, title: str, description: str) -> Task:
        async with SessionLocal() as session:
            task = Task(public_id=public_id, user_id=user_id, title=title, description=description, status="running")
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    async def create_subtask(self, task_id: int, agent_id: int, title: str) -> Subtask:
        async with SessionLocal() as session:
            subtask = Subtask(task_id=task_id, agent_id=agent_id, title=title, status="in_progress")
            session.add(subtask)
            await session.commit()
            await session.refresh(subtask)
            return subtask

    async def store_message(self, task_id: int, agent_id: int | None, channel: str, body: str) -> None:
        async with SessionLocal() as session:
            session.add(Message(task_id=task_id, agent_id=agent_id, channel=channel, body=body))
            await session.commit()

    async def store_delegation(self, task_id: int, from_agent_id: int, to_agent_id: int, reason: str) -> None:
        async with SessionLocal() as session:
            session.add(Delegation(task_id=task_id, from_agent_id=from_agent_id, to_agent_id=to_agent_id, reason=reason))
            await session.commit()

    async def remember(self, agent_id: int, key: str, value: str) -> None:
        async with SessionLocal() as session:
            session.add(Memory(agent_id=agent_id, key=key, value=value))
            await session.commit()

    async def increment_completed(self, agent_id: int) -> None:
        async with SessionLocal() as session:
            row = await session.scalar(select(Stat).where(Stat.agent_id == agent_id))
            if row is None:
                row = Stat(agent_id=agent_id, tasks_completed=0, delegations_made=0)
                session.add(row)
            row.tasks_completed += 1
            await session.commit()

    async def list_agents(self) -> list[Agent]:
        async with SessionLocal() as session:
            result = await session.scalars(select(Agent))
            return list(result)
