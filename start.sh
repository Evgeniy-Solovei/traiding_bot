#!/usr/bin/env bash
set -euo pipefail

# Локальный запуск (не для production):
# - uvicorn backend
# - telegram bot
# - celery worker
# - celery beat
# - redis (если не запущен)

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

PYTHON="$ROOT_DIR/.venv/bin/python"
CELERY="$ROOT_DIR/.venv/bin/celery"
UVICORN="$ROOT_DIR/.venv/bin/uvicorn"

if [ ! -x "$PYTHON" ] || [ ! -x "$CELERY" ] || [ ! -x "$UVICORN" ]; then
  echo "Не найдено виртуальное окружение (.venv) или бинарники."
  exit 1
fi

mkdir -p logs

if redis-cli ping >/dev/null 2>&1; then
  echo "Redis уже запущен."
else
  echo "Запускаю Redis..."
  redis-server --daemonize yes
  sleep 1
fi

echo "Применяю миграции..."
"$PYTHON" manage.py migrate --noinput

echo "Запускаю uvicorn..."
"$UVICORN" trading_bot.asgi:application --host 0.0.0.0 --port 8000 > logs/web.log 2>&1 &
WEB_PID=$!

echo "Запускаю Telegram бота..."
"$PYTHON" bot_main.py > logs/bot.log 2>&1 &
BOT_PID=$!

echo "Запускаю Celery worker..."
"$CELERY" -A trading_bot worker -l info > logs/celery_worker.log 2>&1 &
WORKER_PID=$!

echo "Запускаю Celery beat..."
"$CELERY" -A trading_bot beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler > logs/celery_beat.log 2>&1 &
BEAT_PID=$!

echo
echo "Локальный запуск выполнен:"
echo "WEB_PID=$WEB_PID"
echo "BOT_PID=$BOT_PID"
echo "WORKER_PID=$WORKER_PID"
echo "BEAT_PID=$BEAT_PID"
echo
echo "Логи:"
echo "  tail -f logs/web.log"
echo "  tail -f logs/bot.log"
echo "  tail -f logs/celery_worker.log"
echo "  tail -f logs/celery_beat.log"
echo
echo "Остановка:"
echo "  kill $WEB_PID $BOT_PID $WORKER_PID $BEAT_PID"

trap 'kill $WEB_PID $BOT_PID $WORKER_PID $BEAT_PID 2>/dev/null || true; exit 0' INT TERM
wait
