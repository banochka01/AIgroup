from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from jarvis_multiagent.core.config import settings
from jarvis_multiagent.telegram.bots.backend_bot import BackendBot
from jarvis_multiagent.telegram.bots.devops_bot import DevopsBot
from jarvis_multiagent.telegram.bots.frontend_bot import FrontendBot
from jarvis_multiagent.telegram.bots.manager_bot import ManagerBot
from jarvis_multiagent.telegram.bots.qa_bot import QaBot
from jarvis_multiagent.telegram.orchestrator import MultiAgentOrchestrator


class TelegramCoordinator:
    def __init__(self) -> None:
        self.orchestrator = MultiAgentOrchestrator()
        self.agent_bots = {
            "Frontend": FrontendBot("Frontend", settings.telegram_frontend_bot_token),
            "Backend": BackendBot("Backend", settings.telegram_backend_bot_token),
            "QA": QaBot("QA", settings.telegram_qa_bot_token),
            "DevOps": DevopsBot("DevOps", settings.telegram_devops_bot_token),
            "Manager": ManagerBot("Manager", settings.telegram_manager_bot_token),
        }

    async def task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = " ".join(context.args).strip()
        task_id = f"tg-{update.effective_message.message_id}"
        result = await self.orchestrator.execute_task(task_id, text)
        if settings.group_mode != "private_only":
            for msg in result["group_messages"][:10]:
                bot = self.agent_bots.get(msg["sender"])
                if bot:
                    await bot.send_group(settings.telegram_group_chat_id, msg["body"])
        await update.effective_chat.send_message(result["private_result"][:3900])

    async def agents_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_chat.send_message("Agents: Frontend, Backend, QA, DevOps, Manager")

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_chat.send_message("System ready")

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_chat.send_message("Context reset")

    def app(self) -> Application:
        app = Application.builder().token(settings.telegram_coordinator_bot_token).build()
        app.add_handler(CommandHandler("task", self.task_command))
        app.add_handler(CommandHandler("agents", self.agents_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("stats", self.status_command))
        app.add_handler(CommandHandler("reset", self.reset_command))
        app.add_handler(CommandHandler("agent", self.agents_command))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.task_command))
        return app
