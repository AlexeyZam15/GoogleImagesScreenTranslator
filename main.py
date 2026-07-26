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
ADMIN_MODE = '--admin' in sys.argv


def is_admin():
    """Проверяет, запущена ли программа с правами администратора"""
    try:
        import ctypes
        return ctypes.windll.shell32.IsUserAnAdmin() != 0
    except:
        return False


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


def run_as_admin():
    """Перезапускает программу с правами администратора"""
    try:
        import ctypes
        import sys
        import os

        # Получаем путь к текущему скрипту
        script_path = os.path.abspath(sys.argv[0])
        # Формируем аргументы командной строки (убираем --admin чтобы не было рекурсии)
        args = ' '.join([arg for arg in sys.argv[1:] if arg != '--admin'])

        # Запускаем с правами администратора
        ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            sys.executable,
            f'"{script_path}" {args}',
            None,
            1
        )
        return True
    except Exception as e:
        print(f"Ошибка при запросе прав администратора: {e}")
        return False


if __name__ == "__main__":
    # Проверяем режим администратора
    if ADMIN_MODE and not is_admin():
        print("👑 Запрос прав администратора...")
        if run_as_admin():
            print("✅ Программа перезапущена с правами администратора")
            sys.exit(0)
        else:
            print("❌ Не удалось получить права администратора")
            print("⚠️ Программа будет запущена с ограниченными правами")
    elif ADMIN_MODE and is_admin():
        print("👑 РЕЖИМ АДМИНИСТРАТОРА: программа запущена с правами администратора")

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