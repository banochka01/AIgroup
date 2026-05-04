import asyncio
import logging

from telegram import Update

from jarvis_multiagent.db.session import init_db
from jarvis_multiagent.telegram.coordinator import TelegramCoordinator


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def main() -> None:
    asyncio.run(init_db())
    app = TelegramCoordinator().app()
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
