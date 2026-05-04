import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from uuid import uuid4


@dataclass
class BusMessage:
    task_id: str
    from_agent: str
    to_agent: str
    payload: str
    hops: int = 0
    kind: str = "task"
    parent_id: str | None = None
    message_id: str = field(default_factory=lambda: uuid4().hex)
    created_at: datetime = field(default_factory=datetime.utcnow)


class AgentMessageBus:
    def __init__(self, max_hops: int = 8, max_messages_per_task: int = 40) -> None:
        self.max_hops = max_hops
        self.max_messages_per_task = max_messages_per_task
        self._queues: dict[tuple[str, str], asyncio.Queue[BusMessage]] = defaultdict(asyncio.Queue)
        self._seen_routes: set[str] = set()
        self._message_counts: dict[str, int] = defaultdict(int)

    async def publish(self, message: BusMessage) -> bool:
        if message.hops > self.max_hops:
            return False
        if self._message_counts[message.task_id] >= self.max_messages_per_task:
            return False

        route_key = self._route_key(message)
        if route_key in self._seen_routes:
            return False

        self._seen_routes.add(route_key)
        self._message_counts[message.task_id] += 1
        await self._queues[(message.task_id, message.to_agent)].put(message)
        return True

    async def consume(self, agent_name: str, task_id: str, timeout: float = 0.05) -> BusMessage | None:
        try:
            return await asyncio.wait_for(self._queues[(task_id, agent_name)].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None

    async def consume_all(self, agent_name: str, task_id: str, limit: int = 5) -> list[BusMessage]:
        messages: list[BusMessage] = []
        for _ in range(limit):
            message = await self.consume(agent_name, task_id)
            if message is None:
                break
            messages.append(message)
        return messages

    def has_pending(self, task_id: str, agent_names: list[str]) -> bool:
        return any(not self._queues[(task_id, agent_name)].empty() for agent_name in agent_names)

    def _route_key(self, message: BusMessage) -> str:
        payload_digest = sha256(message.payload.encode("utf-8", errors="ignore")).hexdigest()[:16]
        return "|".join([message.task_id, message.from_agent, message.to_agent, message.kind, payload_digest])
