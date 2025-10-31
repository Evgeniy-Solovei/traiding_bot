#!/bin/bash

echo "🛑 Остановка торгового бота..."

# Остановка Celery Worker
if [ -f celery_worker.pid ]; then
    echo "📦 Остановка Celery Worker..."
    celery -A config control shutdown
    rm celery_worker.pid
else
    echo "⚠️  Celery Worker не запущен"
fi

# Остановка Celery Beat
if [ -f celery_beat.pid ]; then
    echo "⏰ Остановка Celery Beat..."
    kill $(cat celery_beat.pid) 2>/dev/null
    rm celery_beat.pid
else
    echo "⚠️  Celery Beat не запущен"
fi

# Остановка Telegram Bot
if [ -f bot.pid ]; then
    echo "🤖 Остановка Telegram Bot..."
    kill $(cat bot.pid) 2>/dev/null
    rm bot.pid
else
    echo "⚠️  Telegram Bot не запущен"
fi

echo ""
echo "✅ Все компоненты остановлены"
