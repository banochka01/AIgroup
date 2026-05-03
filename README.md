# JarvisOpenAI Multi-Agent Telegram Workspace (Extended)

This repository now contains a production-oriented extension scaffold for a **multi-bot Telegram AI team** architecture.

## What was added
- Multi-agent orchestrator with 3 modes:
  - `group_showcase` (default)
  - `private_only`
  - `full_debug`
- Provider abstraction (`OpenAI` and `Anthropic` placeholders)
- Async FastAPI admin API:
  - `/health`
  - `/agents`
  - `/tasks`
  - `/stats`
  - `/approvals`
- Security command policy module (whitelist + blocked tokens)
- SQLAlchemy async schema for:
  - users, agents, tasks, subtasks, messages, delegations, memory, stats, approvals, settings
- Deploy files:
  - `Dockerfile`
  - `docker-compose.yml`
  - `.env.example`

## Structure
- `src/jarvis_multiagent/api` FastAPI app
- `src/jarvis_multiagent/telegram` orchestrator and routing core
- `src/jarvis_multiagent/agents` agent profiles + role definitions
- `src/jarvis_multiagent/services` LLM provider abstraction
- `src/jarvis_multiagent/security` sandbox command policy
- `src/jarvis_multiagent/db` async DB models/session

## Local setup
1. Create env file:
   ```bash
   cp .env.example .env
   ```
2. Install:
   ```bash
   pip install -e .
   ```
3. Run API:
   ```bash
   uvicorn jarvis_multiagent.api.main:app --reload
   ```

## Docker deploy
```bash
docker compose up --build -d
```

## VPS deploy (basic)
1. Provision Ubuntu 22.04+
2. Install Docker + Docker Compose
3. Clone repo, set `.env`
4. `docker compose up --build -d`
5. Put reverse proxy (nginx/caddy) in front
6. Add TLS and lock inbound ports

## Example usage
Create task:
```bash
curl -X POST http://localhost:8000/tasks \
  -H 'content-type: application/json' \
  -d '{"task_id": "t-1", "text": "create landing page for FPV shop"}'
```

## Security notes
- Command execution must pass whitelist checks.
- Dangerous tokens are blocked (`rm -rf`, `sudo`, secret paths, etc.).
- Keep approvals required for risky actions.
- Never access credentials/cookies/system secrets.

## Next extension points
- Hook real Telegram bot updates for each token.
- Persist orchestrator messages and per-agent memory.
- Integrate real OpenAI/Anthropic clients with retries/rate limits.
- Implement `/build`, `/plan`, `/run`, `/agent`, `/pc`, `/shell`, `/files`, `/read`, `/write` command handlers using existing Jarvis command semantics in this backend.
