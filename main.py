#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Точка входа в приложение GoogleScreenTranslate
"""

import sys
import os
import argparse
import logging
from pathlib import Path


def main():
    """Главная функция запуска приложения"""

    # ============================================================
    # ДОБАВЛЯЕМ: ПРОВЕРКА ВЕРСИИ ПРИ ЗАПУСКЕ
    # ============================================================
    try:
        from src.version_checker import check_and_clean_version
        app_docs_path = Path.home() / "Documents" / "GoogleScreenTranslate"
        check_and_clean_version(app_docs_path)
        print("✅ Проверка версии выполнена")
    except Exception as e:
        print(f"⚠️ Ошибка проверки версии: {e}")

    # ============================================================
    # ОЧИСТКА СТАРЫХ ВРЕМЕННЫХ ПРОФИЛЕЙ ПРИ ЗАПУСКЕ (старше 7 дней)
    # ============================================================
    try:
        from src.temp_cleaner import cleanup_old_profiles
        deleted = cleanup_old_profiles(max_age_days=7)
        if deleted > 0:
            print(f"🧹 Удалено {deleted} старых временных папок")
    except Exception as e:
        print(f"⚠️ Ошибка очистки временных папок: {e}")

    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Google Screen Translate')
    parser.add_argument('--debug', action='store_true', help='Включить режим отладки')
    args = parser.parse_args()

    debug_mode = args.debug

    if getattr(sys, 'frozen', False) and not debug_mode:
        debug_mode = False
        print("🔧 Запуск из .exe: debug-режим отключён")

    # Настройка путей
    project_root = os.path.dirname(os.path.abspath(__file__))
    src_path = os.path.join(project_root, 'src')

    if src_path not in sys.path:
        sys.path.insert(0, project_root)
        sys.path.insert(0, src_path)

    print("=" * 70)
    print("🚀 ЗАПУСК GoogleScreenTranslate")
    print("=" * 70)
    print(f"📂 Текущая директория: {os.getcwd()}")
    print(f"🐍 Python: {sys.executable}")
    print(f"📋 Аргументы: {sys.argv}")
    print(f"🔧 Режим отладки: {'ВКЛЮЧЕН' if debug_mode else 'ВЫКЛЮЧЕН'}")
    print("=" * 70)

    if debug_mode:
        print("🐞 РЕЖИМ ОТЛАДКИ ВКЛЮЧЕН")
        print("=" * 70)
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        print("🐞 Отладка: добавлена дополнительная информация в логи")

    try:
        from src.app import ScreenshotTranslatorApp

        print("⏳ Запуск приложения...")

        # Создаём приложение
        app = ScreenshotTranslatorApp(debug_mode=debug_mode)

        # ============================================================
        # ПРИНУДИТЕЛЬНАЯ ОТРИСОВКА ОКНА ПЕРЕД ВХОДОМ В ГЛАВНЫЙ ЦИКЛ
        # ============================================================
        if hasattr(app, 'ui') and hasattr(app.ui, 'root'):
            app.ui.root.update()
            app.ui.root.update_idletasks()
            print("✅ Окно отрисовано")

        print("✅ Приложение запущено, вход в главный цикл...")
        app.run()

    except KeyboardInterrupt:
        print("\n⏹️ Приложение остановлено пользователем")
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        input("Нажмите Enter для выхода...")
        sys.exit(1)


if __name__ == "__main__":
    main()
