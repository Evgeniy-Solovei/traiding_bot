"""
Модели для Telegram бота.
Связь Telegram пользователей с Django User.
"""

from django.db import models
from django.contrib.auth.models import User


class BotUser(models.Model):
    """
    Связь между Telegram пользователем и Django User.
    """
    telegram_id = models.BigIntegerField(unique=True, verbose_name='Telegram ID')
    username = models.CharField(max_length=255, blank=True, null=True, verbose_name='Username')
    first_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Имя')
    last_name = models.CharField(max_length=255, blank=True, null=True, verbose_name='Фамилия')
    
    # Связь с Django User
    django_user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        related_name='bot_profile',
        verbose_name='Django пользователь'
    )
    
    # Метаданные
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')
    last_activity = models.DateTimeField(auto_now=True, verbose_name='Последняя активность')
    
    class Meta:
        verbose_name = 'Пользователь бота'
        verbose_name_plural = 'Пользователи бота'
        ordering = ['-created_at']
    
    def __str__(self):
        username_str = f"@{self.username}" if self.username else str(self.telegram_id)
        return f"{username_str} ({self.django_user.username})"
    
    @property
    def full_name(self):
        """Полное имя пользователя"""
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.username:
            return f"@{self.username}"
        else:
            return str(self.telegram_id)
