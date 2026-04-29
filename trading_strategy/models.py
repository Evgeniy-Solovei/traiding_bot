"""
Модели для торгового приложения.
Хранят настройки пользователей, биржи, торговые пары и историю сделок.
"""

from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal


class Exchange(models.Model):
    """
    Биржа пользователя с зашифрованными API ключами.
    """
    EXCHANGE_CHOICES = [
        ('bybit', 'Bybit'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='exchanges', verbose_name='Пользователь')
    name = models.CharField(max_length=50, choices=EXCHANGE_CHOICES, default='bybit', verbose_name='Название биржи')
    api_key_encrypted = models.BinaryField(verbose_name='Зашифрованный API ключ')
    api_secret_encrypted = models.BinaryField(verbose_name='Зашифрованный API секрет')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    is_testnet = models.BooleanField(default=True, verbose_name='Тестовая сеть')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Биржа'
        verbose_name_plural = 'Биржи'
        unique_together = ['user', 'name']
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.name} ({'testnet' if self.is_testnet else 'mainnet'})"


class UserTradingSettings(models.Model):
    """
    Настройки торговли пользователя.
    Включает параметры риск-менеджмента и настройки стратегии.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='trading_settings', verbose_name='Пользователь')
    
    # === НАСТРАИВАЕМЫЕ ПАРАМЕТРЫ ===
    ORDER_SIZE_MODE_CHOICES = [
        ('fixed_usd', 'Фиксированный размер ($)'),
        ('percent_balance', 'Процент от депозита (%)'),
    ]

    order_size_mode = models.CharField(
        max_length=20,
        choices=ORDER_SIZE_MODE_CHOICES,
        default='fixed_usd',
        verbose_name='Режим размера ордера',
        help_text='Фиксированная сумма в $ или процент от свободного баланса USDT'
    )

    base_order_size = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('5.00'),
        validators=[MinValueValidator(Decimal('1.00'))],
        verbose_name='Базовый размер ордера ($)',
        help_text='Размер позиции в долларах'
    )

    order_size_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.10')), MaxValueValidator(Decimal('100.00'))],
        verbose_name='Размер ордера (% от депозита)',
        help_text='Используется при режиме "Процент от депозита"'
    )
    
    leverage = models.IntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        verbose_name='Плечо',
        help_text='Размер плеча (1-100x)'
    )
    
    risk_per_trade = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('1.00'),
        validators=[MinValueValidator(Decimal('0.10')), MaxValueValidator(Decimal('100.00'))],
        verbose_name='Риск на сделку (%)',
        help_text='Процент от депозита, который рискуете на одной сделке'
    )

    daily_loss_limit_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('3.00'),
        validators=[MinValueValidator(Decimal('0.10')), MaxValueValidator(Decimal('100.00'))],
        verbose_name='Дневной лимит убытка (%)',
        help_text='При достижении этого лимита торговля автоматически ставится на паузу'
    )

    max_consecutive_losses = models.IntegerField(
        default=3,
        validators=[MinValueValidator(1), MaxValueValidator(20)],
        verbose_name='Максимум убыточных подряд',
        help_text='После N убыточных сделок подряд торговля автоматически ставится на паузу'
    )

    auto_pause_on_risk = models.BooleanField(
        default=True,
        verbose_name='Автопауза по рискам',
        help_text='Если включено, бот останавливает торговлю при срабатывании лимитов'
    )
    
    # Выбор стратегии
    strategy_name = models.CharField(
        max_length=50,
        default='main',
        verbose_name='Стратегия',
        help_text='Название используемой стратегии'
    )
    
    # === ФИКСИРОВАННЫЕ ПАРАМЕТРЫ СТРАТЕГИИ (НЕ МЕНЯЮТСЯ) ===
    timeframe = models.CharField(
        max_length=10, 
        default='5m', 
        verbose_name='Таймфрейм',
        help_text='Таймфрейм для анализа (зашит в стратегии)'
    )
    
    # Параметры индикаторов (зашиты в стратегию, не меняются пользователем)
    ema_fast_period = models.IntegerField(default=9, verbose_name='Период быстрой EMA')
    ema_slow_period = models.IntegerField(default=21, verbose_name='Период медленной EMA')
    rsi_period = models.IntegerField(default=14, verbose_name='Период RSI')
    williams_r_period = models.IntegerField(default=14, verbose_name='Период Williams %R')
    channel_period = models.IntegerField(default=20, verbose_name='Период канала (свечей)')
    
    # Параметры управления рисками
    atr_period = models.IntegerField(default=14, verbose_name='Период ATR')
    stop_loss_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('20.00'),
        verbose_name='Стоп-лосс (% от цены входа)'
    )
    take_profit_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('35.00'),
        verbose_name='Тейк-профит (% от цены входа)'
    )
    # Старые поля для обратной совместимости (deprecated)
    stop_loss_atr_multiplier = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        default=Decimal('1.5'),
        verbose_name='[DEPRECATED] Множитель ATR для стоп-лосса'
    )
    take_profit_atr_multiplier = models.DecimalField(
        max_digits=3, 
        decimal_places=1, 
        default=Decimal('2.5'),
        verbose_name='[DEPRECATED] Множитель ATR для тейк-профита'
    )
    
    # Статус торговли
    is_trading_active = models.BooleanField(default=False, verbose_name='Торговля активна')
    is_test_mode = models.BooleanField(default=False, verbose_name='Тестовый режим', 
                                       help_text='Если True, сигналы отправляются как уведомления без реальных сделок')
    is_risk_paused = models.BooleanField(default=False, verbose_name='Пауза по рискам')
    risk_pause_reason = models.TextField(blank=True, verbose_name='Причина паузы по рискам')
    risk_paused_at = models.DateTimeField(null=True, blank=True, verbose_name='Время паузы по рискам')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Настройки торговли'
        verbose_name_plural = 'Настройки торговли'

    def __str__(self):
        size_desc = f"${self.base_order_size}"
        return f"Настройки {self.user.username} | Ордер: {size_desc} | Плечо: {self.leverage}x | Риск: {self.risk_per_trade}%"


class TradingPair(models.Model):
    """
    Торговая пара, которую отслеживает пользователь.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trading_pairs', verbose_name='Пользователь')
    symbol = models.CharField(max_length=20, verbose_name='Символ', help_text='Например: BTCUSDT')
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Торговая пара'
        verbose_name_plural = 'Торговые пары'
        unique_together = ['user', 'symbol']
        ordering = ['symbol']

    def __str__(self):
        return f"{self.user.username} - {self.symbol}"


class Trade(models.Model):
    """
    История торговых сделок.
    """
    SIDE_CHOICES = [
        ('long', 'LONG'),
        ('short', 'SHORT'),
    ]
    
    STATUS_CHOICES = [
        ('open', 'Открыта'),
        ('closed', 'Закрыта'),
        ('cancelled', 'Отменена'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trades', verbose_name='Пользователь')
    exchange = models.ForeignKey(Exchange, on_delete=models.SET_NULL, null=True, related_name='trades', verbose_name='Биржа')
    symbol = models.CharField(max_length=20, verbose_name='Символ')
    side = models.CharField(max_length=10, choices=SIDE_CHOICES, verbose_name='Направление')
    
    # Параметры позиции
    entry_price = models.DecimalField(max_digits=15, decimal_places=6, verbose_name='Цена входа')
    exit_price = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True, verbose_name='Цена выхода')
    quantity = models.DecimalField(max_digits=15, decimal_places=6, verbose_name='Количество')
    leverage = models.IntegerField(verbose_name='Плечо')
    
    # Риск-менеджмент
    stop_loss = models.DecimalField(max_digits=15, decimal_places=6, verbose_name='Стоп-лосс')
    take_profit = models.DecimalField(max_digits=15, decimal_places=6, verbose_name='Тейк-профит')
    
    # Результаты
    pnl = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='PnL ($)')
    pnl_percent = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name='PnL (%)')
    
    # Ордера на бирже
    order_id = models.CharField(max_length=100, blank=True, verbose_name='ID ордера')
    
    # Статус и время
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open', verbose_name='Статус')
    opened_at = models.DateTimeField(auto_now_add=True, verbose_name='Время открытия')
    closed_at = models.DateTimeField(null=True, blank=True, verbose_name='Время закрытия')
    
    # Дополнительная информация
    notes = models.TextField(blank=True, verbose_name='Заметки', help_text='Причина открытия/закрытия позиции')

    class Meta:
        verbose_name = 'Сделка'
        verbose_name_plural = 'Сделки'
        ordering = ['-opened_at']

    def __str__(self):
        return f"{self.user.username} | {self.side.upper()} {self.symbol} @ ${self.entry_price} | {self.status}"

    def calculate_pnl(self):
        """Расчет PnL при закрытии позиции"""
        if self.exit_price and self.status == 'closed':
            if self.side == 'long':
                pnl_value = (self.exit_price - self.entry_price) * self.quantity
            else:  # short
                pnl_value = (self.entry_price - self.exit_price) * self.quantity
            
            self.pnl = pnl_value
            self.pnl_percent = (pnl_value / (self.entry_price * self.quantity)) * 100
            self.save()
            return self.pnl
        return None


class TradingStatistics(models.Model):
    """
    Статистика торговли пользователя.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='trading_stats', verbose_name='Пользователь')
    
    # Общая статистика
    total_trades = models.IntegerField(default=0, verbose_name='Всего сделок')
    winning_trades = models.IntegerField(default=0, verbose_name='Прибыльных сделок')
    losing_trades = models.IntegerField(default=0, verbose_name='Убыточных сделок')
    
    # Финансовая статистика
    total_pnl = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), verbose_name='Общий PnL ($)')
    total_pnl_percent = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal('0.00'), verbose_name='Общий PnL (%)')
    
    # Средние значения
    average_win = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Средняя прибыль ($)')
    average_loss = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Средний убыток ($)')
    
    # Максимальные значения
    max_win = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Максимальная прибыль ($)')
    max_loss = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Максимальный убыток ($)')
    max_drawdown = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name='Максимальная просадка ($)')
    
    # Win Rate
    win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal('0.00'), verbose_name='Винрейт (%)')
    
    # Временные метки
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Статистика торговли'
        verbose_name_plural = 'Статистика торговли'

    def __str__(self):
        return f"Статистика {self.user.username} | Сделок: {self.total_trades} | Винрейт: {self.win_rate}%"

    def update_statistics(self):
        """Обновление статистики на основе закрытых сделок"""
        closed_trades = Trade.objects.filter(user=self.user, status='closed')
        
        self.total_trades = closed_trades.count()
        self.winning_trades = closed_trades.filter(pnl__gt=0).count()
        self.losing_trades = closed_trades.filter(pnl__lt=0).count()
        
        if self.total_trades > 0:
            self.total_pnl = sum([trade.pnl or 0 for trade in closed_trades])
            self.win_rate = (self.winning_trades / self.total_trades) * 100
            
            winning_trades_list = closed_trades.filter(pnl__gt=0)
            losing_trades_list = closed_trades.filter(pnl__lt=0)
            
            if winning_trades_list.exists():
                self.average_win = sum([trade.pnl for trade in winning_trades_list]) / len(winning_trades_list)
                self.max_win = max([trade.pnl for trade in winning_trades_list])
            
            if losing_trades_list.exists():
                self.average_loss = sum([trade.pnl for trade in losing_trades_list]) / len(losing_trades_list)
                self.max_loss = min([trade.pnl for trade in losing_trades_list])
        
        self.save()


class SignalHistory(models.Model):
    """
    История сигналов стратегии для анализа и статистики.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='signal_history', verbose_name='Пользователь')
    symbol = models.CharField(max_length=20, verbose_name='Символ')
    
    # Данные сигнала
    signal = models.CharField(max_length=10, choices=[('LONG', 'LONG'), ('SHORT', 'SHORT')], verbose_name='Направление')
    entry_price = models.DecimalField(max_digits=15, decimal_places=6, verbose_name='Цена входа')
    stop_loss = models.DecimalField(max_digits=15, decimal_places=6, verbose_name='Стоп-лосс')
    take_profit = models.DecimalField(max_digits=15, decimal_places=6, verbose_name='Тейк-профит')
    confidence = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Уверенность (%)')
    reason = models.TextField(blank=True, verbose_name='Причина сигнала')
    
    # Результат (заполняется позже)
    was_opened = models.BooleanField(default=False, verbose_name='Позиция была открыта')
    was_profitable = models.BooleanField(null=True, blank=True, verbose_name='Прибыльная сделка')
    actual_pnl = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name='Фактический PnL')
    
    # Индикаторы на момент сигнала
    ema9 = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True, verbose_name='EMA9')
    ema21 = models.DecimalField(max_digits=15, decimal_places=6, null=True, blank=True, verbose_name='EMA21')
    rsi = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='RSI')
    williams_r = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name='Williams %R')
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Время сигнала')
    
    class Meta:
        verbose_name = 'История сигналов'
        verbose_name_plural = 'История сигналов'
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.username} | {self.signal} {self.symbol} @ {self.created_at.strftime('%Y-%m-%d %H:%M')}"
