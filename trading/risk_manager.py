"""
Модуль управления рисками для торгового бота.
Расчет размеров позиций, стоп-лоссов и тейк-профитов.
"""

from decimal import Decimal
from typing import Dict, Tuple
from dataclasses import dataclass


@dataclass
class PositionSize:
    """Результат расчета размера позиции"""
    quantity: float  # Количество контрактов
    position_size_usd: float  # Размер позиции в USD
    risk_amount: float  # Сумма риска в USD
    stop_loss_distance: float  # Расстояние до стоп-лосса
    leverage_used: int  # Использованное плечо


class RiskManager:
    """
    Менеджер управления рисками.
    
    Отвечает за:
    - Расчет размера позиции на основе риска
    - Валидацию параметров сделки
    - Проверку достаточности баланса
    """
    
    def __init__(
        self,
        balance: Decimal,
        risk_per_trade: Decimal,
        base_order_size: Decimal,
        leverage: int,
        max_leverage: int = 100
    ):
        """
        Args:
            balance: Доступный баланс в USD
            risk_per_trade: Риск на сделку в % от баланса
            base_order_size: Базовый размер ордера в USD
            leverage: Плечо
            max_leverage: Максимальное плечо
        """
        self.balance = float(balance)
        self.risk_per_trade = float(risk_per_trade)
        self.base_order_size = float(base_order_size)
        self.leverage = min(leverage, max_leverage)
        self.max_leverage = max_leverage
    
    def calculate_position_size(
        self,
        entry_price: float,
        stop_loss_price: float,
        side: str
    ) -> PositionSize:
        """
        Расчет размера позиции на основе риска.
        
        Логика:
        1. Рассчитываем максимальную сумму риска (% от баланса)
        2. Определяем расстояние до стоп-лосса
        3. Вычисляем количество контрактов
        4. Применяем плечо для определения финального размера
        
        Args:
            entry_price: Цена входа
            stop_loss_price: Цена стоп-лосса
            side: 'long' или 'short'
            
        Returns:
            PositionSize: Рассчитанный размер позиции
        """
        # Максимальная сумма риска в USD
        risk_amount = self.balance * (self.risk_per_trade / 100)
        
        # Расстояние до стоп-лосса в %
        if side == 'long':
            stop_loss_distance = abs(entry_price - stop_loss_price) / entry_price
        else:  # short
            stop_loss_distance = abs(stop_loss_price - entry_price) / entry_price
        
        # Размер позиции в USD (с учетом плеча)
        # Формула: риск / расстояние_до_sl = размер_позиции
        position_size_usd = risk_amount / stop_loss_distance
        
        # Ограничиваем размер позиции базовым размером ордера, если он меньше
        position_size_usd = min(position_size_usd, self.base_order_size * self.leverage)
        
        # Количество контрактов (без плеча)
        quantity = position_size_usd / entry_price
        
        return PositionSize(
            quantity=quantity,
            position_size_usd=position_size_usd,
            risk_amount=risk_amount,
            stop_loss_distance=stop_loss_distance * 100,  # в процентах
            leverage_used=self.leverage
        )
    
    def validate_position(self, position_size: PositionSize) -> Tuple[bool, str]:
        """
        Валидация параметров позиции.
        
        Args:
            position_size: Размер позиции для проверки
            
        Returns:
            tuple: (валидна, сообщение)
        """
        # Проверка: достаточно ли баланса
        required_margin = position_size.position_size_usd / self.leverage
        
        if required_margin > self.balance:
            return False, f"Недостаточно баланса. Требуется: ${required_margin:.2f}, доступно: ${self.balance:.2f}"
        
        # Проверка: не слишком ли большой риск
        if position_size.risk_amount > self.balance * 0.1:  # максимум 10% от баланса
            return False, f"Слишком большой риск: ${position_size.risk_amount:.2f} (>10% от баланса)"
        
        # Проверка: минимальный размер позиции
        if position_size.position_size_usd < 5:  # минимум $5
            return False, f"Размер позиции слишком мал: ${position_size.position_size_usd:.2f} (<$5)"
        
        # Проверка: стоп-лосс не слишком далеко
        if position_size.stop_loss_distance > 10:  # максимум 10%
            return False, f"Стоп-лосс слишком далеко: {position_size.stop_loss_distance:.2f}% (>10%)"
        
        return True, "Позиция валидна"
    
    def calculate_pnl(
        self,
        entry_price: float,
        exit_price: float,
        quantity: float,
        side: str,
        leverage: int
    ) -> Dict[str, float]:
        """
        Расчет PnL (прибыль/убыток).
        
        Args:
            entry_price: Цена входа
            exit_price: Цена выхода
            quantity: Количество контрактов
            side: 'long' или 'short'
            leverage: Плечо
            
        Returns:
            dict: {'pnl_usd', 'pnl_percent', 'roe_percent'}
        """
        if side == 'long':
            pnl_usd = (exit_price - entry_price) * quantity
        else:  # short
            pnl_usd = (entry_price - exit_price) * quantity
        
        # Процент от размера позиции
        position_value = entry_price * quantity
        pnl_percent = (pnl_usd / position_value) * 100 if position_value > 0 else 0
        
        # ROE (Return on Equity) - доходность с учетом плеча
        margin_used = position_value / leverage
        roe_percent = (pnl_usd / margin_used) * 100 if margin_used > 0 else 0
        
        return {
            'pnl_usd': pnl_usd,
            'pnl_percent': pnl_percent,
            'roe_percent': roe_percent
        }
    
    def adjust_for_fees(self, position_size_usd: float, fee_rate: float = 0.0006) -> float:
        """
        Корректировка размера позиции с учетом комиссий.
        
        Args:
            position_size_usd: Размер позиции в USD
            fee_rate: Ставка комиссии (по умолчанию 0.06% на Bybit)
            
        Returns:
            float: Скорректированный размер позиции
        """
        # Учитываем комиссию за открытие и закрытие позиции
        total_fee_rate = fee_rate * 2
        adjusted_size = position_size_usd * (1 - total_fee_rate)
        
        return adjusted_size
    
    def get_max_position_size(self) -> float:
        """
        Максимальный размер позиции с учетом баланса и плеча.
        
        Returns:
            float: Максимальный размер в USD
        """
        return self.balance * self.leverage


def calculate_position_for_signal(
    balance: Decimal,
    risk_per_trade: Decimal,
    base_order_size: Decimal,
    leverage: int,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    side: str
) -> Dict:
    """
    Вспомогательная функция для расчета полной информации о позиции.
    
    Args:
        balance: Баланс
        risk_per_trade: Риск на сделку (%)
        base_order_size: Базовый размер ордера
        leverage: Плечо
        entry_price: Цена входа
        stop_loss: Стоп-лосс
        take_profit: Тейк-профит
        side: Направление ('long' или 'short')
        
    Returns:
        dict: Полная информация о позиции
    """
    rm = RiskManager(balance, risk_per_trade, base_order_size, leverage)
    
    # Расчет размера позиции
    position_size = rm.calculate_position_size(entry_price, stop_loss, side)
    
    # Валидация
    is_valid, message = rm.validate_position(position_size)
    
    # Расчет потенциального PnL
    potential_profit = rm.calculate_pnl(
        entry_price, take_profit, position_size.quantity, side, leverage
    )
    
    potential_loss = rm.calculate_pnl(
        entry_price, stop_loss, position_size.quantity, side, leverage
    )
    
    # Risk/Reward соотношение
    risk_reward_ratio = abs(potential_profit['pnl_usd'] / potential_loss['pnl_usd']) if potential_loss['pnl_usd'] != 0 else 0
    
    return {
        'is_valid': is_valid,
        'validation_message': message,
        'quantity': position_size.quantity,
        'position_size_usd': position_size.position_size_usd,
        'risk_amount': position_size.risk_amount,
        'stop_loss_distance_percent': position_size.stop_loss_distance,
        'leverage': position_size.leverage_used,
        'potential_profit': potential_profit['pnl_usd'],
        'potential_loss': potential_loss['pnl_usd'],
        'risk_reward_ratio': risk_reward_ratio,
        'roe_profit_percent': potential_profit['roe_percent'],
        'roe_loss_percent': potential_loss['roe_percent'],
    }
