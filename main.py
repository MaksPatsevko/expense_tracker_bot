import logging
import asyncio
import os
import asyncpg
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher
from aiohttp import web
from services.db import DatabaseRepository
from services.monobank import handle_mono_webhook
from handlers import start, expenses, income, limits, categories, accounts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def start_telegram():
    logger.info("🤖 Запуск Telegram бота...")
    await dp.start_polling(bot)


async def start_web_server(db: DatabaseRepository):
    app = web.Application()

    app["db"] = db
    app["bot"] = bot

    app.router.add_post('/mono/{user_id}', handle_mono_webhook)
    app.router.add_get('/mono/{user_id}', lambda r: web.Response(text="OK", status=200))

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    logger.info("🌐 Веб-сервер запущено на порту 8080...")
    await site.start()


async def main():
    try:
        pool = await asyncpg.create_pool(os.getenv("DATABASE_URL"))

        db = DatabaseRepository(pool)

        dp["db"] = db

        dp.include_router(start.router)
        dp.include_router(limits.router)
        dp.include_router(categories.router)
        dp.include_router(expenses.router)
        dp.include_router(income.router)
        dp.include_router(accounts.router)

        await asyncio.gather(
            start_web_server(db),
            start_telegram()
        )
    except Exception as e:
        logger.critical("Критична помилка при запуску: %s", e)
    finally:
        if 'pool' in locals():
            await pool.close()
            logger.info("З'єднання з базою даних закрито.")


if __name__ == "__main__":
    asyncio.run(main())