from dataclasses import dataclass
from enum import Enum

from jarvis_multiagent.agents.schema import DEFAULT_PROFILES
from jarvis_multiagent.core.config import settings
from jarvis_multiagent.services.llm import ProviderFactory
from jarvis_multiagent.services.message_bus import AgentMessageBus, BusMessage


class OrchestratorMode(str, Enum):
    group_showcase = "group_showcase"
    private_only = "private_only"
    full_debug = "full_debug"


@dataclass
class OrchestratedMessage:
    task_id: str
    sender: str
    target: str
    body: str


class MultiAgentOrchestrator:
    def __init__(self) -> None:
        self.mode = OrchestratorMode(settings.group_mode)
        self.provider = ProviderFactory.create()
        self.max_rounds = settings.max_rounds_per_task
        self.bus = AgentMessageBus(max_hops=self.max_rounds + 2)

    async def execute_task(self, task_id: str, user_request: str) -> dict:
        group_messages: list[OrchestratedMessage] = []
        planner = next(p for p in DEFAULT_PROFILES if p.name.lower() == "manager")
        plan = await self.provider.complete(planner.system_prompt, f"Create short plan with roles for: {user_request}")

        for profile in DEFAULT_PROFILES:
            await self.bus.publish(BusMessage(task_id=task_id, from_agent="manager", to_agent=profile.name, payload=plan, hops=0))

        for round_idx in range(1, self.max_rounds + 1):
            for profile in DEFAULT_PROFILES:
                inbound = await self.bus.consume(profile.name)
                if inbound is None:
                    continue
                prompt = f"task={task_id};round={round_idx};from={inbound.from_agent};context={inbound.payload};user={user_request}"
                answer = await self.provider.complete(profile.system_prompt, prompt)
                short = answer[:220]
                group_messages.append(OrchestratedMessage(task_id, profile.name, "group", short))
                if "NEED_HELP:" in answer:
                    target = answer.split("NEED_HELP:", 1)[1].split()[0]
                    await self.bus.publish(BusMessage(task_id=task_id, from_agent=profile.name, to_agent=target, payload=short, hops=inbound.hops + 1))

        final = await self.provider.complete("You are coordinator", f"User task: {user_request}\nAgent outputs: {[m.body for m in group_messages]}\nReturn final answer.")
        return {
            "task_id": task_id,
            "mode": self.mode.value,
            "group_messages": [m.__dict__ for m in group_messages] if self.mode != OrchestratorMode.private_only else [],
            "private_result": final,
        }
