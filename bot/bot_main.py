"""
Главный файл запуска Telegram бота.
Объединяет все роутеры и запускает бота.
"""

import asyncio
import logging
import sys
import os
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.redis import RedisStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from django.conf import settings
from redis.asyncio import Redis

# Импорт роутеров
from . import handlers
from . import handlers_api


async def main():
    """
    Главная функция запуска бота.
    """
    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        stream=sys.stdout
    )
    
    logger = logging.getLogger(__name__)
    
    # Проверка токена
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN не установлен в настройках!")
        sys.exit(1)
    
    # Создание Redis хранилища для FSM
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    storage = RedisStorage(redis=redis)
    
    # Создание бота и диспетчера
    bot = Bot(
        token=settings.TELEGRAM_BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    dp = Dispatcher(storage=storage)
    
    # Регистрация роутеров
    dp.include_router(handlers.router)
    dp.include_router(handlers_api.router)
    
    logger.info("🚀 Бот запущен!")
    logger.info(f"🔗 Redis: {settings.REDIS_URL}")
    
    try:
        # Запуск polling
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await bot.session.close()
        await redis.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Бот остановлен")
