"""
Клиент для работы с биржей Bybit через ccxt.
Асинхронное взаимодействие с API биржи.
"""

import ccxt.async_support as ccxt
import pandas as pd
from typing import Optional, Dict, List
from decimal import Decimal
import asyncio
from django.conf import settings


class BybitClient:
    """
    Асинхронный клиент для работы с Bybit.
    """
    
    def __init__(self, api_key: str, api_secret: str, testnet: bool = True):
        """
        Инициализация клиента Bybit.
        
        Args:
            api_key: API ключ
            api_secret: API секрет
            testnet: Использовать тестовую сеть
        """
        self.exchange = ccxt.bybit({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'future',  # Используем фьючерсы
                'recvWindow': 60000,
            }
        })
        
        if testnet:
            self.exchange.set_sandbox_mode(True)
        
        self.testnet = testnet
    
    async def close(self):
        """Закрытие соединения"""
        await self.exchange.close()
    
    async def fetch_ohlcv(self, symbol: str, timeframe: str = '5m', limit: int = 100) -> pd.DataFrame:
        """
        Получение OHLCV данных (свечей).
        
        Args:
            symbol: Торговая пара (например 'BTC/USDT')
            timeframe: Таймфрейм ('1m', '5m', '15m', '1h', '4h', '1d')
            limit: Количество свечей
            
        Returns:
            DataFrame с колонками: timestamp, open, high, low, close, volume
        """
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            
            df = pd.DataFrame(
                ohlcv, 
                columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
            )
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            return df
            
        except Exception as e:
            raise Exception(f"Ошибка получения OHLCV: {str(e)}")
    
    async def get_balance(self) -> Dict:
        """
        Получение баланса аккаунта.
        
        Returns:
            dict: Баланс по валютам
        """
        try:
            balance = await self.exchange.fetch_balance()
            return balance
        except Exception as e:
            raise Exception(f"Ошибка получения баланса: {str(e)}")
    
    async def get_ticker(self, symbol: str) -> Dict:
        """
        Получение текущей цены и информации о символе.
        
        Args:
            symbol: Торговая пара
            
        Returns:
            dict: Информация о цене
        """
        try:
            ticker = await self.exchange.fetch_ticker(symbol)
            return ticker
        except Exception as e:
            raise Exception(f"Ошибка получения тикера: {str(e)}")
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """
        Установка плеча для символа.
        
        Args:
            symbol: Торговая пара
            leverage: Размер плеча (1-100)
            
        Returns:
            bool: Успешность операции
        """
        try:
            await self.exchange.set_leverage(leverage, symbol)
            return True
        except Exception as e:
            raise Exception(f"Ошибка установки плеча: {str(e)}")
    
    async def create_market_order(
        self, 
        symbol: str, 
        side: str, 
        amount: float,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Создание рыночного ордера.
        
        Args:
            symbol: Торговая пара
            side: 'buy' или 'sell'
            amount: Количество
            params: Дополнительные параметры
            
        Returns:
            dict: Информация об ордере
        """
        try:
            order = await self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                params=params or {}
            )
            return order
        except Exception as e:
            raise Exception(f"Ошибка создания ордера: {str(e)}")
    
    async def create_limit_order(
        self, 
        symbol: str, 
        side: str, 
        amount: float,
        price: float,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Создание лимитного ордера.
        
        Args:
            symbol: Торговая пара
            side: 'buy' или 'sell'
            amount: Количество
            price: Цена
            params: Дополнительные параметры
            
        Returns:
            dict: Информация об ордере
        """
        try:
            order = await self.exchange.create_order(
                symbol=symbol,
                type='limit',
                side=side,
                amount=amount,
                price=price,
                params=params or {}
            )
            return order
        except Exception as e:
            raise Exception(f"Ошибка создания лимитного ордера: {str(e)}")
    
    async def create_stop_loss_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        stop_price: float,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Создание стоп-лосс ордера.
        
        Args:
            symbol: Торговая пара
            side: 'buy' или 'sell'
            amount: Количество
            stop_price: Цена срабатывания стоп-лосса
            params: Дополнительные параметры
            
        Returns:
            dict: Информация об ордере
        """
        try:
            params = params or {}
            params.update({
                'stopPrice': stop_price,
                'triggerBy': 'LastPrice'
            })
            
            order = await self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                params=params
            )
            return order
        except Exception as e:
            raise Exception(f"Ошибка создания стоп-лосс ордера: {str(e)}")
    
    async def create_take_profit_order(
        self,
        symbol: str,
        side: str,
        amount: float,
        take_profit_price: float,
        params: Optional[Dict] = None
    ) -> Dict:
        """
        Создание тейк-профит ордера.
        
        Args:
            symbol: Торговая пара
            side: 'buy' или 'sell'
            amount: Количество
            take_profit_price: Цена срабатывания тейк-профита
            params: Дополнительные параметры
            
        Returns:
            dict: Информация об ордере
        """
        try:
            params = params or {}
            params.update({
                'takeProfit': take_profit_price,
                'triggerBy': 'LastPrice'
            })
            
            order = await self.exchange.create_order(
                symbol=symbol,
                type='market',
                side=side,
                amount=amount,
                params=params
            )
            return order
        except Exception as e:
            raise Exception(f"Ошибка создания тейк-профит ордера: {str(e)}")
    
    async def get_position(self, symbol: str) -> Optional[Dict]:
        """
        Получение информации о текущей позиции.
        
        Args:
            symbol: Торговая пара
            
        Returns:
            dict или None: Информация о позиции
        """
        try:
            positions = await self.exchange.fetch_positions([symbol])
            
            for position in positions:
                if position['symbol'] == symbol and float(position['contracts']) > 0:
                    return position
            
            return None
        except Exception as e:
            raise Exception(f"Ошибка получения позиции: {str(e)}")
    
    async def close_position(self, symbol: str) -> Dict:
        """
        Закрытие текущей позиции по рынку.
        
        Args:
            symbol: Торговая пара
            
        Returns:
            dict: Информация об ордере закрытия
        """
        try:
            position = await self.get_position(symbol)
            
            if not position:
                raise Exception("Нет открытой позиции")
            
            side = 'sell' if position['side'] == 'long' else 'buy'
            amount = float(position['contracts'])
            
            order = await self.create_market_order(
                symbol=symbol,
                side=side,
                amount=amount,
                params={'reduceOnly': True}
            )
            
            return order
        except Exception as e:
            raise Exception(f"Ошибка закрытия позиции: {str(e)}")
    
    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """
        Отмена ордера.
        
        Args:
            order_id: ID ордера
            symbol: Торговая пара
            
        Returns:
            bool: Успешность операции
        """
        try:
            await self.exchange.cancel_order(order_id, symbol)
            return True
        except Exception as e:
            raise Exception(f"Ошибка отмены ордера: {str(e)}")
    
    async def get_open_orders(self, symbol: str) -> List[Dict]:
        """
        Получение списка открытых ордеров.
        
        Args:
            symbol: Торговая пара
            
        Returns:
            list: Список ордеров
        """
        try:
            orders = await self.exchange.fetch_open_orders(symbol)
            return orders
        except Exception as e:
            raise Exception(f"Ошибка получения открытых ордеров: {str(e)}")


async def test_connection(api_key: str, api_secret: str, testnet: bool = True) -> Dict:
    """
    Тестирование подключения к Bybit.
    
    Args:
        api_key: API ключ
        api_secret: API секрет
        testnet: Использовать тестовую сеть
        
    Returns:
        dict: Результат тестирования
    """
    client = BybitClient(api_key, api_secret, testnet)
    
    try:
        balance = await client.get_balance()
        
        result = {
            'success': True,
            'message': 'Подключение успешно',
            'balance': balance.get('USDT', {}).get('free', 0) if balance else 0
        }
    except Exception as e:
        result = {
            'success': False,
            'message': f'Ошибка подключения: {str(e)}',
            'balance': 0
        }
    finally:
        await client.close()
    
    return result
