"""
Веб-кабинет для управления API ключами и торговыми настройками.
"""

import asyncio

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.shortcuts import redirect, render

from .encryption import decrypt_api_credentials, encrypt_api_credentials
from .exchange_client import test_connection
from .forms import APICredentialsForm, TradingSettingsForm
from .models import Exchange, UserTradingSettings


def _mask_api_key(api_key: str) -> str:
    """Возвращает маску API ключа для отображения в кабинете."""
    if len(api_key) <= 8:
        return '***'
    return f"{api_key[:4]}...{api_key[-4:]}"


def cabinet_login(request):
    """
    Авторизация в веб-кабинете.
    """
    if request.user.is_authenticated:
        return redirect('cabinet_dashboard')

    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        login(request, form.get_user())
        return redirect('cabinet_dashboard')

    return render(request, 'cabinet/login.html', {'form': form})


@login_required(login_url='cabinet_login')
def cabinet_logout(request):
    """
    Выход из кабинета.
    """
    logout(request)
    return redirect('cabinet_login')


@login_required(login_url='cabinet_login')
def cabinet_dashboard(request):
    """
    Главная страница кабинета:
    - управление API ключами Bybit
    - торговые настройки
    """
    trading_settings, _ = UserTradingSettings.objects.get_or_create(user=request.user)
    exchange = Exchange.objects.filter(user=request.user, name='bybit').first()

    api_initial = {
        'is_testnet': exchange.is_testnet if exchange else True,
        'is_active': exchange.is_active if exchange else True,
        'validate_connection': True,
    }

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'save_api':
            api_form = APICredentialsForm(request.POST, initial=api_initial)
            settings_form = TradingSettingsForm(instance=trading_settings)

            if api_form.is_valid():
                api_key = (api_form.cleaned_data.get('api_key') or '').strip()
                api_secret = (api_form.cleaned_data.get('api_secret') or '').strip()
                is_testnet = api_form.cleaned_data['is_testnet']
                is_active = api_form.cleaned_data['is_active']
                validate_connection = api_form.cleaned_data['validate_connection']

                if not exchange and not (api_key and api_secret):
                    api_form.add_error(None, 'Для первого сохранения API ключей заполните API Key и API Secret.')
                else:
                    if validate_connection and api_key and api_secret:
                        try:
                            test_result = asyncio.run(test_connection(api_key, api_secret, is_testnet))
                            if not test_result.get('success'):
                                api_form.add_error(None, f"Ошибка подключения: {test_result.get('message')}")
                        except Exception as exc:
                            api_form.add_error(None, f'Не удалось проверить подключение: {exc}')

                if not api_form.errors:
                    if exchange is None:
                        encrypted_key, encrypted_secret = encrypt_api_credentials(api_key, api_secret)
                        exchange = Exchange.objects.create(
                            user=request.user,
                            name='bybit',
                            api_key_encrypted=encrypted_key,
                            api_secret_encrypted=encrypted_secret,
                            is_testnet=is_testnet,
                            is_active=is_active,
                        )
                    else:
                        if api_key and api_secret:
                            encrypted_key, encrypted_secret = encrypt_api_credentials(api_key, api_secret)
                            exchange.api_key_encrypted = encrypted_key
                            exchange.api_secret_encrypted = encrypted_secret

                        exchange.is_testnet = is_testnet
                        exchange.is_active = is_active
                        exchange.save(update_fields=[
                            'api_key_encrypted',
                            'api_secret_encrypted',
                            'is_testnet',
                            'is_active',
                            'updated_at',
                        ])

                    messages.success(request, 'API ключи сохранены.')
                    return redirect('cabinet_dashboard')

        elif action == 'save_settings':
            settings_form = TradingSettingsForm(request.POST, instance=trading_settings)
            api_form = APICredentialsForm(initial=api_initial)

            if settings_form.is_valid():
                saved_settings = settings_form.save()
                if saved_settings.is_trading_active and saved_settings.is_risk_paused:
                    saved_settings.is_risk_paused = False
                    saved_settings.risk_pause_reason = ''
                    saved_settings.risk_paused_at = None
                    saved_settings.save(update_fields=['is_risk_paused', 'risk_pause_reason', 'risk_paused_at', 'updated_at'])
                messages.success(request, 'Торговые настройки сохранены.')
                return redirect('cabinet_dashboard')
        else:
            api_form = APICredentialsForm(initial=api_initial)
            settings_form = TradingSettingsForm(instance=trading_settings)
    else:
        api_form = APICredentialsForm(initial=api_initial)
        settings_form = TradingSettingsForm(instance=trading_settings)

    api_key_hint = None
    if exchange:
        try:
            api_key_raw, _ = decrypt_api_credentials(exchange.api_key_encrypted, exchange.api_secret_encrypted)
            api_key_hint = _mask_api_key(api_key_raw)
        except Exception:
            api_key_hint = 'ключ сохранен'

    context = {
        'api_form': api_form,
        'settings_form': settings_form,
        'exchange': exchange,
        'api_key_hint': api_key_hint,
    }
    return render(request, 'cabinet/dashboard.html', context)
