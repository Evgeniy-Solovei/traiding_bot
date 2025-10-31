"""
Административная панель для Telegram бота.
"""

from django.contrib import admin
from .models import BotUser


@admin.register(BotUser)
class BotUserAdmin(admin.ModelAdmin):
    """Администрирование пользователей бота"""
    list_display = (
        'telegram_id', 'username', 'full_name',
        'django_user', 'is_active', 'created_at', 'last_activity'
    )
    list_filter = ('is_active', 'created_at', 'last_activity')
    search_fields = ('telegram_id', 'username', 'first_name', 'last_name', 'django_user__username')
    readonly_fields = ('created_at', 'last_activity')
    
    fieldsets = (
        ('Telegram информация', {
            'fields': ('telegram_id', 'username', 'first_name', 'last_name')
        }),
        ('Связь с Django', {
            'fields': ('django_user',)
        }),
        ('Статус', {
            'fields': ('is_active',)
        }),
        ('Метаданные', {
            'fields': ('created_at', 'last_activity'),
            'classes': ('collapse',)
        }),
    )
