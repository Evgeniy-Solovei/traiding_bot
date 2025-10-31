# 🤖 Торговый Бот для Bybit

Автоматический торговый бот для фьючерсов на Bybit с управлением через Telegram.

## 📋 Описание

Асинхронный Telegram бот на Django 5.2 и aiogram 3.x для автоматической торговли фьючерсами на Bybit. Использует стратегию "Ловим отскоки от границ ценового канала" с подтверждением 4-мя индикаторами.

### 🎯 Стратегия

**Философия**: Ловим отскоки от границ ценового канала в направлении тренда с подтверждением 4-мя индикаторами.

**Индикаторы**:
- EMA (9/21) - определение тренда
- RSI (14) - перекупленность/перепроданность  
- Williams %R (14) - перекупленность/перепроданность
- Ценовой канал (20 свечей) - границы для входа
- Объем - подтверждение силы движения

**Сигналы**:
- **LONG**: Цена у нижней границы канала + RSI<30 + Williams<-80 + EMA9 пересекает EMA21 снизу вверх + увеличение объема
- **SHORT**: Цена у верхней границы канала + RSI>70 + Williams>-20 + EMA9 пересекает EMA21 сверху вниз + увеличение объема

**Риск-менеджмент**:
- Стоп-лосс: 1.5x ATR
- Тейк-профит: 2.5x ATR
- Расчет размера позиции на основе % риска от депозита

## 🚀 Возможности

✅ Автоматический анализ рынка каждую минуту  
✅ Открытие/закрытие позиций по сигналам стратегии  
✅ Управление рисками (размер позиции, SL/TP)  
✅ Поддержка нескольких торговых пар одновременно  
✅ Testnet и Mainnet режимы  
✅ Уведомления о сделках в Telegram  
✅ Статистика и история торговли  
✅ Шифрование API ключей (Fernet)  
✅ Админ-панель Django для управления  

## 🛠 Технологии

- **Backend**: Django 5.2 (async), Python 3.12
- **Telegram Bot**: aiogram 3.x
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Task Queue**: Celery + Celery Beat
- **Exchange API**: ccxt (Bybit)
- **Indicators**: pandas, numpy, ta

## 📦 Установка

### 1. Клонирование репозитория

```bash
git clone <repository-url>
cd webapp
```

### 2. Создание виртуального окружения

```bash
python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка PostgreSQL

```bash
# Установите PostgreSQL если еще не установлен
sudo apt install postgresql postgresql-contrib  # Ubuntu/Debian

# Создайте базу данных
sudo -u postgres psql
CREATE DATABASE trading_bot;
CREATE USER your_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE trading_bot TO your_user;
\q
```

### 5. Установка Redis

```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis
sudo systemctl enable redis

# Проверка
redis-cli ping  # должен ответить PONG
```

### 6. Настройка переменных окружения

Скопируйте `.env.example` в `.env` и заполните:

```bash
cp .env.example .env
nano .env
```

**Обязательные переменные**:

```env
# Django
SECRET_KEY=your-django-secret-key-here
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL
DB_NAME=trading_bot
DB_USER=your_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432

# Telegram Bot
TELEGRAM_BOT_TOKEN=your-bot-token-from-botfather

# Redis
REDIS_URL=redis://localhost:6379/0

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Шифрование (будет сгенерирован автоматически при первом запуске)
ENCRYPTION_KEY=

# Bybit (для тестирования)
BYBIT_TESTNET=True
```

### 7. Генерация ключа шифрования

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Скопируйте вывод в `ENCRYPTION_KEY` в файле `.env`.

### 8. Создание миграций и применение

```bash
python manage.py makemigrations
python manage.py migrate
```

### 9. Создание суперпользователя для админки

```bash
python manage.py createsuperuser
```

## 🏃 Запуск

### Вариант 1: Ручной запуск всех компонентов

**Терминал 1 - Django (опционально для админки)**:
```bash
python manage.py runserver
```

**Терминал 2 - Telegram Bot**:
```bash
python -m bot.bot_main
```

**Терминал 3 - Celery Worker**:
```bash
celery -A config worker -l info
```

**Терминал 4 - Celery Beat (периодические задачи)**:
```bash
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### Вариант 2: Использование скриптов (рекомендуется)

Создайте файл `start.sh`:

```bash
#!/bin/bash

# Запуск всех компонентов в фоновом режиме

# Celery Worker
celery -A config worker -l info --detach --pidfile=celery_worker.pid --logfile=celery_worker.log

# Celery Beat
celery -A config beat -l info --detach --pidfile=celery_beat.pid --logfile=celery_beat.log --scheduler django_celery_beat.schedulers:DatabaseScheduler

# Telegram Bot
nohup python -m bot.bot_main > bot.log 2>&1 &
echo $! > bot.pid

echo "✅ Все компоненты запущены"
echo "📝 Логи:"
echo "  - Celery Worker: celery_worker.log"
echo "  - Celery Beat: celery_beat.log"
echo "  - Telegram Bot: bot.log"
```

Для остановки создайте `stop.sh`:

```bash
#!/bin/bash

# Остановка всех компонентов

# Остановка Celery Worker
if [ -f celery_worker.pid ]; then
    celery -A config control shutdown
    rm celery_worker.pid
fi

# Остановка Celery Beat
if [ -f celery_beat.pid ]; then
    kill $(cat celery_beat.pid)
    rm celery_beat.pid
fi

# Остановка Telegram Bot
if [ -f bot.pid ]; then
    kill $(cat bot.pid)
    rm bot.pid
fi

echo "✅ Все компоненты остановлены"
```

Сделайте скрипты исполняемыми:
```bash
chmod +x start.sh stop.sh
```

Запуск:
```bash
./start.sh
```

Остановка:
```bash
./stop.sh
```

## 📱 Использование бота

### 1. Получение API ключей Bybit

**Для testnet** (рекомендуется для начала):
1. Зайдите на https://testnet.bybit.com
2. Зарегистрируйтесь или войдите
3. Перейдите в API Management
4. Создайте новый API ключ с правами: Trading (Read/Write), Position (Read/Write)
5. Скопируйте API Key и API Secret

**Для mainnet** (реальная торговля):
1. Зайдите на https://www.bybit.com
2. Перейдите в API Management
3. Создайте новый API ключ с правами: Trading (Read/Write), Position (Read/Write)
4. **ВАЖНО**: Добавьте IP whitelist для безопасности!

### 2. Настройка бота в Telegram

1. Найдите вашего бота в Telegram (токен из `.env`)
2. Отправьте `/start` - бот создаст вам аккаунт
3. Нажмите `🔑 API Ключи` → `➕ Добавить ключи`
4. Выберите сеть (Testnet или Mainnet)
5. Введите API Key и API Secret
6. Бот проверит подключение и покажет баланс

### 3. Настройка параметров торговли

Нажмите `⚙️ Настройки` и настройте:

- **💰 Размер ордера**: Базовый размер позиции в USD (минимум $5)
- **🎚 Плечо**: От 1x до 100x (рекомендуется 10-20x)
- **⚠️ Риск на сделку**: % от депозита (рекомендуется 1-2%)

**Пример**:
- Депозит: $1000
- Риск: 1%
- Плечо: 10x

При срабатывании стоп-лосса вы потеряете максимум $10 (1% от $1000).

### 4. Добавление торговых пар

Нажмите `📈 Торговые пары` → `➕ Добавить пару`

Введите символ в формате: `BTCUSDT`, `ETHUSDT`, `SOLUSDT`

Можно добавить несколько пар - бот будет мониторить все активные.

### 5. Запуск торговли

Нажмите `▶️ Старт`

Бот начнет:
- Анализировать рынок каждую минуту
- Искать сигналы по вашей стратегии
- Открывать позиции при обнаружении сигнала
- Отправлять уведомления о каждой сделке

### 6. Мониторинг

- `📊 Статистика` - общая статистика торговли
- `📝 Открытые позиции` - текущие открытые сделки (можно закрыть вручную)
- `📜 История` - все закрытые сделки

### 7. Остановка

Нажмите `⏸ Стоп` для остановки торговли.

Открытые позиции продолжат отслеживаться и закроются при достижении SL/TP.

## 🔧 Админ-панель Django

Доступна по адресу: http://localhost:8000/admin

**Возможности**:
- Просмотр всех пользователей и их настроек
- Управление биржами и API ключами
- Просмотр истории сделок
- Просмотр статистики
- Ручное изменение параметров стратегии

## 📊 Структура проекта

```
webapp/
├── config/                  # Настройки Django и Celery
│   ├── settings.py
│   ├── celery.py
│   └── urls.py
├── trading/                 # Торговое приложение
│   ├── models.py           # Модели БД
│   ├── strategy.py         # Торговая стратегия
│   ├── exchange_client.py  # Клиент Bybit
│   ├── risk_manager.py     # Управление рисками
│   ├── encryption.py       # Шифрование API ключей
│   ├── tasks.py            # Celery задачи
│   └── admin.py            # Админка
├── bot/                     # Telegram бот
│   ├── models.py           # Модели бота
│   ├── handlers.py         # Обработчики команд
│   ├── handlers_api.py     # Обработчики API ключей
│   ├── keyboards.py        # Клавиатуры
│   ├── notifications.py    # Уведомления
│   ├── states.py           # FSM состояния
│   ├── bot_main.py         # Главный файл бота
│   └── admin.py            # Админка
├── requirements.txt         # Зависимости
├── .env.example            # Пример переменных окружения
├── .gitignore
└── README.md
```

## ⚠️ Важные замечания

### Безопасность

1. **API ключи шифруются** с помощью Fernet перед сохранением в БД
2. **Храните ENCRYPTION_KEY в безопасности** - без него невозможно расшифровать ключи
3. **Не коммитьте .env файл** в git
4. **Используйте IP whitelist** на Bybit для mainnet ключей

### Риски

⚠️ **ВАЖНО**: Торговля криптовалютными фьючерсами сопряжена с высоким риском потери средств.

- Начните с **testnet** для тестирования
- Используйте **риск 1-2%** на сделку
- Не используйте средства, которые не можете позволить себе потерять
- Бот **НЕ гарантирует** прибыль
- Следите за балансом и статистикой

### Ограничения

- Поддерживается только биржа **Bybit**
- Только **фьючерсы USDT**
- Одна стратегия (не изменяемая пользователем)
- Рекомендуемый таймфрейм: **5m** (можно изменить в админке)

## 🐛 Решение проблем

### Бот не отвечает

1. Проверьте, что бот запущен: `ps aux | grep bot_main`
2. Проверьте логи: `tail -f bot.log`
3. Проверьте Redis: `redis-cli ping`

### Сделки не открываются

1. Проверьте, что торговля запущена (▶️ Старт в боте)
2. Проверьте Celery Worker: `celery -A config inspect active`
3. Проверьте логи Celery: `tail -f celery_worker.log`
4. Проверьте API ключи: нажмите `🔍 Проверить подключение` в боте

### Ошибки подключения к Bybit

1. Проверьте API ключи (правильность ввода)
2. Проверьте права API ключей (Trading, Position)
3. Проверьте сеть (testnet/mainnet)
4. Проверьте IP whitelist (для mainnet)

### Ошибки БД

```bash
# Пересоздание миграций
python manage.py migrate --fake trading zero
python manage.py migrate trading

# Сброс БД (ОСТОРОЖНО - удалит все данные!)
python manage.py flush
python manage.py migrate
```

## 📞 Поддержка

Если возникли вопросы или проблемы:

1. Проверьте раздел "Решение проблем" выше
2. Проверьте логи (`bot.log`, `celery_worker.log`, `celery_beat.log`)
3. Откройте Issue в репозитории GitHub

## 📝 Лицензия

MIT License

## 🙏 Благодарности

- [Django](https://www.djangoproject.com/)
- [aiogram](https://github.com/aiogram/aiogram)
- [ccxt](https://github.com/ccxt/ccxt)
- [Celery](https://docs.celeryproject.org/)
- [Bybit](https://www.bybit.com/)

---

**Disclaimer**: Используйте бота на свой страх и риск. Автор не несет ответственности за любые финансовые потери.
