"""
Основные обработчики команд и сообщений Telegram бота.
"""

from aiogram import Router, F
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal, InvalidOperation
import asyncio

from .models import BotUser
from .keyboards import (
    get_main_keyboard, get_settings_keyboard, get_api_keys_keyboard,
    get_trading_pairs_keyboard, get_open_positions_keyboard,
    get_confirm_keyboard, get_testnet_keyboard, get_cancel_keyboard,
    get_popular_pairs_keyboard
)
from .states import APIKeysStates, SettingsStates, TradingPairStates
from trading_strategy.models import (
    UserTradingSettings, Exchange, TradingPair, Trade, TradingStatistics
)
from trading_strategy.encryption import encrypt_api_credentials
from trading_strategy.exchange_client import test_connection
from trading_strategy.tasks import close_position_manually

router = Router()


# ==== КОМАНДА /start ====
@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Обработка команды /start.
    Регистрация нового пользователя или приветствие существующего.
    """
    telegram_id = message.from_user.id
    
    # Проверяем, существует ли пользователь
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=telegram_id).first
    )
    
    if not bot_user:
        # Создаем нового пользователя
        username = f"user_{telegram_id}"
        
        django_user = await asyncio.to_thread(
            User.objects.create,
            username=username
        )
        
        bot_user = await asyncio.to_thread(
            BotUser.objects.create,
            telegram_id=telegram_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
            django_user=django_user
        )
        
        # Создаем настройки торговли по умолчанию
        await asyncio.to_thread(
            UserTradingSettings.objects.create,
            user=django_user
        )
        
        # Создаем статистику
        await asyncio.to_thread(
            TradingStatistics.objects.create,
            user=django_user
        )
        
        welcome_text = f"""
👋 Добро пожаловать, {bot_user.full_name}!

🤖 Я торговый бот для автоматической торговли фьючерсами на Bybit.

📚 <b>Что я умею:</b>
• Автоматический анализ рынка по вашей стратегии
• Открытие и закрытие позиций по сигналам
• Управление рисками и размером позиций
• Отправка уведомлений о сделках

🎯 <b>Стратегия:</b>
Ловлю отскоки от границ ценового канала в направлении тренда с подтверждением 4-мя индикаторами (EMA, RSI, Williams %R, объем).

📈 <b>Давайте начнем! Выберите торговые пары для мониторинга:</b>

Выберите популярные пары или добавьте свою.
"""
        
        # Предлагаем выбрать популярные пары
        await message.answer(welcome_text, reply_markup=get_popular_pairs_keyboard(), parse_mode="HTML")
    else:
        welcome_text = f"""
👋 С возвращением, {bot_user.full_name}!

Используйте меню ниже для управления ботом.
"""
        
        await message.answer(welcome_text, reply_markup=get_main_keyboard(), parse_mode="HTML")


# ==== КОМАНДА /help ====
@router.message(Command("help"))
@router.message(F.text == "ℹ️ Помощь")
async def cmd_help(message: Message):
    """
    Помощь и инструкции.
    """
    help_text = """
📖 <b>РУКОВОДСТВО ПО ИСПОЛЬЗОВАНИЮ</b>

<b>1. Настройка API ключей</b>
• Перейдите в 🔑 API Ключи
• Создайте API ключи на bybit.com
• Для testnet: testnet.bybit.com
• Права: Trading (Read/Write), Position (Read/Write)
• Добавьте ключи в бота

<b>2. Настройка параметров</b>
• ⚙️ Настройки → выберите параметр
• 💰 Размер ордера: фиксированный размер позиции в $
• 🎚 Плечо: множитель (1-100x)

<b>3. Торговые пары</b>
• 📈 Торговые пары → ➕ Добавить
• Формат: BTCUSDT, ETHUSDT и т.д.
• Можно добавить несколько пар

<b>4. Запуск бота</b>
• Нажмите ▶️ Старт
• Бот начнет мониторинг каждую минуту
• Уведомления о сделках придут сюда

<b>5. Мониторинг</b>
• 📊 Статистика: общая статистика торговли
• 📝 Открытые позиции: текущие сделки
• 📜 История: все закрытые сделки

⚠️ <b>ВАЖНО:</b>
• Начните с testnet для тестирования
• Начните с фиксированного ордера $1-$5 и плеча 1x-3x
• Бот НЕ гарантирует прибыль
• Следите за балансом и статистикой

💡 Вопросы? Пишите в поддержку.
"""
    
    await message.answer(help_text, parse_mode="HTML")


# ==== СТАТИСТИКА ====
@router.message(F.text == "📊 Статистика")
async def show_statistics(message: Message):
    """
    Показ статистики торговли пользователя.
    """
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        return
    
    stats = await asyncio.to_thread(
        TradingStatistics.objects.filter(user=bot_user.django_user).first
    )
    
    if not stats:
        await message.answer("📊 Статистика пока отсутствует. Совершите первую сделку!")
        return
    
    stats_text = f"""
📊 <b>СТАТИСТИКА ТОРГОВЛИ</b>

📈 Всего сделок: <b>{stats.total_trades}</b>
✅ Прибыльных: <b>{stats.winning_trades}</b>
❌ Убыточных: <b>{stats.losing_trades}</b>

{'💰' if stats.total_pnl >= 0 else '❌'} Общий PnL: <b>${stats.total_pnl}</b>

📊 Винрейт: <b>{stats.win_rate}%</b>

📈 Средняя прибыль: <code>${stats.average_win}</code>
📉 Средний убыток: <code>${stats.average_loss}</code>

🔝 Максимальная прибыль: <code>${stats.max_win}</code>
🔻 Максимальный убыток: <code>${stats.max_loss}</code>

⚠️ Макс. просадка: <code>${stats.max_drawdown}</code>

📅 Обновлено: <code>{stats.updated_at.strftime('%Y-%m-%d %H:%M')}</code>
"""
    
    await message.answer(stats_text, parse_mode="HTML")


# ==== НАСТРОЙКИ ====
@router.message(F.text == "⚙️ Настройки")
async def show_settings(message: Message):
    """
    Показ текущих настроек торговли.
    """
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        return
    
    settings = await asyncio.to_thread(
        lambda: bot_user.django_user.trading_settings
    )

    order_size_text = f"${settings.base_order_size}"

    settings_text = f"""
⚙️ <b>НАСТРОЙКИ ТОРГОВЛИ</b>

💰 Размер ордера: <code>{order_size_text}</code>
🎚 Плечо: <code>{settings.leverage}x</code>
🛑 Дневной лимит: <code>{settings.daily_loss_limit_percent}%</code>
📉 Убыточных подряд (стоп): <code>{settings.max_consecutive_losses}</code>
🧯 Автопауза: <code>{'вкл' if settings.auto_pause_on_risk else 'выкл'}</code>
🚦 Риск-пауза: <code>{'активна' if settings.is_risk_paused else 'нет'}</code>

📊 Таймфрейм: <code>{settings.timeframe}</code>
📈 EMA: <code>{settings.ema_fast_period}/{settings.ema_slow_period}</code>
📊 RSI период: <code>{settings.rsi_period}</code>
📉 Williams %R: <code>{settings.williams_r_period}</code>

🔴 Стоп-лосс: <code>{settings.stop_loss_percent}% от цены входа</code>
🟢 Тейк-профит: <code>{settings.take_profit_percent}% от цены входа</code>

Выберите параметр для изменения:
"""
    
    await message.answer(settings_text, reply_markup=get_settings_keyboard(), parse_mode="HTML")


# ==== CALLBACK: Изменение размера ордера ====
@router.callback_query(F.data == "settings_order_size")
async def settings_order_size_callback(callback: CallbackQuery, state: FSMContext):
    """Начало изменения размера ордера"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )

    if not bot_user:
        await callback.message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        await callback.answer()
        return

    settings = await asyncio.to_thread(lambda: bot_user.django_user.trading_settings)
    current_order_size_text = f"${settings.base_order_size}"

    await callback.message.answer(
        "💰 Изменение размера ордера\n\n"
        f"Текущее значение: <code>{current_order_size_text}</code>\n"
        "Режим: <code>фиксированный USD</code>\n\n"
        "Введите новый размер ордера в USD (минимум $1).\n\n"
        "Пример: <code>10</code>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_order_size)
    await callback.answer()


@router.message(SettingsStates.waiting_for_order_size)
async def process_order_size(message: Message, state: FSMContext):
    """Обработка нового размера ордера"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    try:
        order_size = Decimal(message.text.strip())
        
        if order_size < Decimal('1.0'):
            await message.answer("❌ Размер ордера должен быть минимум $1. Попробуйте снова:")
            return
        
        bot_user = await asyncio.to_thread(
            BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
        )
        
        settings = await asyncio.to_thread(
            lambda: bot_user.django_user.trading_settings
        )
        settings.order_size_mode = 'fixed_usd'
        settings.base_order_size = order_size
        await asyncio.to_thread(settings.save)
        
        await message.answer(
            f"✅ Размер ордера изменен на ${order_size}",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except (ValueError, InvalidOperation):
        await message.answer("❌ Неверный формат. Введите число (например: 10):")


# ==== CALLBACK: Изменение плеча ====
@router.callback_query(F.data == "settings_leverage")
async def settings_leverage_callback(callback: CallbackQuery, state: FSMContext):
    """Начало изменения плеча"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )

    if not bot_user:
        await callback.message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        await callback.answer()
        return

    settings = await asyncio.to_thread(lambda: bot_user.django_user.trading_settings)

    await callback.message.answer(
        "🎚 Изменение плеча\n\n"
        f"Текущее плечо: <code>{settings.leverage}x</code>\n\n"
        "Введите новое плечо (1-100).\n\n"
        "Пример: <code>10</code>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_leverage)
    await callback.answer()


@router.message(SettingsStates.waiting_for_leverage)
async def process_leverage(message: Message, state: FSMContext):
    """Обработка нового плеча"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    try:
        leverage = int(message.text.strip())
        
        if not (1 <= leverage <= 100):
            await message.answer("❌ Плечо должно быть от 1 до 100. Попробуйте снова:")
            return
        
        bot_user = await asyncio.to_thread(
            BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
        )
        
        settings = await asyncio.to_thread(
            lambda: bot_user.django_user.trading_settings
        )
        settings.leverage = leverage
        await asyncio.to_thread(settings.save)
        
        await message.answer(
            f"✅ Плечо изменено на {leverage}x",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число от 1 до 100:")


# ==== CALLBACK: Изменение дневного лимита ====
@router.callback_query(F.data == "settings_daily_limit")
async def settings_daily_limit_callback(callback: CallbackQuery, state: FSMContext):
    """Начало изменения дневного лимита убытка"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )

    if not bot_user:
        await callback.message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        await callback.answer()
        return

    settings = await asyncio.to_thread(lambda: bot_user.django_user.trading_settings)

    await callback.message.answer(
        "🛑 Изменение дневного лимита убытка\n\n"
        f"Текущее значение: <code>{settings.daily_loss_limit_percent}%</code>\n\n"
        "Введите новый дневной лимит в % (0.1-100).\n\n"
        "Рекомендуется: <code>1-3%</code>\n"
        "Пример: <code>2</code>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_daily_limit)
    await callback.answer()


@router.message(SettingsStates.waiting_for_daily_limit)
async def process_daily_limit(message: Message, state: FSMContext):
    """Обработка нового дневного лимита"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return

    try:
        daily_limit = Decimal(message.text.strip())

        if not (Decimal('0.1') <= daily_limit <= Decimal('100')):
            await message.answer("❌ Лимит должен быть от 0.1% до 100%. Попробуйте снова:")
            return

        bot_user = await asyncio.to_thread(
            BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
        )

        settings = await asyncio.to_thread(
            lambda: bot_user.django_user.trading_settings
        )
        settings.daily_loss_limit_percent = daily_limit
        await asyncio.to_thread(settings.save)

        await message.answer(
            f"✅ Дневной лимит изменен на {daily_limit}%",
            reply_markup=get_main_keyboard()
        )
        await state.clear()

    except (ValueError, InvalidOperation):
        await message.answer("❌ Неверный формат. Введите число (например: 2):")


# ==== CALLBACK: Изменение лимита убыточных подряд ====
@router.callback_query(F.data == "settings_max_losses")
async def settings_max_losses_callback(callback: CallbackQuery, state: FSMContext):
    """Начало изменения лимита убыточных подряд"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )

    if not bot_user:
        await callback.message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        await callback.answer()
        return

    settings = await asyncio.to_thread(lambda: bot_user.django_user.trading_settings)

    await callback.message.answer(
        "📉 Изменение лимита убыточных подряд\n\n"
        f"Текущее значение: <code>{settings.max_consecutive_losses}</code>\n\n"
        "Введите новое число убыточных подряд (1-20).\n\n"
        "Рекомендуется: <code>2-4</code>\n"
        "Пример: <code>3</code>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_max_losses)
    await callback.answer()


@router.message(SettingsStates.waiting_for_max_losses)
async def process_max_losses(message: Message, state: FSMContext):
    """Обработка нового лимита убыточных подряд"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return

    try:
        max_losses = int(message.text.strip())

        if not (1 <= max_losses <= 20):
            await message.answer("❌ Значение должно быть от 1 до 20. Попробуйте снова:")
            return

        bot_user = await asyncio.to_thread(
            BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
        )

        settings = await asyncio.to_thread(
            lambda: bot_user.django_user.trading_settings
        )
        settings.max_consecutive_losses = max_losses
        await asyncio.to_thread(settings.save)

        await message.answer(
            f"✅ Лимит убыточных подряд изменен на {max_losses}",
            reply_markup=get_main_keyboard()
        )
        await state.clear()

    except ValueError:
        await message.answer("❌ Неверный формат. Введите целое число от 1 до 20:")


# ==== CALLBACK: Переключение автопаузы ====
@router.callback_query(F.data == "settings_auto_pause")
async def settings_auto_pause_callback(callback: CallbackQuery):
    """Переключение автопаузы по рискам"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )

    if not bot_user:
        await callback.message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        await callback.answer()
        return

    settings = await asyncio.to_thread(lambda: bot_user.django_user.trading_settings)
    settings.auto_pause_on_risk = not settings.auto_pause_on_risk
    await asyncio.to_thread(settings.save)

    status_text = "включена" if settings.auto_pause_on_risk else "выключена"
    await callback.message.answer(
        f"✅ Автопауза по рискам {status_text}.",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


# ==== CALLBACK: Переключение риск-паузы ====
@router.callback_query(F.data == "settings_risk_pause_toggle")
async def settings_risk_pause_toggle_callback(callback: CallbackQuery):
    """Ручное переключение риск-паузы"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )

    if not bot_user:
        await callback.message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        await callback.answer()
        return

    settings = await asyncio.to_thread(lambda: bot_user.django_user.trading_settings)

    if settings.is_risk_paused:
        settings.is_risk_paused = False
        settings.risk_pause_reason = ''
        settings.risk_paused_at = None
        await asyncio.to_thread(settings.save)
        await callback.message.answer(
            "✅ Риск-пауза снята.\n"
            "Чтобы продолжить торговлю, нажмите ▶️ Старт.",
            reply_markup=get_main_keyboard()
        )
    else:
        settings.is_risk_paused = True
        settings.is_trading_active = False
        settings.risk_pause_reason = 'Установлено вручную пользователем'
        settings.risk_paused_at = timezone.now()
        await asyncio.to_thread(settings.save)
        await callback.message.answer(
            "⏸ Риск-пауза включена вручную.\n"
            "Торговля остановлена до снятия паузы.",
            reply_markup=get_main_keyboard()
        )

    await callback.answer()


# ==== CALLBACK: Изменение риска ====
@router.callback_query(F.data == "settings_risk")
async def settings_risk_callback(callback: CallbackQuery, state: FSMContext):
    """Начало изменения риска"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )

    if not bot_user:
        await callback.message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        await callback.answer()
        return

    settings = await asyncio.to_thread(lambda: bot_user.django_user.trading_settings)

    await callback.message.answer(
        "⚠️ Изменение риска на сделку\n\n"
        f"Текущее значение: <code>{settings.risk_per_trade}%</code>\n\n"
        "Введите новый риск на сделку в % (0.1-100).\n\n"
        "Рекомендуется: 1-2%\n"
        "Пример: <code>1.5</code>",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(SettingsStates.waiting_for_risk)
    await callback.answer()


@router.message(SettingsStates.waiting_for_risk)
async def process_risk(message: Message, state: FSMContext):
    """Обработка нового риска"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    try:
        risk = Decimal(message.text.strip())
        
        if not (Decimal('0.1') <= risk <= Decimal('100')):
            await message.answer("❌ Риск должен быть от 0.1% до 100%. Попробуйте снова:")
            return
        
        bot_user = await asyncio.to_thread(
            BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
        )
        
        settings = await asyncio.to_thread(
            lambda: bot_user.django_user.trading_settings
        )
        settings.risk_per_trade = risk
        await asyncio.to_thread(settings.save)
        
        await message.answer(
            f"✅ Риск на сделку изменен на {risk}%",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except (ValueError, InvalidOperation):
        await message.answer("❌ Неверный формат. Введите число (например: 1.5):")


# ==== ТОРГОВЫЕ ПАРЫ ====
@router.message(F.text == "📈 Торговые пары")
async def show_trading_pairs(message: Message):
    """
    Показ списка торговых пар пользователя.
    """
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        return
    
    pairs = await asyncio.to_thread(
        lambda: list(TradingPair.objects.filter(user=bot_user.django_user).order_by('symbol'))
    )
    
    if not pairs:
        pairs_text = """
📈 <b>ТОРГОВЫЕ ПАРЫ</b>

❌ У вас пока нет добавленных торговых пар.

Нажмите "➕ Добавить пару" чтобы добавить первую пару.

📝 <b>Формат:</b> BTCUSDT, ETHUSDT, SOLUSDT и т.д.
"""
        await message.answer(pairs_text, reply_markup=get_trading_pairs_keyboard([]), parse_mode="HTML")
        return
    
    pairs_text = """
📈 <b>ТОРГОВЫЕ ПАРЫ</b>

Список ваших торговых пар:
"""
    for pair in pairs:
        status_emoji = "✅" if pair.is_active else "❌"
        pairs_text += f"\n{status_emoji} <code>{pair.symbol}</code>"
    
    pairs_text += "\n\nВыберите действие:"
    
    await message.answer(pairs_text, reply_markup=get_trading_pairs_keyboard(pairs), parse_mode="HTML")


# ==== CALLBACK: Быстрое добавление популярной пары ====
@router.callback_query(F.data.startswith("quick_add_pair_"))
async def quick_add_pair_callback(callback: CallbackQuery):
    """Быстрое добавление популярной торговой пары"""
    symbol = callback.data.replace("quick_add_pair_", "").upper()
    
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await callback.answer("❌ Ошибка: пользователь не найден", show_alert=True)
        return
    
    # Проверяем, не добавлена ли уже эта пара
    existing_pair = await asyncio.to_thread(
        TradingPair.objects.filter(user=bot_user.django_user, symbol=symbol).first
    )
    
    if existing_pair:
        existing_pair.is_active = True
        await asyncio.to_thread(existing_pair.save)
        await callback.answer(f"✅ {symbol} уже была добавлена и теперь активирована!")
    else:
        # Создаем новую пару
        await asyncio.to_thread(
            TradingPair.objects.create,
            user=bot_user.django_user,
            symbol=symbol,
            is_active=True
        )
        await callback.answer(f"✅ {symbol} успешно добавлена!")
    
    # Проверяем, сколько пар уже добавлено
    pairs_count = await asyncio.to_thread(
        lambda: TradingPair.objects.filter(user=bot_user.django_user, is_active=True).count()
    )
    
    if pairs_count == 1:
        # Первая пара - предлагаем добавить еще или начать
        try:
            await callback.message.edit_text(
                f"✅ Торговая пара <code>{symbol}</code> добавлена!\n\n"
                f"📈 Вы можете добавить еще пары или начать мониторинг.\n\n"
                f"💡 После добавления пар нажмите <b>▶️ Старт</b> для начала торговли.",
                reply_markup=get_popular_pairs_keyboard(),
                parse_mode="HTML"
            )
        except TelegramBadRequest as e:
            if "message is not modified" in str(e):
                # Игнорируем ошибку, так как контент не изменился
                pass
            else:
                # Пробрасываем другие ошибки
                raise
    else:
        # Уже есть пары - показываем обновленный список
        pairs_text = f"✅ <code>{symbol}</code> добавлена!\n\n📈 <b>Ваши торговые пары:</b>\n"
        all_pairs = await asyncio.to_thread(
            lambda: list(TradingPair.objects.filter(user=bot_user.django_user, is_active=True).order_by('symbol'))
        )
        for p in all_pairs:
            pairs_text += f"\n✅ <code>{p.symbol}</code>"
        
        pairs_text += f"\n\nВсего активных пар: <b>{pairs_count}</b>\n\n"
        pairs_text += "💡 Готовы начать? Нажмите <b>▶️ Старт</b> в главном меню!"
        
        await callback.message.edit_text(
            pairs_text,
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )


# ==== CALLBACK: Пропустить настройку пар ====
@router.callback_query(F.data == "skip_pairs_setup")
async def skip_pairs_setup_callback(callback: CallbackQuery):
    """Пропуск начальной настройки торговых пар"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    pairs_count = await asyncio.to_thread(
        lambda: TradingPair.objects.filter(user=bot_user.django_user, is_active=True).count()
    )
    
    if pairs_count == 0:
        message_text = """
📈 Вы можете добавить торговые пары позже через меню <b>📈 Торговые пары</b>.

⚙️ <b>Для начала работы:</b>
1. Добавьте торговые пары (📈 Торговые пары)
2. (Опционально) Добавьте API ключи для реальной торговли (🔑 API Ключи)
3. Настройте параметры (⚙️ Настройки)
4. Запустите бота (▶️ Старт)

💡 Используйте кнопку "ℹ️ Помощь" для подробной инструкции.
"""
    else:
        message_text = f"""
✅ У вас уже добавлено <b>{pairs_count}</b> торговых пар.

⚙️ <b>Для начала работы:</b>
1. (Опционально) Добавьте API ключи для реальной торговли (🔑 API Ключи)
2. Настройте параметры (⚙️ Настройки)
3. Запустите бота (▶️ Старт)

💡 Используйте кнопку "ℹ️ Помощь" для подробной инструкции.
"""
    
    await callback.message.edit_text(message_text, reply_markup=get_main_keyboard(), parse_mode="HTML")
    await callback.answer()


# ==== CALLBACK: Добавить торговую пару ====
@router.callback_query(F.data == "pair_add")
async def pair_add_callback(callback: CallbackQuery, state: FSMContext):
    """Начало добавления торговой пары"""
    await callback.message.answer(
        "📈 Введите символ торговой пары:\n\n"
        "📝 <b>Формат:</b> BTCUSDT, ETHUSDT, SOLUSDT и т.д.\n\n"
        "⚠️ Без символа / (BTC/USDT не нужно, только BTCUSDT)",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    await state.set_state(TradingPairStates.waiting_for_symbol)
    await callback.answer()


# ==== Обработка ввода символа ====
@router.message(TradingPairStates.waiting_for_symbol)
async def process_trading_pair(message: Message, state: FSMContext):
    """Обработка добавления торговой пары"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    symbol = message.text.strip().upper()
    
    # Валидация формата
    if not symbol.endswith('USDT'):
        await message.answer(
            "❌ Неверный формат. Символ должен заканчиваться на USDT.\n"
            "Пример: BTCUSDT, ETHUSDT\n\nПопробуйте снова:"
        )
        return
    
    if len(symbol) < 7 or len(symbol) > 20:
        await message.answer(
            "❌ Неверный формат символа.\n"
            "Правильный формат: BTCUSDT, ETHUSDT и т.д.\n\nПопробуйте снова:"
        )
        return
    
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    # Проверяем, не добавлена ли уже эта пара
    existing_pair = await asyncio.to_thread(
        TradingPair.objects.filter(user=bot_user.django_user, symbol=symbol).first
    )
    
    if existing_pair:
        existing_pair.is_active = True
        await asyncio.to_thread(existing_pair.save)
        await message.answer(
            f"✅ Торговая пара <code>{symbol}</code> уже была добавлена и теперь активирована!",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        # Создаем новую пару
        await asyncio.to_thread(
            TradingPair.objects.create,
            user=bot_user.django_user,
            symbol=symbol,
            is_active=True
        )
        await message.answer(
            f"✅ Торговая пара <code>{symbol}</code> успешно добавлена!",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    
    await state.clear()


# ==== CALLBACK: Переключение статуса пары ====
@router.callback_query(F.data.startswith("pair_toggle_"))
async def pair_toggle_callback(callback: CallbackQuery):
    """Переключение активности торговой пары"""
    pair_id = int(callback.data.split("_")[-1])
    
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )
    
    pair = await asyncio.to_thread(
        TradingPair.objects.filter(id=pair_id, user=bot_user.django_user).first
    )
    
    if not pair:
        await callback.answer("❌ Торговая пара не найдена", show_alert=True)
        return
    
    pair.is_active = not pair.is_active
    await asyncio.to_thread(pair.save)
    
    status = "активирована" if pair.is_active else "деактивирована"
    await callback.answer(f"✅ Пара {pair.symbol} {status}")
    
    # Обновляем список пар
    pairs = await asyncio.to_thread(
        lambda: list(TradingPair.objects.filter(user=bot_user.django_user).order_by('symbol'))
    )
    
    pairs_text = """
📈 <b>ТОРГОВЫЕ ПАРЫ</b>

Список ваших торговых пар:
"""
    for p in pairs:
        status_emoji = "✅" if p.is_active else "❌"
        pairs_text += f"\n{status_emoji} <code>{p.symbol}</code>"
    
    pairs_text += "\n\nВыберите действие:"
    
    await callback.message.edit_text(pairs_text, reply_markup=get_trading_pairs_keyboard(pairs), parse_mode="HTML")


# ==== СТАРТ ТОРГОВЛИ ====
@router.message(F.text == "▶️ Старт")
async def start_trading(message: Message):
    """
    Запуск автоматической торговли.
    """
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        return
    
    settings = await asyncio.to_thread(
        lambda: bot_user.django_user.trading_settings
    )
    
    # Проверяем наличие торговых пар
    pairs_count = await asyncio.to_thread(
        lambda: TradingPair.objects.filter(user=bot_user.django_user, is_active=True).count()
    )
    
    if pairs_count == 0:
        await message.answer(
            "❌ Нет активных торговых пар!\n\n"
            "Добавьте торговые пары через меню 📈 Торговые пары",
            reply_markup=get_main_keyboard()
        )
        return
    
    # Проверяем наличие API ключей (опционально для тестового режима)
    exchange = await asyncio.to_thread(
        Exchange.objects.filter(user=bot_user.django_user, is_active=True).first
    )
    
    if not exchange:
        # Включаем тестовый режим
        settings.is_trading_active = True
        settings.is_test_mode = True  # Добавим это поле позже
        settings.is_risk_paused = False
        settings.risk_pause_reason = ''
        settings.risk_paused_at = None
        await asyncio.to_thread(settings.save)
        
        await message.answer(
            "✅ <b>Торговля запущена в тестовом режиме!</b>\n\n"
            "🧪 <b>Тестовый режим</b>:\n"
            "• Мониторинг рынка активен\n"
            "• Сигналы будут отправляться как уведомления\n"
            "• Реальные сделки НЕ будут открываться\n\n"
            f"📈 Отслеживается пар: <b>{pairs_count}</b>\n"
            "⏰ Мониторинг каждую минуту\n\n"
            "💡 Добавьте API ключи для реальной торговли.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
    else:
        # Реальный режим с API ключами
        settings.is_trading_active = True
        settings.is_test_mode = False
        settings.is_risk_paused = False
        settings.risk_pause_reason = ''
        settings.risk_paused_at = None
        await asyncio.to_thread(settings.save)
        
        await message.answer(
            "✅ <b>Торговля запущена!</b>\n\n"
            "💰 <b>Реальный режим</b>:\n"
            "• Мониторинг рынка активен\n"
            "• Автоматическое открытие позиций\n"
            "• Уведомления о всех сделках\n\n"
            f"📈 Отслеживается пар: <b>{pairs_count}</b>\n"
            "⏰ Мониторинг каждую минуту",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )


# ==== СТОП ТОРГОВЛИ ====
@router.message(F.text == "⏸ Стоп")
async def stop_trading(message: Message):
    """
    Остановка автоматической торговли.
    """
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        return
    
    settings = await asyncio.to_thread(
        lambda: bot_user.django_user.trading_settings
    )
    
    settings.is_trading_active = False
    await asyncio.to_thread(settings.save)
    
    await message.answer(
        "⏸ <b>Торговля остановлена</b>\n\n"
        "🔒 Автоматический мониторинг прекращен.\n"
        "📝 Открытые позиции продолжат отслеживаться.",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )


# ==== ОТКРЫТЫЕ ПОЗИЦИИ ====
@router.message(F.text == "📝 Открытые позиции")
async def show_open_positions(message: Message):
    """
    Показ открытых позиций пользователя.
    """
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        return
    
    open_trades = await asyncio.to_thread(
        lambda: list(Trade.objects.filter(user=bot_user.django_user, status='open').order_by('-opened_at'))
    )
    
    if not open_trades:
        await message.answer(
            "📝 <b>ОТКРЫТЫЕ ПОЗИЦИИ</b>\n\n"
            "У вас нет открытых позиций.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    positions_text = "📝 <b>ОТКРЫТЫЕ ПОЗИЦИИ</b>\n\n"
    
    for trade in open_trades:
        emoji = "🟢" if trade.side == 'long' else "🔴"
        positions_text += f"""
{emoji} <b>{trade.symbol}</b> {trade.side.upper()}
💰 Вход: <code>${trade.entry_price}</code>
📦 Количество: <code>{trade.quantity}</code>
🎚 Плечо: <code>{trade.leverage}x</code>
🛑 SL: <code>${trade.stop_loss}</code>
🎯 TP: <code>${trade.take_profit}</code>
⏰ Открыта: <code>{trade.opened_at.strftime('%Y-%m-%d %H:%M')}</code>
---
"""
    
    await message.answer(positions_text, reply_markup=get_open_positions_keyboard(open_trades), parse_mode="HTML")


# ==== CALLBACK: Обновить позиции ====
@router.callback_query(F.data == "refresh_positions")
async def refresh_positions_callback(callback: CallbackQuery):
    """Обновление списка открытых позиций"""
    # Просто перезапускаем функцию показа позиций
    await show_open_positions(callback.message)
    await callback.answer("🔄 Позиции обновлены")


# ==== CALLBACK: Закрыть позицию ====
@router.callback_query(F.data.startswith("close_trade_"))
async def close_trade_callback(callback: CallbackQuery):
    """Закрытие позиции вручную"""
    trade_id = int(callback.data.split("_")[-1])
    
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )
    
    trade = await asyncio.to_thread(
        Trade.objects.filter(id=trade_id, user=bot_user.django_user, status='open').first
    )
    
    if not trade:
        await callback.answer("❌ Позиция не найдена или уже закрыта", show_alert=True)
        return
    
    await callback.answer("🔄 Закрываю позицию...")
    
    # Закрываем через задачу Celery
    close_position_manually.delay(trade_id)
    
    await callback.message.answer(
        f"✅ Команда на закрытие позиции <code>{trade.symbol}</code> отправлена.\n"
        f"Позиция будет закрыта в ближайшее время.",
        parse_mode="HTML"
    )


# ==== ИСТОРИЯ СДЕЛОК ====
@router.message(F.text == "📜 История")
async def show_trade_history(message: Message):
    """
    Показ истории закрытых сделок.
    """
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        return
    
    closed_trades = await asyncio.to_thread(
        lambda: list(Trade.objects.filter(user=bot_user.django_user, status='closed').order_by('-closed_at')[:20])
    )
    
    if not closed_trades:
        await message.answer(
            "📜 <b>ИСТОРИЯ СДЕЛОК</b>\n\n"
            "История сделок пуста.",
            reply_markup=get_main_keyboard(),
            parse_mode="HTML"
        )
        return
    
    history_text = "📜 <b>ИСТОРИЯ СДЕЛОК</b> (последние 20)\n\n"
    
    for trade in closed_trades:
        emoji = "💰" if trade.pnl and trade.pnl > 0 else "❌"
        pnl_text = f"{emoji} <b>${trade.pnl} ({trade.pnl_percent}%)</b>" if trade.pnl else "—"
        
        history_text += f"""
<b>{trade.symbol}</b> {trade.side.upper()}
💰 Вход/Выход: <code>${trade.entry_price}</code> → <code>${trade.exit_price}</code>
{pnl_text}
⏰ {trade.opened_at.strftime('%Y-%m-%d %H:%M')} - {trade.closed_at.strftime('%H:%M')}
---
"""
    
    await message.answer(history_text, reply_markup=get_main_keyboard(), parse_mode="HTML")


# ==== CALLBACK: Назад в главное меню ====
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text("Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()
