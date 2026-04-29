"""
Формы веб-кабинета для управления API ключами и торговыми настройками.
"""

from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError

from .models import UserTradingSettings


class APICredentialsForm(forms.Form):
    """
    Форма API-ключей Bybit.

    API key/secret можно оставить пустыми только если ключи уже были сохранены ранее
    и пользователь меняет только сеть/статус.
    """

    api_key = forms.CharField(
        label='API Key',
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'off'}),
    )
    api_secret = forms.CharField(
        label='API Secret',
        required=False,
        widget=forms.PasswordInput(render_value=False, attrs={'autocomplete': 'off'}),
    )
    is_testnet = forms.BooleanField(
        label='Использовать testnet',
        required=False,
        initial=True,
    )
    is_active = forms.BooleanField(
        label='Ключи активны',
        required=False,
        initial=True,
    )
    validate_connection = forms.BooleanField(
        label='Проверить подключение перед сохранением',
        required=False,
        initial=True,
    )

    def clean(self):
        cleaned_data = super().clean()
        api_key = (cleaned_data.get('api_key') or '').strip()
        api_secret = (cleaned_data.get('api_secret') or '').strip()

        if (api_key and not api_secret) or (api_secret and not api_key):
            raise ValidationError('Введите и API Key, и API Secret, либо оставьте оба поля пустыми.')

        return cleaned_data


class TradingSettingsForm(forms.ModelForm):
    """
    Форма торговых настроек для кабинета.
    """

    class Meta:
        model = UserTradingSettings
        fields = [
            'base_order_size',
            'leverage',
            'daily_loss_limit_percent',
            'max_consecutive_losses',
            'auto_pause_on_risk',
            'is_trading_active',
            'is_test_mode',
        ]

    def clean(self):
        cleaned_data = super().clean()
        base_order_size = cleaned_data.get('base_order_size')

        if base_order_size is None or base_order_size < Decimal('1.00'):
            self.add_error('base_order_size', 'Укажите фиксированный размер ордера минимум $1.')

        daily_loss_limit_percent = cleaned_data.get('daily_loss_limit_percent')
        if daily_loss_limit_percent is not None and (
            daily_loss_limit_percent < Decimal('0.10') or daily_loss_limit_percent > Decimal('100.00')
        ):
            self.add_error('daily_loss_limit_percent', 'Дневной лимит убытка должен быть в диапазоне 0.10% - 100.00%.')

        max_consecutive_losses = cleaned_data.get('max_consecutive_losses')
        if max_consecutive_losses is not None and not (1 <= max_consecutive_losses <= 20):
            self.add_error('max_consecutive_losses', 'Серия убыточных сделок должна быть от 1 до 20.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        # Принудительно фиксированный режим размера ордера
        instance.order_size_mode = 'fixed_usd'
        if commit:
            instance.save()
        return instance
