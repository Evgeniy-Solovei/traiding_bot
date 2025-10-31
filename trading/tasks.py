"""
Celery задачи для автоматической торговли.
"""

from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
import asyncio
import pandas as pd
from typing import Optional

from .models import (
    Exchange, UserTradingSettings, TradingPair, 
    Trade, TradingStatistics
)
from .strategy import TradingStrategy, SignalResult
from .exchange_client import BybitClient
from .risk_manager import calculate_position_for_signal
from .encryption import decrypt_api_credentials


@shared_task
def monitor_market(timeframe: str = '5m'):
    """
    Мониторинг рынка для всех активных пользователей.
    Анализирует сигналы и открывает позиции при необходимости.
    
    Args:
        timeframe: Таймфрейм для анализа
    """
    # Получаем всех пользователей с активной торговлей
    active_users = User.objects.filter(
        trading_settings__is_trading_active=True
    ).select_related('trading_settings')
    
    for user in active_users:
        try:
            # Получаем торговые пары пользователя
            trading_pairs = TradingPair.objects.filter(
                user=user,
                is_active=True
            )
            
            for pair in trading_pairs:
                # Проверяем, есть ли открытая позиция
                open_trade = Trade.objects.filter(
                    user=user,
                    symbol=pair.symbol,
                    status='open'
                ).first()
                
                if open_trade:
                    continue  # Уже есть открытая позиция, пропускаем
                
                # Анализируем рынок
                asyncio.run(analyze_and_trade(user, pair.symbol, timeframe))
                
        except Exception as e:
            print(f"Ошибка мониторинга для {user.username}: {str(e)}")


async def analyze_and_trade(user: User, symbol: str, timeframe: str):
    """
    Анализ рынка и открытие позиции если есть сигнал.
    
    Args:
        user: Пользователь
        symbol: Торговая пара
        timeframe: Таймфрейм
    """
    try:
        # Получаем биржу пользователя
        exchange = Exchange.objects.filter(user=user, is_active=True).first()
        if not exchange:
            return
        
        # Дешифруем API ключи
        api_key, api_secret = decrypt_api_credentials(
            exchange.api_key_encrypted,
            exchange.api_secret_encrypted
        )
        
        # Создаем клиента биржи
        client = BybitClient(api_key, api_secret, exchange.is_testnet)
        
        try:
            # Получаем исторические данные
            # CCXT использует формат 'BTC/USDT' вместо 'BTCUSDT'
            ccxt_symbol = symbol.replace('USDT', '/USDT')
            df = await client.fetch_ohlcv(ccxt_symbol, timeframe, limit=100)
            
            if df.empty:
                return
            
            # Получаем настройки торговли
            settings = user.trading_settings
            
            # Создаем стратегию
            strategy = TradingStrategy(
                ema_fast_period=settings.ema_fast_period,
                ema_slow_period=settings.ema_slow_period,
                rsi_period=settings.rsi_period,
                williams_r_period=settings.williams_r_period,
                channel_period=settings.channel_period,
                atr_period=settings.atr_period,
                stop_loss_atr_multiplier=float(settings.stop_loss_atr_multiplier),
                take_profit_atr_multiplier=float(settings.take_profit_atr_multiplier)
            )
            
            # Анализ рынка
            signal = strategy.analyze(df)
            
            if signal and signal.signal:
                # Получаем баланс
                balance_data = await client.get_balance()
                usdt_balance = Decimal(str(balance_data.get('USDT', {}).get('free', 0)))
                
                if usdt_balance < Decimal('5.0'):
                    print(f"Недостаточный баланс у {user.username}: ${usdt_balance}")
                    return
                
                # Рассчитываем размер позиции
                position_info = calculate_position_for_signal(
                    balance=usdt_balance,
                    risk_per_trade=settings.risk_per_trade,
                    base_order_size=settings.base_order_size,
                    leverage=settings.leverage,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    side=signal.signal.lower()
                )
                
                if not position_info['is_valid']:
                    print(f"Невалидная позиция: {position_info['validation_message']}")
                    return
                
                # Устанавливаем плечо
                await client.set_leverage(ccxt_symbol, settings.leverage)
                
                # Открываем позицию
                side_map = {'LONG': 'buy', 'SHORT': 'sell'}
                order = await client.create_market_order(
                    symbol=ccxt_symbol,
                    side=side_map[signal.signal],
                    amount=position_info['quantity']
                )
                
                # Сохраняем сделку в БД
                trade = Trade.objects.create(
                    user=user,
                    exchange=exchange,
                    symbol=symbol,
                    side=signal.signal.lower(),
                    entry_price=Decimal(str(signal.entry_price)),
                    quantity=Decimal(str(position_info['quantity'])),
                    leverage=settings.leverage,
                    stop_loss=Decimal(str(signal.stop_loss)),
                    take_profit=Decimal(str(signal.take_profit)),
                    order_id=order.get('id', ''),
                    status='open',
                    notes=signal.reason
                )
                
                # Отправляем уведомление в Telegram
                from bot.notifications import send_trade_notification
                asyncio.create_task(
                    send_trade_notification(user, trade, 'opened')
                )
                
                print(f"✅ Открыта позиция {signal.signal} {symbol} для {user.username}")
                
        finally:
            await client.close()
            
    except Exception as e:
        print(f"Ошибка анализа и торговли: {str(e)}")


@shared_task
def check_open_positions():
    """
    Проверка открытых позиций и закрытие при достижении SL/TP.
    """
    open_trades = Trade.objects.filter(status='open').select_related('user', 'exchange')
    
    for trade in open_trades:
        try:
            asyncio.run(check_and_close_position(trade))
        except Exception as e:
            print(f"Ошибка проверки позиции {trade.id}: {str(e)}")


async def check_and_close_position(trade: Trade):
    """
    Проверка и закрытие позиции при необходимости.
    
    Args:
        trade: Открытая сделка
    """
    try:
        # Получаем биржу
        exchange = trade.exchange
        if not exchange:
            return
        
        # Дешифруем API ключи
        api_key, api_secret = decrypt_api_credentials(
            exchange.api_key_encrypted,
            exchange.api_secret_encrypted
        )
        
        # Создаем клиента
        client = BybitClient(api_key, api_secret, exchange.is_testnet)
        
        try:
            # Получаем текущую цену
            ccxt_symbol = trade.symbol.replace('USDT', '/USDT')
            ticker = await client.get_ticker(ccxt_symbol)
            current_price = ticker['last']
            
            should_close = False
            close_reason = ""
            
            # Проверка стоп-лосса и тейк-профита
            if trade.side == 'long':
                if current_price <= float(trade.stop_loss):
                    should_close = True
                    close_reason = f"Стоп-лосс достигнут: ${current_price} <= ${trade.stop_loss}"
                elif current_price >= float(trade.take_profit):
                    should_close = True
                    close_reason = f"Тейк-профит достигнут: ${current_price} >= ${trade.take_profit}"
            
            else:  # short
                if current_price >= float(trade.stop_loss):
                    should_close = True
                    close_reason = f"Стоп-лосс достигнут: ${current_price} >= ${trade.stop_loss}"
                elif current_price <= float(trade.take_profit):
                    should_close = True
                    close_reason = f"Тейк-профит достигнут: ${current_price} <= ${trade.take_profit}"
            
            if should_close:
                # Закрываем позицию
                await client.close_position(ccxt_symbol)
                
                # Обновляем сделку
                trade.exit_price = Decimal(str(current_price))
                trade.status = 'closed'
                trade.closed_at = timezone.now()
                trade.notes += f"\n{close_reason}"
                trade.calculate_pnl()
                trade.save()
                
                # Обновляем статистику
                update_user_statistics_for_user(trade.user)
                
                # Отправляем уведомление
                from bot.notifications import send_trade_notification
                asyncio.create_task(
                    send_trade_notification(trade.user, trade, 'closed')
                )
                
                print(f"✅ Закрыта позиция {trade.side} {trade.symbol} для {trade.user.username}")
                print(f"   PnL: ${trade.pnl} ({trade.pnl_percent}%)")
                
        finally:
            await client.close()
            
    except Exception as e:
        print(f"Ошибка закрытия позиции: {str(e)}")


@shared_task
def update_user_statistics():
    """
    Обновление статистики для всех пользователей.
    """
    users = User.objects.filter(trades__isnull=False).distinct()
    
    for user in users:
        try:
            update_user_statistics_for_user(user)
        except Exception as e:
            print(f"Ошибка обновления статистики для {user.username}: {str(e)}")


def update_user_statistics_for_user(user: User):
    """
    Обновление статистики для конкретного пользователя.
    
    Args:
        user: Пользователь
    """
    stats, created = TradingStatistics.objects.get_or_create(user=user)
    stats.update_statistics()
    print(f"📊 Обновлена статистика для {user.username}")


@shared_task
def close_position_manually(trade_id: int):
    """
    Ручное закрытие позиции по ID.
    
    Args:
        trade_id: ID сделки
    """
    try:
        trade = Trade.objects.get(id=trade_id, status='open')
        asyncio.run(check_and_close_position(trade))
    except Trade.DoesNotExist:
        print(f"Сделка {trade_id} не найдена или уже закрыта")
    except Exception as e:
        print(f"Ошибка ручного закрытия позиции {trade_id}: {str(e)}")
