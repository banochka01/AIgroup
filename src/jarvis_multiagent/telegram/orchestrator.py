from dataclasses import dataclass
from enum import Enum

from jarvis_multiagent.agents.schema import DEFAULT_PROFILES
from jarvis_multiagent.core.config import settings
from jarvis_multiagent.services.llm import ProviderFactory


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

    async def execute_task(self, task_id: str, user_request: str) -> dict:
        rounds: list[OrchestratedMessage] = []
        for i, profile in enumerate(DEFAULT_PROFILES[: self.max_rounds], start=1):
            reply = await self.provider.complete(
                profile.system_prompt,
                f"task={task_id}; round={i}; request={user_request}; keep short and actionable",
            )
            rounds.append(OrchestratedMessage(task_id, profile.name, "group", reply[:240]))

        final = await self.provider.complete(
            "You are coordinator.",
            f"Summarize outputs for private user delivery: {[m.body for m in rounds]}",
        )
        return {
            "task_id": task_id,
            "mode": self.mode.value,
            "group_messages": [m.__dict__ for m in rounds] if self.mode != OrchestratorMode.private_only else [],
            "private_result": final,
        }
