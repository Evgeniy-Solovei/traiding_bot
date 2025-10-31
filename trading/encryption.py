"""
Утилита для шифрования и дешифрования API ключей.
Использует Fernet (симметричное шифрование) из cryptography.
"""

from cryptography.fernet import Fernet
from django.conf import settings
import os


class EncryptionManager:
    """
    Менеджер для безопасного шифрования и дешифрования данных.
    """
    
    def __init__(self):
        """
        Инициализация с ключом шифрования.
        Если ключ не указан в settings, генерирует новый.
        """
        encryption_key = settings.ENCRYPTION_KEY
        
        if not encryption_key:
            # Генерируем новый ключ, если не указан
            encryption_key = Fernet.generate_key().decode()
            print(f"⚠️  ВНИМАНИЕ: Сгенерирован новый ключ шифрования!")
            print(f"📝 Добавьте его в .env файл:")
            print(f"   ENCRYPTION_KEY={encryption_key}")
            print(f"⚠️  БЕЗ ЭТОГО КЛЮЧА НЕВОЗМОЖНО РАСШИФРОВАТЬ ДАННЫЕ!")
        
        self.cipher = Fernet(encryption_key.encode() if isinstance(encryption_key, str) else encryption_key)
    
    def encrypt(self, plain_text: str) -> bytes:
        """
        Шифрует строку и возвращает байты.
        
        Args:
            plain_text: Исходный текст для шифрования
            
        Returns:
            bytes: Зашифрованные данные
        """
        if not plain_text:
            raise ValueError("Невозможно зашифровать пустую строку")
        
        return self.cipher.encrypt(plain_text.encode())
    
    def decrypt(self, encrypted_data: bytes) -> str:
        """
        Дешифрует байты и возвращает строку.
        
        Args:
            encrypted_data: Зашифрованные данные
            
        Returns:
            str: Расшифрованный текст
        """
        if not encrypted_data:
            raise ValueError("Невозможно расшифровать пустые данные")
        
        try:
            decrypted = self.cipher.decrypt(encrypted_data)
            return decrypted.decode()
        except Exception as e:
            raise ValueError(f"Ошибка дешифрования: {str(e)}")
    
    @staticmethod
    def generate_key() -> str:
        """
        Генерирует новый ключ шифрования.
        
        Returns:
            str: Новый ключ шифрования в base64
        """
        return Fernet.generate_key().decode()


# Глобальный экземпляр для использования в проекте
encryption_manager = EncryptionManager()


def encrypt_api_credentials(api_key: str, api_secret: str) -> tuple:
    """
    Шифрует API ключ и секрет.
    
    Args:
        api_key: API ключ
        api_secret: API секрет
        
    Returns:
        tuple: (зашифрованный_ключ, зашифрованный_секрет)
    """
    encrypted_key = encryption_manager.encrypt(api_key)
    encrypted_secret = encryption_manager.encrypt(api_secret)
    return encrypted_key, encrypted_secret


def decrypt_api_credentials(encrypted_key: bytes, encrypted_secret: bytes) -> tuple:
    """
    Дешифрует API ключ и секрет.
    
    Args:
        encrypted_key: Зашифрованный API ключ
        encrypted_secret: Зашифрованный API секрет
        
    Returns:
        tuple: (api_ключ, api_секрет)
    """
    api_key = encryption_manager.decrypt(encrypted_key)
    api_secret = encryption_manager.decrypt(encrypted_secret)
    return api_key, api_secret
