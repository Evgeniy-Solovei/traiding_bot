"""
Конфигурация Celery для асинхронных задач.
"""

import os
from celery import Celery
from celery.schedules import crontab

# Установка настроек Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('trading_bot')

# Загрузка конфигурации из Django settings
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматическое обнаружение tasks.py в приложениях Django
app.autodiscover_tasks()


# ==== ПЕРИОДИЧЕСКИЕ ЗАДАЧИ ====
app.conf.beat_schedule = {
    # Мониторинг рынка каждые 1 минуту для таймфрейма 5m
    'monitor-market-5m': {
        'task': 'trading.tasks.monitor_market',
        'schedule': 60.0,  # каждые 60 секунд
        'args': ('5m',)
    },
    
    # Проверка открытых позиций каждые 30 секунд
    'check-open-positions': {
        'task': 'trading.tasks.check_open_positions',
        'schedule': 30.0,  # каждые 30 секунд
    },
    
    # Обновление статистики раз в час
    'update-statistics': {
        'task': 'trading.tasks.update_user_statistics',
        'schedule': crontab(minute=0),  # каждый час
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Тестовая задача для отладки"""
    print(f'Request: {self.request!r}')
