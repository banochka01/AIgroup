from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from jarvis_multiagent.agents.schema import DEFAULT_PROFILES
from jarvis_multiagent.db.models import Agent, Approval, Delegation, Memory, Message, Stat, Subtask, Task, User
from jarvis_multiagent.db.session import SessionLocal


class TaskService:
    async def get_or_create_user(self, telegram_user_id: str, username: str | None = None) -> User:
        async with SessionLocal() as session:
            user = await session.scalar(select(User).where(User.telegram_user_id == telegram_user_id))
            if user is None:
                user = User(telegram_user_id=telegram_user_id, username=username)
                session.add(user)
            else:
                user.username = username or user.username
            await session.commit()
            await session.refresh(user)
            return user

    async def create_task(self, public_id: str, user_id: int, title: str, description: str) -> Task:
        async with SessionLocal() as session:
            existing = await session.scalar(select(Task).where(Task.public_id == public_id))
            if existing is not None:
                return existing

            task = Task(public_id=public_id, user_id=user_id, title=title[:255], description=description, status="running")
            session.add(task)
            await session.commit()
            await session.refresh(task)
            return task

    async def set_task_status(self, task_id: int, status: str) -> None:
        async with SessionLocal() as session:
            task = await session.get(Task, task_id)
            if task is not None:
                task.status = status
                task.updated_at = datetime.utcnow()
                await session.commit()

    async def create_subtask(self, task_id: int, agent_id: int, title: str, details: str = "") -> Subtask:
        async with SessionLocal() as session:
            subtask = Subtask(
                task_id=task_id,
                agent_id=agent_id,
                title=title[:255],
                details=details,
                status="in_progress",
            )
            session.add(subtask)
            await session.commit()
            await session.refresh(subtask)
            return subtask

    async def complete_subtasks_for_agent(self, task_id: int, agent_id: int) -> None:
        async with SessionLocal() as session:
            result = await session.scalars(
                select(Subtask).where(Subtask.task_id == task_id, Subtask.agent_id == agent_id, Subtask.status != "done")
            )
            now = datetime.utcnow()
            for subtask in result:
                subtask.status = "done"
                subtask.completed_at = now
            await session.commit()

    async def store_message(self, task_id: int, agent_id: int | None, channel: str, body: str) -> None:
        async with SessionLocal() as session:
            session.add(Message(task_id=task_id, agent_id=agent_id, channel=channel, body=body))
            await session.commit()

    async def store_delegation(self, task_id: int, from_agent_id: int, to_agent_id: int, reason: str) -> None:
        async with SessionLocal() as session:
            session.add(Delegation(task_id=task_id, from_agent_id=from_agent_id, to_agent_id=to_agent_id, reason=reason))
            stat = await session.scalar(select(Stat).where(Stat.agent_id == from_agent_id))
            if stat is None:
                stat = Stat(agent_id=from_agent_id, tasks_completed=0, delegations_made=0)
                session.add(stat)
            stat.delegations_made += 1
            await session.commit()

    async def remember(self, agent_id: int, key: str, value: str) -> None:
        async with SessionLocal() as session:
            memory = await session.scalar(select(Memory).where(Memory.agent_id == agent_id, Memory.key == key))
            if memory is None:
                session.add(Memory(agent_id=agent_id, key=key, value=value))
            else:
                memory.value = value
                memory.updated_at = datetime.utcnow()
            await session.commit()

    async def increment_completed(self, agent_id: int) -> None:
        async with SessionLocal() as session:
            row = await session.scalar(select(Stat).where(Stat.agent_id == agent_id))
            if row is None:
                row = Stat(agent_id=agent_id, tasks_completed=0, delegations_made=0)
                session.add(row)
            row.tasks_completed += 1
            await session.commit()

    async def get_agent_map(self) -> dict[str, Agent]:
        async with SessionLocal() as session:
            result = await session.scalars(select(Agent))
            return {agent.name: agent for agent in result}

    async def list_agents(self) -> list[Agent]:
        async with SessionLocal() as session:
            result = await session.scalars(select(Agent).order_by(Agent.id))
            return list(result)

    async def stats(self) -> dict:
        async with SessionLocal() as session:
            task_count = await session.scalar(select(func.count(Task.id)))
            running_count = await session.scalar(select(func.count(Task.id)).where(Task.status == "running"))
            message_count = await session.scalar(select(func.count(Message.id)))
            delegation_count = await session.scalar(select(func.count(Delegation.id)))
            agents = await session.scalars(select(Agent).order_by(Agent.name))
            stats_rows = await session.scalars(select(Stat))
            stats_by_agent = {row.agent_id: row for row in stats_rows}
            agent_payload = []
            for agent in agents:
                row = stats_by_agent.get(agent.id)
                agent_payload.append(
                    {
                        "name": agent.name,
                        "role": agent.role,
                        "status": agent.status,
                        "tasks_completed": row.tasks_completed if row else 0,
                        "delegations_made": row.delegations_made if row else 0,
                    }
                )
            return {
                "tasks_total": task_count or 0,
                "tasks_running": running_count or 0,
                "messages_total": message_count or 0,
                "delegations_total": delegation_count or 0,
                "agents": agent_payload,
            }

    async def pending_approvals(self) -> list[dict]:
        async with SessionLocal() as session:
            result = await session.scalars(select(Approval).where(Approval.approved.is_(False)).order_by(Approval.created_at))
            return [
                {"id": approval.id, "task_id": approval.task_id, "action": approval.action, "created_at": approval.created_at.isoformat()}
                for approval in result
            ]

    async def seed_default_agents(self) -> None:
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
