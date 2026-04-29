"""
Модуль отправки уведомлений пользователям в Telegram.
"""

import html
from aiogram import Bot
from aiogram.enums import ParseMode
from django.conf import settings
from django.contrib.auth.models import User
from typing import Optional
from trading_strategy.models import Trade
from typing import Literal


async def send_trade_notification(
    user: User, 
    trade: Trade, 
    action: Literal['opened', 'closed', 'cancelled']
):
    """
    Отправка уведомления об открытии/закрытии сделки.
    
    Args:
        user: Пользователь
        trade: Сделка
        action: Тип действия ('opened', 'closed', 'cancelled')
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        # Получаем telegram_id пользователя из профиля
        # (предполагается, что у User есть связь с профилем бота)
        from bot.models import BotUser
        bot_user = await BotUser.objects.filter(django_user=user).afirst()
        
        if not bot_user:
            return
        
        telegram_id = bot_user.telegram_id
        
        if action == 'opened':
            emoji = "🟢" if trade.side == 'long' else "🔴"
            message = f"""
{emoji} <b>ПОЗИЦИЯ ОТКРЫТА</b>

📊 Символ: <code>{trade.symbol}</code>
📈 Направление: <b>{trade.side.upper()}</b>
💰 Цена входа: <code>${trade.entry_price}</code>
📦 Количество: <code>{trade.quantity}</code>
🎚 Плечо: <code>{trade.leverage}x</code>

🛑 Стоп-лосс: <code>${trade.stop_loss}</code>
🎯 Тейк-профит: <code>${trade.take_profit}</code>

📝 Причина: {trade.notes}
"""
        
        elif action == 'closed':
            if trade.pnl and trade.pnl > 0:
                pnl_emoji = "✅"
                pnl_text = f"✅ <b>ЗАКРЫЛИ В +${abs(trade.pnl):.2f}</b> ({trade.pnl_percent:.2f}%)"
            else:
                pnl_emoji = "❌"
                pnl_text = f"❌ <b>ЗАКРЫЛИ В -${abs(trade.pnl):.2f}</b> ({trade.pnl_percent:.2f}%)"
            
            message = f"""
{pnl_emoji} <b>ПОЗИЦИЯ ЗАКРЫТА</b>

📊 Символ: <code>{trade.symbol}</code>
📈 Направление: <b>{trade.side.upper()}</b>

💰 <b>Цена входа:</b> <code>${trade.entry_price}</code>
💰 <b>Цена выхода:</b> <code>${trade.exit_price}</code>

{pnl_text}

⏱ <b>Время удержания:</b> <code>{(trade.closed_at - trade.opened_at).total_seconds() / 60:.1f} мин</code>

📝 {trade.notes.split('\\n')[-1] if trade.notes else 'Закрыта автоматически'}
"""
        
        elif action == 'cancelled':
            message = f"""
⚠️ <b>ПОЗИЦИЯ ОТМЕНЕНА</b>

📊 Символ: <code>{trade.symbol}</code>
📈 Направление: <b>{trade.side.upper()}</b>
💰 Цена входа: <code>${trade.entry_price}</code>

📝 {trade.notes.split('\\n')[-1] if trade.notes else 'Отменена пользователем'}
"""
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        print(f"Ошибка отправки уведомления: {str(e)}")
    
    finally:
        await bot.session.close()


async def send_signal_notification(user: User, signal_info: dict):
    """
    Отправка уведомления о найденном сигнале (но не открытой позиции).
    
    Args:
        user: Пользователь
        signal_info: Информация о сигнале
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        from bot.models import BotUser
        bot_user = await BotUser.objects.filter(django_user=user).afirst()
        
        if not bot_user:
            return
        
        telegram_id = bot_user.telegram_id
        
        emoji = "🟢" if signal_info['signal'] == 'LONG' else "🔴"
        message = f"""
{emoji} <b>СИГНАЛ ОБНАРУЖЕН</b>

📊 Символ: <code>{signal_info['symbol']}</code>
📈 Направление: <b>{signal_info['signal']}</b>
💰 Цена входа: <code>${signal_info['entry_price']}</code>
🎯 Уверенность: <b>{signal_info['confidence']}%</b>

🛑 Стоп-лосс: <code>${signal_info['stop_loss']}</code>
🎯 Тейк-профит: <code>${signal_info['take_profit']}</code>

📝 Причина: {signal_info['reason']}

⚠️ <i>Позиция не открыта автоматически. Проверьте настройки.</i>
"""
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        print(f"Ошибка отправки сигнала: {str(e)}")
    
    finally:
        await bot.session.close()


async def send_risk_pause_notification(user: User, reason: str):
    """
    Уведомление о принудительной паузе торговли по риск-лимитам.
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)

    try:
        from bot.models import BotUser
        bot_user = await BotUser.objects.filter(django_user=user).afirst()

        if not bot_user:
            return

        message = f"""
🛑 <b>ТОРГОВЛЯ ОСТАНОВЛЕНА ПО РИСКАМ</b>

Причина:
<code>{html.escape(reason)}</code>

Чтобы продолжить торговлю:
1) проверьте статистику и открытые позиции;
2) скорректируйте риск-настройки;
3) вручную запустите торговлю снова.
"""

        await bot.send_message(
            chat_id=bot_user.telegram_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        print(f"Ошибка отправки уведомления о риск-паузе: {str(e)}")
    finally:
        await bot.session.close()


async def send_error_notification(user: User, error_message: str):
    """
    Отправка уведомления об ошибке.
    
    Args:
        user: Пользователь
        error_message: Сообщение об ошибке
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        from bot.models import BotUser
        bot_user = await BotUser.objects.filter(django_user=user).afirst()
        
        if not bot_user:
            return
        
        telegram_id = bot_user.telegram_id
        
        message = f"""
❌ <b>ОШИБКА</b>

{error_message}

⚠️ <i>Торговля автоматически приостановлена. Проверьте настройки и API ключи.</i>
"""
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        print(f"Ошибка отправки уведомления об ошибке: {str(e)}")
    
    finally:
        await bot.session.close()


async def send_statistics_report(user: User, stats: dict):
    """
    Отправка отчета со статистикой.
    
    Args:
        user: Пользователь
        stats: Статистика торговли
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        from bot.models import BotUser
        bot_user = await BotUser.objects.filter(django_user=user).afirst()
        
        if not bot_user:
            return
        
        telegram_id = bot_user.telegram_id
        
        message = f"""
📊 <b>СТАТИСТИКА ТОРГОВЛИ</b>

📈 Всего сделок: <b>{stats['total_trades']}</b>
✅ Прибыльных: <b>{stats['winning_trades']}</b>
❌ Убыточных: <b>{stats['losing_trades']}</b>

💰 Общий PnL: <b>${stats['total_pnl']} ({stats['total_pnl_percent']}%)</b>

📊 Винрейт: <b>{stats['win_rate']}%</b>

📈 Средняя прибыль: <code>${stats['average_win']}</code>
📉 Средний убыток: <code>${stats['average_loss']}</code>

🔝 Максимальная прибыль: <code>${stats['max_win']}</code>
🔻 Максимальный убыток: <code>${stats['max_loss']}</code>

⚠️ Макс. просадка: <code>${stats['max_drawdown']}</code>

📅 Обновлено: <code>{stats['updated_at'].strftime('%Y-%m-%d %H:%M')}</code>
"""
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        print(f"Ошибка отправки статистики: {str(e)}")
    
    finally:
        await bot.session.close()


async def send_signal_notification_detailed(
    user: User,
    symbol: str,
    signal: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    confidence: float,
    reason: str,
    position_size: float = None,
    is_test_mode: bool = False,
    trade: 'Trade' = None,
    validation_message: Optional[str] = None
):
    """
    Отправка детального уведомления о сигнале/открытии позиции.
    
    Args:
        user: Пользователь
        symbol: Торговая пара
        signal: LONG или SHORT
        entry_price: Цена входа
        stop_loss: Стоп-лосс
        take_profit: Тейк-профит (цена закрытия в плюс)
        confidence: Уверенность
        reason: Причина сигнала
        position_size: Размер позиции в USD (None для тестового режима)
        is_test_mode: Тестовый режим
        trade: Объект Trade (если позиция была открыта)
        validation_message: Причина, почему позиция не была открыта
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        from bot.models import BotUser
        bot_user = await BotUser.objects.filter(django_user=user).afirst()
        
        if not bot_user:
            return
        
        telegram_id = bot_user.telegram_id
        
        signal_emoji = "🟢" if signal == 'LONG' else "🔴"
        signal_text = "LONG (покупка)" if signal == 'LONG' else "SHORT (продажа)"

        if signal == 'LONG':
            stop_loss_price_move = ((entry_price - stop_loss) / entry_price) * 100 if entry_price else 0
            take_profit_price_move = ((take_profit - entry_price) / entry_price) * 100 if entry_price else 0
        else:
            stop_loss_price_move = ((stop_loss - entry_price) / entry_price) * 100 if entry_price else 0
            take_profit_price_move = ((entry_price - take_profit) / entry_price) * 100 if entry_price else 0

        risk_hint = (
            f"📐 <b>Дистанция:</b> "
            f"SL {stop_loss_price_move:.2f}% цены, "
            f"TP {take_profit_price_move:.2f}% цены\n"
        )
        
        validation_text = ""
        if validation_message:
            validation_text = f"\n⚠️ <b>Позиция не открыта:</b> {html.escape(validation_message)}"

        if trade:
            # Позиция была открыта (реальный режим)
            message = f"""
{signal_emoji} <b>ПОЗИЦИЯ ОТКРЫТА</b>

💹 Символ: <code>{symbol}</code>
📈 Направление: <b>{signal_text}</b>

💰 <b>Цена входа:</b> <code>${entry_price:.2f}</code>

🛑 <b>Стоп-лосс:</b> <code>${stop_loss:.2f}</code>
   (Убыток при достижении)

✅ <b>Закрываем в + по цене:</b> <code>${take_profit:.2f}</code>

{risk_hint}

💵 <b>Размер позиции:</b> <code>${position_size:.2f}</code>
🎚 <b>Плечо:</b> <code>{trade.leverage}x</code>

📊 <b>Уверенность:</b> {confidence:.1f}%

📝 <b>Причина:</b> {reason}
"""
        else:
            # Только сигнал, позиция не открыта (тестовый режим)
            mode_text = "🧪 <b>ТЕСТОВЫЙ РЕЖИМ</b> (позиция не открыта)\n\n" if is_test_mode else ""
            message = f"""
{signal_emoji} <b>СИГНАЛ ОБНАРУЖЕН</b>

{mode_text}💹 Символ: <code>{symbol}</code>
📈 Направление: <b>{signal_text}</b>

💰 <b>Цена входа:</b> <code>${entry_price:.2f}</code>

🛑 <b>Стоп-лосс:</b> <code>${stop_loss:.2f}</code>
   (Убыток при достижении)

✅ <b>Закрываем в + по цене:</b> <code>${take_profit:.2f}</code>

{risk_hint}

{'⚠️ <i>Для открытия позиции добавьте API ключи</i>' if is_test_mode else ''}

📊 <b>Уверенность:</b> {confidence:.1f}%

📝 <b>Причина:</b> {reason}
{validation_text}
"""
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        print(f"Ошибка отправки детального уведомления: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        await bot.session.close()


async def send_market_analysis(user: User, symbol: str, analysis_data: dict):
    """
    Отправка сообщения о текущем анализе рынка (даже если сигнала нет).
    
    Args:
        user: Пользователь
        symbol: Торговая пара
        analysis_data: Данные анализа (trend, indicators, current_price, etc.)
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        from bot.models import BotUser
        bot_user = await BotUser.objects.filter(django_user=user).afirst()
        
        if not bot_user:
            return
        
        telegram_id = bot_user.telegram_id
        
        trend_emoji = {"BULLISH": "🟢", "BEARISH": "🔴", "NEUTRAL": "⚪"}.get(analysis_data.get('trend', 'NEUTRAL'), "⚪")
        trend_text = {
            "BULLISH": "Бычий",
            "BEARISH": "Медвежий",
            "NEUTRAL": "Нейтральный"
        }.get(analysis_data.get('trend', 'NEUTRAL'), "Неизвестен")
        
        rsi_status = ""
        rsi_val = analysis_data.get('rsi', 50)
        if rsi_val > 70:
            rsi_status = "(перекуплен)"
        elif rsi_val < 30:
            rsi_status = "(перепродан)"
        
        price_pos = analysis_data.get('price_position')
        price_pos_text = ""
        if price_pos == 'upper':
            price_pos_text = "Верх канала"
        elif price_pos == 'lower':
            price_pos_text = "Низ канала"
        else:
            price_pos_text = "Середина"
        
        signal_text = ""
        if analysis_data.get('signal'):
            signal_text = f"""
🟢 <b>Сигнал найден!</b>

📈 Направление: <b>{analysis_data['signal']}</b>
🎯 Уверенность: <b>{analysis_data.get('confidence', 0):.1f}%</b>
🛑 Стоп-лосс: <code>${analysis_data.get('stop_loss', 0):.2f}</code>
🎯 Тейк-профит: <code>${analysis_data.get('take_profit', 0):.2f}</code>
"""
        else:
            signal_text = "⚪ Сигнала нет - ждём условий..."
        
        message = f"""
📊 <b>АНАЛИЗ РЫНКА</b>

💹 Символ: <code>{symbol}</code>
💰 Текущая цена: <code>${analysis_data.get('current_price', 0):.2f}</code>

{trend_emoji} <b>Тренд:</b> {trend_text}

📈 <b>Индикаторы:</b>
• EMA9/EMA21: <code>${analysis_data.get('ema9', 0):.2f}</code> / <code>${analysis_data.get('ema21', 0):.2f}</code>
• RSI: <code>{analysis_data.get('rsi', 0):.1f}</code> {rsi_status}
• Williams %R: <code>{analysis_data.get('williams_r', 0):.1f}</code>
• ATR: <code>${analysis_data.get('atr', 0):.2f}</code>

📊 <b>Ценовой канал:</b>
• Верх: <code>${analysis_data.get('channel_upper', 0):.2f}</code>
• Низ: <code>${analysis_data.get('channel_lower', 0):.2f}</code>
• Позиция: {price_pos_text}

{signal_text}
"""
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        print(f"Ошибка отправки анализа: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        await bot.session.close()


async def send_monitoring_update(user: User, symbol: str, analysis_details: dict, signal: Optional = None):
    """
    Отправка сообщения о текущем мониторинге рынка.
    
    Args:
        user: Пользователь
        symbol: Торговая пара
        analysis_details: Детали анализа от strategy.analyze_detailed()
        signal: Сигнал (если есть)
    """
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
    
    try:
        from bot.models import BotUser
        bot_user = await BotUser.objects.filter(django_user=user).afirst()
        
        if not bot_user:
            return
        
        telegram_id = bot_user.telegram_id
        
        trend_emoji = {
            "BULLISH": "🟢",
            "BEARISH": "🔴",
            "NEUTRAL": "⚪"
        }.get(analysis_details.get('trend'), "⚪")
        
        trend_text = {
            "BULLISH": "Бычий",
            "BEARISH": "Медвежий",
            "NEUTRAL": "Нейтральный"
        }.get(analysis_details.get('trend'), "Неизвестен")
        
        conditions_met = analysis_details.get('conditions_met', 0)
        total_conditions = analysis_details.get('total_conditions', 5)
        
        indicators = analysis_details.get('indicators', {})
        current_price = analysis_details.get('current_price', 0)
        
        # Формируем сообщение о проверенных условиях для ОБОИХ направлений
        condition_names = {
            'near_lower_bound': '📉 Цена у нижней границы канала',
            'near_upper_bound': '📈 Цена у верхней границы канала',
            'rsi_oversold': '📊 RSI меньше 30 (перепроданность)',
            'rsi_overbought': '📊 RSI больше 70 (перекупленность)',
            'williams_oversold': '📊 Williams %R меньше -80 (перепроданность)',
            'williams_overbought': '📊 Williams %R больше -20 (перекупленность)',
            'ema_crossover': '📈 EMA9 пересекает EMA21 (гибко)',
            'volume_increase': '📊 Объем больше среднего на 20%',
            'near_fibonacci': '📐 Цена у уровня Фибоначчи'
        }
        
        # LONG условия (основные требования и подтверждения)
        long_conditions = analysis_details.get('long_conditions', {})
        long_main_met = analysis_details.get('long_main_met', 0)
        long_confirm_met = analysis_details.get('long_confirm_met', 0)
        
        # Разделяем основные требования и подтверждения
        long_main_status = []
        long_confirm_status = []
        for key, value in long_conditions.items():
            emoji = "✅" if value else "❌"
            name = condition_names.get(key, key)
            name_safe = name.replace('<', '&lt;').replace('>', '&gt;')
            
            if key in ['near_lower_bound', 'rsi_oversold', 'williams_oversold']:
                # Основное требование
                long_main_status.append(f"{emoji} {name_safe}")
            else:
                # Подтверждающий сигнал
                long_confirm_status.append(f"{emoji} {name_safe}")
        
        # SHORT условия (основные требования и подтверждения)
        short_conditions = analysis_details.get('short_conditions', {})
        short_main_met = analysis_details.get('short_main_met', 0)
        short_confirm_met = analysis_details.get('short_confirm_met', 0)
        
        # Разделяем основные требования и подтверждения
        short_main_status = []
        short_confirm_status = []
        for key, value in short_conditions.items():
            emoji = "✅" if value else "❌"
            name = condition_names.get(key, key)
            name_safe = name.replace('<', '&lt;').replace('>', '&gt;')
            
            if key in ['near_upper_bound', 'rsi_overbought', 'williams_overbought']:
                # Основное требование
                short_main_status.append(f"{emoji} {name_safe}")
            else:
                # Подтверждающий сигнал
                short_confirm_status.append(f"{emoji} {name_safe}")
        
        # Если есть сигнал, НЕ отправляем это сообщение (будет отдельное уведомление)
        if signal and signal.signal:
            return
        
        # Формируем понятное объяснение статуса
        reason = analysis_details.get('reason_no_signal', 'Мониторинг...')
        reason_explanation = ""
        
        if "Недостаточно данных" in reason:
            reason_explanation = "Нужно больше свечей для расчета индикаторов"
        elif "Боковик" in reason or "нейтральном тренде" in reason:
            reason_explanation = "Рынок в боковом движении - ждем четкого тренда (бычьего или медвежьего)"
        elif "канал не валидный" in reason.lower():
            reason_explanation = "Ценовой канал не сформирован (нужно минимум 2 касания верхней и нижней границы за последние 20 свечей)"
        elif "Совпало только" in reason:
            reason_explanation = "Не все условия выполнены - стратегия очень строгая для минимизации ложных сигналов"
        else:
            reason_explanation = reason
        
        # Формируем дополнительные строки
        trend_hint = ""
        if analysis_details.get('trend') == 'BULLISH':
            trend_hint = "(В бычьем тренде ищем LONG сигналы)"
        elif analysis_details.get('trend') == 'BEARISH':
            trend_hint = "(В медвежьем тренде ищем SHORT сигналы)"
        
        # Безопасно формируем фильтр 1h
        h1h_filter_text = ""
        h1h_trend = analysis_details.get('higher_timeframe_trend')
        if h1h_trend:
            h1h_trend_text = {
                "BULLISH": "Бычий",
                "BEARISH": "Медвежий",
                "NEUTRAL": "Нейтральный"
            }.get(h1h_trend, "Неизвестен")
            h1h_trend_safe = html.escape(str(h1h_trend_text))
            h1h_filter_text = f"📊 <b>Фильтр 1h:</b> {h1h_trend_safe} тренд"
        
        rsi_hint = ""
        rsi_val = indicators.get('RSI', 50)
        if rsi_val < 30:
            rsi_hint = " (перепродан)"
        elif rsi_val > 70:
            rsi_hint = " (перекуплен)"
        
        # Формируем тексты для LONG
        long_main_text = "\n".join(long_main_status) if long_main_status else "⚠️ Не проверены"
        long_confirm_text = "\n".join(long_confirm_status) if long_confirm_status else "⚠️ Не проверены"
        
        # Формируем тексты для SHORT
        short_main_text = "\n".join(short_main_status) if short_main_status else "⚠️ Не проверены"
        short_confirm_text = "\n".join(short_confirm_status) if short_confirm_status else "⚠️ Не проверены"
        
        # Экранируем reason_explanation на всякий случай
        reason_explanation_safe = html.escape(str(reason_explanation))
        
        # Формируем полное сообщение
        message_parts = [
            "🔍 <b>МОНИТОРИНГ РЫНКА</b>",
            "",
            f"💹 Символ: <code>{symbol}</code>",
            f"💰 Цена: <code>${current_price:.2f}</code>",
            "",
            f"{trend_emoji} <b>Тренд:</b> {trend_text}",
        ]
        
        if trend_hint:
            message_parts.append(html.escape(trend_hint))
        
        if h1h_filter_text:
            message_parts.append(h1h_filter_text)
        
        message_parts.extend([
            "",
            "📊 <b>Индикаторы:</b>",
            f"• RSI: <code>{rsi_val:.1f}</code>{html.escape(rsi_hint)}",
            f"• Williams %R: <code>{indicators.get('WilliamsR', -50):.1f}</code>",
            f"• EMA9/EMA21: <code>${indicators.get('EMA9', 0):.2f}</code> / <code>${indicators.get('EMA21', 0):.2f}</code>",
            "",
            "🟢 <b>LONG сигнал:</b>",
            f"🔴 Основные требования: {long_main_met}/3 (нужно минимум 2)",
            long_main_text,
            "",
            f"🔵 Подтверждающие сигналы: {long_confirm_met}/3 (нужно минимум 1)",
            long_confirm_text,
            "",
            "🔴 <b>SHORT сигнал:</b>",
            f"🔴 Основные требования: {short_main_met}/3 (нужно минимум 2)",
            short_main_text,
            "",
            f"🔵 Подтверждающие сигналы: {short_confirm_met}/3 (нужно минимум 1)",
            short_confirm_text,
            "",
            f"📝 <b>Статус:</b> {reason_explanation_safe}",
        ])
        
        message = "\n".join(message_parts)
        
        await bot.send_message(
            chat_id=telegram_id,
            text=message,
            parse_mode=ParseMode.HTML
        )
        
    except Exception as e:
        print(f"Ошибка отправки мониторинга: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        await bot.session.close()
