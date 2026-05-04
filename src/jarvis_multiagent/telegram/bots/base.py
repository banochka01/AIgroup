from telegram import Bot


class AgentBot:
    def __init__(self, name: str, token: str) -> None:
        self.name = name
        self.bot = Bot(token=token)

    async def send_group(self, chat_id: int, text: str) -> None:
        await self.bot.send_message(chat_id=chat_id, text=f"{self.name}: {text}")
