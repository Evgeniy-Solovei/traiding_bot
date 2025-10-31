#!/usr/bin/env python3
"""
Генератор ключа шифрования для .env файла.
"""

from cryptography.fernet import Fernet

if __name__ == "__main__":
    key = Fernet.generate_key().decode()
    print("\n" + "="*60)
    print("🔐 КЛЮЧ ШИФРОВАНИЯ СГЕНЕРИРОВАН")
    print("="*60)
    print("\nДобавьте эту строку в ваш .env файл:")
    print(f"\nENCRYPTION_KEY={key}")
    print("\n" + "="*60)
    print("⚠️  ВАЖНО: Сохраните этот ключ в безопасном месте!")
    print("   Без него невозможно расшифровать API ключи пользователей.")
    print("="*60 + "\n")
