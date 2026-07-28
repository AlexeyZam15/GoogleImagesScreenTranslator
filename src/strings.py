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
        'capturing_area': "● Захват области...",
        'capture_error': "● Ошибка захвата",
        'translating': "● Перевод...",
        'translate_error': "● Ошибка перевода",
        'error': "● Ошибка",
        'overlay': "Оверлей",
        'shown': "показан",
        'hidden': "скрыт",
        'overlay_remove_hint': "Наведите на оверлей и нажмите ESC для удаления",
        'edit_mode_on': "ВКЛЮЧЕН",  # <-- ДОБАВЛЯЕМ
        'edit_mode_off': "ВЫКЛЮЧЕН",  # <-- ДОБАВЛЯЕМ
    }


def get_english_main_strings():
    """Возвращает основные английские строки приложения"""
    return {
        'app_title': "Screen Translator",
        'ready': "● Ready",
        'starting': "● Starting...",
        'starting_browser': "● Starting browser...",
        'capturing': "● Capturing...",
        'capturing_area': "● Capturing area...",
        'capture_error': "● Capture error",
        'translating': "● Translating...",
        'translate_error': "● Translation error",
        'error': "● Error",
        'overlay': "Overlay",
        'shown': "shown",
        'hidden': "hidden",
        'overlay_remove_hint': "Hover over overlay and press ESC to remove",
        'edit_mode_on': "ON",  # <-- ДОБАВЛЯЕМ
        'edit_mode_off': "OFF",  # <-- ДОБАВЛЯЕМ
    }


def get_russian_button_strings():
    """Возвращает русские строки для кнопок"""
    return {
        'btn_capture': "Сделать скриншот",
        'btn_area': "Выбрать область",
        'btn_toggle': "Показать/скрыть",
        'btn_clear_all': "Очистить все",
        'hotkeys_info': "F2 - скриншот окна | F3 - область | F1 - оверлей | F4 - удалить все | ESC - удалить оверлей под мышью",
        'edit_mode': "Редактирование",
        'clear_all': "Очистить все",
    }


def get_english_button_strings():
    """Возвращает английские строки для кнопок"""
    return {
        'btn_capture': "Take screenshot",
        'btn_area': "Select area",
        'btn_toggle': "Show/Hide",
        'btn_clear_all': "Clear all",
        'hotkeys_info': "F2 - window screenshot | F3 - area | F1 - overlay | F4 - clear all | ESC - remove overlay under cursor",
        'edit_mode': "Edit mode",
        'clear_all': "Clear all",
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
        'menu_help_instruction': "📖 Инструкция и ссылки",
        'menu_shortcuts': "Горячие клавиши",
        'menu_about': "О программе",
        'menu_open_folder': "📁 Открыть папку приложения",
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
        'menu_help_instruction': "📖 Help & Links",
        'menu_shortcuts': "Shortcuts",
        'menu_about': "About",
        'menu_open_folder': "📁 Open App Folder",
    }


def get_russian_settings_window_strings():
    """Возвращает русские строки для окна настроек."""
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
        'auto_windowed_fullscreen': "Фулскрин → оконный фулскрин при F3",
        'edit_mode': "✏️ Режим редактирования",
        'edit_mode_tooltip': "Разрешить перемещение и удаление оверлеев",
        'settings_hotkeys': "⌨️ Горячие клавиши",
        'settings_hotkeys_action_screenshot': "Скриншот окна",
        'settings_hotkeys_action_area': "Выделение области",
        'settings_hotkeys_action_toggle_overlay': "Показать/скрыть оверлей",
        'settings_hotkeys_action_clear_all': "Удалить все оверлеи",
        'settings_hotkeys_action_edit_mode': "Режим редактирования",
        'settings_hotkeys_press_key': "Нажмите клавишу...",
        'settings_hotkeys_click_to_change': "Нажмите для изменения",
        # НОВЫЕ СТРОКИ ДЛЯ ПОИСКА БРАУЗЕРОВ
        'browser_find_title': "Выберите браузер",
        'browser_find_header': "Выберите браузер для использования:",
        'browser_find_recommend': "💡 Рекомендуется использовать Яндекс Браузер для лучшей совместимости",
        'browser_find_hint': "Кликните по браузеру для выбора, затем нажмите 'Выбрать'",
        'browser_find_select': "✅ Выбрать",
        'browser_find_cancel': "❌ Отмена",
        'browser_find_path_label': "Выберите браузер из списка",
        'browser_find_selected': "✅ Выбран: {}",
        'browser_find_path_prefix': "📁 {}",
        'browser_find_not_found': "Браузеры не найдены.",
        'browser_find_install_hint': "Убедитесь, что установлен один из браузеров:\n• Google Chrome\n• Yandex Browser (Яндекс Браузер)",
        'browser_find_not_found_recommend': "💡 Рекомендуется использовать Яндекс Браузер для лучшей совместимости.",
        'browser_find_warning_title': "Внимание",
        'browser_find_warning_message': "Выберите браузер из списка",
    }


def get_english_settings_window_strings():
    """Возвращает английские строки для окна настроек."""
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
        'auto_windowed_fullscreen': "Fullscreen → windowed fullscreen on F3",
        'edit_mode': "✏️ Edit mode",
        'edit_mode_tooltip': "Allow moving and removing overlays",
        'settings_hotkeys': "⌨️ Hotkeys",
        'settings_hotkeys_action_screenshot': "Screenshot",
        'settings_hotkeys_action_area': "Area selection",
        'settings_hotkeys_action_toggle_overlay': "Show/Hide overlay",
        'settings_hotkeys_action_clear_all': "Clear all overlays",
        'settings_hotkeys_action_edit_mode': "Edit mode",
        'settings_hotkeys_press_key': "Press a key...",
        'settings_hotkeys_click_to_change': "Click to change",
        # НОВЫЕ СТРОКИ ДЛЯ ПОИСКА БРАУЗЕРОВ
        'browser_find_title': "Select Browser",
        'browser_find_header': "Select browser to use:",
        'browser_find_recommend': "💡 Yandex Browser is recommended for best compatibility",
        'browser_find_hint': "Click on a browser to select it, then click 'Select'",
        'browser_find_select': "✅ Select",
        'browser_find_cancel': "❌ Cancel",
        'browser_find_path_label': "Select a browser from the list",
        'browser_find_selected': "✅ Selected: {}",
        'browser_find_path_prefix': "📁 {}",
        'browser_find_not_found': "Browsers not found.",
        'browser_find_install_hint': "Make sure one of the following browsers is installed:\n• Google Chrome\n• Yandex Browser",
        'browser_find_not_found_recommend': "💡 Yandex Browser is recommended for best compatibility.",
        'browser_find_warning_title': "Warning",
        'browser_find_warning_message': "Select a browser from the list",
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
        'shortcuts_text': "📋 Горячие клавиши:\n\nF2 - Сделать скриншот окна\nF3 - Выделить область для перевода\nF1 - Показать/скрыть оверлей\nESC - Закрыть оверлей",
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
    strings.update(get_russian_help_strings())  # <-- ДОБАВЛЯЕМ
    return strings


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
    strings.update(get_english_help_strings())  # <-- ДОБАВЛЯЕМ
    return strings


def get_russian_help_strings():
    """Возвращает русские строки для окна помощи"""
    return {
        'help_title': "Помощь и ссылки",
        'help_subtitle': "Перевод скриншотов через Google Translate",
        'help_info': "Полная инструкция и последняя версия доступны на GitHub:",
        'help_close': "Закрыть",
    }


def get_english_help_strings():
    """Возвращает английские строки для окна помощи"""
    return {
        'help_title': "Help & Links",
        'help_subtitle': "Screenshot translation via Google Translate",
        'help_info': "Full instructions and latest version available on GitHub:",
        'help_close': "Close",
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
        'shortcuts_text': "📋 Keyboard shortcuts:\n\nF2 - Take window screenshot\nF3 - Select area to translate\nF1 - Show/Hide overlay\nESC - Close overlay",
    }



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
