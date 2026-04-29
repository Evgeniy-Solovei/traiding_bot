"""
Стратегия скальпинга.
Работает в боковике, лонг и шорт. Быстрые сделки до 1 часа.
"""

import pandas as pd
from typing import Optional, Dict, Literal
from .base_strategy import BaseStrategy, SignalResult


class ScalpingStrategy(BaseStrategy):
    """
    Стратегия скальпинга для быстрых сделок.
    
    Философия:
    - Работает в любом тренде (боковик, лонг, шорт)
    - Использует краткосрочные индикаторы (1m, 5m)
    - Быстрый вход и выход (максимум 1 час)
    - Небольшие стоп-лоссы и тейк-профиты
    """
    
    def __init__(
        self,
        stop_loss_percent: float = 0.5,  # Небольшой SL для скальпинга
        take_profit_percent: float = 1.0,  # Небольшой TP для скальпинга
        leverage: int = 10,
        rsi_period: int = 9,  # Более быстрый RSI для скальпинга
        ema_fast_period: int = 5,
        ema_slow_period: int = 13,
        max_hold_time_minutes: int = 60  # Максимум 1 час в сделке
    ):
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.leverage = leverage
        self.rsi_period = rsi_period
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.max_hold_time_minutes = max_hold_time_minutes
    
    @property
    def name(self) -> str:
        return "scalping"
    
    @property
    def description(self) -> str:
        return "Скальпинг: быстрые сделки до 1 часа, работает в любом тренде"

    def calculate_sl_tp_prices(self, entry_price: float, side: str) -> tuple[float, float]:
        """
        Расчет SL/TP в процентах ОТ ЦЕНЫ.
        """
        side_upper = side.upper()
        if side_upper == 'LONG':
            stop_loss = entry_price * (1 - (self.stop_loss_percent / 100))
            take_profit = entry_price * (1 + (self.take_profit_percent / 100))
            return stop_loss, take_profit
        if side_upper == 'SHORT':
            stop_loss = entry_price * (1 + (self.stop_loss_percent / 100))
            take_profit = entry_price * (1 - (self.take_profit_percent / 100))
            return stop_loss, take_profit
        raise ValueError(f"Неизвестное направление сделки: {side}")
    
    def calculate_ema(self, data: pd.Series, period: int) -> pd.Series:
        """Расчет экспоненциальной скользящей средней"""
        return data.ewm(span=period, adjust=False).mean()
    
    def calculate_rsi(self, data: pd.Series, period: int = 9) -> pd.Series:
        """Расчет индекса относительной силы (RSI)"""
        delta = data.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi
    
    def calculate_macd(self, data: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> Dict[str, pd.Series]:
        """Расчет MACD"""
        ema_fast = data.ewm(span=fast, adjust=False).mean()
        ema_slow = data.ewm(span=slow, adjust=False).mean()
        macd_line = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal, adjust=False).mean()
        histogram = macd_line - signal_line
        
        return {
            'macd': macd_line,
            'signal': signal_line,
            'histogram': histogram
        }
    
    def check_scalping_long_signal(self, df: pd.DataFrame) -> bool:
        """
        Проверка сигнала на LONG для скальпинга.
        
        Условия:
        - EMA5 выше EMA13 (краткосрочный бычий тренд)
        - RSI между 40-60 (не перекуплен, не перепродан)
        - MACD гистограмма положительная и растет
        - Цена выше EMA5
        """
        if len(df) < max(self.ema_slow_period, 26):
            return False
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) >= 2 else last_row
        
        ema_fast = last_row['EMA_fast']
        ema_slow = last_row['EMA_slow']
        rsi = last_row['RSI']
        macd_hist = last_row['MACD_hist']
        macd_hist_prev = prev_row['MACD_hist'] if 'MACD_hist' in prev_row else 0
        current_price = last_row['close']
        
        # Основные условия для LONG
        conditions = [
            ema_fast > ema_slow,  # Бычий тренд
            40 < rsi < 60,  # RSI в нейтральной зоне
            macd_hist > 0,  # MACD выше сигнальной линии
            macd_hist > macd_hist_prev,  # MACD растет
            current_price > ema_fast  # Цена выше быстрой EMA
        ]
        
        return sum(conditions) >= 4  # Минимум 4 из 5 условий
    
    def check_scalping_short_signal(self, df: pd.DataFrame) -> bool:
        """
        Проверка сигнала на SHORT для скальпинга.
        
        Условия:
        - EMA5 ниже EMA13 (краткосрочный медвежий тренд)
        - RSI между 40-60 (не перекуплен, не перепродан)
        - MACD гистограмма отрицательная и падает
        - Цена ниже EMA5
        """
        if len(df) < max(self.ema_slow_period, 26):
            return False
        
        last_row = df.iloc[-1]
        prev_row = df.iloc[-2] if len(df) >= 2 else last_row
        
        ema_fast = last_row['EMA_fast']
        ema_slow = last_row['EMA_slow']
        rsi = last_row['RSI']
        macd_hist = last_row['MACD_hist']
        macd_hist_prev = prev_row['MACD_hist'] if 'MACD_hist' in prev_row else 0
        current_price = last_row['close']
        
        # Основные условия для SHORT
        conditions = [
            ema_fast < ema_slow,  # Медвежий тренд
            40 < rsi < 60,  # RSI в нейтральной зоне
            macd_hist < 0,  # MACD ниже сигнальной линии
            macd_hist < macd_hist_prev,  # MACD падает
            current_price < ema_fast  # Цена ниже быстрой EMA
        ]
        
        return sum(conditions) >= 4  # Минимум 4 из 5 условий
    
    def analyze(
        self, 
        df: pd.DataFrame, 
        higher_timeframe_trend: Optional[Literal['BULLISH', 'BEARISH', 'NEUTRAL']] = None
    ) -> Optional[SignalResult]:
        """
        Анализ для скальпинга - работает в любом тренде.
        """
        if len(df) < max(self.ema_slow_period, 26):
            return None
        
        # Расчет индикаторов
        df['EMA_fast'] = self.calculate_ema(df['close'], self.ema_fast_period)
        df['EMA_slow'] = self.calculate_ema(df['close'], self.ema_slow_period)
        df['RSI'] = self.calculate_rsi(df['close'], self.rsi_period)
        
        macd_data = self.calculate_macd(df['close'])
        df['MACD'] = macd_data['macd']
        df['MACD_signal'] = macd_data['signal']
        df['MACD_hist'] = macd_data['histogram']
        
        last_row = df.iloc[-1]
        current_price = last_row['close']
        
        # Проверяем сигналы (скальпинг работает в любом тренде)
        long_signal = self.check_scalping_long_signal(df)
        short_signal = self.check_scalping_short_signal(df)
        
        if long_signal:
            # Расчет SL/TP как % от цены входа
            stop_loss, take_profit = self.calculate_sl_tp_prices(current_price, 'LONG')
            
            confidence = 75.0  # Базовая уверенность для скальпинга
            
            return SignalResult(
                signal='LONG',
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=f"Скальпинг LONG: EMA{self.ema_fast_period} > EMA{self.ema_slow_period}, RSI={last_row['RSI']:.1f}, MACD положительный"
            )
        
        if short_signal:
            # Расчет SL/TP как % от цены входа
            stop_loss, take_profit = self.calculate_sl_tp_prices(current_price, 'SHORT')
            
            confidence = 75.0  # Базовая уверенность для скальпинга
            
            return SignalResult(
                signal='SHORT',
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=f"Скальпинг SHORT: EMA{self.ema_fast_period} < EMA{self.ema_slow_period}, RSI={last_row['RSI']:.1f}, MACD отрицательный"
            )
        
        return None
    
    def analyze_detailed(self, df: pd.DataFrame) -> Dict:
        """Детальный анализ для отображения"""
        result = {
            'trend': 'NEUTRAL',  # Скальпинг работает в любом тренде
            'channel_valid': True,
            'conditions_checked': {},
            'conditions_met': 0,
            'total_conditions': 5,
            'current_price': 0,
            'indicators': {},
            'reason_no_signal': ''
        }
        
        if len(df) < max(self.ema_slow_period, 26):
            result['reason_no_signal'] = 'Недостаточно данных'
            return result
        
        # Расчет индикаторов
        df['EMA_fast'] = self.calculate_ema(df['close'], self.ema_fast_period)
        df['EMA_slow'] = self.calculate_ema(df['close'], self.ema_slow_period)
        df['RSI'] = self.calculate_rsi(df['close'], self.rsi_period)
        
        macd_data = self.calculate_macd(df['close'])
        df['MACD'] = macd_data['macd']
        df['MACD_signal'] = macd_data['signal']
        df['MACD_hist'] = macd_data['histogram']
        
        last_row = df.iloc[-1]
        result['current_price'] = float(last_row['close'])
        result['indicators'] = {
            f'EMA{self.ema_fast_period}': float(last_row['EMA_fast']),
            f'EMA{self.ema_slow_period}': float(last_row['EMA_slow']),
            'RSI': float(last_row['RSI']),
            'MACD': float(last_row['MACD']),
            'MACD_signal': float(last_row['MACD_signal']),
            'MACD_hist': float(last_row['MACD_hist']),
        }
        
        # Проверка условий
        long_conditions = {
            'ema_trend': last_row['EMA_fast'] > last_row['EMA_slow'],
            'rsi_neutral': 40 < last_row['RSI'] < 60,
            'macd_positive': last_row['MACD_hist'] > 0,
            'macd_growing': len(df) >= 2 and last_row['MACD_hist'] > df.iloc[-2]['MACD_hist'],
            'price_above_ema': last_row['close'] > last_row['EMA_fast']
        }
        
        short_conditions = {
            'ema_trend': last_row['EMA_fast'] < last_row['EMA_slow'],
            'rsi_neutral': 40 < last_row['RSI'] < 60,
            'macd_negative': last_row['MACD_hist'] < 0,
            'macd_falling': len(df) >= 2 and last_row['MACD_hist'] < df.iloc[-2]['MACD_hist'],
            'price_below_ema': last_row['close'] < last_row['EMA_fast']
        }
        
        long_met = sum(long_conditions.values())
        short_met = sum(short_conditions.values())
        
        result['long_conditions'] = long_conditions
        result['short_conditions'] = short_conditions
        result['long_main_met'] = long_met
        result['short_main_met'] = short_met
        result['long_confirm_met'] = 0  # Для скальпинга нет разделения на основные/подтверждающие
        result['short_confirm_met'] = 0
        
        if long_met >= 4:
            result['reason_no_signal'] = f'LONG сигнал найден ({long_met}/5 условий)'
        elif short_met >= 4:
            result['reason_no_signal'] = f'SHORT сигнал найден ({short_met}/5 условий)'
        else:
            result['reason_no_signal'] = f'Нет сигнала. LONG: {long_met}/5, SHORT: {short_met}/5'
        
        return result


# Автоматическая регистрация стратегии
from .strategy_registry import StrategyRegistry
StrategyRegistry.register(ScalpingStrategy)
