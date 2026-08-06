"""
Строки локализации для приложения GoogleScreenTranslate
"""


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
    strings.update(get_russian_help_strings())
    strings.update(get_russian_hotkeys_strings())

    # НОВЫЕ КЛЮЧИ:
    strings['area_selector_instruction'] = "Выделите область (ПКМ/ESC/Enter - выход)"
    strings['area_selector_counter'] = "Выделено: {}"
    strings['area_selector_error_title'] = "Ошибка"
    strings['area_selector_error_too_small'] = "Выделите область размером больше {min_size}x{min_size} пикселей"
    strings['context_menu_remove_overlays'] = "🗑️ Удалить оверлеи"
    strings['temporary_lifetime'] = "⏱ Время жизни временного оверлея:"
    strings['temporary_lifetime_tooltip'] = "Время в секундах, через которое временный оверлей автоматически удалится"
    strings[
        'temporary_lifetime_tooltip_new'] = "Время в секундах, через которое временный оверлей, созданный через ПКМ в режиме F3, автоматически удалится"
    strings['overlay_toggle_no_overlays'] = "Нет оверлеев для переключения"
    strings['overlay_toggle_unknown_app'] = "Не удалось определить текущее приложение"
    strings['overlay_toggle_no_overlays_for_app'] = "Нет оверлеев для {app_name}"
    strings['overlay_toggle_status_shown'] = "показаны"
    strings['overlay_toggle_status_hidden'] = "скрыты"
    strings['overlay_toggle_notification'] = "Оверлеи для {app_name} {status}"
    strings['overlay_toggle_no_templates_found'] = "Не найдено шаблонов на экране"
    strings['clear_all_no_app'] = "Не удалось определить текущее приложение"
    strings['clear_all_no_overlays'] = "Нет оверлеев для {app_name}"
    strings['clear_all_completed'] = "✅ Оверлеи для {app_name} удалены ({count} шт.)"
    strings['translation_status_translating'] = "Перевод..."
    strings['translation_status_ready'] = "✅ Готово!"
    strings['notification_capturing'] = "Скриншот..."
    strings['notification_select_area'] = "Выберите область..."
    strings['notification_select_area_temporary'] = "Выберите область (временный перевод)..."
    strings['notification_translation_ready'] = "Перевод готов"
    strings['notification_remove_no_app'] = "Не удалось определить текущее приложение"
    strings[
        'hotkey_area_temporary_hint'] = "💡 Временный перевод: ПКМ в режиме F3 — оверлей автоматически удалится через заданное время (настраивается в Настройках → Интерфейс)"
    # F3 HOLD
    strings['f3_hold_notification'] = "📸 Захват окна для OCR..."
    strings['f3_hold_ocr_processing'] = "🔄 Выполняется OCR анализ..."
    strings['f3_hold_no_text'] = "ℹ️ Текст не обнаружен на переведённом изображении"
    strings['f3_hold_overlays_created'] = "✅ Создано {count} оверлеев"
    strings['f3_hold_error_ocr'] = "❌ Ошибка OCR: {error}"
    strings['f3_hold_missing_easyocr'] = "❌ EasyOCR не установлен. Установите: pip install easyocr"
    strings['f3_hold_creating_overlays'] = "📝 Создание {count} оверлеев..."

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
    strings.update(get_english_help_strings())
    strings.update(get_english_hotkeys_strings())

    # НОВЫЕ КЛЮЧИ:
    strings['area_selector_instruction'] = "Select area (RMB/ESC/Enter - exit)"
    strings['area_selector_counter'] = "Selected: {}"
    strings['area_selector_error_title'] = "Error"
    strings['area_selector_error_too_small'] = "Select an area larger than {min_size}x{min_size} pixels"
    strings['context_menu_remove_overlays'] = "🗑️ Remove overlays"
    strings['temporary_lifetime'] = "⏱ Temporary overlay lifetime:"
    strings[
        'temporary_lifetime_tooltip'] = "Time in seconds after which the temporary overlay will be automatically removed"
    strings[
        'temporary_lifetime_tooltip_new'] = "Time in seconds after which the temporary overlay created via RMB in F3 mode will be automatically removed"
    strings['overlay_toggle_no_overlays'] = "No overlays to toggle"
    strings['overlay_toggle_unknown_app'] = "Failed to determine current application"
    strings['overlay_toggle_no_overlays_for_app'] = "No overlays for {app_name}"
    strings['overlay_toggle_status_shown'] = "shown"
    strings['overlay_toggle_status_hidden'] = "hidden"
    strings['overlay_toggle_notification'] = "Overlays for {app_name} {status}"
    strings['overlay_toggle_no_templates_found'] = "No templates found on screen"
    strings['clear_all_no_app'] = "Failed to determine current application"
    strings['clear_all_no_overlays'] = "No overlays for {app_name}"
    strings['clear_all_completed'] = "✅ Overlays for {app_name} removed ({count} pcs.)"
    strings['translation_status_translating'] = "Translating..."
    strings['translation_status_ready'] = "✅ Ready!"
    strings['notification_capturing'] = "Screenshotting..."
    strings['notification_select_area'] = "Select area..."
    strings['notification_select_area_temporary'] = "Select area (temporary translation)..."
    strings['notification_translation_ready'] = "Translation ready"
    strings['notification_remove_no_app'] = "Failed to determine current application"
    strings[
        'hotkey_area_temporary_hint'] = "💡 Temporary translation: RMB in F3 mode — overlay will be automatically removed after specified time (adjustable in Settings → Interface)"
    # F3 HOLD
    strings['f3_hold_notification'] = "📸 Capturing window for OCR..."
    strings['f3_hold_ocr_processing'] = "🔄 Running OCR analysis..."
    strings['f3_hold_no_text'] = "ℹ️ No text detected on translated image"
    strings['f3_hold_overlays_created'] = "✅ Created {count} overlays"
    strings['f3_hold_error_ocr'] = "❌ OCR error: {error}"
    strings['f3_hold_missing_easyocr'] = "❌ EasyOCR not installed. Install: pip install easyocr"
    strings['f3_hold_creating_overlays'] = "📝 Creating {count} overlays..."

    return strings


def get_russian_hotkeys_strings():
    """Возвращает русские строки для окна горячих клавиш"""
    return {
        'menu_hotkeys': "Хоткеи",
        'menu_hotkeys_show': "Показать горячие клавиши",
        'hotkeys_title': "Горячие клавиши",
        'hotkeys_change_in_settings': "⚙️ Изменить горячие клавиши",
        'hotkeys_close': "Закрыть",
        'hotkey_toggle_overlay': "Показать/скрыть оверлей",
        'hotkey_toggle_overlay_desc': "Переключает видимость всех оверлеев (переводов) на экране",
        'hotkey_screenshot': "Скриншот окна",
        'hotkey_screenshot_desc': "Делает скриншот активного окна и переводит его",
        'hotkey_area': "Выделение области",
        'hotkey_area_desc': "Позволяет выбрать произвольную область экрана для перевода",
        'hotkey_area_temporary': "Временная область",
        'hotkey_area_temporary_desc': "Выделить область для временного перевода — оверлей автоматически удалится через заданное время",
        'hotkey_area_temporary_time_hint': "💡 Время жизни временного оверлея настраивается в Настройках → Интерфейс → ползунок «Время жизни временного оверлея»",
        'hotkey_clear_all': "Удалить все оверлеи",
        'hotkey_clear_all_desc': "Удаляет все оверлеи с экрана и очищает историю переводов",
        'hotkey_edit_mode': "Режим редактирования",
        'hotkey_edit_mode_desc': "Включает/выключает режим, в котором оверлеи можно перемещать и удалять",
        'hotkey_auto_replace': "Автозамена областей",
        'hotkey_auto_replace_desc': "Включает/выключает автоматический поиск и замену уже переведённых областей",
        'hotkey_esc': "ESC — удалить оверлей",
        'hotkey_esc_desc': "В режиме редактирования удаляет оверлей под курсором",
        # НОВЫЙ КЛЮЧ ДЛЯ F3 HOLD
        'hotkey_fullscreen_ocr': "Авто-OCR всего окна",
        'hotkey_fullscreen_ocr_desc': "Длительное зажатие F3 (500мс) — скриншот всего окна, перевод и автоматическое создание оверлеев для всех текстовых зон",
    }


def get_english_hotkeys_strings():
    """Возвращает английские строки для окна горячих клавиш"""
    return {
        'menu_hotkeys': "Hotkeys",
        'menu_hotkeys_show': "Show hotkeys",
        'hotkeys_title': "Hotkeys",
        'hotkeys_change_in_settings': "⚙️ Change hotkeys",
        'hotkeys_close': "Close",
        'hotkey_toggle_overlay': "Show/Hide overlay",
        'hotkey_toggle_overlay_desc': "Toggles visibility of all overlays (translations) on screen",
        'hotkey_screenshot': "Window screenshot",
        'hotkey_screenshot_desc': "Takes a screenshot of the active window and translates it",
        'hotkey_area': "Area selection",
        'hotkey_area_desc': "Allows selecting any area of the screen for translation",
        'hotkey_area_temporary': "Temporary area",
        'hotkey_area_temporary_desc': "Select area for temporary translation — the overlay will be automatically removed after the specified time",
        'hotkey_area_temporary_time_hint': "💡 Temporary overlay lifetime can be adjusted in Settings → Interface → «Temporary overlay lifetime» slider",
        'hotkey_clear_all': "Clear all overlays",
        'hotkey_clear_all_desc': "Removes all overlays from screen and clears translation history",
        'hotkey_edit_mode': "Edit mode",
        'hotkey_edit_mode_desc': "Toggles edit mode where overlays can be moved and removed",
        'hotkey_auto_replace': "Auto-replace areas",
        'hotkey_auto_replace_desc': "Toggles automatic detection and replacement of already translated areas",
        'hotkey_esc': "ESC — remove overlay",
        'hotkey_esc_desc': "In edit mode, removes the overlay under the mouse cursor",
        # NEW KEY FOR F3 HOLD
        'hotkey_fullscreen_ocr': "Auto-OCR full window",
        'hotkey_fullscreen_ocr_desc': "Long press F3 (500ms) — screenshot of entire window, translation and automatic overlay creation for all text zones",
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
        'settings_browser_find_button': "🔍 Найти",
        'settings_save': "💾 Сохранить",
        'settings_cancel': "❌ Отмена",
        'settings_ui': "🎨 Интерфейс",
        'auto_windowed_fullscreen': "Фулскрин → оконный фулскрин при F3",
        'auto_replace_translated': "🔄 Автозамена переведённых областей",
        'auto_replace_translated_tooltip': "Автоматически показывать перевод при обнаружении той же области на экране",
        'edit_mode': "✏️ Режим редактирования",
        'edit_mode_tooltip': "Разрешить перемещение и удаление оверлеев",
        'settings_monitor': "🔍 Мониторинг",
        'settings_confidence': "Порог уверенности для поиска областей:",
        'settings_monitor_delay': "Задержка между сканированиями:",
        'settings_scan_fullscreen': "Сканировать весь экран (а не только активное окно)",
        'settings_scan_fullscreen_tooltip': "Если выключено — сканируется только активное окно",
        'settings_hotkeys': "⌨️ Горячие клавиши",
        'settings_hotkeys_action_screenshot': "Скриншот окна",
        'settings_hotkeys_action_area': "Выделение области",
        'settings_hotkeys_action_toggle_overlay': "Показать/скрыть оверлей",
        'settings_hotkeys_action_clear_all': "Удалить все оверлеи",
        'settings_hotkeys_action_edit_mode': "Режим редактирования",
        'settings_hotkeys_action_auto_replace': "Автозамена (F6)",
        'settings_hotkeys_press_key': "Нажмите клавишу...",
        'settings_hotkeys_click_to_change': "Нажмите для изменения",
        'settings_language': "🌐 Язык",
        'settings_language_label': "Выберите язык:",
        'settings_reset': "↺ Сбросить",
        'settings_reset_confirm': "Сбросить все настройки к стандартным?",
        'settings_reset_done': "Настройки сброшены к стандартным",
        'settings_saved': "Настройки сохранены",
        'settings_title': "Настройки программы",
        'show_translation_indicator': "Показывать индикатор перевода",
        'target_language': "Целевой язык перевода:",
        'browser_not_found': "Браузер не найден",
        'browser_not_found_msg': "Не удалось найти Яндекс Браузер или Google Chrome.\n\nДля работы программы необходим один из этих браузеров.",
        'auto_hide_overlay': "Автоскрытие оверлея при переключении окон",
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
        'settings_browser_find_button': "🔍 Find",
        'settings_save': "💾 Save",
        'settings_cancel': "❌ Cancel",
        'settings_ui': "🎨 Interface",
        'auto_windowed_fullscreen': "Fullscreen → windowed fullscreen on F3",
        'auto_replace_translated': "🔄 Auto-replace translated areas",
        'auto_replace_translated_tooltip': "Automatically show translation when the same area appears on screen",
        'edit_mode': "✏️ Edit mode",
        'edit_mode_tooltip': "Allow moving and removing overlays",
        'settings_monitor': "🔍 Monitoring",
        'settings_confidence': "Confidence threshold for area detection:",
        'settings_monitor_delay': "Scan interval:",
        'settings_scan_fullscreen': "Scan entire screen (not just active window)",
        'settings_scan_fullscreen_tooltip': "If disabled, only the active window is scanned",
        'settings_hotkeys': "⌨️ Hotkeys",
        'settings_hotkeys_action_screenshot': "Screenshot",
        'settings_hotkeys_action_area': "Area selection",
        'settings_hotkeys_action_toggle_overlay': "Show/Hide overlay",
        'settings_hotkeys_action_clear_all': "Clear all overlays",
        'settings_hotkeys_action_edit_mode': "Edit mode",
        'settings_hotkeys_action_auto_replace': "Auto-replace (F6)",
        'settings_hotkeys_press_key': "Press a key...",
        'settings_hotkeys_click_to_change': "Click to change",
        'settings_language': "🌐 Language",
        'settings_language_label': "Select language:",
        'settings_reset': "↺ Reset",
        'settings_reset_confirm': "Reset all settings to defaults?",
        'settings_reset_done': "Settings reset to defaults",
        'settings_saved': "Settings saved",
        'settings_title': "Program Settings",
        'show_translation_indicator': "Show translation indicator",
        'target_language': "Target translation language:",
        'browser_not_found': "Browser not found",
        'browser_not_found_msg': "Could not find Yandex Browser or Google Chrome.\n\nOne of these browsers is required for the program to work.",
        'auto_hide_overlay': "Auto-hide overlay when switching windows",
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


def get_russian_main_strings():
    """Возвращает основные русские строки приложения"""
    return {
        'app_title': "Перевод скриншотов",
        'ready': "● Готов",
        'ready_notification': "✅ Переводчик готов",
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
        'edit_mode_on': "ВКЛЮЧЕН",
        'edit_mode_off': "ВЫКЛЮЧЕН",
        'windows_with_translations': "📋 Окна с переводами:",
    }


def get_english_main_strings():
    """Возвращает основные английские строки приложения"""
    return {
        'app_title': "Screen Translator",
        'ready': "● Ready",
        'ready_notification': "✅ Translator Ready",
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
        'edit_mode_on': "ON",
        'edit_mode_off': "OFF",
        'windows_with_translations': "📋 Windows with translations:",
    }


def get_russian_button_strings():
    """Возвращает русские строки для кнопок"""
    return {
        'btn_capture': "Сделать скриншот",
        'btn_area': "Выбрать область",
        'btn_toggle': "Показать/скрыть",
        'btn_clear_all': "Очистить все",
        'hotkeys_info': "F2 - скриншот окна | F3 - область | F1 - оверлей | F4 - удалить все | F5 - редактирование | F6 - автозамена | ESC - удалить оверлей под мышью",
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
        'hotkeys_info': "F2 - window screenshot | F3 - area | F1 - overlay | F4 - clear all | F5 - edit mode | F6 - auto-replace | ESC - remove overlay under cursor",
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


def get_russian_about_strings():
    """Возвращает русские строки для окна 'О программе'"""
    return {
        'about_title': "О программе",
        'about_text': "📸 Google Screen Translate\n\nПрограмма для перевода скриншотов с помощью Google Translate.\n\nВерсия: 1.0",
    }


def get_english_about_strings():
    """Возвращает английские строки для окна 'О программе'"""
    return {
        'about_title': "About",
        'about_text': "📸 Google Screen Translate\n\nProgram for translating screenshots using Google Translate.\n\nVersion: 1.0",
    }


def get_russian_shortcuts_strings():
    """Возвращает русские строки для горячих клавиш"""
    return {
        'shortcuts_title': "Горячие клавиши",
        'shortcuts_text': "📋 Горячие клавиши:\n\nF2 - Сделать скриншот окна\nF3 - Выделить область для перевода\nF1 - Показать/скрыть оверлей\nESC - Закрыть оверлей",
    }


def get_english_shortcuts_strings():
    """Возвращает английские строки для горячих клавиш"""
    return {
        'shortcuts_title': "Keyboard Shortcuts",
        'shortcuts_text': "📋 Keyboard shortcuts:\n\nF2 - Take window screenshot\nF3 - Select area to translate\nF1 - Show/Hide overlay\nESC - Close overlay",
    }


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
