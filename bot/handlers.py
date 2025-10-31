"""
Основные обработчики команд и сообщений Telegram бота.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import asyncio

from .models import BotUser
from .keyboards import (
    get_main_keyboard, get_settings_keyboard, get_api_keys_keyboard,
    get_trading_pairs_keyboard, get_open_positions_keyboard,
    get_confirm_keyboard, get_testnet_keyboard, get_cancel_keyboard
)
from .states import APIKeysStates, SettingsStates, TradingPairStates
from trading.models import (
    UserTradingSettings, Exchange, TradingPair, Trade, TradingStatistics
)
from trading.encryption import encrypt_api_credentials
from trading.exchange_client import test_connection
from trading.tasks import close_position_manually

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
            User.objects.create_user,
            username=username,
            password=User.objects.make_random_password()
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

⚙️ <b>Для начала работы:</b>
1. Добавьте API ключи Bybit (🔑 API Ключи)
2. Настройте параметры риска (⚙️ Настройки)
3. Добавьте торговые пары (📈 Торговые пары)
4. Запустите бота (▶️ Старт)

💡 Используйте кнопку "ℹ️ Помощь" для подробной инструкции.
"""
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
• 💰 Размер ордера: базовый размер позиции в $
• 🎚 Плечо: множитель (1-100x)
• ⚠️ Риск: % от депозита на сделку (рекомендую 1-2%)

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
• Используйте риск 1-2% на сделку
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
    
    settings_text = f"""
⚙️ <b>НАСТРОЙКИ ТОРГОВЛИ</b>

💰 Размер ордера: <code>${settings.base_order_size}</code>
🎚 Плечо: <code>{settings.leverage}x</code>
⚠️ Риск на сделку: <code>{settings.risk_per_trade}%</code>

📊 Таймфрейм: <code>{settings.timeframe}</code>
📈 EMA: <code>{settings.ema_fast_period}/{settings.ema_slow_period}</code>
📊 RSI период: <code>{settings.rsi_period}</code>
📉 Williams %R: <code>{settings.williams_r_period}</code>

🔴 Стоп-лосс: <code>{settings.stop_loss_atr_multiplier}x ATR</code>
🟢 Тейк-профит: <code>{settings.take_profit_atr_multiplier}x ATR</code>

Выберите параметр для изменения:
"""
    
    await message.answer(settings_text, reply_markup=get_settings_keyboard(), parse_mode="HTML")


# ==== CALLBACK: Изменение размера ордера ====
@router.callback_query(F.data == "settings_order_size")
async def settings_order_size_callback(callback: CallbackQuery, state: FSMContext):
    """Начало изменения размера ордера"""
    await callback.message.answer(
        "💰 Введите новый размер ордера в USD (минимум $5):\n\nПример: <code>10</code>",
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
        
        if order_size < Decimal('5.0'):
            await message.answer("❌ Размер ордера должен быть минимум $5. Попробуйте снова:")
            return
        
        bot_user = await asyncio.to_thread(
            BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
        )
        
        settings = await asyncio.to_thread(
            lambda: bot_user.django_user.trading_settings
        )
        settings.base_order_size = order_size
        await asyncio.to_thread(settings.save)
        
        await message.answer(
            f"✅ Размер ордера изменен на ${order_size}",
            reply_markup=get_main_keyboard()
        )
        await state.clear()
        
    except (ValueError, Decimal.InvalidOperation):
        await message.answer("❌ Неверный формат. Введите число (например: 10):")


# ==== CALLBACK: Изменение плеча ====
@router.callback_query(F.data == "settings_leverage")
async def settings_leverage_callback(callback: CallbackQuery, state: FSMContext):
    """Начало изменения плеча"""
    await callback.message.answer(
        "🎚 Введите новое плечо (1-100):\n\nПример: <code>10</code>",
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


# ==== CALLBACK: Изменение риска ====
@router.callback_query(F.data == "settings_risk")
async def settings_risk_callback(callback: CallbackQuery, state: FSMContext):
    """Начало изменения риска"""
    await callback.message.answer(
        "⚠️ Введите новый риск на сделку в % (0.1-100):\n\n"
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
        
    except (ValueError, Decimal.InvalidOperation):
        await message.answer("❌ Неверный формат. Введите число (например: 1.5):")


# ==== CALLBACK: Назад в главное меню ====
@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text("Главное меню:", reply_markup=get_main_keyboard())
    await callback.answer()


# Продолжение в следующем файле из-за ограничения по размеру...
