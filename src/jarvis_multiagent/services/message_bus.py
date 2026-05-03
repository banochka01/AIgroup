import asyncio
from collections import defaultdict
from dataclasses import dataclass


@dataclass
class BusMessage:
    task_id: str
    from_agent: str
    to_agent: str
    payload: str
    hops: int = 0


class AgentMessageBus:
    def __init__(self, max_hops: int = 8) -> None:
        self.max_hops = max_hops
        self._queues: dict[str, asyncio.Queue[BusMessage]] = defaultdict(asyncio.Queue)

    async def publish(self, message: BusMessage) -> bool:
        if message.hops > self.max_hops:
            return False
        await self._queues[message.to_agent].put(message)
        return True

    async def consume(self, agent_name: str, timeout: float = 0.05) -> BusMessage | None:
        try:
            return await asyncio.wait_for(self._queues[agent_name].get(), timeout=timeout)
        except asyncio.TimeoutError:
            return None
