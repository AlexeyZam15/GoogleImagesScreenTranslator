#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Точка входа в приложение GoogleScreenTranslate
"""

import sys
import os
import argparse
import logging


def main():
    """Главная функция запуска приложения"""

    # Парсинг аргументов командной строки
    parser = argparse.ArgumentParser(description='Google Screen Translate')
    parser.add_argument('--debug', action='store_true', help='Включить режим отладки')
    args = parser.parse_args()

    # Устанавливаем флаг отладки
    debug_mode = args.debug

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
        # Включаем вывод логов в консоль
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        print("🐞 Отладка: добавлена дополнительная информация в логи")

    try:
        from src.app import ScreenshotTranslatorApp

        print("⏳ Запуск приложения...")

        # Передаем флаг отладки в приложение
        app = ScreenshotTranslatorApp(debug_mode=debug_mode)

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