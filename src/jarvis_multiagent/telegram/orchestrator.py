from dataclasses import dataclass
from enum import Enum
import json
import logging
from uuid import uuid4

from jarvis_multiagent.agents.schema import DEFAULT_PROFILES, AgentProfile, get_profile
from jarvis_multiagent.core.config import settings
from jarvis_multiagent.services.llm import ProviderFactory
from jarvis_multiagent.services.message_bus import AgentMessageBus, BusMessage
from jarvis_multiagent.services.task_service import TaskService


logger = logging.getLogger(__name__)


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
        self.bus = AgentMessageBus(max_hops=self.max_rounds + 2, max_messages_per_task=settings.max_messages_per_task)
        self.task_service = TaskService()

    async def execute_task(
        self,
        task_id: str | None,
        user_request: str,
        *,
        telegram_user_id: str | None = None,
        username: str | None = None,
        source: str = "api",
    ) -> dict:
        public_id = task_id or f"task-{uuid4().hex[:12]}"
        user = await self.task_service.get_or_create_user(telegram_user_id or source, username)
        task = await self.task_service.create_task(public_id, user.id, user_request[:120] or "Untitled task", user_request)
        await self.task_service.seed_default_agents()
        agent_map = await self.task_service.get_agent_map()

        group_messages: list[OrchestratedMessage] = []
        transcript: list[str] = []
        try:
            manager = get_profile("manager")
            if manager is None:
                raise RuntimeError("Manager profile is not configured")

            plan = await self._build_plan(manager, user_request)
            selected_profiles = self._profiles_from_plan(plan, user_request)
            manager_message = self._shorten(f"План: {plan.get('summary') or 'распределяю задачу между агентами'}")
            group_messages.append(OrchestratedMessage(public_id, "Manager", "group", manager_message))
            transcript.append(f"Manager: {manager_message}")
            await self.task_service.store_message(task.id, agent_map["Manager"].id, "group", manager_message)

            for item in plan.get("subtasks", []):
                profile = get_profile(str(item.get("agent", "")))
                if profile is None:
                    continue
                agent_id = agent_map[profile.name].id
                await self.task_service.create_subtask(
                    task.id,
                    agent_id,
                    str(item.get("title") or f"{profile.name} work"),
                    str(item.get("details") or ""),
                )
                await self.bus.publish(
                    BusMessage(
                        task_id=public_id,
                        from_agent="Manager",
                        to_agent=profile.name,
                        payload=json.dumps(item, ensure_ascii=False),
                        hops=0,
                        kind="subtask",
                    )
                )

            if not plan.get("subtasks"):
                for profile in selected_profiles:
                    await self.bus.publish(
                        BusMessage(
                            task_id=public_id,
                            from_agent="Manager",
                            to_agent=profile.name,
                            payload=user_request,
                            hops=0,
                            kind="subtask",
                        )
                    )

            await self._run_rounds(public_id, task.id, user_request, selected_profiles, agent_map, group_messages, transcript)

            final = await self._finalize(manager, user_request, transcript)
            await self.task_service.store_message(task.id, agent_map["Manager"].id, "private", final)
            await self.task_service.set_task_status(task.id, "done")
            await self.task_service.increment_completed(agent_map["Manager"].id)

            return {
                "task_id": public_id,
                "mode": self.mode.value,
                "group_messages": [m.__dict__ for m in group_messages] if self.mode != OrchestratorMode.private_only else [],
                "private_result": final,
            }
        except Exception as exc:
            logger.exception("Task orchestration failed")
            error = f"Задача {public_id} завершилась ошибкой: {exc}"
            await self.task_service.store_message(task.id, None, "error", error)
            await self.task_service.set_task_status(task.id, "failed")
            return {"task_id": public_id, "mode": self.mode.value, "group_messages": [], "private_result": error}

    async def _build_plan(self, manager: AgentProfile, user_request: str) -> dict:
        allowed = ", ".join(profile.name for profile in DEFAULT_PROFILES if profile.name != "Manager")
        prompt = f"""
Create an execution plan for this user task.

Allowed agents: {allowed}.
Return JSON only with this schema:
{{
  "summary": "one short sentence in Russian",
  "subtasks": [
    {{"agent": "Backend", "title": "short title", "details": "what this agent must do"}}
  ]
}}

User task:
{user_request}
"""
        raw = await self.provider.complete(manager.system_prompt, prompt, max_tokens=700)
        plan = self._parse_json(raw)
        subtasks = plan.get("subtasks")
        if not isinstance(subtasks, list):
            plan["subtasks"] = []
        return plan

    async def _run_rounds(
        self,
        public_id: str,
        db_task_id: int,
        user_request: str,
        selected_profiles: list[AgentProfile],
        agent_map: dict,
        group_messages: list[OrchestratedMessage],
        transcript: list[str],
    ) -> None:
        profiles = [profile for profile in DEFAULT_PROFILES if profile.name != "Manager"]
        active_names = [profile.name for profile in profiles]
        selected_names = {profile.name for profile in selected_profiles}

        for round_idx in range(1, self.max_rounds + 1):
            activity = False
            for profile in profiles:
                inbound_messages = await self.bus.consume_all(profile.name, public_id)
                if not inbound_messages:
                    continue
                activity = True
                prompt = self._agent_prompt(profile, user_request, inbound_messages, round_idx)
                raw = await self.provider.complete(profile.system_prompt, prompt)
                parsed = self._parse_agent_response(raw)
                message = self._shorten(parsed["message"], limit=900 if self.mode == OrchestratorMode.full_debug else 240)

                agent_id = agent_map[profile.name].id
                group_messages.append(OrchestratedMessage(public_id, profile.name, "group", message))
                transcript.append(f"{profile.name}: {parsed['message']}")
                await self.task_service.store_message(db_task_id, agent_id, "group", message)

                for key, value in parsed.get("memory", {}).items():
                    await self.task_service.remember(agent_id, str(key), str(value))

                delegate_to = parsed.get("delegate_to")
                if delegate_to:
                    target = get_profile(str(delegate_to))
                    if target is not None and target.name in active_names and target.name != profile.name:
                        reason = str(parsed.get("delegate_reason") or "Agent requested help")
                        published = await self.bus.publish(
                            BusMessage(
                                task_id=public_id,
                                from_agent=profile.name,
                                to_agent=target.name,
                                payload=f"{reason}\n\nContext from {profile.name}: {parsed['message']}",
                                hops=max(message.hops for message in inbound_messages) + 1,
                                kind="delegation",
                                parent_id=inbound_messages[-1].message_id,
                            )
                        )
                        if published:
                            await self.task_service.store_delegation(db_task_id, agent_id, agent_map[target.name].id, reason)
                            selected_names.add(target.name)

                if parsed.get("done"):
                    await self.task_service.complete_subtasks_for_agent(db_task_id, agent_id)
                    await self.task_service.increment_completed(agent_id)

            if not activity or not self.bus.has_pending(public_id, active_names):
                break

        for name in selected_names:
            if name in agent_map:
                await self.task_service.complete_subtasks_for_agent(db_task_id, agent_map[name].id)

    async def _finalize(self, manager: AgentProfile, user_request: str, transcript: list[str]) -> str:
        prompt = f"""
Prepare the final private answer for the user in Russian.
Be complete, but do not invent file changes or actions that agents did not report.

User task:
{user_request}

Agent transcript:
{chr(10).join(transcript)}
"""
        return await self.provider.complete(manager.system_prompt, prompt, max_tokens=1200)

    def _profiles_from_plan(self, plan: dict, user_request: str) -> list[AgentProfile]:
        profiles: list[AgentProfile] = []
        for item in plan.get("subtasks", []):
            profile = get_profile(str(item.get("agent", "")))
            if profile is not None and profile.name != "Manager" and profile not in profiles:
                profiles.append(profile)
        if profiles:
            return profiles
        return self._select_agents(user_request)

    def _select_agents(self, text: str) -> list[AgentProfile]:
        lowered = text.lower()
        role_keywords = {
            "frontend": ["ui", "frontend", "react", "css", "html", "страниц", "интерфейс", "дизайн"],
            "backend": ["api", "backend", "db", "database", "sql", "fastapi", "сервер", "база"],
            "qa": ["test", "qa", "bug", "провер", "тест", "ошиб"],
            "devops": ["docker", "deploy", "vps", "ci", "server", "деплой", "сервер"],
            "designer": ["ux", "brand", "copy", "лендинг", "макет", "презентац"],
        }
        selected: list[AgentProfile] = []
        for role, keywords in role_keywords.items():
            if any(keyword in lowered for keyword in keywords):
                profile = get_profile(role)
                if profile is not None:
                    selected.append(profile)
        if selected:
            return selected
        return [profile for profile in DEFAULT_PROFILES if profile.name in {"Backend", "QA", "DevOps"}]

    def _agent_prompt(self, profile: AgentProfile, user_request: str, inbound_messages: list[BusMessage], round_idx: int) -> str:
        context = "\n\n".join(
            f"from={message.from_agent}; kind={message.kind}; hops={message.hops}; payload={message.payload}"
            for message in inbound_messages
        )
        allowed = ", ".join(agent.name for agent in DEFAULT_PROFILES if agent.name not in {"Manager", profile.name})
        return f"""
You are working inside a real Telegram multi-agent group.
Round: {round_idx}
User task: {user_request}

Incoming messages:
{context}

Return JSON only:
{{
  "message": "short useful progress update in Russian",
  "delegate_to": null or one of [{allowed}],
  "delegate_reason": "why that agent is needed, empty when no delegation",
  "memory": {{}},
  "done": true
}}
"""

    def _parse_agent_response(self, raw: str) -> dict:
        parsed = self._parse_json(raw)
        message = parsed.get("message")
        if not isinstance(message, str) or not message.strip():
            message = raw
        memory = parsed.get("memory")
        if not isinstance(memory, dict):
            memory = {}
        delegate_to = parsed.get("delegate_to")
        if isinstance(delegate_to, str) and not delegate_to.strip():
            delegate_to = None
        return {
            "message": message.strip(),
            "delegate_to": delegate_to,
            "delegate_reason": parsed.get("delegate_reason") or "",
            "memory": memory,
            "done": bool(parsed.get("done", True)),
        }

    def _parse_json(self, raw: str) -> dict:
        text = raw.strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(text[start : end + 1])
                except json.JSONDecodeError:
                    pass
        return {"message": raw}

    def _shorten(self, text: str, limit: int = 240) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "..."
