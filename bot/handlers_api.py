"""
Обработчики для управления API ключами.
"""

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
import asyncio

from .models import BotUser
from .keyboards import (
    get_api_keys_keyboard, get_testnet_keyboard,
    get_cancel_keyboard, get_main_keyboard
)
from .states import APIKeysStates
from trading_strategy.models import Exchange
from trading_strategy.encryption import encrypt_api_credentials
from trading_strategy.exchange_client import test_connection

router = Router()


# ==== API КЛЮЧИ ====
@router.message(F.text == "🔑 API Ключи")
async def show_api_keys(message: Message):
    """
    Показ информации об API ключах.
    """
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await message.answer("❌ Ошибка: пользователь не найден. Используйте /start")
        return
    
    exchange = await asyncio.to_thread(
        Exchange.objects.filter(user=bot_user.django_user, is_active=True).first
    )
    
    if exchange:
        api_text = f"""
🔑 <b>API КЛЮЧИ НАСТРОЕНЫ</b>

🏦 Биржа: <b>{exchange.name.upper()}</b>
🌐 Сеть: <b>{'Testnet 🧪' if exchange.is_testnet else 'Mainnet 💰'}</b>
✅ Статус: <b>{'Активны' if exchange.is_active else 'Неактивны'}</b>

📅 Добавлены: <code>{exchange.created_at.strftime('%Y-%m-%d %H:%M')}</code>

Выберите действие:
"""
    else:
        api_text = """
🔑 <b>API КЛЮЧИ</b>

❌ API ключи еще не добавлены.

Для автоматической торговли необходимы API ключи от Bybit.

📝 <b>Как получить API ключи:</b>
1. Зайдите на bybit.com (или testnet.bybit.com)
2. Перейдите в API Management
3. Создайте новый API ключ
4. Права: Trading, Position (Read/Write)
5. Скопируйте ключ и секрет

Выберите действие:
"""
    
    await message.answer(api_text, reply_markup=get_api_keys_keyboard(), parse_mode="HTML")


# ==== CALLBACK: Добавить ключи ====
@router.callback_query(F.data == "api_add")
async def api_add_callback(callback: CallbackQuery, state: FSMContext):
    """Начало добавления API ключей"""
    
    # Проверяем, не добавлены ли уже ключи
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )
    
    existing_exchange = await asyncio.to_thread(
        Exchange.objects.filter(user=bot_user.django_user, is_active=True).first
    )
    
    if existing_exchange:
        await callback.message.answer(
            "⚠️ API ключи уже добавлены. Сначала удалите существующие ключи."
        )
        await callback.answer()
        return
    
    await callback.message.answer(
        "🌐 Выберите сеть для API ключей:",
        reply_markup=get_testnet_keyboard()
    )
    await state.set_state(APIKeysStates.choosing_network)
    await callback.answer()


# ==== CALLBACK: Выбор сети (testnet/mainnet) ====
@router.callback_query(F.data.startswith("network_"))
async def network_choice_callback(callback: CallbackQuery, state: FSMContext):
    """Обработка выбора сети"""
    is_testnet = callback.data == "network_testnet"
    
    await state.update_data(is_testnet=is_testnet)
    
    network_name = "Testnet 🧪" if is_testnet else "Mainnet 💰"
    
    await callback.message.edit_text(
        f"✅ Выбрана сеть: <b>{network_name}</b>\n\n"
        f"📝 Введите API Key от Bybit:\n\n"
        f"⚠️ Ключ должен иметь права Trading и Position (Read/Write)",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    
    await state.set_state(APIKeysStates.waiting_for_api_key)
    await callback.answer()


# ==== Ввод API Key ====
@router.message(APIKeysStates.waiting_for_api_key)
async def process_api_key(message: Message, state: FSMContext):
    """Обработка API ключа"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    api_key = message.text.strip()
    
    # Удаляем сообщение с ключом для безопасности
    try:
        await message.delete()
    except:
        pass
    
    await state.update_data(api_key=api_key)
    
    await message.answer(
        "🔐 Теперь введите API Secret:\n\n"
        "⚠️ Ваши ключи будут зашифрованы и надежно сохранены.",
        reply_markup=get_cancel_keyboard(),
        parse_mode="HTML"
    )
    
    await state.set_state(APIKeysStates.waiting_for_api_secret)


# ==== Ввод API Secret ====
@router.message(APIKeysStates.waiting_for_api_secret)
async def process_api_secret(message: Message, state: FSMContext):
    """Обработка API секрета и сохранение"""
    if message.text == "❌ Отмена":
        await state.clear()
        await message.answer("Отменено.", reply_markup=get_main_keyboard())
        return
    
    api_secret = message.text.strip()
    
    # Удаляем сообщение с секретом для безопасности
    try:
        await message.delete()
    except:
        pass
    
    # Получаем сохраненные данные
    data = await state.get_data()
    api_key = data['api_key']
    is_testnet = data['is_testnet']
    
    # Тестируем подключение
    test_msg = await message.answer("🔄 Проверяю подключение к Bybit...")
    
    test_result = await test_connection(api_key, api_secret, is_testnet)
    
    if not test_result['success']:
        await test_msg.edit_text(
            f"❌ Ошибка подключения:\n\n{test_result['message']}\n\n"
            f"Попробуйте еще раз или обратитесь в поддержку."
        )
        await state.clear()
        return
    
    # Шифруем и сохраняем ключи
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=message.from_user.id).select_related('django_user').first
    )
    
    encrypted_key, encrypted_secret = await asyncio.to_thread(
        encrypt_api_credentials,
        api_key,
        api_secret
    )
    
    exchange = await asyncio.to_thread(
        Exchange.objects.create,
        user=bot_user.django_user,
        name='bybit',
        api_key_encrypted=encrypted_key,
        api_secret_encrypted=encrypted_secret,
        is_testnet=is_testnet,
        is_active=True
    )
    
    network_name = "Testnet 🧪" if is_testnet else "Mainnet 💰"
    
    await test_msg.edit_text(
        f"✅ API ключи успешно добавлены!\n\n"
        f"🏦 Биржа: <b>Bybit</b>\n"
        f"🌐 Сеть: <b>{network_name}</b>\n"
        f"💰 Баланс USDT: <code>${test_result['balance']}</code>\n\n"
        f"Теперь настройте торговые параметры (⚙️ Настройки) и добавьте торговые пары (📈 Торговые пары).",
        reply_markup=get_main_keyboard(),
        parse_mode="HTML"
    )
    
    await state.clear()


# ==== CALLBACK: Изменить ключи ====
@router.callback_query(F.data == "api_edit")
async def api_edit_callback(callback: CallbackQuery, state: FSMContext):
    """Изменение API ключей (то же что добавление, но с удалением старых)"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )
    
    if not bot_user:
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
    # Удаляем старые ключи
    old_exchange = await asyncio.to_thread(
        Exchange.objects.filter(user=bot_user.django_user, is_active=True).first
    )
    
    if old_exchange:
        await asyncio.to_thread(old_exchange.delete)
    
    await callback.message.answer(
        "🌐 Выберите сеть для новых API ключей:",
        reply_markup=get_testnet_keyboard()
    )
    await state.set_state(APIKeysStates.choosing_network)
    await callback.answer()


# ==== CALLBACK: Удалить ключи ====
@router.callback_query(F.data == "api_delete")
async def api_delete_callback(callback: CallbackQuery):
    """Удаление API ключей"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )
    
    exchange = await asyncio.to_thread(
        Exchange.objects.filter(user=bot_user.django_user, is_active=True).first
    )
    
    if not exchange:
        await callback.message.answer("❌ API ключи не найдены.")
        await callback.answer()
        return
    
    # Останавливаем торговлю
    settings = await asyncio.to_thread(
        lambda: bot_user.django_user.trading_settings
    )
    settings.is_trading_active = False
    await asyncio.to_thread(settings.save)
    
    # Удаляем ключи
    await asyncio.to_thread(exchange.delete)
    
    await callback.message.answer(
        "✅ API ключи удалены.\n"
        "Торговля остановлена.",
        reply_markup=get_main_keyboard()
    )
    await callback.answer()


# ==== CALLBACK: Тест подключения ====
@router.callback_query(F.data == "api_test")
async def api_test_callback(callback: CallbackQuery):
    """Проверка подключения к бирже"""
    bot_user = await asyncio.to_thread(
        BotUser.objects.filter(telegram_id=callback.from_user.id).select_related('django_user').first
    )
    
    exchange = await asyncio.to_thread(
        Exchange.objects.filter(user=bot_user.django_user, is_active=True).first
    )
    
    if not exchange:
        await callback.message.answer("❌ API ключи не найдены. Добавьте их сначала.")
        await callback.answer()
        return
    
    await callback.message.edit_text("🔄 Проверяю подключение...")
    
    from trading_strategy.encryption import decrypt_api_credentials
    
    api_key, api_secret = await asyncio.to_thread(
        decrypt_api_credentials,
        exchange.api_key_encrypted,
        exchange.api_secret_encrypted
    )
    
    test_result = await test_connection(api_key, api_secret, exchange.is_testnet)
    
    if test_result['success']:
        network_name = "Testnet 🧪" if exchange.is_testnet else "Mainnet 💰"
        await callback.message.edit_text(
            f"✅ Подключение успешно!\n\n"
            f"🏦 Биржа: <b>Bybit</b>\n"
            f"🌐 Сеть: <b>{network_name}</b>\n"
            f"💰 Баланс USDT: <code>${test_result['balance']}</code>",
            reply_markup=get_api_keys_keyboard(),
            parse_mode="HTML"
        )
    else:
        await callback.message.edit_text(
            f"❌ Ошибка подключения:\n\n{test_result['message']}\n\n"
            f"Проверьте ваши API ключи.",
            reply_markup=get_api_keys_keyboard()
        )
    
    await callback.answer()
