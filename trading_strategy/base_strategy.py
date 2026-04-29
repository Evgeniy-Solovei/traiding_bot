"""
Базовый класс для всех торговых стратегий.
Все стратегии должны наследоваться от этого класса.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Literal
from dataclasses import dataclass
import pandas as pd


@dataclass
class SignalResult:
    """Результат анализа сигнала"""
    signal: Optional[Literal['LONG', 'SHORT']]
    entry_price: float
    stop_loss: float
    take_profit: float
    confidence: float  # Уверенность в сигнале 0-100%
    reason: str  # Причина сигнала


class BaseStrategy(ABC):
    """
    Базовый класс для всех торговых стратегий.
    
    Каждая стратегия должна реализовать методы:
    - analyze() - основной анализ и генерация сигналов
    - analyze_detailed() - детальный анализ для отображения
    """
    
    def __init__(self, **kwargs):
        """Инициализация стратегии с параметрами"""
        pass
    
    @abstractmethod
    def analyze(
        self, 
        df: pd.DataFrame, 
        higher_timeframe_trend: Optional[Literal['BULLISH', 'BEARISH', 'NEUTRAL']] = None
    ) -> Optional[SignalResult]:
        """
        Главный метод анализа рынка и генерации сигналов.
        
        Args:
            df: DataFrame с OHLCV данными (columns: open, high, low, close, volume)
            higher_timeframe_trend: Тренд с более высокого таймфрейма для фильтрации
            
        Returns:
            SignalResult или None если сигнала нет
        """
        pass
    
    @abstractmethod
    def analyze_detailed(self, df: pd.DataFrame) -> Dict:
        """
        Детальный анализ для отладки - возвращает информацию о проверке условий.
        
        Returns:
            dict с информацией о текущем состоянии анализа
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Название стратегии"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Описание стратегии"""
        pass

