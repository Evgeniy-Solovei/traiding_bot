"""
Celery задачи для автоматической торговли.
"""

from celery import shared_task
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timezone as dt_timezone
import asyncio
import pandas as pd
from typing import Optional

from .models import (
    Exchange, UserTradingSettings, TradingPair, 
    Trade, TradingStatistics, SignalHistory
)
from .base_strategy import SignalResult
from .main_strategy import MainStrategy  # Для временного использования в анализе тренда
from .exchange_client import BybitClient
from .encryption import decrypt_api_credentials

MIN_ORDER_SIZE_USD = Decimal('1.0')
TIMEFRAME_TO_SECONDS = {
    '1m': 60,
    '3m': 180,
    '5m': 300,
    '15m': 900,
    '30m': 1800,
    '1h': 3600,
    '4h': 14400,
    '1d': 86400,
}


def resolve_order_size_usd(settings: UserTradingSettings, _usdt_balance: Decimal | None = None) -> Decimal:
    """
    Возвращает фиксированный размер ордера в USD.
    """
    return settings.base_order_size.quantize(Decimal('0.01'))


def trim_unclosed_candle(df: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """
    Удаляет последнюю свечу, если она еще формируется.
    Это снижает риск "перерисовки" сигналов.
    """
    if df.empty or len(df) < 2 or 'timestamp' not in df.columns:
        return df

    timeframe_seconds = TIMEFRAME_TO_SECONDS.get(timeframe)
    if not timeframe_seconds:
        return df

    last_candle_ts = pd.Timestamp(df.iloc[-1]['timestamp']).to_pydatetime()
    if last_candle_ts.tzinfo is None:
        last_candle_ts = last_candle_ts.replace(tzinfo=dt_timezone.utc)

    now_utc = datetime.now(dt_timezone.utc)
    candle_age_seconds = (now_utc - last_candle_ts).total_seconds()

    if candle_age_seconds < timeframe_seconds:
        return df.iloc[:-1].copy()
    return df


def extract_order_execution_price(order: Optional[dict], fallback_price: float) -> float:
    """
    Извлекает фактическую цену исполнения ордера.
    """
    if not order:
        return fallback_price

    for key in ('average', 'price'):
        value = order.get(key)
        if value:
            try:
                parsed = float(value)
                if parsed > 0:
                    return parsed
            except (TypeError, ValueError):
                continue

    cost = order.get('cost')
    filled = order.get('filled')
    try:
        if cost is not None and filled is not None and float(filled) > 0:
            return float(cost) / float(filled)
    except (TypeError, ValueError, ZeroDivisionError):
        pass

    trades = order.get('trades') or []
    if trades:
        weighted_sum = 0.0
        total_amount = 0.0
        for trade in trades:
            try:
                trade_price = float(trade.get('price', 0))
                trade_amount = float(trade.get('amount', 0))
            except (TypeError, ValueError):
                continue
            if trade_price > 0 and trade_amount > 0:
                weighted_sum += trade_price * trade_amount
                total_amount += trade_amount
        if total_amount > 0:
            return weighted_sum / total_amount

    return fallback_price


def extract_order_filled_amount(order: Optional[dict], fallback_amount: float) -> float:
    """
    Извлекает фактически исполненный объем ордера.
    """
    if not order:
        return fallback_amount

    for key in ('filled', 'amount'):
        value = order.get(key)
        if value:
            try:
                parsed = float(value)
                if parsed > 0:
                    return parsed
            except (TypeError, ValueError):
                continue

    return fallback_amount


def update_trade_pnl_fields(trade: Trade) -> None:
    """
    Пересчитывает PnL поля на объекте сделки без записи в БД.
    """
    if not trade.exit_price or trade.status != 'closed':
        return

    if trade.side == 'long':
        pnl_value = (trade.exit_price - trade.entry_price) * trade.quantity
    else:
        pnl_value = (trade.entry_price - trade.exit_price) * trade.quantity

    trade.pnl = pnl_value
    position_value = trade.entry_price * trade.quantity
    if position_value > 0:
        trade.pnl_percent = (pnl_value / position_value) * Decimal('100')
    else:
        trade.pnl_percent = Decimal('0')


def count_consecutive_losses(recent_pnls: list[Decimal]) -> int:
    """
    Считает длину текущей серии убыточных сделок (с конца истории).
    """
    streak = 0
    for pnl in recent_pnls:
        if pnl < 0:
            streak += 1
        else:
            break
    return streak


def is_daily_loss_limit_reached(
    daily_pnl: Decimal,
    current_balance: Decimal,
    daily_loss_limit_percent: Decimal,
    unrealized_pnl: Decimal = Decimal('0'),
) -> tuple[bool, Decimal]:
    """
    Проверяет, достигнут ли дневной лимит убытка.
    Возвращает (достигнут_ли_лимит, лимит_в_usd).
    """
    total_day_pnl = daily_pnl + unrealized_pnl
    estimated_day_start_equity = current_balance - total_day_pnl
    if estimated_day_start_equity <= 0:
        estimated_day_start_equity = max(current_balance, Decimal('1'))

    limit_usd = (estimated_day_start_equity * (daily_loss_limit_percent / Decimal('100'))).quantize(Decimal('0.01'))
    breached = total_day_pnl < 0 and abs(total_day_pnl) >= limit_usd
    return breached, limit_usd


async def evaluate_risk_guards(
    user: User,
    settings: UserTradingSettings,
    usdt_balance: Decimal,
    unrealized_pnl: Decimal = Decimal('0'),
) -> tuple[bool, str]:
    """
    Проверяет риск-стопы перед открытием новой позиции.
    """
    now = timezone.now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    daily_pnl = Decimal('0')
    daily_pnls_qs = Trade.objects.filter(
        user=user,
        status='closed',
        closed_at__gte=day_start
    ).values_list('pnl', flat=True)

    async for pnl in daily_pnls_qs:
        daily_pnl += pnl or Decimal('0')

    daily_limit_reached, daily_limit_usd = is_daily_loss_limit_reached(
        daily_pnl=daily_pnl,
        current_balance=usdt_balance,
        daily_loss_limit_percent=settings.daily_loss_limit_percent,
        unrealized_pnl=unrealized_pnl,
    )
    if daily_limit_reached:
        total_day_pnl = daily_pnl + unrealized_pnl
        return False, (
            f"Дневной лимит убытка достигнут: {total_day_pnl:.2f} USD "
            f"(закрытые: {daily_pnl:.2f}, unrealized: {unrealized_pnl:.2f}), "
            f"лимит -{daily_limit_usd:.2f} USD ({settings.daily_loss_limit_percent}%)."
        )

    recent_closed_qs = Trade.objects.filter(
        user=user,
        status='closed',
    ).order_by('-closed_at').values_list('pnl', flat=True)[: settings.max_consecutive_losses]

    recent_pnls = []
    async for pnl in recent_closed_qs:
        recent_pnls.append(pnl or Decimal('0'))

    losing_streak = count_consecutive_losses(recent_pnls)
    if losing_streak >= settings.max_consecutive_losses:
        return False, (
            f"Серия убыточных сделок: {losing_streak} подряд. "
            f"Лимит: {settings.max_consecutive_losses}."
        )

    return True, ''


async def apply_risk_pause(settings: UserTradingSettings, user: User, reason: str) -> None:
    """
    Ставит торговлю на паузу и отправляет уведомление пользователю.
    """
    if not settings.auto_pause_on_risk:
        return

    if settings.is_risk_paused and settings.risk_pause_reason == reason and not settings.is_trading_active:
        return

    settings.is_trading_active = False
    settings.is_risk_paused = True
    settings.risk_pause_reason = reason
    settings.risk_paused_at = timezone.now()
    await settings.asave(update_fields=[
        'is_trading_active',
        'is_risk_paused',
        'risk_pause_reason',
        'risk_paused_at',
        'updated_at',
    ])

    from bot.notifications import send_risk_pause_notification
    await send_risk_pause_notification(user, reason)


async def sync_signal_history_after_close(trade: Trade) -> None:
    """
    Синхронизирует результат закрытия сделки с последним открытым сигналом.
    """
    signal_history = await SignalHistory.objects.filter(
        user=trade.user,
        symbol=trade.symbol,
        signal=trade.side.upper(),
        was_opened=True,
        was_profitable__isnull=True
    ).order_by('-created_at').afirst()

    if not signal_history:
        return

    signal_history.was_profitable = trade.pnl > 0 if trade.pnl else False
    signal_history.actual_pnl = trade.pnl if trade.pnl else Decimal('0')
    await signal_history.asave()


async def finalize_trade_close(
    trade: Trade,
    exit_price: float,
    close_reason: str,
    notify: bool = True,
) -> None:
    """
    Закрывает сделку в БД, пересчитывает статистику и отправляет уведомление.
    """
    trade.exit_price = Decimal(str(exit_price))
    trade.status = 'closed'
    trade.closed_at = timezone.now()
    trade.notes = f"{(trade.notes or '').rstrip()}\n{close_reason}".strip()
    update_trade_pnl_fields(trade)
    await trade.asave()

    await sync_signal_history_after_close(trade)
    await asyncio.to_thread(update_user_statistics_for_user, trade.user)

    if notify:
        from bot.notifications import send_trade_notification
        await send_trade_notification(trade.user, trade, 'closed')


@shared_task
def monitor_market(timeframe: str = '5m'):
    """
    Мониторинг рынка для всех активных пользователей.
    Анализирует сигналы и открывает позиции при необходимости.
    
    Args:
        timeframe: Таймфрейм для анализа
    """
    asyncio.run(monitor_market_async(timeframe))


async def monitor_market_async(timeframe: str = '5m'):
    """
    Асинхронная версия мониторинга рынка.
    """
    # Получаем всех пользователей с активной торговлей (async итерация)
    active_users_qs = User.objects.filter(
        trading_settings__is_trading_active=True
    ).select_related('trading_settings')
    
    # Используем async for для итерации по QuerySet
    async for user in active_users_qs:
        try:
            # Получаем торговые пары пользователя (async)
            trading_pairs_qs = TradingPair.objects.filter(
                user=user,
                is_active=True
            )
            trading_pairs = [pair async for pair in trading_pairs_qs]
            
            if not trading_pairs:
                print(f"⚠️ У пользователя {user.username} нет активных торговых пар")
                continue
            
            print(f"📊 Мониторинг для {user.username}: {len(trading_pairs)} активных пар")
            
            for pair in trading_pairs:
                # Проверяем, есть ли открытая позиция (async)
                open_trade = await Trade.objects.filter(
                    user=user,
                    symbol=pair.symbol,
                    status='open'
                ).afirst()
                
                if open_trade:
                    continue  # Уже есть открытая позиция, пропускаем
                
                # Анализируем рынок (async)
                await analyze_and_trade(user, pair.symbol, timeframe)
                
        except Exception as e:
            print(f"Ошибка мониторинга для {user.username}: {str(e)}")
            import traceback
            traceback.print_exc()


async def fetch_market_data_public(symbol: str, timeframe: str = '5m', limit: int = 100):
    """
    Получение рыночных данных через публичный API (без авторизации).
    Используется для тестового режима.
    
    Args:
        symbol: Торговая пара (например 'BTCUSDT')
        timeframe: Таймфрейм
        limit: Количество свечей
        
    Returns:
        DataFrame с OHLCV данными
    """
    import ccxt.async_support as ccxt
    
    # Создаем клиент без авторизации для публичного API
    exchange = ccxt.bybit({
        'enableRateLimit': True,
        'options': {
            'defaultType': 'future',
        }
    })
    
    try:
        ccxt_symbol = symbol.replace('USDT', '/USDT')
        ohlcv = await exchange.fetch_ohlcv(ccxt_symbol, timeframe, limit=limit)
        
        df = pd.DataFrame(
            ohlcv, 
            columns=['timestamp', 'open', 'high', 'low', 'close', 'volume']
        )
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        
        return df
    except Exception as e:
        raise Exception(f"Ошибка получения публичных данных: {str(e)}")
    finally:
        await exchange.close()


async def analyze_and_trade(user: User, symbol: str, timeframe: str):
    """
    Анализ рынка и открытие позиции если есть сигнал.
    Поддерживает тестовый режим без API ключей.
    
    Args:
        user: Пользователь
        symbol: Торговая пара
        timeframe: Таймфрейм
    """
    try:
        # Получаем настройки торговли (async)
        settings = await UserTradingSettings.objects.aget(user=user)
        is_test_mode = settings.is_test_mode
        
        # Получаем биржу пользователя (если есть) - async
        exchange = await Exchange.objects.filter(user=user, is_active=True).afirst()
        
        # Получаем данные о рынке
        if is_test_mode or not exchange:
            # Тестовый режим: используем публичный API без авторизации
            print(f"🧪 Тестовый режим для {user.username}: получение данных по {symbol}")
            df = await fetch_market_data_public(symbol, timeframe, limit=100)
        else:
            # Реальный режим: используем авторизованный API
            api_key, api_secret = decrypt_api_credentials(
                exchange.api_key_encrypted,
                exchange.api_secret_encrypted
            )
            client = BybitClient(api_key, api_secret, exchange.is_testnet)
            
            try:
                ccxt_symbol = symbol.replace('USDT', '/USDT')
                df = await client.fetch_ohlcv(ccxt_symbol, timeframe, limit=100)
            finally:
                await client.close()

        # Работаем только по закрытым свечам, чтобы избежать "перерисовки" сигналов
        df = trim_unclosed_candle(df, timeframe)
        
        if df.empty:
            print(f"⚠️ Пустые данные для {symbol} у {user.username}")
            return
        
        print(f"📈 Получено {len(df)} свечей для {symbol} на {timeframe}")
        
        # МНОГОТАЙМФРЕЙМНЫЙ ФИЛЬТР: получаем данные с 1h таймфрейма
        higher_timeframe_trend = None
        if timeframe == '5m':
            # Для 5m проверяем тренд на 1h
            if is_test_mode or not exchange:
                df_1h = await fetch_market_data_public(symbol, '1h', limit=100)
            else:
                api_key, api_secret = decrypt_api_credentials(
                    exchange.api_key_encrypted,
                    exchange.api_secret_encrypted
                )
                client = BybitClient(api_key, api_secret, exchange.is_testnet)
                try:
                    ccxt_symbol = symbol.replace('USDT', '/USDT')
                    df_1h = await client.fetch_ohlcv(ccxt_symbol, '1h', limit=100)
                finally:
                    await client.close()

            df_1h = trim_unclosed_candle(df_1h, '1h')
            
            if not df_1h.empty and len(df_1h) >= 21:
                # Определяем тренд на 1h
                temp_strategy = MainStrategy()
                df_1h['EMA9'] = temp_strategy.calculate_ema(df_1h['close'], 9)
                df_1h['EMA21'] = temp_strategy.calculate_ema(df_1h['close'], 21)
                df_1h['RSI'] = temp_strategy.calculate_rsi(df_1h['close'], 14)
                higher_timeframe_trend = temp_strategy.determine_trend(df_1h)
                print(f"📊 Тренд на 1h: {higher_timeframe_trend}")
        
        # Получаем стратегию из реестра по имени
        from .strategy_registry import StrategyRegistry
        
        # Параметры для стратегии (передаем все, что может понадобиться)
        strategy_params = {
            'stop_loss_percent': float(settings.stop_loss_percent),
            'take_profit_percent': float(settings.take_profit_percent),
            'leverage': settings.leverage,
        }
        
        # Если это основная стратегия, добавляем дополнительные параметры
        if settings.strategy_name == 'main':
            strategy_params.update({
                'ema_fast_period': settings.ema_fast_period,
                'ema_slow_period': settings.ema_slow_period,
                'rsi_period': settings.rsi_period,
                'williams_r_period': settings.williams_r_period,
                'channel_period': settings.channel_period,
                'atr_period': settings.atr_period,
            })
        elif settings.strategy_name == 'scalping':
            # Для скальпинга используем небольшие SL/TP по умолчанию
            if 'stop_loss_percent' not in strategy_params or strategy_params['stop_loss_percent'] > 2.0:
                strategy_params['stop_loss_percent'] = 0.5  # 0.5% для скальпинга
            if 'take_profit_percent' not in strategy_params or strategy_params['take_profit_percent'] > 3.0:
                strategy_params['take_profit_percent'] = 1.0  # 1.0% для скальпинга
        
        # Создаем стратегию из реестра
        strategy = StrategyRegistry.get_strategy(settings.strategy_name, **strategy_params)
        
        # Анализ рынка с учетом старшего таймфрейма
        signal = strategy.analyze(df, higher_timeframe_trend)
        
        # Детальный анализ для отправки в бот
        analysis_details = strategy.analyze_detailed(df)
        analysis_details['higher_timeframe_trend'] = higher_timeframe_trend  # Добавляем информацию о старшем таймфрейме
        
        # Отправляем информацию о текущем анализе в бот
        from bot.notifications import send_monitoring_update
        await send_monitoring_update(user, symbol, analysis_details, signal)
        
        # Сохраняем сигнал в историю и отправляем уведомление (ТОЛЬКО если есть сигнал)
        signal_history = None
        if signal and signal.signal:
            # Получаем текущие значения индикаторов для истории
            last_row = df.iloc[-1]
            ema9_val = float(last_row['EMA9']) if 'EMA9' in last_row else 0
            ema21_val = float(last_row['EMA21']) if 'EMA21' in last_row else 0
            rsi_val = float(last_row['RSI']) if 'RSI' in last_row else 50
            williams_r_val = float(last_row['WilliamsR']) if 'WilliamsR' in last_row else -50
            
            signal_history = await SignalHistory.objects.acreate(
                user=user,
                symbol=symbol,
                signal=signal.signal,
                entry_price=Decimal(str(signal.entry_price)),
                stop_loss=Decimal(str(signal.stop_loss)),
                take_profit=Decimal(str(signal.take_profit)),
                confidence=Decimal(str(signal.confidence)),
                reason=signal.reason,
                ema9=Decimal(str(ema9_val)),
                ema21=Decimal(str(ema21_val)),
                rsi=Decimal(str(rsi_val)),
                williams_r=Decimal(str(williams_r_val)),
                was_opened=False  # Пока не открыта
            )
        
        if signal and signal.signal:
            # ТЕСТОВЫЙ РЕЖИМ: только отправляем уведомление о сигнале (без открытия позиции)
            if is_test_mode or not exchange:
                # Отправляем детальное уведомление о сигнале
                from bot.notifications import send_signal_notification_detailed
                await send_signal_notification_detailed(
                    user=user,
                    symbol=symbol,
                    signal=signal.signal,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    confidence=signal.confidence,
                    reason=signal.reason,
                    position_size=None,  # В тестовом режиме нет размера
                    is_test_mode=True
                )
                
                # Обновляем историю сигнала
                if signal_history:
                    signal_history.was_opened = False  # В тестовом режиме не открываем
                    await signal_history.asave()
                
                print(f"🧪 Тестовый режим: Сигнал {signal.signal} обнаружен для {symbol} у {user.username}")
                return
            
            # РЕАЛЬНЫЙ РЕЖИМ: открываем позицию
            if not exchange:
                return
            
            # Дешифруем API ключи
            api_key, api_secret = decrypt_api_credentials(
                exchange.api_key_encrypted,
                exchange.api_secret_encrypted
            )
            
            client = BybitClient(api_key, api_secret, exchange.is_testnet)
            
            try:
                # Получаем баланс (async)
                balance_data = await client.get_balance()
                usdt_balance = Decimal(str(balance_data.get('USDT', {}).get('free', 0)))
                
                if usdt_balance < MIN_ORDER_SIZE_USD:
                    print(f"Недостаточный баланс у {user.username}: ${usdt_balance}")
                    return

                try:
                    unrealized_pnl = await client.get_total_unrealized_pnl()
                except Exception as unrealized_error:
                    unrealized_pnl = Decimal('0')
                    print(
                        f"⚠️ Не удалось получить unrealized PnL для {user.username}: "
                        f"{unrealized_error}. Используем 0."
                    )

                risk_allowed, risk_block_reason = await evaluate_risk_guards(
                    user=user,
                    settings=settings,
                    usdt_balance=usdt_balance,
                    unrealized_pnl=unrealized_pnl,
                )
                if not risk_allowed:
                    print(f"🛑 Риск-стоп сработал для {user.username}: {risk_block_reason}")
                    if settings.auto_pause_on_risk:
                        await apply_risk_pause(settings, user, risk_block_reason)
                        risk_validation_message = f"Торговля на паузе по рискам: {risk_block_reason}"
                    else:
                        risk_validation_message = f"Сигнал отклонен риск-лимитами: {risk_block_reason}"

                    from bot.notifications import send_signal_notification_detailed
                    await send_signal_notification_detailed(
                        user=user,
                        symbol=symbol,
                        signal=signal.signal,
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        confidence=signal.confidence,
                        reason=signal.reason,
                        validation_message=risk_validation_message,
                    )
                    return

                order_size_usd = resolve_order_size_usd(settings, usdt_balance)
                if order_size_usd < MIN_ORDER_SIZE_USD:
                    print(
                        f"Размер ордера слишком мал у {user.username}: ${order_size_usd}"
                    )
                    return

                if signal.entry_price <= 0:
                    print(f"Некорректная цена входа для {symbol}: {signal.entry_price}")
                    return

                if settings.leverage <= 0:
                    print(f"Некорректное плечо у {user.username}: {settings.leverage}")
                    return

                required_margin_usd = (order_size_usd / Decimal(settings.leverage)).quantize(Decimal('0.01'))
                if required_margin_usd > usdt_balance:
                    validation_message = (
                        f"Недостаточно баланса для ордера ${order_size_usd}. "
                        f"Нужно маржи: ${required_margin_usd}, доступно: ${usdt_balance}."
                    )
                    print(f"Невалидная позиция: {validation_message}")
                    from bot.notifications import send_signal_notification_detailed
                    await send_signal_notification_detailed(
                        user=user,
                        symbol=symbol,
                        signal=signal.signal,
                        entry_price=signal.entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        confidence=signal.confidence,
                        reason=signal.reason,
                        position_size=float(order_size_usd),
                        validation_message=validation_message
                    )
                    return

                position_size_usd = float(order_size_usd)
                quantity = position_size_usd / float(signal.entry_price)
                if quantity <= 0:
                    print(f"Некорректное количество для {symbol}: {quantity}")
                    return
                
                ccxt_symbol = symbol.replace('USDT', '/USDT')

                # Антидубли: дополнительно проверяем реальную открытую позицию на бирже.
                # Это защищает от рассинхронизации "биржа ↔ локальная БД".
                existing_exchange_position = await client.get_position(ccxt_symbol)
                if existing_exchange_position:
                    existing_contracts = float(existing_exchange_position.get('contracts') or 0)
                    if existing_contracts > 0:
                        validation_message = (
                            f"На бирже уже есть открытая позиция по {symbol}. "
                            "Новый ордер не открыт, чтобы не удвоить риск."
                        )
                        print(f"⚠️ {validation_message}")
                        from bot.notifications import send_signal_notification_detailed
                        await send_signal_notification_detailed(
                            user=user,
                            symbol=symbol,
                            signal=signal.signal,
                            entry_price=signal.entry_price,
                            stop_loss=signal.stop_loss,
                            take_profit=signal.take_profit,
                            confidence=signal.confidence,
                            reason=signal.reason,
                            position_size=position_size_usd,
                            validation_message=validation_message
                        )
                        return

                # Устанавливаем плечо и открываем позицию
                await client.set_leverage(ccxt_symbol, settings.leverage)
                side_map = {'LONG': 'buy', 'SHORT': 'sell'}
                order = await client.create_market_order(
                    symbol=ccxt_symbol,
                    side=side_map[signal.signal],
                    amount=quantity
                )

                executed_entry_price = extract_order_execution_price(order, float(signal.entry_price))
                executed_quantity = extract_order_filled_amount(order, float(quantity))

                # Ставим защитные ордера. Если не удалось выставить оба (SL и TP),
                # аварийно закрываем позицию, чтобы не оставлять ее без защиты.
                sl_side = 'sell' if signal.signal == 'LONG' else 'buy'
                tp_side = 'sell' if signal.signal == 'LONG' else 'buy'
                protective_errors = []

                try:
                    await client.create_stop_loss_order(
                        symbol=ccxt_symbol,
                        side=sl_side,
                        amount=executed_quantity,
                        stop_price=signal.stop_loss
                    )
                    print(f"✅ Установлен стоп-лосс на ${signal.stop_loss:.2f}")
                except Exception as sl_error:
                    protective_errors.append(f"SL: {sl_error}")
                    print(f"⚠️ Ошибка установки стоп-лосса: {str(sl_error)}")

                try:
                    await client.create_take_profit_order(
                        symbol=ccxt_symbol,
                        side=tp_side,
                        amount=executed_quantity,
                        take_profit_price=signal.take_profit
                    )
                    print(f"✅ Установлен тейк-профит на ${signal.take_profit:.2f}")
                except Exception as tp_error:
                    protective_errors.append(f"TP: {tp_error}")
                    print(f"⚠️ Ошибка установки тейк-профита: {str(tp_error)}")

                if protective_errors:
                    emergency_close_error = None
                    emergency_exit_price = executed_entry_price
                    trade_status = 'closed'
                    close_note = (
                        "Защитные ордера выставлены не полностью. "
                        "Позиция закрыта аварийно для защиты капитала."
                    )
                    try:
                        close_order = await client.close_position(ccxt_symbol)
                        emergency_exit_price = extract_order_execution_price(close_order, executed_entry_price)
                    except Exception as close_error:
                        emergency_close_error = str(close_error)
                        trade_status = 'open'

                    notes = (
                        f"{signal.reason}\n"
                        f"{close_note}\n"
                        f"Ошибки защиты: {'; '.join(protective_errors)}"
                    )
                    if emergency_close_error:
                        notes += f"\nНе удалось аварийно закрыть позицию: {emergency_close_error}"

                    trade = await Trade.objects.acreate(
                        user=user,
                        exchange=exchange,
                        symbol=symbol,
                        side=signal.signal.lower(),
                        entry_price=Decimal(str(executed_entry_price)),
                        quantity=Decimal(str(executed_quantity)),
                        leverage=settings.leverage,
                        stop_loss=Decimal(str(signal.stop_loss)),
                        take_profit=Decimal(str(signal.take_profit)),
                        order_id=order.get('id', ''),
                        status=trade_status,
                        notes=notes,
                        exit_price=Decimal(str(emergency_exit_price)) if trade_status == 'closed' else None,
                        closed_at=timezone.now() if trade_status == 'closed' else None,
                    )

                    if trade_status == 'closed':
                        update_trade_pnl_fields(trade)
                        await trade.asave()
                        await asyncio.to_thread(update_user_statistics_for_user, user)
                        if signal_history:
                            signal_history.was_opened = True
                            signal_history.was_profitable = trade.pnl > 0 if trade.pnl is not None else False
                            signal_history.actual_pnl = trade.pnl if trade.pnl is not None else Decimal('0')
                            await signal_history.asave()
                    else:
                        if signal_history:
                            signal_history.was_opened = True
                            await signal_history.asave()

                    from bot.notifications import send_signal_notification_detailed
                    await send_signal_notification_detailed(
                        user=user,
                        symbol=symbol,
                        signal=signal.signal,
                        entry_price=executed_entry_price,
                        stop_loss=signal.stop_loss,
                        take_profit=signal.take_profit,
                        confidence=signal.confidence,
                        reason=signal.reason,
                        position_size=executed_entry_price * executed_quantity,
                        validation_message=(
                            close_note if trade_status == 'closed'
                            else f"{close_note} Требуется ручная проверка позиции на бирже: {emergency_close_error}"
                        )
                    )
                    return
                
                # Сохраняем сделку в БД (async)
                trade = await Trade.objects.acreate(
                    user=user,
                    exchange=exchange,
                    symbol=symbol,
                    side=signal.signal.lower(),
                    entry_price=Decimal(str(executed_entry_price)),
                    quantity=Decimal(str(executed_quantity)),
                    leverage=settings.leverage,
                    stop_loss=Decimal(str(signal.stop_loss)),
                    take_profit=Decimal(str(signal.take_profit)),
                    order_id=order.get('id', ''),
                    status='open',
                    notes=signal.reason
                )
                
                # Обновляем историю сигнала - помечаем что позиция была открыта
                if signal_history:
                    signal_history.was_opened = True
                    await signal_history.asave()
                
                # Отправляем детальное уведомление об открытии позиции
                from bot.notifications import send_signal_notification_detailed
                position_size_usd = executed_quantity * executed_entry_price
                await send_signal_notification_detailed(
                    user=user,
                    symbol=symbol,
                    signal=signal.signal,
                    entry_price=executed_entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    confidence=signal.confidence,
                    reason=signal.reason,
                    position_size=position_size_usd,
                    is_test_mode=False,
                    trade=trade
                )
                
                print(f"✅ Открыта позиция {signal.signal} {symbol} для {user.username}")
                
            finally:
                await client.close()
            
    except Exception as e:
        print(f"Ошибка анализа и торговли для {symbol}: {str(e)}")
        import traceback
        traceback.print_exc()


@shared_task
def check_open_positions():
    """
    Проверка открытых позиций и закрытие при достижении SL/TP.
    """
    asyncio.run(check_open_positions_async())


async def check_open_positions_async():
    """
    Асинхронная версия проверки открытых позиций.
    Проверяет SL/TP и закрывает позиции скальпинга старше 1 часа.
    """
    open_trades_qs = Trade.objects.filter(status='open').select_related('user', 'exchange')
    # Используем async итерацию вместо all()
    async for trade in open_trades_qs:
        try:
            await check_and_close_position(trade)
        except Exception as e:
            print(f"Ошибка проверки позиции {trade.id}: {str(e)}")
            import traceback
            traceback.print_exc()


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
            ccxt_symbol = trade.symbol.replace('USDT', '/USDT')

            # Сначала проверяем факт существования позиции на бирже.
            # Если позиция уже закрыта извне (SL/TP/ручное действие) — синхронизируем БД.
            exchange_position = await client.get_position(ccxt_symbol)
            ticker = await client.get_ticker(ccxt_symbol)
            current_price = ticker['last']

            if not exchange_position:
                close_reason = (
                    "Позиция уже закрыта на бирже (вне бота). "
                    "Локальная сделка синхронизирована автоматически."
                )
                await finalize_trade_close(
                    trade=trade,
                    exit_price=float(current_price),
                    close_reason=close_reason,
                )
                print(f"🔄 Синхронизация: позиция {trade.side} {trade.symbol} помечена как закрытая")
                return

            should_close = False
            close_reason = ""
            
            # Получаем настройки пользователя для проверки стратегии
            settings = await UserTradingSettings.objects.aget(user=trade.user)
            
            # Для скальпинга: проверяем время удержания позиции (максимум 1 час)
            if settings.strategy_name == 'scalping':
                time_open = timezone.now() - trade.opened_at
                if time_open.total_seconds() >= 3600:  # 1 час = 3600 секунд
                    should_close = True
                    close_reason = f"Скальпинг: позиция открыта более 1 часа ({time_open.seconds // 60} минут)"
            
            # Проверка стоп-лосса и тейк-профита
            if trade.side == 'long':
                if current_price <= float(trade.stop_loss):
                    should_close = True
                    close_reason = f"Стоп-лосс достигнут: ${current_price:.2f} <= ${trade.stop_loss}"
                elif current_price >= float(trade.take_profit):
                    should_close = True
                    close_reason = f"Тейк-профит достигнут: ${current_price:.2f} >= ${trade.take_profit}"
            
            else:  # short
                if current_price >= float(trade.stop_loss):
                    should_close = True
                    close_reason = f"Стоп-лосс достигнут: ${current_price:.2f} >= ${trade.stop_loss}"
                elif current_price <= float(trade.take_profit):
                    should_close = True
                    close_reason = f"Тейк-профит достигнут: ${current_price:.2f} <= ${trade.take_profit}"
            
            if should_close:
                execution_exit_price = float(current_price)
                try:
                    close_order = await client.close_position(ccxt_symbol)
                    execution_exit_price = extract_order_execution_price(close_order, float(current_price))
                except Exception as close_error:
                    close_error_text = str(close_error)
                    if "Нет открытой позиции" in close_error_text:
                        close_reason = (
                            f"{close_reason}. Позиция уже закрыта на бирже к моменту закрытия ботом, "
                            "выполнена синхронизация."
                        )
                    else:
                        raise

                await finalize_trade_close(
                    trade=trade,
                    exit_price=execution_exit_price,
                    close_reason=close_reason,
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
    asyncio.run(close_position_manually_async(trade_id))


async def close_position_manually_async(trade_id: int):
    """
    Асинхронная версия ручного закрытия позиции.
    """
    try:
        trade = await Trade.objects.aget(id=trade_id, status='open')
        exchange = trade.exchange
        if not exchange:
            print(f"Сделка {trade_id} не привязана к бирже, ручное закрытие невозможно")
            return

        api_key, api_secret = decrypt_api_credentials(
            exchange.api_key_encrypted,
            exchange.api_secret_encrypted
        )
        client = BybitClient(api_key, api_secret, exchange.is_testnet)

        try:
            ccxt_symbol = trade.symbol.replace('USDT', '/USDT')
            ticker = await client.get_ticker(ccxt_symbol)
            current_price = float(ticker['last'])

            close_reason = "Позиция закрыта вручную пользователем"
            exit_price = current_price

            try:
                close_order = await client.close_position(ccxt_symbol)
                exit_price = extract_order_execution_price(close_order, current_price)
            except Exception as close_error:
                close_error_text = str(close_error)
                if "Нет открытой позиции" in close_error_text:
                    close_reason = (
                        "Ручное закрытие: позиция уже была закрыта на бирже. "
                        "Локальная сделка синхронизирована."
                    )
                else:
                    raise

            await finalize_trade_close(
                trade=trade,
                exit_price=exit_price,
                close_reason=close_reason,
            )
            print(f"✅ Ручное закрытие выполнено для сделки {trade_id}")
        finally:
            await client.close()
    except Trade.DoesNotExist:
        print(f"Сделка {trade_id} не найдена или уже закрыта")
    except Exception as e:
        print(f"Ошибка ручного закрытия позиции {trade_id}: {str(e)}")
        import traceback
        traceback.print_exc()
