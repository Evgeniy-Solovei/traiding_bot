# 🤖 Торговый Бот для Bybit

Автоматический торговый бот для фьючерсов на Bybit с управлением через Telegram.

## 📋 Функционал

### Основные возможности

- ✅ **Автоматический анализ рынка** каждую минуту
- ✅ **Уведомления о текущем состоянии рынка** с полным анализом индикаторов
- ✅ **Открытие/закрытие позиций** по сигналам стратегии
- ✅ **Управление рисками** (размер позиции, SL/TP)
- ✅ **Поддержка нескольких торговых пар** одновременно
- ✅ **Тестовый режим** без API ключей (только анализ и уведомления)
- ✅ **Реальный режим** с автоматической торговлей
- ✅ **Статистика сигналов** (успешные/неуспешные)
- ✅ **История всех сделок**
- ✅ **Шифрование API ключей** (Fernet)
- ✅ **Веб-кабинет** для ввода API ключей и торговых настроек

### Стратегия

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
- Режим размера ордера: фиксированный `$` или `% от свободного USDT`

## 🛠 Технологии

- **Backend**: Django 5.2 (async), Python 3.12
- **Telegram Bot**: aiogram 3.x
- **Database**: PostgreSQL
- **Cache/Queue**: Redis
- **Task Queue**: Celery + Celery Beat
- **Exchange API**: ccxt (Bybit)
- **Indicators**: pandas, numpy, ta

## 📦 Установка

### 1. Предварительные требования

**macOS:**
```bash
brew install postgresql@14 redis
brew services start postgresql@14
brew services start redis
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install postgresql redis-server -y
sudo systemctl start postgresql
sudo systemctl start redis
```

### 2. Клонирование и настройка

```bash
cd /path/to/project
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. База данных

```bash
# Создание БД
createdb trading_bot
psql trading_bot -c "CREATE USER user WITH PASSWORD 'password';"
psql trading_bot -c "GRANT ALL PRIVILEGES ON DATABASE trading_bot TO user;"
psql trading_bot -c "GRANT ALL ON SCHEMA public TO user;"
```

### 4. Создание .env файла

Создайте файл `.env` в корне проекта:

```env
# Django
SECRET_KEY=django-insecure-8*)rs+%vhropla9w%#+w7w0)7*of7$n=pk3s*gf6-w3#wbl3#r
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# PostgreSQL
DB_NAME=trading_bot
DB_USER=user
DB_PASSWORD=password
DB_HOST=localhost
DB_PORT=5432

# Telegram Bot (ОБЯЗАТЕЛЬНО!)
TELEGRAM_BOT_TOKEN=ваш-токен-от-BotFather

# Redis
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Шифрование (ОБЯЗАТЕЛЬНО!)
ENCRYPTION_KEY=сгенерированный-ключ

# Bybit
BYBIT_TESTNET=True
```

**Как получить TELEGRAM_BOT_TOKEN:**
1. Откройте Telegram → [@BotFather](https://t.me/BotFather)
2. Отправьте `/newbot`
3. Следуйте инструкциям
4. Скопируйте токен

**Как сгенерировать ENCRYPTION_KEY:**
```bash
python3 generate_key.py
```

### 5. Миграции

```bash
python manage.py migrate
python manage.py createsuperuser  # опционально
```

## 🚀 Запуск

### Локально (БД установлена на компьютере)

Локально используем PostgreSQL, установленный на машине (не контейнер).

В `.env`:
- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5432`

Быстрый запуск:

```bash
chmod +x start.sh
./start.sh
```

`start.sh` запускает локально:
- `uvicorn`
- `python bot_main.py`
- `celery worker`
- `celery beat`
- `redis` (если не запущен)

Ручной запуск (если без скрипта, в отдельных терминалах):

```bash
redis-server
```

```bash
uvicorn trading_bot.asgi:application --host 0.0.0.0 --port 8000
```

```bash
python bot_main.py
```

```bash
celery -A trading_bot worker -l info
```

```bash
celery -A trading_bot beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

### На Сервере (БД в Docker, PostgreSQL 17)

1. Подготовьте `.env`:

```bash
cp .env.example .env
```

Заполните минимум:
- `SECRET_KEY`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `TELEGRAM_BOT_TOKEN`
- `ENCRYPTION_KEY` (`python3 generate_key.py`)
- `ALLOWED_HOSTS` и `CSRF_TRUSTED_ORIGINS` под ваш домен/IP

2. Поднимите всё:

```bash
docker compose up -d --build
```

Сервисы:
- `app` (миграции + Uvicorn + Telegram bot)
- `postgres` (`postgres:17-alpine`)
- `redis`
- `celery`
- `celery-beat`

3. Создайте администратора кабинета:

```bash
docker compose exec app python manage.py createsuperuser
```

4. Откройте кабинет:
- `http://<server-ip-or-domain>:8000/cabinet/login/`

5. Контроль:

```bash
docker compose ps
docker compose logs -f app postgres redis celery celery-beat
docker compose down
```

## 🧭 Веб-кабинет

Кабинет нужен для управления ключами и рисками на сервере без Telegram-команд.

**Вход:**
- URL: `http://<ваш_сервер>:8000/cabinet/login/`
- Используется Django-пользователь (`python manage.py createsuperuser`)

**В кабинете можно:**
- Сохранить/обновить API Key и API Secret Bybit
- Выбрать сеть: `Testnet` или `Mainnet`
- Настроить фиксированный размер ордера в USD
- Настроить плечо и тестовый/реальный режим
- Настроить риск-стопы:
  - дневной лимит убытка (%)
  - максимум убыточных сделок подряд
  - автопауза торговли при срабатывании лимитов

## 💸 Запуск на маленьких суммах (рекомендация)

Для первого запуска на реальном аккаунте:
1. Начните с `Testnet`, проверьте 30-60 минут.
2. Для `Mainnet` поставьте фиксированный размер `1-5 USD`.
3. Плечо `1x-3x`.
4. Запустите только 1-2 торговые пары, затем расширяйте.

**Тест на 1 час (минимальный риск):**
1. Поставьте `Фиксированный размер = 1.00 USD`.
2. Плечо `1x-3x`.
3. Включите `Testnet`, активируйте торговлю и дайте боту поработать 1 час.
4. Только после этого переключайте сеть на `Mainnet`.

## 📱 Использование бота

### Первый запуск

1. Найдите вашего бота в Telegram
2. Отправьте `/start`
3. Выберите торговые пары (Bitcoin, Ethereum или добавьте свои)
4. Нажмите `▶️ Старт`

### Сообщения о мониторинге

**Каждую минуту** бот отправляет сообщения о текущем состоянии рынка:

```
🔍 МОНИТОРИНГ РЫНКА

💹 Символ: BTCUSDT
💰 Цена: $45000.00

🟢 Тренд: Бычий (В бычьем тренде ищем LONG сигналы)

📊 Индикаторы:
• RSI: 65.5
• Williams %R: -35.2
• EMA9/EMA21: $44900.00 / $44800.00

🟢 LONG условия (2/5):
❌ 📉 Цена у нижней границы канала
❌ 📊 RSI < 30 (перепроданность)
✅ 📊 Williams %R < -80 (перепроданность)
❌ 📈 EMA9 пересекает EMA21
✅ 📊 Объем > среднего на 20%

🔴 SHORT условия (1/5):
❌ 📈 Цена у верхней границы канала
❌ 📊 RSI > 70 (перекупленность)
❌ 📊 Williams %R > -20 (перекупленность)
❌ 📈 EMA9 пересекает EMA21
✅ 📊 Объем > среднего на 20%

📝 Статус: В бычьем тренде ищем LONG. 
Совпало 2 из 5 условий (нужно минимум 3)
```

**Объяснение терминов:**
- **Боковик (нейтральный тренд)** — рынок движется горизонтально, без четкого направления. Бот не торгует в боковике.
- **Канал не валидный** — ценовой канал не сформирован (нужно минимум 2 касания верхней и нижней границы за 20 свечей).
- **Совпало X из 5 условий** — стратегия проверяет 5 условий одновременно; нужно минимум 3 для сигнала (это снижает количество ложных сигналов).

**Как отключить сообщения мониторинга (для продакшена):**

Если сообщения каждую минуту мешают, отредактируйте `trading_strategy/tasks.py`:

```python
# В функции analyze_and_trade найдите строку:
await send_monitoring_update(user, symbol, analysis_details, signal)

# И закомментируйте или удалите её:
# await send_monitoring_update(user, symbol, analysis_details, signal)
```

Сообщения о **сигналах** (когда 3+ условий совпало) и **закрытии позиций** будут приходить в любом случае.

### Основные команды

- **📊 Статистика** - общая статистика торговли
- **⚙️ Настройки** - настройка размера ордера, плеча, риска
- **🔑 API Ключи** - добавление API ключей Bybit (для реальной торговли)
- **📈 Торговые пары** - управление торговыми парами
- **▶️ Старт** - запуск мониторинга
- **⏸ Стоп** - остановка мониторинга
- **📝 Открытые позиции** - текущие открытые сделки
- **📜 История** - история всех сделок

### Тестовый режим

Без API ключей бот работает в **тестовом режиме**:
- ✅ Мониторинг рынка активен
- ✅ Анализ стратегии работает
- ✅ Уведомления о текущем состоянии рынка каждую минуту
- ✅ Уведомления о сигналах
- ❌ Реальные сделки не открываются

**Что вы получаете:**
- Полный анализ рынка (цена, индикаторы, тренд, канал)
- Информацию о каждом найденном сигнале
- Статистику сигналов (сохраняется в БД)
- Возможность анализировать работу стратегии

### Реальный режим

Для реальной торговли:
1. Получите API ключи на [Bybit](https://www.bybit.com) или [Testnet](https://testnet.bybit.com)
2. Права: Trading, Position (Read/Write)
3. В боте: `🔑 API Ключи` → `➕ Добавить ключи`
4. Выберите сеть (Testnet/Mainnet)
5. Введите ключи

После добавления ключей бот автоматически переключится на реальный режим и начнет открывать позиции.

## 📊 Что вы видите в боте

### Каждую минуту вы получаете:

```
📊 АНАЛИЗ РЫНКА

💹 Символ: BTCUSDT
💰 Текущая цена: $45000.00

🟢 Тренд: BULLISH

📈 Индикаторы:
• EMA9/EMA21: $44900.00 / $44800.00
• RSI: 65.5
• Williams %R: -35.2
• ATR: $500.00

📊 Ценовой канал:
• Верх: $46000.00
• Низ: $44000.00
• Позиция: Середина

⚪ Сигнала нет - ждём условий...
```

### При обнаружении сигнала:

```
🟢 СИГНАЛ ОБНАРУЖЕН

📊 Символ: BTCUSDT
📈 Направление: LONG
💰 Цена входа: $44200.00
🎯 Уверенность: 80.0%

🛑 Стоп-лосс: $43700.00
🎯 Тейк-профит: $45450.00

📝 Причина: LONG сигнал: near_lower_bound, rsi_oversold...
```

## 🔧 Структура проекта

```
trading_bot/
├── bot_main.py             # Главный файл запуска Telegram-бота
├── bot/                    # Telegram бот (роутеры, хендлеры, модели)
│   ├── handlers.py        # Обработчики команд
│   ├── handlers_api.py    # Обработчики API ключей
│   ├── keyboards.py       # Клавиатуры
│   ├── notifications.py   # Уведомления
│   └── models.py         # Модели бота
├── trading_strategy/       # Торговое приложение
│   ├── models.py          # Модели БД (Exchange, Trade, SignalHistory)
│   ├── strategy.py        # Торговая стратегия
│   ├── exchange_client.py # Клиент Bybit
│   ├── risk_manager.py    # Управление рисками
│   ├── tasks.py           # Celery задачи (мониторинг)
│   └── encryption.py      # Шифрование API ключей
├── trading_bot/           # Настройки Django
│   ├── settings.py
│   ├── celery.py
│   └── urls.py
├── requirements.txt
├── manage.py
└── .env                   # Переменные окружения (создать вручную)
```

## ⚠️ Важные замечания

### Безопасность

1. **API ключи шифруются** перед сохранением в БД
2. **Храните ENCRYPTION_KEY в безопасности**
3. **Не коммитьте .env** в git
4. **Используйте IP whitelist** на Bybit для mainnet

### Риски

⚠️ **ВАЖНО**: Торговля криптовалютными фьючерсами сопряжена с высоким риском потери средств.

- Начните с **testnet** для тестирования
- Используйте **риск 1-2%** на сделку
- Не используйте средства, которые не можете позволить себе потерять
- Бот **НЕ гарантирует** прибыль
- Следите за балансом и статистикой

## 🐛 Решение проблем

### Бот не отвечает

```bash
# Проверьте логи
tail -f bot.log

# Проверьте токен (без кавычек в .env!)
cat .env | grep TELEGRAM_BOT_TOKEN

# Перезапустите
pkill -f bot_main
python bot_main.py
```

### Redis не работает

```bash
redis-cli ping  # Должно вернуть PONG
redis-server    # Если не запущен
```

### Ошибки БД

```bash
python manage.py migrate
python manage.py showmigrations
```

### Уведомления не приходят

1. Проверьте что торговля запущена (`▶️ Старт`)
2. Проверьте что есть активные торговые пары
3. Проверьте логи: `docker compose logs -f app celery celery-beat redis`
4. Подождите 1-2 минуты (мониторинг каждую минуту)

## 📝 Лицензия

MIT License

---

**Disclaimer**: Используйте бота на свой страх и риск. Автор не несет ответственности за любые финансовые потери.
