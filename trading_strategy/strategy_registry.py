"""
Реестр всех доступных стратегий.
Новые стратегии автоматически регистрируются при импорте.
"""

from typing import Dict, Type
from .base_strategy import BaseStrategy


class StrategyRegistry:
    """Реестр стратегий"""
    
    _strategies: Dict[str, Type[BaseStrategy]] = {}
    
    @classmethod
    def register(cls, strategy_class: Type[BaseStrategy]):
        """
        Регистрация стратегии.
        
        Args:
            strategy_class: Класс стратегии (должен наследоваться от BaseStrategy)
        """
        if not issubclass(strategy_class, BaseStrategy):
            raise ValueError(f"Стратегия {strategy_class.__name__} должна наследоваться от BaseStrategy")
        
        # Создаем временный экземпляр для получения имени
        temp_instance = strategy_class()
        strategy_name = temp_instance.name
        
        cls._strategies[strategy_name] = strategy_class
        print(f"✅ Зарегистрирована стратегия: {strategy_name}")
    
    @classmethod
    def get_strategy(cls, name: str, **kwargs) -> BaseStrategy:
        """
        Получить экземпляр стратегии по имени.
        
        Args:
            name: Название стратегии
            **kwargs: Параметры для инициализации стратегии
            
        Returns:
            Экземпляр стратегии
        """
        if name not in cls._strategies:
            raise ValueError(f"Стратегия '{name}' не найдена. Доступные: {list(cls._strategies.keys())}")
        
        return cls._strategies[name](**kwargs)
    
    @classmethod
    def list_strategies(cls) -> Dict[str, str]:
        """
        Получить список всех зарегистрированных стратегий.
        
        Returns:
            dict: {название: описание}
        """
        result = {}
        for name, strategy_class in cls._strategies.items():
            temp_instance = strategy_class()
            result[name] = temp_instance.description
        return result
    
    @classmethod
    def is_registered(cls, name: str) -> bool:
        """Проверить, зарегистрирована ли стратегия"""
        return name in cls._strategies


# Автоматический импорт всех стратегий для регистрации
def _auto_register_strategies():
    """Автоматическая регистрация всех стратегий при импорте модуля"""
    try:
        # Импортируем стратегии - они автоматически регистрируются при импорте
        from .main_strategy import MainStrategy  # Основная стратегия
        from .scalping_strategy import ScalpingStrategy  # Скальпинг стратегия
        # Добавьте импорты других стратегий здесь:
        # from .your_strategy import YourStrategy
    except ImportError as e:
        print(f"⚠️ Предупреждение при загрузке стратегий: {e}")


# Автоматически регистрируем стратегии при импорте модуля
_auto_register_strategies()

