"""
Реализация торговой стратегии "Основная стратегия v1.0".
Ловим отскоки от границ ценового канала в направлении тренда.
"""

import numpy as np
import pandas as pd
from typing import Optional, Dict, Literal
from dataclasses import dataclass


@dataclass
class SignalResult:
    """Результат анализа сигнала"""
    signal: Optional[Literal['LONG', 'SHORT']]
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float  # Уверенность в сигнале 0-100%
    reason: str  # Причина сигнала


class TradingStrategy:
    """
    Основная торговая стратегия v1.0.
    
    Философия: Ловим отскоки от границ ценового канала в направлении тренда 
    с подтверждением 4-мя индикаторами.
    """
    
    def __init__(
        self,
        ema_fast_period: int = 9,
        ema_slow_period: int = 21,
        rsi_period: int = 14,
        williams_r_period: int = 14,
        channel_period: int = 20,
        atr_period: int = 14,
        stop_loss_atr_multiplier: float = 1.5,
        take_profit_atr_multiplier: float = 2.5
    ):
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.rsi_period = rsi_period
        self.williams_r_period = williams_r_period
        self.channel_period = channel_period
        self.atr_period = atr_period
        self.stop_loss_atr_multiplier = stop_loss_atr_multiplier
        self.take_profit_atr_multiplier = take_profit_atr_multiplier
    
    def calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """Расчет экспоненциальной скользящей средней"""
        return data.ewm(span=period, adjust=False).mean()
    
    def calculate_rsi(self, data: pd.Series, period: int = 14) -> pd.Series:
        """Расчет индекса относительной силы (RSI)"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_williams_r(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Расчет Williams %R"""
        highest_high = high.rolling(window=period).max()
        lowest_low = low.rolling(window=period).min()
        
        williams_r = ((highest_high - close) / (highest_high - lowest_low)) * -100
        return williams_r
    
    def calculate_atr(self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
        """Расчет Average True Range (ATR)"""
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        return atr
    
    def find_channel(self, high: pd.Series, low: pd.Series, period: int = 20) -> tuple:
        """
        Определение ценового канала по локальным максимумам и минимумам.
        
        Returns:
            tuple: (верхняя_граница, нижняя_граница, валидность_канала)
        """
        # Берем последние period свечей
        recent_high = high.tail(period)
        recent_low = low.tail(period)
        
        # Находим максимум и минимум
        upper_bound = recent_high.max()
        lower_bound = recent_low.min()
        
        # Проверяем валидность канала (минимум 2 касания сверху и снизу)
        upper_touches = (recent_high >= upper_bound * 0.998).sum()  # 0.2% допуск
        lower_touches = (recent_low <= lower_bound * 1.002).sum()
        
        is_valid = upper_touches >= 2 and lower_touches >= 2
        
        return upper_bound, lower_bound, is_valid
    
    def determine_trend(self, df: pd.DataFrame) -> Literal['BULLISH', 'BEARISH', 'NEUTRAL']:
        """
        Определение тренда.
        
        Бычий тренд: EMA9 > EMA21 + RSI > 50
        Медвежий тренд: EMA9 < EMA21 + RSI < 50
        """
        last_row = df.iloc[-1]
        
        ema9 = last_row['EMA9']
        ema21 = last_row['EMA21']
        rsi = last_row['RSI']
        
        if ema9 > ema21 and rsi > 50:
            return 'BULLISH'
        elif ema9 < ema21 and rsi < 50:
            return 'BEARISH'
        else:
            return 'NEUTRAL'
    
    def check_long_signal(self, df: pd.DataFrame, upper_bound: float, lower_bound: float) -> Optional[SignalResult]:
        """
        Проверка сигнала на LONG.
        
        Условия:
        1. Цена у НИЖНЕЙ границы канала
        2. RSI < 30 (перепроданность)
        3. Williams %R < -80 (перепроданность)
        4. EMA9 пересекает EMA21 СНИЗУ ВВЕРХ
        5. Объем увеличивается на отскоке
        """
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        current_price = last_row['close']
        rsi = last_row['RSI']
        williams_r = last_row['WilliamsR']
        ema9_curr = last_row['EMA9']
        ema21_curr = last_row['EMA21']
        ema9_prev = prev_row['EMA9']
        ema21_prev = prev_row['EMA21']
        volume_curr = last_row['volume']
        volume_avg = df['volume'].tail(20).mean()
        atr = last_row['ATR']
        
        # Проверка условий
        conditions = {
            'near_lower_bound': abs(current_price - lower_bound) / lower_bound < 0.005,  # в пределах 0.5%
            'rsi_oversold': rsi < 30,
            'williams_oversold': williams_r < -80,
            'ema_crossover': ema9_curr > ema21_curr and ema9_prev <= ema21_prev,
            'volume_increase': volume_curr > volume_avg * 1.2  # объем на 20% выше среднего
        }
        
        # Подсчет выполненных условий
        conditions_met = sum(conditions.values())
        confidence = (conditions_met / len(conditions)) * 100
        
        # Минимум 3 из 5 условий должны быть выполнены
        if conditions_met >= 3:
            stop_loss = current_price - (atr * self.stop_loss_atr_multiplier)
            take_profit = current_price + (atr * self.take_profit_atr_multiplier)
            
            reasons = [key for key, value in conditions.items() if value]
            reason = f"LONG сигнал: {', '.join(reasons)}"
            
            return SignalResult(
                signal='LONG',
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=reason
            )
        
        return None
    
    def check_short_signal(self, df: pd.DataFrame, upper_bound: float, lower_bound: float) -> Optional[SignalResult]:
        """
        Проверка сигнала на SHORT.
        
        Условия:
        1. Цена у ВЕРХНЕЙ границы канала
        2. RSI > 70 (перекупленность)
        3. Williams %R > -20 (перекупленность)
        4. EMA9 пересекает EMA21 СВЕРХУ ВНИЗ
        5. Объем увеличивается на отскоке
        """
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2]
        
        current_price = last_row['close']
        rsi = last_row['RSI']
        williams_r = last_row['WilliamsR']
        ema9_curr = last_row['EMA9']
        ema21_curr = last_row['EMA21']
        ema9_prev = prev_row['EMA9']
        ema21_prev = prev_row['EMA21']
        volume_curr = last_row['volume']
        volume_avg = df['volume'].tail(20).mean()
        atr = last_row['ATR']
        
        # Проверка условий
        conditions = {
            'near_upper_bound': abs(current_price - upper_bound) / upper_bound < 0.005,  # в пределах 0.5%
            'rsi_overbought': rsi > 70,
            'williams_overbought': williams_r > -20,
            'ema_crossover': ema9_curr < ema21_curr and ema9_prev >= ema21_prev,
            'volume_increase': volume_curr > volume_avg * 1.2  # объем на 20% выше среднего
        }
        
        # Подсчет выполненных условий
        conditions_met = sum(conditions.values())
        confidence = (conditions_met / len(conditions)) * 100
        
        # Минимум 3 из 5 условий должны быть выполнены
        if conditions_met >= 3:
            stop_loss = current_price + (atr * self.stop_loss_atr_multiplier)
            take_profit = current_price - (atr * self.take_profit_atr_multiplier)
            
            reasons = [key for key, value in conditions.items() if value]
            reason = f"SHORT сигнал: {', '.join(reasons)}"
            
            return SignalResult(
                signal='SHORT',
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=reason
            )
        
        return None
    
    def analyze(self, df: pd.DataFrame) -> Optional[SignalResult]:
        """
        Главный метод анализа рынка и генерации сигналов.
        
        Args:
            df: DataFrame с OHLCV данными (columns: open, high, low, close, volume)
            
        Returns:
            SignalResult или None если сигнала нет
        """
        if len(df) < max(self.ema_slow_period, self.channel_period, self.rsi_period, self.williams_r_period):
            return None
        
        # Расчет индикаторов
        df['EMA9'] = self.calculate_ema(df['close'], self.ema_fast_period)
        df['EMA21'] = self.calculate_ema(df['close'], self.ema_slow_period)
        df['RSI'] = self.calculate_rsi(df['close'], self.rsi_period)
        df['WilliamsR'] = self.calculate_williams_r(df['high'], df['low'], df['close'], self.williams_r_period)
        df['ATR'] = self.calculate_atr(df['high'], df['low'], df['close'], self.atr_period)
        
        # Определение тренда
        trend = self.determine_trend(df)
        
        if trend == 'NEUTRAL':
            return None  # Не торгуем в боковике
        
        # Построение канала
        upper_bound, lower_bound, is_valid_channel = self.find_channel(
            df['high'], 
            df['low'], 
            self.channel_period
        )
        
        if not is_valid_channel:
            return None  # Канал не валидный
        
        # Проверка сигналов в зависимости от тренда
        if trend == 'BULLISH':
            # В бычьем тренде ищем только LONG сигналы
            signal = self.check_long_signal(df, upper_bound, lower_bound)
            return signal
        
        elif trend == 'BEARISH':
            # В медвежьем тренде ищем только SHORT сигналы
            signal = self.check_short_signal(df, upper_bound, lower_bound)
            return signal
        
        return None
