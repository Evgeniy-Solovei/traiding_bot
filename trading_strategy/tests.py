from datetime import datetime, timedelta, timezone as dt_timezone
from decimal import Decimal

import pandas as pd
from django.test import SimpleTestCase

from .main_strategy import MainStrategy
from .scalping_strategy import ScalpingStrategy
from .models import UserTradingSettings
from .tasks import (
    count_consecutive_losses,
    extract_order_execution_price,
    extract_order_filled_amount,
    is_daily_loss_limit_reached,
    resolve_order_size_usd,
    trim_unclosed_candle,
)


class RiskSizingHelpersTests(SimpleTestCase):
    def test_resolve_order_size_fixed_mode(self):
        settings = UserTradingSettings(
            order_size_mode='fixed_usd',
            base_order_size=Decimal('7.50'),
            order_size_percent=Decimal('1.00'),
        )
        self.assertEqual(resolve_order_size_usd(settings, Decimal('500')), Decimal('7.50'))

    def test_resolve_order_size_percent_mode(self):
        settings = UserTradingSettings(
            order_size_mode='percent_balance',
            base_order_size=Decimal('7.50'),
            order_size_percent=Decimal('2.50'),
        )
        self.assertEqual(resolve_order_size_usd(settings, Decimal('200')), Decimal('7.50'))


class CandleFilteringTests(SimpleTestCase):
    def test_trim_unclosed_candle_removes_last_row_when_still_forming(self):
        now = datetime.now(dt_timezone.utc)
        df = pd.DataFrame(
            {
                'timestamp': [now - timedelta(minutes=10), now - timedelta(minutes=2)],
                'open': [1, 1],
                'high': [1, 1],
                'low': [1, 1],
                'close': [1, 1],
                'volume': [1, 1],
            }
        )

        trimmed = trim_unclosed_candle(df, '5m')
        self.assertEqual(len(trimmed), 1)

    def test_trim_unclosed_candle_keeps_closed_last_row(self):
        now = datetime.now(dt_timezone.utc)
        df = pd.DataFrame(
            {
                'timestamp': [now - timedelta(minutes=15), now - timedelta(minutes=7)],
                'open': [1, 1],
                'high': [1, 1],
                'low': [1, 1],
                'close': [1, 1],
                'volume': [1, 1],
            }
        )

        trimmed = trim_unclosed_candle(df, '5m')
        self.assertEqual(len(trimmed), 2)


class OrderExecutionHelpersTests(SimpleTestCase):
    def test_extract_order_execution_price_prefers_average(self):
        order = {'average': '101.5', 'price': '102', 'filled': '2', 'cost': '203'}
        self.assertEqual(extract_order_execution_price(order, fallback_price=100.0), 101.5)

    def test_extract_order_execution_price_uses_cost_div_filled_fallback(self):
        order = {'price': None, 'average': None, 'filled': '2', 'cost': '206'}
        self.assertEqual(extract_order_execution_price(order, fallback_price=100.0), 103.0)

    def test_extract_order_filled_amount_prefers_filled(self):
        order = {'filled': '0.123', 'amount': '0.150'}
        self.assertEqual(extract_order_filled_amount(order, fallback_amount=1.0), 0.123)


class MainStrategyChannelTests(SimpleTestCase):
    def test_find_channel_marks_valid_with_touches(self):
        strategy = MainStrategy()
        high = pd.Series(
            [100, 101, 100.5, 101, 100.7, 100.2, 101, 100.4, 100.6, 101,
             100.8, 100.9, 101, 100.3, 100.5, 101, 100.7, 100.8, 101, 100.6]
        )
        low = pd.Series(
            [95, 95.5, 96, 95, 95.3, 95.1, 95, 95.4, 95.2, 95,
             95.6, 95.5, 95, 95.3, 95.4, 95, 95.2, 95.1, 95, 95.3]
        )

        _, _, is_valid = strategy.find_channel(high, low, period=20)
        self.assertTrue(is_valid)

    def test_analyze_detailed_reports_invalid_channel_when_touches_are_missing(self):
        strategy = MainStrategy()
        closes = pd.Series([100 + (i * 0.0025) for i in range(80)])
        df = pd.DataFrame(
            {
                'open': closes,
                'high': closes * 1.0005,
                'low': closes * 0.9995,
                'close': closes,
                'volume': pd.Series([1000 + i for i in range(80)]),
            }
        )

        details = strategy.analyze_detailed(df)
        self.assertFalse(details['channel_valid'])
        self.assertIn('Канал невалиден', details['reason_no_signal'])


class MainStrategyRiskModelTests(SimpleTestCase):
    def test_sl_tp_calculated_from_price_percent_for_long(self):
        strategy = MainStrategy(stop_loss_percent=20.0, take_profit_percent=35.0, leverage=10)
        stop_loss, take_profit = strategy.calculate_sl_tp_prices(100.0, 'LONG')
        self.assertAlmostEqual(stop_loss, 80.0)
        self.assertAlmostEqual(take_profit, 135.0)

    def test_sl_tp_calculated_from_price_percent_for_short(self):
        strategy = MainStrategy(stop_loss_percent=20.0, take_profit_percent=35.0, leverage=10)
        stop_loss, take_profit = strategy.calculate_sl_tp_prices(100.0, 'SHORT')
        self.assertAlmostEqual(stop_loss, 120.0)
        self.assertAlmostEqual(take_profit, 65.0)

    def test_leverage_does_not_change_sl_tp_levels(self):
        strategy_x1 = MainStrategy(stop_loss_percent=20.0, take_profit_percent=35.0, leverage=1)
        strategy_x50 = MainStrategy(stop_loss_percent=20.0, take_profit_percent=35.0, leverage=50)

        stop_loss_x1, take_profit_x1 = strategy_x1.calculate_sl_tp_prices(250.0, 'LONG')
        stop_loss_x50, take_profit_x50 = strategy_x50.calculate_sl_tp_prices(250.0, 'LONG')

        self.assertAlmostEqual(stop_loss_x1, stop_loss_x50)
        self.assertAlmostEqual(take_profit_x1, take_profit_x50)


class ScalpingStrategyRiskModelTests(SimpleTestCase):
    def test_sl_tp_calculated_from_price_percent_for_long(self):
        strategy = ScalpingStrategy(stop_loss_percent=1.0, take_profit_percent=2.0, leverage=25)
        stop_loss, take_profit = strategy.calculate_sl_tp_prices(100.0, 'LONG')
        self.assertAlmostEqual(stop_loss, 99.0)
        self.assertAlmostEqual(take_profit, 102.0)

    def test_leverage_does_not_change_sl_tp_levels(self):
        strategy_x1 = ScalpingStrategy(stop_loss_percent=1.0, take_profit_percent=2.0, leverage=1)
        strategy_x50 = ScalpingStrategy(stop_loss_percent=1.0, take_profit_percent=2.0, leverage=50)

        stop_loss_x1, take_profit_x1 = strategy_x1.calculate_sl_tp_prices(250.0, 'SHORT')
        stop_loss_x50, take_profit_x50 = strategy_x50.calculate_sl_tp_prices(250.0, 'SHORT')

        self.assertAlmostEqual(stop_loss_x1, stop_loss_x50)
        self.assertAlmostEqual(take_profit_x1, take_profit_x50)


class RiskGuardHelpersTests(SimpleTestCase):
    def test_count_consecutive_losses(self):
        pnls = [Decimal('-1.00'), Decimal('-0.50'), Decimal('2.00'), Decimal('-3.00')]
        self.assertEqual(count_consecutive_losses(pnls), 2)

    def test_daily_loss_limit_reached(self):
        reached, limit_usd = is_daily_loss_limit_reached(
            daily_pnl=Decimal('-12.00'),
            current_balance=Decimal('88.00'),
            daily_loss_limit_percent=Decimal('10.00'),
        )
        self.assertTrue(reached)
        self.assertEqual(limit_usd, Decimal('10.00'))

    def test_daily_loss_limit_reached_with_unrealized_loss(self):
        reached, limit_usd = is_daily_loss_limit_reached(
            daily_pnl=Decimal('-1.00'),
            unrealized_pnl=Decimal('-9.00'),
            current_balance=Decimal('90.00'),
            daily_loss_limit_percent=Decimal('10.00'),
        )
        self.assertTrue(reached)
        self.assertEqual(limit_usd, Decimal('10.00'))

    def test_unrealized_profit_reduces_total_daily_loss(self):
        reached, _ = is_daily_loss_limit_reached(
            daily_pnl=Decimal('-9.00'),
            unrealized_pnl=Decimal('4.00'),
            current_balance=Decimal('95.00'),
            daily_loss_limit_percent=Decimal('10.00'),
        )
        self.assertFalse(reached)
