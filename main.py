#!/usr/bin/env python
"""
Точка входа в приложение GoogleScreenTranslate
"""

import sys
import os
import argparse
import tkinter as tk
from pathlib import Path

# Добавляем корневую папку в путь
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.app import ScreenshotTranslatorApp
from src.version_checker import check_and_clean_version, APP_VERSION


def parse_arguments():
    """Парсит аргументы командной строки"""
    parser = argparse.ArgumentParser(
        description="GoogleScreenTranslate - перевод скриншотов через Google Translate",
        epilog="Пример: python main.py --debug"
    )

    parser.add_argument(
        '--debug',
        '-d',
        action='store_true',
        help='Включить режим отладки (подробные логи)'
    )

    parser.add_argument(
        '--no-browser',
        action='store_true',
        help='Запустить без отображения браузера'
    )

    parser.add_argument(
        '--lang',
        '-l',
        type=str,
        choices=['ru', 'en'],
        default=None,
        help='Язык интерфейса (ru/en)'
    )

    parser.add_argument(
        '--version',
        '-v',
        action='version',
        version=f'GoogleScreenTranslate v{APP_VERSION}'
    )

    return parser.parse_args()


def setup_debug_logging():
    """Настраивает расширенное логирование для debug режима"""
    import logging

    # Устанавливаем уровень логирования DEBUG для всех модулей
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Включаем DEBUG для всех модулей src
    for logger_name in ['src.app', 'src.overlay', 'src.overlay_manager',
                        'src.hotkeys', 'src.translation_monitor',
                        'src.browser_worker', 'src.translator']:
        logging.getLogger(logger_name).setLevel(logging.DEBUG)

    # Отключаем излишние логи от сторонних библиотек
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)

    print("🐞 РЕЖИМ ОТЛАДКИ ВКЛЮЧЕН")
    print("=" * 70)


def main():
    """Главная функция запуска"""
    # Парсим аргументы командной строки
    args = parse_arguments()

    print("=" * 70)
    print("🚀 ЗАПУСК GoogleScreenTranslate")
    print("=" * 70)
    print(f"📂 Текущая директория: {os.getcwd()}")
    print(f"🐍 Python: {sys.executable}")
    print(f"📋 Аргументы: {sys.argv}")
    print(f"🔧 Режим отладки: {'ВКЛЮЧЕН' if args.debug else 'ВЫКЛЮЧЕН'}")
    print("=" * 70)
    print("⏳ Запуск приложения...")

    # Если включен debug режим - настраиваем расширенное логирование
    if args.debug:
        setup_debug_logging()

    # Проверяем и очищаем папку приложения при несоответствии версий
    app_docs_path = Path.home() / "Documents" / "GoogleScreenTranslate"
    check_and_clean_version(app_docs_path)

    # Создаем приложение
    app = ScreenshotTranslatorApp()

    # Применяем аргументы командной строки
    if args.lang:
        app.settings.set_language(args.lang)
        app.ui.update_ui_language()
        print(f"🌐 Язык интерфейса установлен: {args.lang}")

    if args.no_browser:
        app.settings.set_show_browser(False)
        print("🌐 Браузер будет скрыт")

    # ============================================================
    # ОБРАБОТКА ЗАКРЫТИЯ ОКНА
    # ============================================================
    def on_closing():
        """Обработчик закрытия главного окна"""
        print("\n🛑 Закрытие приложения...")
        app.on_close()

    # Привязываем обработчик закрытия к окну
    app.ui.root.protocol("WM_DELETE_WINDOW", on_closing)

    # Также обрабатываем Ctrl+Q для выхода
    app.ui.root.bind('<Control-q>', lambda e: on_closing())
    app.ui.root.bind('<Control-Q>', lambda e: on_closing())

    # Обработка Alt+F4 (стандартное закрытие окна)
    app.ui.root.bind('<Alt-F4>', lambda e: on_closing())

    # В debug режиме добавляем дополнительную информацию в статус
    if args.debug:
        app.ui.update_status("🐞 DEBUG режим", '#ff9800')
        print("🐞 Отладка: добавлена дополнительная информация в логи")

    print("✅ Приложение запущено, вход в главный цикл...")

    try:
        app.run()
    except KeyboardInterrupt:
        print("\n⏹️ Прервано пользователем (Ctrl+C)")
        app.on_close()
    except Exception as e:
        print(f"\n❌ Критическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        app.on_close()
        sys.exit(1)


if __name__ == "__main__":
    main()