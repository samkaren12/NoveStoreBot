import asyncio
import logging
import uvicorn

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import settings
from db import Database
from handlers import router
from web_panel import app as web_app, configure


async def main() -> None:
    if not settings.bot_token or not settings.owner_id:
        raise RuntimeError("BOT_TOKEN و OWNER_ID را در فایل .env تنظیم کنید.")
    logging.basicConfig(level=logging.INFO)
    db = Database(settings.db_path)
    await db.init()
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    configure(db, bot, settings)
    dispatcher = Dispatcher(storage=MemoryStorage())
    dispatcher.include_router(router)
    web_config = uvicorn.Config(web_app, host=settings.web_host, port=settings.web_port, log_level="warning")
    web_server = uvicorn.Server(web_config)
    web_task = asyncio.create_task(web_server.serve())
    try:
        await dispatcher.start_polling(bot, db=db, settings=settings)
    finally:
        web_server.should_exit = True
        await web_task


if __name__ == "__main__":
    asyncio.run(main())
