from uuid import uuid4

from fastapi import FastAPI

from jarvis_multiagent.agents.schema import DEFAULT_PROFILES
from jarvis_multiagent.db.session import init_db
from jarvis_multiagent.security.sandbox import SandboxExecutor, validate_command
from jarvis_multiagent.services.task_service import TaskService
from jarvis_multiagent.telegram.orchestrator import MultiAgentOrchestrator

app = FastAPI(title="Jarvis Multi-Agent API")
orchestrator = MultiAgentOrchestrator()
task_service = TaskService()
sandbox = SandboxExecutor()


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/agents")
async def agents() -> dict:
    return {"agents": [agent.__dict__ for agent in DEFAULT_PROFILES]}


@app.post("/tasks")
async def create_task(payload: dict) -> dict:
    task_id = payload.get("task_id") or f"api-{uuid4().hex[:12]}"
    text = payload.get("text", "")
    return await orchestrator.execute_task(task_id, text, source="api")


@app.get("/stats")
async def stats() -> dict:
    return await task_service.stats()


@app.get("/approvals")
async def approvals() -> dict:
    return {"pending": await task_service.pending_approvals()}


@app.post("/sandbox/validate")
async def sandbox_validate(payload: dict) -> dict:
    result = validate_command(payload.get("command", ""), payload.get("workspace", "/workspace"))
    return result.__dict__


@app.post("/sandbox/execute")
async def sandbox_execute(payload: dict) -> dict:
    result = await sandbox.execute(
        payload.get("command", ""),
        workspace=payload.get("workspace", "/workspace"),
        task_public_id=payload.get("task_id"),
        approved=bool(payload.get("approved", False)),
    )
    return result.__dict__
