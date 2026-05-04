from telegram import Bot


class AgentBot:
    def __init__(self, name: str, token: str) -> None:
        self.name = name
        self.token = token
        self.bot = Bot(token=token) if token else None

    @property
    def configured(self) -> bool:
        return self.bot is not None

    async def send_group(self, chat_id: int, text: str) -> bool:
        if self.bot is None or not chat_id:
            return False
        await self.bot.send_message(chat_id=chat_id, text=f"{self.name}: {text}")
        return True
