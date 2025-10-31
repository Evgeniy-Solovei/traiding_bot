#!/bin/bash

echo "🚀 Запуск торгового бота..."

# Активация виртуального окружения
source venv/bin/activate

# Проверка Redis
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis не запущен! Запустите: sudo systemctl start redis"
    exit 1
fi

# Celery Worker
echo "📦 Запуск Celery Worker..."
celery -A config worker -l info --detach --pidfile=celery_worker.pid --logfile=celery_worker.log

# Celery Beat
echo "⏰ Запуск Celery Beat..."
celery -A config beat -l info --detach --pidfile=celery_beat.pid --logfile=celery_beat.log --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Telegram Bot
echo "🤖 Запуск Telegram Bot..."
nohup python -m bot.bot_main > bot.log 2>&1 &
echo $! > bot.pid

echo ""
echo "✅ Все компоненты запущены!"
echo ""
echo "📝 Логи:"
echo "  - Celery Worker: celery_worker.log"
echo "  - Celery Beat: celery_beat.log"
echo "  - Telegram Bot: bot.log"
echo ""
echo "🛑 Остановка: ./stop.sh"
echo "📊 Просмотр логов бота: tail -f bot.log"
