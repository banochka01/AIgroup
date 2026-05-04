# Jarvis Multi-Agent Telegram Workspace

Реальная multi-bot архитектура для Telegram-группы: coordinator bot принимает задачи, OpenAI строит план, отдельные agent bots публикуют короткий прогресс в группе, а полный финальный ответ уходит пользователю в личку coordinator-бота.

## Агенты

- `Frontend` - UI, frontend architecture, accessibility
- `Backend` - API, services, DB, security boundaries
- `QA` - тесты, регрессии, acceptance checks
- `DevOps` - Docker, VPS, окружение, деплой
- `Designer` - UX, copy, presentation quality
- `Manager` - планирование, маршрутизация, итоговая сборка

Каждый агент использует отдельный Telegram token и отправляет сообщения самостоятельно.

## Что есть

- OpenAI async LLM provider с retry/backoff, timeout и понятными ошибками конфигурации.
- Multi-round orchestrator: планирование, подзадачи, очереди сообщений, делегации, защита от циклов.
- Agent-to-agent message bus с `task_id`, `hops`, дедупликацией маршрутов и лимитом сообщений на задачу.
- Telegram coordinator commands:
  - `/task`
  - `/agents`
  - `/agent <name>`
  - `/status`
  - `/stats`
  - `/reset`
- Dual-mode messaging:
  - `group_showcase` - короткий прогресс в группе, финал в личку
  - `private_only` - только личка
  - `full_debug` - более подробные group updates
- Async SQLAlchemy schema и сервисы для users, agents, tasks, subtasks, messages, delegations, memory, stats, approvals, execution logs.
- Sandbox executor без shell: строгий allowlist, проверка путей, timeout, safe env, approval для рискованных команд, логи исполнения.
- Docker Compose для VPS: Postgres + API + Telegram worker.

## Env

Создайте `.env` из `.env.example` и заполните:

```bash
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4.1-mini

TELEGRAM_COORDINATOR_BOT_TOKEN=
TELEGRAM_FRONTEND_BOT_TOKEN=
TELEGRAM_BACKEND_BOT_TOKEN=
TELEGRAM_QA_BOT_TOKEN=
TELEGRAM_DEVOPS_BOT_TOKEN=
TELEGRAM_DESIGNER_BOT_TOKEN=
TELEGRAM_MANAGER_BOT_TOKEN=
TELEGRAM_GROUP_CHAT_ID=
```

Важно: пользователь должен сначала открыть coordinator-бота и отправить `/start`, иначе Telegram не разрешит отправить ему финальный ответ в личку.

## Локальный запуск

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
```

API:

```bash
uvicorn jarvis_multiagent.api.main:app --reload
```

Telegram worker:

```bash
python -m jarvis_multiagent.telegram.runner
```

Для локального SQLite можно временно указать:

```bash
DATABASE_URL=sqlite+aiosqlite:///./jarvis.db
```

## VPS запуск

Одна группа команд для свежего Ubuntu/Debian VPS:

```bash
sudo apt-get update && sudo apt-get install -y git ca-certificates curl && \
git clone https://github.com/banochka01/AIgroup.git AIgroup && \
cd AIgroup && \
cp .env.example .env && \
nano .env && \
bash scripts/deploy_vps.sh
```

После изменения `.env` или обновления кода:

```bash
cd AIgroup && git pull && bash scripts/deploy_vps.sh
```

Если проект уже склонирован и `.env` заполнен:

```bash
bash scripts/deploy_vps.sh
```

```bash
cp .env.example .env
# заполните токены и OPENAI_API_KEY
docker compose up --build -d
docker compose logs -f api telegram
```

Сервисы:

- `api` - FastAPI на `:8000`
- `telegram` - polling coordinator bot
- `db` - Postgres 16

## API примеры

```bash
curl -X POST http://localhost:8000/tasks \
  -H "content-type: application/json" \
  -d '{"text": "Подготовить план деплоя Telegram multi-agent системы на VPS"}'
```

```bash
curl http://localhost:8000/stats
curl http://localhost:8000/approvals
```

Sandbox:

```bash
curl -X POST http://localhost:8000/sandbox/execute \
  -H "content-type: application/json" \
  -d '{"command": "pytest", "workspace": "/app"}'
```

## Telegram пример

1. Добавьте всех agent bots и coordinator bot в одну Telegram-группу.
2. Пользователь пишет coordinator-боту в личку `/start`.
3. В группе:

```text
/task Сделать аудит backend API, проверить Docker деплой и предложить тест-план
```

4. В группе появляются короткие сообщения от `Backend`, `QA`, `DevOps`, `Manager`.
5. Полный итог приходит пользователю в личку от coordinator bot.
