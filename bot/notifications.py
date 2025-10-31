"""
Модуль отправки уведомлений пользователям в Telegram.
"""

from aiogram import Bot
from aiogram.types import ParseMode
from django.conf import settings
from django.contrib.auth.models import User
from trading.models import Trade
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
        bot_user = BotUser.objects.filter(django_user=user).first()
        
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
            pnl_emoji = "🟢" if trade.pnl and trade.pnl > 0 else "🔴"
            message = f"""
{pnl_emoji} <b>ПОЗИЦИЯ ЗАКРЫТА</b>

📊 Символ: <code>{trade.symbol}</code>
📈 Направление: <b>{trade.side.upper()}</b>

💰 Вход: <code>${trade.entry_price}</code>
💰 Выход: <code>${trade.exit_price}</code>

{'💰' if trade.pnl and trade.pnl > 0 else '❌'} PnL: <b>${trade.pnl} ({trade.pnl_percent}%)</b>

⏱ Время удержания: <code>{(trade.closed_at - trade.opened_at).total_seconds() / 60:.1f} мин</code>

📝 {trade.notes.split('\\n')[-1] if trade.notes else 'Закрыта вручную'}
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
        bot_user = BotUser.objects.filter(django_user=user).first()
        
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
        bot_user = BotUser.objects.filter(django_user=user).first()
        
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
        bot_user = BotUser.objects.filter(django_user=user).first()
        
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
