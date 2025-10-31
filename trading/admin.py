"""
Административная панель Django для торговых моделей.
"""

from django.contrib import admin
from .models import (
    Exchange, UserTradingSettings, TradingPair,
    Trade, TradingStatistics
)


@admin.register(Exchange)
class ExchangeAdmin(admin.ModelAdmin):
    """Администрирование бирж"""
    list_display = ('user', 'name', 'is_testnet', 'is_active', 'created_at')
    list_filter = ('name', 'is_testnet', 'is_active', 'created_at')
    search_fields = ('user__username',)
    readonly_fields = ('api_key_encrypted', 'api_secret_encrypted', 'created_at', 'updated_at')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'name', 'is_testnet', 'is_active')
        }),
        ('API ключи (зашифрованы)', {
            'fields': ('api_key_encrypted', 'api_secret_encrypted'),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(UserTradingSettings)
class UserTradingSettingsAdmin(admin.ModelAdmin):
    """Администрирование настроек торговли"""
    list_display = ('user', 'base_order_size', 'leverage', 'risk_per_trade', 'is_trading_active')
    list_filter = ('is_trading_active', 'leverage')
    search_fields = ('user__username',)
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Настраиваемые параметры', {
            'fields': ('base_order_size', 'leverage', 'risk_per_trade', 'is_trading_active')
        }),
        ('Параметры стратегии', {
            'fields': (
                'timeframe',
                'ema_fast_period', 'ema_slow_period',
                'rsi_period', 'williams_r_period',
                'channel_period', 'atr_period'
            ),
            'classes': ('collapse',)
        }),
        ('Управление рисками', {
            'fields': ('stop_loss_atr_multiplier', 'take_profit_atr_multiplier'),
            'classes': ('collapse',)
        }),
    )


@admin.register(TradingPair)
class TradingPairAdmin(admin.ModelAdmin):
    """Администрирование торговых пар"""
    list_display = ('user', 'symbol', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('user__username', 'symbol')


@admin.register(Trade)
class TradeAdmin(admin.ModelAdmin):
    """Администрирование сделок"""
    list_display = (
        'user', 'symbol', 'side', 'entry_price', 'exit_price',
        'pnl', 'status', 'opened_at', 'closed_at'
    )
    list_filter = ('status', 'side', 'opened_at', 'closed_at')
    search_fields = ('user__username', 'symbol', 'order_id')
    readonly_fields = ('opened_at', 'closed_at', 'pnl', 'pnl_percent')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'exchange', 'symbol', 'side', 'status')
        }),
        ('Параметры позиции', {
            'fields': ('entry_price', 'exit_price', 'quantity', 'leverage')
        }),
        ('Риск-менеджмент', {
            'fields': ('stop_loss', 'take_profit')
        }),
        ('Результаты', {
            'fields': ('pnl', 'pnl_percent')
        }),
        ('Ордера и время', {
            'fields': ('order_id', 'opened_at', 'closed_at')
        }),
        ('Дополнительно', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(TradingStatistics)
class TradingStatisticsAdmin(admin.ModelAdmin):
    """Администрирование статистики"""
    list_display = (
        'user', 'total_trades', 'winning_trades', 'losing_trades',
        'total_pnl', 'win_rate', 'updated_at'
    )
    list_filter = ('updated_at',)
    search_fields = ('user__username',)
    readonly_fields = ('updated_at',)
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Общая статистика', {
            'fields': ('total_trades', 'winning_trades', 'losing_trades', 'win_rate')
        }),
        ('Финансовые показатели', {
            'fields': ('total_pnl', 'total_pnl_percent')
        }),
        ('Средние значения', {
            'fields': ('average_win', 'average_loss'),
            'classes': ('collapse',)
        }),
        ('Максимальные значения', {
            'fields': ('max_win', 'max_loss', 'max_drawdown'),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Запрет создания статистики вручную"""
        return False
