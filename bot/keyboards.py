"""
Клавиатуры для Telegram бота.
"""

from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """
    Главная клавиатура бота.
    """
    builder = ReplyKeyboardBuilder()
    
    builder.row(
        KeyboardButton(text="📊 Статистика"),
        KeyboardButton(text="⚙️ Настройки")
    )
    builder.row(
        KeyboardButton(text="🔑 API Ключи"),
        KeyboardButton(text="📈 Торговые пары")
    )
    builder.row(
        KeyboardButton(text="▶️ Старт"),
        KeyboardButton(text="⏸ Стоп")
    )
    builder.row(
        KeyboardButton(text="📝 Открытые позиции"),
        KeyboardButton(text="📜 История")
    )
    builder.row(
        KeyboardButton(text="ℹ️ Помощь")
    )
    
    return builder.as_markup(resize_keyboard=True)


def get_settings_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура настроек торговли.
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="💰 Размер ордера", callback_data="settings_order_size")
    )
    builder.row(
        InlineKeyboardButton(text="🎚 Плечо (Leverage)", callback_data="settings_leverage")
    )
    builder.row(
        InlineKeyboardButton(text="🛑 Дневной лимит", callback_data="settings_daily_limit")
    )
    builder.row(
        InlineKeyboardButton(text="📉 Убыточных подряд", callback_data="settings_max_losses")
    )
    builder.row(
        InlineKeyboardButton(text="🧯 Автопауза вкл/выкл", callback_data="settings_auto_pause")
    )
    builder.row(
        InlineKeyboardButton(text="🚦 Риск-пауза вкл/выкл", callback_data="settings_risk_pause_toggle")
    )
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_api_keys_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура управления API ключами.
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="➕ Добавить ключи", callback_data="api_add")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Изменить ключи", callback_data="api_edit")
    )
    builder.row(
        InlineKeyboardButton(text="🗑 Удалить ключи", callback_data="api_delete")
    )
    builder.row(
        InlineKeyboardButton(text="🔍 Проверить подключение", callback_data="api_test")
    )
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_trading_pairs_keyboard(pairs: list) -> InlineKeyboardMarkup:
    """
    Клавиатура управления торговыми парами.
    
    Args:
        pairs: Список торговых пар пользователя
    """
    builder = InlineKeyboardBuilder()
    
    for pair in pairs:
        status = "✅" if pair.is_active else "❌"
        builder.row(
            InlineKeyboardButton(
                text=f"{status} {pair.symbol}",
                callback_data=f"pair_toggle_{pair.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="➕ Добавить пару", callback_data="pair_add")
    )
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_open_positions_keyboard(trades: list) -> InlineKeyboardMarkup:
    """
    Клавиатура открытых позиций с возможностью закрыть.
    
    Args:
        trades: Список открытых сделок
    """
    builder = InlineKeyboardBuilder()
    
    for trade in trades:
        builder.row(
            InlineKeyboardButton(
                text=f"❌ Закрыть {trade.side.upper()} {trade.symbol}",
                callback_data=f"close_trade_{trade.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="🔄 Обновить", callback_data="refresh_positions")
    )
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_confirm_keyboard(action: str, item_id: str = None) -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения действия.
    
    Args:
        action: Действие для подтверждения
        item_id: ID элемента (опционально)
    """
    builder = InlineKeyboardBuilder()
    
    callback_yes = f"confirm_{action}" if not item_id else f"confirm_{action}_{item_id}"
    callback_no = f"cancel_{action}" if not item_id else f"cancel_{action}_{item_id}"
    
    builder.row(
        InlineKeyboardButton(text="✅ Да", callback_data=callback_yes),
        InlineKeyboardButton(text="❌ Нет", callback_data=callback_no)
    )
    
    return builder.as_markup()


def get_testnet_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура выбора: testnet или mainnet.
    """
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="🧪 Testnet (Тестовая сеть)", callback_data="network_testnet")
    )
    builder.row(
        InlineKeyboardButton(text="💰 Mainnet (Реальная торговля)", callback_data="network_mainnet")
    )
    builder.row(
        InlineKeyboardButton(text="« Назад", callback_data="back_to_main")
    )
    
    return builder.as_markup()


def get_cancel_keyboard() -> ReplyKeyboardMarkup:
    """
    Клавиатура отмены текущего действия.
    """
    builder = ReplyKeyboardBuilder()
    builder.row(KeyboardButton(text="❌ Отмена"))
    return builder.as_markup(resize_keyboard=True)


def get_popular_pairs_keyboard() -> InlineKeyboardMarkup:
    """
    Клавиатура с популярными торговыми парами для быстрого выбора.
    """
    builder = InlineKeyboardBuilder()
    
    # Популярные пары
    popular_pairs = [
        ("BTCUSDT", "₿ Bitcoin"),
        ("ETHUSDT", "Ξ Ethereum"),
    ]
    
    for symbol, name in popular_pairs:
        builder.row(
            InlineKeyboardButton(
                text=f"{name} ({symbol})",
                callback_data=f"quick_add_pair_{symbol}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="➕ Добавить свою пару", callback_data="pair_add")
    )
    builder.row(
        InlineKeyboardButton(text="⏭ Пропустить", callback_data="skip_pairs_setup")
    )
    
    return builder.as_markup()
