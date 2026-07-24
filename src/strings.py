"""

Строки локализации для приложения GoogleScreenTranslate

"""


def get_russian_main_strings():
    """Возвращает основные русские строки приложения"""
    return {
        'app_title': "Перевод скриншотов",
        'ready': "● Готов",
        'starting': "● Запуск...",
        'starting_browser': "● Запуск браузера...",
        'capturing': "● Захват...",
        'capture_error': "● Ошибка захвата",
        'translating': "● Перевод...",
        'translate_error': "● Ошибка перевода",
        'error': "● Ошибка",
        'overlay': "Оверлей",
        'shown': "показан",
        'hidden': "скрыт",
    }


def get_russian_button_strings():
    """Возвращает русские строки для кнопок"""
    return {
        'btn_capture': "Сделать скриншот (F2)",
        'btn_toggle': "Показать/скрыть (F1)",
        'hotkeys_info': "F2 - скриншот | F1 - оверлей | ESC - закрыть оверлей",
    }


def get_russian_settings_strings():
    """Возвращает русские строки для настроек"""
    return {
        'settings_saved': "Настройки сохранены",
        'settings_reset_confirm': "Сбросить все настройки к стандартным?",
        'settings_reset_done': "Настройки сброшены к стандартным",
        'settings_title': "Настройки программы",
        'show_translation_indicator': "Показывать индикатор перевода",
        'target_language': "Целевой язык перевода:",
        'browser_not_found': "Браузер не найден",
        'browser_not_found_msg': "Не удалось найти Яндекс Браузер или Google Chrome.\n\nДля работы программы необходим один из этих браузеров.",
        'auto_hide_overlay': "Автоскрытие оверлея при переключении окон",
        'settings_reset': "Сбросить",
    }


def get_russian_menu_strings():
    """Возвращает русские строки для меню"""
    return {
        'menu_file': "Файл",
        'menu_exit': "Выход (Ctrl+Q)",
        'menu_settings': "Настройки",
        'menu_settings_item': "Настройки (Ctrl+S)",
        'menu_reset_settings': "Сбросить настройки",
        'menu_help': "Помощь",
        'menu_shortcuts': "Горячие клавиши",
        'menu_about': "О программе",
        'menu_open_folder': "📁 Открыть папку приложения",
    }


def get_russian_settings_window_strings():
    """Возвращает русские строки для окна настроек"""
    return {
        'settings_browser_section': "🌐 Браузер",
        'settings_browser_path': "Путь к браузеру:",
        'settings_browser_path_hint': "Оставьте пустым для автоматического поиска",
        'settings_browser_browse': "Обзор...",
        'settings_browser_using': "✅ Используется: {}",
        'settings_browser_not_specified': "⚠️ Браузер не указан (будет выполнен автоматический поиск)",
        'settings_browser_path_label': "Путь: {}",
        'settings_save': "💾 Сохранить",
        'settings_cancel': "❌ Отмена",
        'settings_ui': "🎨 Интерфейс",
    }


def get_russian_about_strings():
    """Возвращает русские строки для окна 'О программе'"""
    return {
        'about_title': "О программе",
        'about_text': "📸 Google Screen Translate\n\nПрограмма для перевода скриншотов с помощью Google Translate.\n\nВерсия: 1.0",
    }


def get_russian_shortcuts_strings():
    """Возвращает русские строки для горячих клавиш"""
    return {
        'shortcuts_title': "Горячие клавиши",
        'shortcuts_text': "📋 Горячие клавиши:\n\nF2 - Сделать скриншот\nF1 - Показать/скрыть оверлей\nESC - Закрыть оверлей",
    }


def get_russian_all_strings():
    """Объединяет все русские строки в один словарь"""
    strings = {}
    strings.update(get_russian_main_strings())
    strings.update(get_russian_button_strings())
    strings.update(get_russian_settings_strings())
    strings.update(get_russian_menu_strings())
    strings.update(get_russian_settings_window_strings())
    strings.update(get_russian_about_strings())
    strings.update(get_russian_shortcuts_strings())
    return strings


def get_english_main_strings():
    """Возвращает основные английские строки приложения"""
    return {
        'app_title': "Screen Translator",
        'ready': "● Ready",
        'starting': "● Starting...",
        'starting_browser': "● Starting browser...",
        'capturing': "● Capturing...",
        'capture_error': "● Capture error",
        'translating': "● Translating...",
        'translate_error': "● Translation error",
        'error': "● Error",
        'overlay': "Overlay",
        'shown': "shown",
        'hidden': "hidden",
    }


def get_english_button_strings():
    """Возвращает английские строки для кнопок"""
    return {
        'btn_capture': "Take screenshot (F2)",
        'btn_toggle': "Show/Hide (F1)",
        'hotkeys_info': "F2 - screenshot | F1 - overlay | ESC - close overlay",
    }


def get_english_settings_strings():
    """Возвращает английские строки для настроек"""
    return {
        'settings_saved': "Settings saved",
        'settings_reset_confirm': "Reset all settings to defaults?",
        'settings_reset_done': "Settings reset to defaults",
        'settings_title': "Program Settings",
        'show_translation_indicator': "Show translation indicator",
        'target_language': "Target translation language:",
        'browser_not_found': "Browser not found",
        'browser_not_found_msg': "Could not find Yandex Browser or Google Chrome.\n\nOne of these browsers is required for the program to work.",
        'auto_hide_overlay': "Auto-hide overlay when switching windows",
        'settings_reset': "Reset",
    }


def get_english_menu_strings():
    """Возвращает английские строки для меню"""
    return {
        'menu_file': "File",
        'menu_exit': "Exit (Ctrl+Q)",
        'menu_settings': "Settings",
        'menu_settings_item': "Settings (Ctrl+S)",
        'menu_reset_settings': "Reset Settings",
        'menu_help': "Help",
        'menu_shortcuts': "Shortcuts",
        'menu_about': "About",
        'menu_open_folder': "📁 Open App Folder",
    }


def get_english_settings_window_strings():
    """Возвращает английские строки для окна настроек"""
    return {
        'settings_browser_section': "🌐 Browser",
        'settings_browser_path': "Browser path:",
        'settings_browser_path_hint': "Leave empty for automatic search",
        'settings_browser_browse': "Browse...",
        'settings_browser_using': "✅ Using: {}",
        'settings_browser_not_specified': "⚠️ Browser not specified (automatic search will be performed)",
        'settings_browser_path_label': "Path: {}",
        'settings_save': "💾 Save",
        'settings_cancel': "❌ Cancel",
        'settings_ui': "🎨 Interface",
    }


def get_english_about_strings():
    """Возвращает английские строки для окна 'О программе'"""
    return {
        'about_title': "About",
        'about_text': "📸 Google Screen Translate\n\nProgram for translating screenshots using Google Translate.\n\nVersion: 1.0",
    }


def get_english_shortcuts_strings():
    """Возвращает английские строки для горячих клавиш"""
    return {
        'shortcuts_title': "Keyboard Shortcuts",
        'shortcuts_text': "📋 Keyboard shortcuts:\n\nF2 - Take screenshot\nF1 - Show/Hide overlay\nESC - Close overlay",
    }


def get_english_all_strings():
    """Объединяет все английские строки в один словарь"""
    strings = {}
    strings.update(get_english_main_strings())
    strings.update(get_english_button_strings())
    strings.update(get_english_settings_strings())
    strings.update(get_english_menu_strings())
    strings.update(get_english_settings_window_strings())
    strings.update(get_english_about_strings())
    strings.update(get_english_shortcuts_strings())
    return strings


def get_strings(language_code='ru'):
    """
    Возвращает словарь строк для указанного языка

    Args:
        language_code: Код языка ('ru' или 'en')

    Returns:
        dict: Словарь со строками
    """
    if language_code == 'en':
        return get_english_all_strings()
    else:
        return get_russian_all_strings()


# Для обратной совместимости сохраняем STRINGS словарь
STRINGS = {
    'ru': get_russian_all_strings(),
    'en': get_english_all_strings(),
}