# 🚀 Развертывание в Production

## Подготовка к продакшену

### 1. Настройки безопасности

В `config/settings.py` измените:

```python
DEBUG = False
SECRET_KEY = 'long-random-secret-key-generate-new-one'
ALLOWED_HOSTS = ['yourdomain.com', 'www.yourdomain.com']
```

### 2. Использование переменных окружения

Создайте `.env` файл:

```env
DEBUG=False
SECRET_KEY=production-secret-key-here
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

DB_NAME=trading_bot_prod
DB_USER=trading_user
DB_PASSWORD=strong-password-here
DB_HOST=localhost
DB_PORT=5432

TELEGRAM_BOT_TOKEN=your-production-bot-token
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

ENCRYPTION_KEY=your-production-encryption-key
BYBIT_TESTNET=False
```

### 3. PostgreSQL Production Setup

```bash
# Создайте пользователя и БД для production
sudo -u postgres psql

CREATE DATABASE trading_bot_prod;
CREATE USER trading_user WITH PASSWORD 'strong-password';
ALTER ROLE trading_user SET client_encoding TO 'utf8';
ALTER ROLE trading_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE trading_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE trading_bot_prod TO trading_user;

# PostgreSQL 15+
\c trading_bot_prod
GRANT ALL ON SCHEMA public TO trading_user;

\q
```

### 4. Настройка Nginx (опционально)

Если хотите админку Django через веб:

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location /static/ {
        alias /home/user/webapp/staticfiles/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### 5. Gunicorn для Django

Установите:
```bash
pip install gunicorn
```

Создайте `gunicorn_config.py`:

```python
bind = "127.0.0.1:8000"
workers = 3
worker_class = "sync"
timeout = 120
accesslog = "gunicorn_access.log"
errorlog = "gunicorn_error.log"
loglevel = "info"
```

Запуск:
```bash
gunicorn config.wsgi:application -c gunicorn_config.py --daemon
```

### 6. Systemd Services

Создайте `/etc/systemd/system/trading-bot.service`:

```ini
[Unit]
Description=Trading Bot Telegram
After=network.target redis.service postgresql.service

[Service]
Type=simple
User=user
WorkingDirectory=/home/user/webapp
Environment="PATH=/home/user/webapp/venv/bin"
ExecStart=/home/user/webapp/venv/bin/python -m bot.bot_main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Celery Worker: `/etc/systemd/system/trading-celery.service`:

```ini
[Unit]
Description=Trading Bot Celery Worker
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=user
WorkingDirectory=/home/user/webapp
Environment="PATH=/home/user/webapp/venv/bin"
ExecStart=/home/user/webapp/venv/bin/celery -A config worker -l info --detach --pidfile=/var/run/celery/worker.pid --logfile=/var/log/celery/worker.log
ExecStop=/home/user/webapp/venv/bin/celery -A config control shutdown
PIDFile=/var/run/celery/worker.pid
Restart=always

[Install]
WantedBy=multi-user.target
```

Celery Beat: `/etc/systemd/system/trading-celery-beat.service`:

```ini
[Unit]
Description=Trading Bot Celery Beat
After=network.target redis.service postgresql.service

[Service]
Type=forking
User=user
WorkingDirectory=/home/user/webapp
Environment="PATH=/home/user/webapp/venv/bin"
ExecStart=/home/user/webapp/venv/bin/celery -A config beat -l info --detach --pidfile=/var/run/celery/beat.pid --logfile=/var/log/celery/beat.log --scheduler django_celery_beat.schedulers:DatabaseScheduler
PIDFile=/var/run/celery/beat.pid
Restart=always

[Install]
WantedBy=multi-user.target
```

Создайте директории:
```bash
sudo mkdir -p /var/run/celery /var/log/celery
sudo chown user:user /var/run/celery /var/log/celery
```

Включите сервисы:
```bash
sudo systemctl daemon-reload
sudo systemctl enable trading-bot
sudo systemctl enable trading-celery
sudo systemctl enable trading-celery-beat

sudo systemctl start trading-bot
sudo systemctl start trading-celery
sudo systemctl start trading-celery-beat
```

### 7. Мониторинг

Проверка статуса:
```bash
sudo systemctl status trading-bot
sudo systemctl status trading-celery
sudo systemctl status trading-celery-beat
```

Логи:
```bash
sudo journalctl -u trading-bot -f
sudo journalctl -u trading-celery -f
sudo journalctl -u trading-celery-beat -f
```

### 8. Backup

Создайте скрипт `backup.sh`:

```bash
#!/bin/bash

DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/home/user/backups"

mkdir -p $BACKUP_DIR

# Backup PostgreSQL
pg_dump -U trading_user trading_bot_prod > $BACKUP_DIR/db_$DATE.sql

# Backup .env
cp /home/user/webapp/.env $BACKUP_DIR/env_$DATE

# Удаление старых бэкапов (старше 7 дней)
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "env_*" -mtime +7 -delete

echo "Backup completed: $DATE"
```

Добавьте в cron:
```bash
crontab -e

# Ежедневный бэкап в 3:00
0 3 * * * /home/user/webapp/backup.sh >> /home/user/webapp/backup.log 2>&1
```

### 9. Firewall

```bash
# Разрешаем только необходимые порты
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP (nginx)
sudo ufw allow 443/tcp  # HTTPS (nginx)
sudo ufw enable
```

### 10. Security Checklist

✅ DEBUG = False  
✅ Новый SECRET_KEY  
✅ Сильные пароли БД  
✅ IP whitelist на Bybit API  
✅ ENCRYPTION_KEY в безопасности  
✅ Firewall настроен  
✅ Автоматические бэкапы  
✅ Мониторинг логов  
✅ SSL сертификат (Let's Encrypt)  

### 11. Обновление

```bash
cd /home/user/webapp

# Остановка сервисов
sudo systemctl stop trading-bot
sudo systemctl stop trading-celery
sudo systemctl stop trading-celery-beat

# Обновление кода
git pull

# Обновление зависимостей
source venv/bin/activate
pip install -r requirements.txt

# Миграции БД
python manage.py migrate

# Статика
python manage.py collectstatic --noinput

# Запуск сервисов
sudo systemctl start trading-celery
sudo systemctl start trading-celery-beat
sudo systemctl start trading-bot
```

## Мониторинг и алерты

### Prometheus + Grafana (опционально)

Для продвинутого мониторинга можно настроить Prometheus и Grafana.

### Простой мониторинг через Telegram

Добавьте в код уведомление администратору при критических ошибках:

```python
# В bot/notifications.py
async def send_admin_alert(message: str):
    """Отправка алерта администратору"""
    ADMIN_TELEGRAM_ID = 123456789  # Ваш Telegram ID
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    await bot.send_message(ADMIN_TELEGRAM_ID, f"⚠️ ALERT: {message}")
```

## Производительность

### Redis настройки

В `/etc/redis/redis.conf`:

```conf
maxmemory 256mb
maxmemory-policy allkeys-lru
save 900 1
save 300 10
save 60 10000
```

### PostgreSQL настройки

В `/etc/postgresql/*/main/postgresql.conf`:

```conf
shared_buffers = 256MB
effective_cache_size = 1GB
work_mem = 16MB
maintenance_work_mem = 64MB
```

Перезапуск:
```bash
sudo systemctl restart postgresql
sudo systemctl restart redis
```

## Масштабирование

Для обработки большего количества пользователей:

1. Увеличьте количество Celery workers:
```bash
celery -A config worker -l info --concurrency=8
```

2. Используйте несколько Redis инстансов (разделите broker и result backend)

3. Настройте репликацию PostgreSQL

4. Используйте load balancer для нескольких экземпляров бота
