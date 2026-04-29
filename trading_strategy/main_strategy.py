"""
Реализация торговой стратегии "Основная стратегия v1.0".
Ловим отскоки от границ ценового канала в направлении тренда.
"""

import pandas as pd
from typing import Optional, Dict, Literal
from .base_strategy import BaseStrategy, SignalResult


class MainStrategy(BaseStrategy):
    """
    Основная торговая стратегия v1.0.
    
    Философия: Ловим отскоки от границ ценового канала в направлении тренда 
    с подтверждением 4-мя индикаторами.
    """
    
    @property
    def name(self) -> str:
        return "main"
    
    @property
    def description(self) -> str:
        return "Основная стратегия: отскоки от границ канала с подтверждением индикаторами"
    
    def __init__(
        self,
        ema_fast_period: int = 9,
        ema_slow_period: int = 21,
        rsi_period: int = 14,
        williams_r_period: int = 14,
        channel_period: int = 20,
        atr_period: int = 14,
        stop_loss_percent: float = 20.0,
        take_profit_percent: float = 35.0,
        leverage: int = 10
    ):
        self.ema_fast_period = ema_fast_period
        self.ema_slow_period = ema_slow_period
        self.rsi_period = rsi_period
        self.williams_r_period = williams_r_period
        self.channel_period = channel_period
        self.atr_period = atr_period
        self.stop_loss_percent = stop_loss_percent
        self.take_profit_percent = take_profit_percent
        self.leverage = leverage

    def calculate_sl_tp_prices(self, entry_price: float, side: str) -> tuple[float, float]:
        """
        Расчет SL/TP в процентах ОТ ЦЕНЫ.

        Пример:
        stop_loss_percent=20 -> стоп на 20% движения цены от входа.
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
        Определение ценового канала по локальным экстремумам.
        Канал считается валидным, если:
        - его ширина не слишком узкая
        - есть хотя бы по 2 касания верхней и нижней границы
        
        Returns:
            tuple: (верхняя_граница, нижняя_граница, валидность_канала)
        """
        if len(high) < period or len(low) < period:
            return 0.0, 0.0, False

        window_high = high.tail(period)
        window_low = low.tail(period)

        upper_bound = float(window_high.max())
        lower_bound = float(window_low.min())

        if lower_bound <= 0 or upper_bound <= lower_bound:
            return upper_bound, lower_bound, False

        channel_width_pct = (upper_bound - lower_bound) / lower_bound
        touch_tolerance = 0.003  # 0.3%

        upper_touches = ((window_high - upper_bound).abs() / upper_bound <= touch_tolerance).sum()
        lower_touches = ((window_low - lower_bound).abs() / lower_bound <= touch_tolerance).sum()

        # Отсеиваем слишком узкие и случайные "каналы" без касаний границ
        is_valid = channel_width_pct >= 0.003 and upper_touches >= 2 and lower_touches >= 2
        
        return upper_bound, lower_bound, is_valid
    
    def calculate_fibonacci_levels(self, high: pd.Series, low: pd.Series, period: int = 20) -> dict:
        """
        Расчет уровней Фибоначчи для определения зон отскока.
        
        Returns:
            dict с уровнями Фибоначчи (38.2%, 50%, 61.8%)
        """
        recent_high = high.tail(period).max()
        recent_low = low.tail(period).min()
        
        diff = recent_high - recent_low
        
        levels = {
            'fib_382': recent_high - (diff * 0.382),  # 38.2% от максимума
            'fib_500': recent_high - (diff * 0.500),  # 50%
            'fib_618': recent_high - (diff * 0.618),  # 61.8%
            'high': recent_high,
            'low': recent_low
        }
        
        return levels
    
    def check_price_near_fibonacci(self, price: float, fib_levels: dict, threshold: float = 0.005) -> tuple:
        """
        Проверка близости цены к уровням Фибоначчи.
        
        Returns:
            tuple: (находится_ли_у_фибо, уровень_фибо)
        """
        for fib_name, fib_level in fib_levels.items():
            if fib_name in ['high', 'low']:
                continue
            if abs(price - fib_level) / fib_level < threshold:
                return True, fib_name
        return False, None
    
    def get_current_indicators(self, df: pd.DataFrame) -> dict:
        """
        Получение текущих значений индикаторов.
        
        Returns:
            dict: Текущие значения индикаторов
        """
        if len(df) < max(self.ema_slow_period, self.channel_period):
            return {}
        
        last_row = df.iloc[-1]
        
        return {
            'EMA9': float(last_row['EMA9']) if 'EMA9' in last_row else 0,
            'EMA21': float(last_row['EMA21']) if 'EMA21' in last_row else 0,
            'RSI': float(last_row['RSI']) if 'RSI' in last_row else 50,
            'WilliamsR': float(last_row['WilliamsR']) if 'WilliamsR' in last_row else -50,
            'ATR': float(last_row['ATR']) if 'ATR' in last_row else 0,
            'close': float(last_row['close']),
        }
    
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
    
    def check_ema_crossover_flexible(self, df: pd.DataFrame, side: str) -> bool:
        """
        Гибкая проверка EMA crossover.
        
        Для LONG: EMA9 была ниже EMA21 последние 2-3 свечи, сейчас выше или очень близко
        Для SHORT: EMA9 была выше EMA21 последние 2-3 свечи, сейчас ниже или очень близко
        """
        if len(df) < 4:
            return False
        
        last_3_rows = df.tail(3)
        
        if side == 'LONG':
            # Проверяем что EMA9 была ниже EMA21 в предыдущих свечах
            prev_rows_lower = (last_3_rows.iloc[:-1]['EMA9'] < last_3_rows.iloc[:-1]['EMA21']).all()
            # Сейчас EMA9 выше или очень близко к EMA21
            current_close = abs(last_3_rows.iloc[-1]['EMA9'] - last_3_rows.iloc[-1]['EMA21']) / last_3_rows.iloc[-1]['EMA21'] < 0.003
            current_above = last_3_rows.iloc[-1]['EMA9'] >= last_3_rows.iloc[-1]['EMA21']
            
            return prev_rows_lower and (current_above or current_close)
        
        elif side == 'SHORT':
            # Проверяем что EMA9 была выше EMA21 в предыдущих свечах
            prev_rows_higher = (last_3_rows.iloc[:-1]['EMA9'] > last_3_rows.iloc[:-1]['EMA21']).all()
            # Сейчас EMA9 ниже или очень близко к EMA21
            current_close = abs(last_3_rows.iloc[-1]['EMA9'] - last_3_rows.iloc[-1]['EMA21']) / last_3_rows.iloc[-1]['EMA21'] < 0.003
            current_below = last_3_rows.iloc[-1]['EMA9'] <= last_3_rows.iloc[-1]['EMA21']
            
            return prev_rows_higher and (current_below or current_close)
        
        return False
    
    def check_long_signal(self, df: pd.DataFrame, upper_bound: float, lower_bound: float) -> Optional[SignalResult]:
        """
        Проверка сигнала на LONG.
        
        МИНИМАЛЬНЫЕ ТРЕБОВАНИЯ (нужно 2 из 3):
        1. Цена у нижней границы канала
        2. RSI < 30 (перепроданность)
        3. Williams %R < -80 (перепроданность)
        
        ПОДТВЕРЖДАЮЩИЕ СИГНАЛЫ (повышают надежность):
        4. EMA crossover (гибкая проверка)
        5. Объем увеличился
        6. Цена у уровня Фибоначчи
        
        ВХОД: минимум 2 основных требования + хотя бы 1 подтверждение
        """
        last_row = df.iloc[-1]
        current_price = last_row['close']
        rsi = last_row['RSI']
        williams_r = last_row['WilliamsR']
        volume_curr = last_row['volume']
        volume_avg = df['volume'].tail(20).mean()
        # Расчет уровней Фибоначчи
        fib_levels = self.calculate_fibonacci_levels(df['high'], df['low'], 20)
        near_fib, fib_name = self.check_price_near_fibonacci(current_price, fib_levels)
        
        # ОСНОВНЫЕ требования (минимум 2 из 3)
        main_conditions = {
            'near_lower_bound': abs(current_price - lower_bound) / lower_bound < 0.005,
            'rsi_oversold': rsi < 30,
            'williams_oversold': williams_r < -80,
        }
        main_met = sum(main_conditions.values())
        
        # ПОДТВЕРЖДАЮЩИЕ сигналы (повышают надежность)
        confirm_conditions = {
            'ema_crossover': self.check_ema_crossover_flexible(df, 'LONG'),
            'volume_increase': volume_curr > volume_avg * 1.2,
            'near_fibonacci': near_fib
        }
        confirm_met = sum(confirm_conditions.values())
        
        # ВХОД: минимум 2 основных требования + хотя бы 1 подтверждение
        if main_met >= 2 and confirm_met >= 1:
            total_conditions = main_met + confirm_met
            confidence = (total_conditions / 6) * 100  # Максимум 6 условий
            
            stop_loss, take_profit = self.calculate_sl_tp_prices(current_price, 'LONG')
            
            reasons = []
            for key, value in {**main_conditions, **confirm_conditions}.items():
                if value:
                    reasons.append(key)
            
            reason = f"LONG сигнал: {', '.join(reasons)}"
            if near_fib:
                reason += f" (у {fib_name})"
            
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
        
        МИНИМАЛЬНЫЕ ТРЕБОВАНИЯ (нужно 2 из 3):
        1. Цена у верхней границы канала
        2. RSI > 70 (перекупленность)
        3. Williams %R > -20 (перекупленность)
        
        ПОДТВЕРЖДАЮЩИЕ СИГНАЛЫ (повышают надежность):
        4. EMA crossover (гибкая проверка)
        5. Объем увеличился
        6. Цена у уровня Фибоначчи
        
        ВХОД: минимум 2 основных требования + хотя бы 1 подтверждение
        """
        last_row = df.iloc[-1]
        current_price = last_row['close']
        rsi = last_row['RSI']
        williams_r = last_row['WilliamsR']
        volume_curr = last_row['volume']
        volume_avg = df['volume'].tail(20).mean()
        # Расчет уровней Фибоначчи
        fib_levels = self.calculate_fibonacci_levels(df['high'], df['low'], 20)
        near_fib, fib_name = self.check_price_near_fibonacci(current_price, fib_levels)
        
        # ОСНОВНЫЕ требования (минимум 2 из 3)
        main_conditions = {
            'near_upper_bound': abs(current_price - upper_bound) / upper_bound < 0.005,
            'rsi_overbought': rsi > 70,
            'williams_overbought': williams_r > -20,
        }
        main_met = sum(main_conditions.values())
        
        # ПОДТВЕРЖДАЮЩИЕ сигналы (повышают надежность)
        confirm_conditions = {
            'ema_crossover': self.check_ema_crossover_flexible(df, 'SHORT'),
            'volume_increase': volume_curr > volume_avg * 1.2,
            'near_fibonacci': near_fib
        }
        confirm_met = sum(confirm_conditions.values())
        
        # ВХОД: минимум 2 основных требования + хотя бы 1 подтверждение
        if main_met >= 2 and confirm_met >= 1:
            total_conditions = main_met + confirm_met
            confidence = (total_conditions / 6) * 100  # Максимум 6 условий
            
            stop_loss, take_profit = self.calculate_sl_tp_prices(current_price, 'SHORT')
            
            reasons = []
            for key, value in {**main_conditions, **confirm_conditions}.items():
                if value:
                    reasons.append(key)
            
            reason = f"SHORT сигнал: {', '.join(reasons)}"
            if near_fib:
                reason += f" (у {fib_name})"
            
            return SignalResult(
                signal='SHORT',
                entry_price=current_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                confidence=confidence,
                reason=reason
            )
        
        return None
    
    def analyze(self, df: pd.DataFrame, higher_timeframe_trend: Optional[Literal['BULLISH', 'BEARISH', 'NEUTRAL']] = None) -> Optional[SignalResult]:
        """
        Главный метод анализа рынка и генерации сигналов.
        
        Args:
            df: DataFrame с OHLCV данными (columns: open, high, low, close, volume)
            higher_timeframe_trend: Тренд с более высокого таймфрейма (1h) для фильтрации
            
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
        
        # Определение тренда на текущем таймфрейме
        trend = self.determine_trend(df)
        
        # МНОГОТАЙМФРЕЙМНЫЙ ФИЛЬТР: используем тренд старшего таймфрейма для определения направления торговли
        # Если есть тренд на старшем таймфрейме - используем его для фильтрации
        trading_trend = trend  # По умолчанию используем текущий тренд
        
        if higher_timeframe_trend:
            if higher_timeframe_trend == 'NEUTRAL':
                return None  # Не торгуем если старший таймфрейм в боковике
            
            # Используем старший таймфрейм для определения направления торговли
            trading_trend = higher_timeframe_trend
        
        if trend == 'NEUTRAL':
            return None  # Не торгуем в боковике
        
        # Построение канала (теперь всегда валидный)
        upper_bound, lower_bound, is_valid_channel = self.find_channel(
            df['high'], 
            df['low'], 
            self.channel_period
        )
        
        if not is_valid_channel:
            return None

        # Проверка сигналов в зависимости от тренда СТАРШЕГО таймфрейма (или текущего если его нет)
        if trading_trend == 'BULLISH':
            # В бычьем тренде ищем только LONG сигналы
            signal = self.check_long_signal(df, upper_bound, lower_bound)
            return signal
        
        elif trading_trend == 'BEARISH':
            # В медвежьем тренде ищем только SHORT сигналы
            signal = self.check_short_signal(df, upper_bound, lower_bound)
            return signal
        
        return None
    
    def analyze_detailed(self, df: pd.DataFrame) -> Dict:
        """
        Детальный анализ для отладки - возвращает информацию о проверке условий.
        
        Returns:
            dict с информацией о текущем состоянии анализа
        """
        result = {
            'trend': None,
            'channel_valid': False,
            'conditions_checked': {},
            'conditions_met': 0,
            'total_conditions': 5,
            'current_price': 0,
            'indicators': {},
            'reason_no_signal': ''
        }
        
        if len(df) < max(self.ema_slow_period, self.channel_period, self.rsi_period, self.williams_r_period):
            result['reason_no_signal'] = 'Недостаточно данных'
            return result
        
        # Расчет индикаторов
        df['EMA9'] = self.calculate_ema(df['close'], self.ema_fast_period)
        df['EMA21'] = self.calculate_ema(df['close'], self.ema_slow_period)
        df['RSI'] = self.calculate_rsi(df['close'], self.rsi_period)
        df['WilliamsR'] = self.calculate_williams_r(df['high'], df['low'], df['close'], self.williams_r_period)
        df['ATR'] = self.calculate_atr(df['high'], df['low'], df['close'], self.atr_period)
        
        last_row = df.iloc[-1]
        result['current_price'] = float(last_row['close'])
        result['indicators'] = {
            'EMA9': float(last_row['EMA9']) if 'EMA9' in last_row else 0,
            'EMA21': float(last_row['EMA21']) if 'EMA21' in last_row else 0,
            'RSI': float(last_row['RSI']) if 'RSI' in last_row else 50,
            'WilliamsR': float(last_row['WilliamsR']) if 'WilliamsR' in last_row else -50,
            'ATR': float(last_row['ATR']) if 'ATR' in last_row else 0,
        }
        
        # Определение тренда
        trend = self.determine_trend(df)
        result['trend'] = trend
        
        if trend == 'NEUTRAL':
            result['reason_no_signal'] = 'Боковик - не торгуем в нейтральном тренде'
            return result
        
        # Построение канала
        upper_bound, lower_bound, is_valid_channel = self.find_channel(
            df['high'], 
            df['low'], 
            self.channel_period
        )
        
        result['channel_valid'] = is_valid_channel
        result['channel_upper'] = float(upper_bound) if is_valid_channel else 0
        result['channel_lower'] = float(lower_bound) if is_valid_channel else 0

        if not is_valid_channel:
            result['reason_no_signal'] = 'Канал невалиден: недостаточно касаний или слишком узкий диапазон'
            return result
        
        # Проверяем условия для ОБОИХ направлений (новая система)
        long_conditions = self._check_long_conditions_detailed(df, upper_bound, lower_bound)
        short_conditions = self._check_short_conditions_detailed(df, upper_bound, lower_bound)
        
        # Разделяем на основные требования и подтверждения
        long_main = sum([v for k, v in long_conditions.items() if k in ['near_lower_bound', 'rsi_oversold', 'williams_oversold']])
        long_confirm = sum([v for k, v in long_conditions.items() if k in ['ema_crossover', 'volume_increase', 'near_fibonacci']])
        long_total = long_main + long_confirm
        
        short_main = sum([v for k, v in short_conditions.items() if k in ['near_upper_bound', 'rsi_overbought', 'williams_overbought']])
        short_confirm = sum([v for k, v in short_conditions.items() if k in ['ema_crossover', 'volume_increase', 'near_fibonacci']])
        short_total = short_main + short_confirm
        
        result['long_conditions'] = long_conditions
        result['long_main_met'] = long_main
        result['long_confirm_met'] = long_confirm
        result['long_conditions_met'] = long_total
        
        result['short_conditions'] = short_conditions
        result['short_main_met'] = short_main
        result['short_confirm_met'] = short_confirm
        result['short_conditions_met'] = short_total
        
        # Определяем какой сигнал ищем в зависимости от тренда
        if trend == 'BULLISH':
            result['conditions_checked'] = long_conditions
            result['conditions_met'] = long_total
            result['signal_type'] = 'LONG'
            if long_main >= 2 and long_confirm >= 1:
                result['reason_no_signal'] = 'LONG сигнал найден!'
            else:
                result['reason_no_signal'] = f"В бычьем тренде ищем LONG. Основных: {long_main}/3, подтверждений: {long_confirm}/3 (нужно минимум 2+1)"
        elif trend == 'BEARISH':
            result['conditions_checked'] = short_conditions
            result['conditions_met'] = short_total
            result['signal_type'] = 'SHORT'
            if short_main >= 2 and short_confirm >= 1:
                result['reason_no_signal'] = 'SHORT сигнал найден!'
            else:
                result['reason_no_signal'] = f"В медвежьем тренде ищем SHORT. Основных: {short_main}/3, подтверждений: {short_confirm}/3 (нужно минимум 2+1)"
        
        return result
    
    def _check_long_conditions_detailed(self, df: pd.DataFrame, upper_bound: float, lower_bound: float) -> Dict[str, bool]:
        """Детальная проверка условий для LONG сигнала"""
        last_row = df.iloc[-1]
        current_price = last_row['close']
        rsi = last_row['RSI']
        williams_r = last_row['WilliamsR']
        volume_curr = last_row['volume']
        volume_avg = df['volume'].tail(20).mean()
        
        # Расчет Фибоначчи
        fib_levels = self.calculate_fibonacci_levels(df['high'], df['low'], 20)
        near_fib, _ = self.check_price_near_fibonacci(current_price, fib_levels)
        
        # ОСНОВНЫЕ требования
        main = {
            'near_lower_bound': abs(current_price - lower_bound) / lower_bound < 0.005,
            'rsi_oversold': rsi < 30,
            'williams_oversold': williams_r < -80,
        }
        
        # ПОДТВЕРЖДАЮЩИЕ сигналы
        confirm = {
            'ema_crossover': self.check_ema_crossover_flexible(df, 'LONG'),
            'volume_increase': volume_curr > volume_avg * 1.2,
            'near_fibonacci': near_fib
        }
        
        return {**main, **confirm}
    
    def _check_short_conditions_detailed(self, df: pd.DataFrame, upper_bound: float, lower_bound: float) -> Dict[str, bool]:
        """Детальная проверка условий для SHORT сигнала"""
        last_row = df.iloc[-1]
        current_price = last_row['close']
        rsi = last_row['RSI']
        williams_r = last_row['WilliamsR']
        volume_curr = last_row['volume']
        volume_avg = df['volume'].tail(20).mean()
        
        # Расчет Фибоначчи
        fib_levels = self.calculate_fibonacci_levels(df['high'], df['low'], 20)
        near_fib, _ = self.check_price_near_fibonacci(current_price, fib_levels)
        
        # ОСНОВНЫЕ требования
        main = {
            'near_upper_bound': abs(current_price - upper_bound) / upper_bound < 0.005,
            'rsi_overbought': rsi > 70,
            'williams_overbought': williams_r > -20,
        }
        
        # ПОДТВЕРЖДАЮЩИЕ сигналы
        confirm = {
            'ema_crossover': self.check_ema_crossover_flexible(df, 'SHORT'),
            'volume_increase': volume_curr > volume_avg * 1.2,
            'near_fibonacci': near_fib
        }
        
        return {**main, **confirm}

# Автоматическая регистрация стратегии
from .strategy_registry import StrategyRegistry
StrategyRegistry.register(MainStrategy)
