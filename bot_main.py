"""
Главный entrypoint Telegram-бота (корневой).
Запуск: python bot_main.py
"""

import asyncio
import logging
import os
import sys

import django
from dotenv import load_dotenv


# Загрузка переменных окружения из .env файла
load_dotenv()

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'trading_bot.settings')
django.setup()

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage
from django.conf import settings
from redis.asyncio import Redis

from bot import handlers, handlers_api


async def main():
    """
    Главная функция запуска бота.
    """
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    logger = logging.getLogger(__name__)

    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен в настройках!")
        sys.exit(1)

    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    storage = RedisStorage(redis=redis)

    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    dp = Dispatcher(storage=storage)
    dp.include_router(handlers.router)
    dp.include_router(handlers_api.router)

    logger.info("🚀 Бот запущен!")
    logger.info(f"🔗 Redis: {settings.REDIS_URL}")

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await redis.aclose()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Бот остановлен")
