#!/usr/bin/env python3
"""
Точка входа для программы перевода скриншотов
"""

import sys
import os
import logging
from pathlib import Path

# Добавляем папку src в путь импорта
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.app import ScreenshotTranslatorApp
from src.settings import Settings

# Проверяем аргументы командной строки
DEBUG_MODE = '--debug' in sys.argv or '-d' in sys.argv


def ensure_app_directories():
    """Создает все необходимые папки приложения"""
    try:
        config_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "config"
        logs_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "logs"
        temp_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "temp"
        config_dir.mkdir(parents=True, exist_ok=True)
        logs_dir.mkdir(parents=True, exist_ok=True)
        temp_dir.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        print(f"Ошибка создания папок: {e}")
        return False


if __name__ == "__main__":
    # Создаем необходимые папки
    ensure_app_directories()

    # Инициализация настроек
    settings = Settings()
    if not settings.profiles:
        settings.profiles = {
            "default": {
                "name": "Профиль по умолчанию",
                "pairs": []
            }
        }
        settings.save()

    # Если включен режим отладки - показываем браузер
    if DEBUG_MODE:
        settings.set_show_browser(True)
        print("🔧 РЕЖИМ ОТЛАДКИ: браузер будет показан")
    else:
        # В обычном режиме браузер скрыт
        settings.set_show_browser(False)

    app = ScreenshotTranslatorApp()
    app.run()
