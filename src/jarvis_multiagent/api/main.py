from fastapi import FastAPI

from jarvis_multiagent.db.session import init_db
from jarvis_multiagent.telegram.orchestrator import MultiAgentOrchestrator

app = FastAPI(title="Jarvis Multi-Agent API")
orchestrator = MultiAgentOrchestrator()


@app.on_event("startup")
async def startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/agents")
async def agents() -> dict:
    from jarvis_multiagent.agents.schema import DEFAULT_PROFILES

    return {"agents": [a.__dict__ for a in DEFAULT_PROFILES]}


@app.post("/tasks")
async def create_task(payload: dict) -> dict:
    task_id = payload.get("task_id", "task-local")
    text = payload.get("text", "")
    return await orchestrator.execute_task(task_id, text)


@app.get("/stats")
async def stats() -> dict:
    return {"tasks_total": 0, "agents_active": 6}


@app.get("/approvals")
async def approvals() -> dict:
    return {"pending": []}
