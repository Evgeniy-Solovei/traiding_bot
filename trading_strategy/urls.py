"""
Маршруты веб-кабинета.
"""

from django.urls import path

from .views import cabinet_dashboard, cabinet_login, cabinet_logout


urlpatterns = [
    path('login/', cabinet_login, name='cabinet_login'),
    path('logout/', cabinet_logout, name='cabinet_logout'),
    path('', cabinet_dashboard, name='cabinet_dashboard'),
]
