import logging

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from jarvis_multiagent.agents.schema import DEFAULT_PROFILES, get_profile
from jarvis_multiagent.core.config import settings
from jarvis_multiagent.services.task_service import TaskService
from jarvis_multiagent.telegram.bots.backend_bot import BackendBot
from jarvis_multiagent.telegram.bots.designer_bot import DesignerBot
from jarvis_multiagent.telegram.bots.devops_bot import DevopsBot
from jarvis_multiagent.telegram.bots.frontend_bot import FrontendBot
from jarvis_multiagent.telegram.bots.manager_bot import ManagerBot
from jarvis_multiagent.telegram.bots.qa_bot import QaBot
from jarvis_multiagent.telegram.orchestrator import MultiAgentOrchestrator


logger = logging.getLogger(__name__)


class TelegramCoordinator:
    def __init__(self) -> None:
        self.orchestrator = MultiAgentOrchestrator()
        self.task_service = TaskService()
        self.agent_bots = {
            "Frontend": FrontendBot("Frontend", settings.telegram_frontend_bot_token),
            "Backend": BackendBot("Backend", settings.telegram_backend_bot_token),
            "QA": QaBot("QA", settings.telegram_qa_bot_token),
            "DevOps": DevopsBot("DevOps", settings.telegram_devops_bot_token),
            "Designer": DesignerBot("Designer", settings.telegram_designer_bot_token),
            "Manager": ManagerBot("Manager", settings.telegram_manager_bot_token),
        }

    async def task_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = self._extract_task_text(update, context)
        if not text:
            await update.effective_chat.send_message("Напишите задачу после /task, например: /task подготовить план деплоя")
            return
        await self._execute_from_update(update, text)

    async def agents_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        keyboard = [
            [InlineKeyboardButton(profile.name, callback_data=f"agent:{profile.name}")]
            for profile in DEFAULT_PROFILES
        ]
        await update.effective_chat.send_message("Агенты команды:", reply_markup=InlineKeyboardMarkup(keyboard))

    async def agent_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        name = " ".join(context.args).strip()
        if not name:
            await self.agents_command(update, context)
            return
        await update.effective_chat.send_message(self._format_agent(name))

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        configured = [name for name, bot in self.agent_bots.items() if bot.configured]
        missing = [name for name, bot in self.agent_bots.items() if not bot.configured]
        text = (
            f"Статус: ready\n"
            f"Режим: {settings.group_mode}\n"
            f"Группа: {settings.telegram_group_chat_id or 'не задана'}\n"
            f"LLM: OpenAI / {settings.openai_model}\n"
            f"Боты с токенами: {', '.join(configured) or 'нет'}\n"
            f"Без токена: {', '.join(missing) or 'нет'}"
        )
        await update.effective_chat.send_message(text)

    async def stats_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        stats = await self.task_service.stats()
        agent_lines = [
            f"{agent['name']}: done={agent['tasks_completed']}, delegations={agent['delegations_made']}"
            for agent in stats["agents"]
        ]
        text = (
            f"Задач всего: {stats['tasks_total']}\n"
            f"В работе: {stats['tasks_running']}\n"
            f"Сообщений: {stats['messages_total']}\n"
            f"Делегаций: {stats['delegations_total']}\n\n"
            + "\n".join(agent_lines)
        )
        await update.effective_chat.send_message(text[:3900])

    async def reset_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self.orchestrator = MultiAgentOrchestrator()
        await update.effective_chat.send_message("Оперативный контекст coordinator сброшен. История в БД сохранена.")

    async def callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        query = update.callback_query
        if query is None:
            return
        await query.answer()
        if query.data and query.data.startswith("agent:"):
            await query.edit_message_text(self._format_agent(query.data.split(":", 1)[1]))

    async def text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.effective_message.text.strip() if update.effective_message and update.effective_message.text else ""
        if text:
            await self._execute_from_update(update, text)

    def app(self) -> Application:
        if not settings.telegram_coordinator_bot_token:
            raise RuntimeError("TELEGRAM_COORDINATOR_BOT_TOKEN is not configured")

        app = Application.builder().token(settings.telegram_coordinator_bot_token).post_init(self._post_init).build()
        app.add_handler(CommandHandler("task", self.task_command))
        app.add_handler(CommandHandler("agents", self.agents_command))
        app.add_handler(CommandHandler("agent", self.agent_command))
        app.add_handler(CommandHandler("status", self.status_command))
        app.add_handler(CommandHandler("stats", self.stats_command))
        app.add_handler(CommandHandler("reset", self.reset_command))
        app.add_handler(CallbackQueryHandler(self.callback_query))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.text_message))
        return app

    async def _execute_from_update(self, update: Update, text: str) -> None:
        message = update.effective_message
        user = update.effective_user
        chat = update.effective_chat
        if message is None or user is None or chat is None:
            return

        task_id = f"tg-{chat.id}-{message.message_id}"
        await chat.send_message(f"Принял задачу {task_id}. Запускаю агентов.")
        result = await self.orchestrator.execute_task(
            task_id,
            text,
            telegram_user_id=str(user.id),
            username=user.username,
            source="telegram",
        )

        group_chat_id = settings.telegram_group_chat_id or (chat.id if chat.type in {"group", "supergroup"} else 0)
        if result["mode"] != "private_only" and group_chat_id:
            for msg in result["group_messages"][:20]:
                bot = self.agent_bots.get(msg["sender"])
                if bot is None:
                    continue
                try:
                    await bot.send_group(group_chat_id, msg["body"])
                except TelegramError:
                    logger.exception("Agent bot %s failed to send group message", msg["sender"])

        await self._send_private_result(update, result["private_result"])

    async def _send_private_result(self, update: Update, text: str) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if user is None or chat is None:
            return
        try:
            await update.get_bot().send_message(chat_id=user.id, text=text[:3900])
        except TelegramError:
            await chat.send_message("Финальный ответ готов, но Telegram не дал написать в личку. Откройте coordinator-бота и отправьте /start.")

    def _extract_task_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> str:
        if context.args:
            return " ".join(context.args).strip()
        message = update.effective_message
        if message is None or not message.text:
            return ""
        return message.text.replace("/task", "", 1).strip()

    def _format_agent(self, name: str) -> str:
        profile = get_profile(name)
        if profile is None:
            return "Неизвестный агент. Доступны: " + ", ".join(profile.name for profile in DEFAULT_PROFILES)
        bot = self.agent_bots.get(profile.name)
        status = "token configured" if bot and bot.configured else "token missing"
        return (
            f"{profile.name}\n"
            f"Роль: {profile.role}\n"
            f"Telegram: {status}\n"
            f"Навыки: {', '.join(profile.skills)}"
        )

    async def _post_init(self, app: Application) -> None:
        await app.bot.set_my_commands(
            [
                BotCommand("task", "создать задачу"),
                BotCommand("agents", "показать агентов"),
                BotCommand("agent", "информация по агенту"),
                BotCommand("status", "статус системы"),
                BotCommand("stats", "статистика"),
                BotCommand("reset", "сбросить оперативный контекст"),
            ]
        )
