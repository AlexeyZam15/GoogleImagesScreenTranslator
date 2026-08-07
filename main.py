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

# === ИМПОРТ ДЛЯ ПРОВЕРКИ ВЕРСИИ ===
from src.version_checker import check_and_clean_version

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


def run_as_admin():
    """Перезапускает программу с правами администратора"""
    try:
        import ctypes
        import sys
        import os

        script_path = os.path.abspath(sys.argv[0])
        args = ' '.join([arg for arg in sys.argv[1:] if arg != '--admin'])

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
    # === ПРОВЕРКА ВЕРСИИ В САМОМ НАЧАЛЕ ===
    app_docs_path = Path.home() / "Documents" / "GoogleScreenTranslate"
    version_ok = check_and_clean_version(app_docs_path)
    if not version_ok:
        print("⚠️ Ошибка при проверке версии, работа продолжается...")

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

    # Инициализация настроек (после проверки версии)
    from src.settings import Settings

    settings = Settings()
    if not settings.profiles:
        settings.profiles = {
            "default": {
                "name": "Профиль по умолчанию",
                "pairs": []
            }
        }
        settings.save()

    if DEBUG_MODE:
        settings.set_show_browser(True)
        print("🔧 РЕЖИМ ОТЛАДКИ: браузер будет показан")
    else:
        settings.set_show_browser(False)

    from src.app import ScreenshotTranslatorApp

    app = ScreenshotTranslatorApp()
    app.run()
