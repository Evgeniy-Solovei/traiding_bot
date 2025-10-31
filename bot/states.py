"""
FSM состояния для Telegram бота.
"""

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Состояния регистрации нового пользователя"""
    waiting_for_confirmation = State()


class APIKeysStates(StatesGroup):
    """Состояния настройки API ключей"""
    choosing_network = State()  # Выбор testnet/mainnet
    waiting_for_api_key = State()
    waiting_for_api_secret = State()
    confirming = State()


class SettingsStates(StatesGroup):
    """Состояния изменения настроек торговли"""
    waiting_for_order_size = State()
    waiting_for_leverage = State()
    waiting_for_risk = State()


class TradingPairStates(StatesGroup):
    """Состояния управления торговыми парами"""
    waiting_for_symbol = State()
    confirming_delete = State()
