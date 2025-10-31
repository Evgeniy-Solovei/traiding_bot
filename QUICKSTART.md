# ⚡ Быстрый старт

Минимальная инструкция для запуска бота за 5 минут.

## Шаг 1: Установка зависимостей (1 мин)

```bash
# PostgreSQL
sudo apt update
sudo apt install postgresql redis-server -y

# Python зависимости
cd /home/user/webapp
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Шаг 2: Настройка БД (1 мин)

```bash
# Создание БД
sudo -u postgres psql -c "CREATE DATABASE trading_bot;"
sudo -u postgres psql -c "CREATE USER user WITH PASSWORD 'password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE trading_bot TO user;"

# PostgreSQL 15+
sudo -u postgres psql trading_bot -c "GRANT ALL ON SCHEMA public TO user;"
```

## Шаг 3: Настройка .env (2 мин)

```bash
# Копируем пример
cp .env.example .env

# Генерируем ключ шифрования
./generate_key.py

# Редактируем .env
nano .env
```

**Минимальные обязательные переменные**:
```env
TELEGRAM_BOT_TOKEN=your-bot-token-from-@BotFather
ENCRYPTION_KEY=generated-key-from-script
DB_PASSWORD=password  # (или ваш пароль из шага 2)
```

## Шаг 4: Миграции БД (30 сек)

```bash
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser  # опционально для админки
```

## Шаг 5: Запуск (10 сек)

```bash
./start.sh
```

Готово! 🎉

## Проверка работы

```bash
# Проверка логов бота
tail -f bot.log

# Проверка Celery
tail -f celery_worker.log

# Проверка статуса
ps aux | grep -E "bot_main|celery"
```

## Использование

1. Найдите вашего бота в Telegram
2. Отправьте `/start`
3. Следуйте инструкциям бота

## Остановка

```bash
./stop.sh
```

## Troubleshooting

### Redis не запущен
```bash
sudo systemctl start redis
sudo systemctl enable redis
```

### Ошибки прав PostgreSQL 15+
```bash
sudo -u postgres psql trading_bot
GRANT ALL ON SCHEMA public TO user;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO user;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO user;
```

### Бот не отвечает
```bash
# Проверьте токен
echo $TELEGRAM_BOT_TOKEN

# Перезапуск
./stop.sh
./start.sh
```

## Следующие шаги

1. Получите API ключи Bybit testnet: https://testnet.bybit.com
2. Добавьте через бота (🔑 API Ключи)
3. Настройте параметры (⚙️ Настройки)
4. Добавьте пару BTCUSDT (📈 Торговые пары)
5. Запустите торговлю (▶️ Старт)

Подробная документация: [README.md](README.md)
