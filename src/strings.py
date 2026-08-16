"""
Строки локализации для приложения GoogleScreenTranslate
"""


def get_russian_main_strings():
    return {
        # === ОСНОВНЫЕ СТРОКИ ПРИЛОЖЕНИЯ ===
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
        'windows_with_translations': "Окна с переводами",

        # === СТРОКИ ДЛЯ ДВИЖКОВ ПЕРЕВОДА ===
        'engine_google': "Google Translate",
        'engine_yandex': "Яндекс.Переводчик (OCR)",
        'engine_switched': "✅ Переключено на {}",
        'engine_switch_error': "❌ Ошибка переключения: {}",

        # === СТРОКИ ДЛЯ ГЛАВНОГО ОКНА ===
        # Заголовки секций
        'translation_settings_header': "⚙️ Настройки перевода",
        'windows_header': "🖥️ Окна с переводами",
        'section_translation_settings': "Настройки перевода",
        'section_windows': "Окна с переводами",

        # Лейблы и подсказки
        'engine_label_short': "Движок:",
        'target_language_short': "Язык:",
        'engine_hint': "(выберите сервис перевода)",
        'language_hint': "(язык, на который переводить)",
        'windows_hint': "— нажмите правой кнопкой для удаления",
        'windows_count': "({})",

        # Подсказка по горячим клавишам в футере
        'footer_hotkeys': "⌨️ F2 — скриншот | F3 — область | F1 — скрыть/показать | F4 — очистить | F5 — редактирование | F6 — автозамена",

        # === СТРОКИ ДЛЯ КНОПКИ МИНИ-БАР ===
        'mini_bar_toggle_tooltip': "Показать/скрыть мини-бар",
        'mini_bar_show_tooltip': "Показать мини-бар",
        'mini_bar_hide_tooltip': "Скрыть мини-бар",
        'mini_bar_disabled_tooltip': "⏳ Доступно после инициализации",

        # === СТРОКИ ДЛЯ СТАТУСА ===
        'status_ready': "Готов",
        'status_starting': "Запуск...",
        'status_starting_browser': "Запуск браузера...",
        'status_capturing': "Захват...",
        'status_translating': "Перевод...",
        'status_error': "Ошибка",

        # === СТРОКИ ДЛЯ УВЕДОМЛЕНИЙ ===
        'notification_settings_saved': "Настройки сохранены",
        'notification_language_changed': "🌐 Язык перевода: {}",
        'notification_engine_changed': "🔄 Движок переключён на {}",
    }


def get_english_main_strings():
    return {
        # === MAIN APPLICATION STRINGS ===
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
        'windows_with_translations': "Windows with translations",

        # === TRANSLATION ENGINE STRINGS ===
        'engine_google': "Google Translate",
        'engine_yandex': "Yandex.Translator (OCR)",
        'engine_switched': "✅ Switched to {}",
        'engine_switch_error': "❌ Switch error: {}",

        # === MAIN WINDOW STRINGS ===
        # Section headers
        'translation_settings_header': "⚙️ Translation Settings",
        'windows_header': "🖥️ Windows with translations",
        'section_translation_settings': "Translation Settings",
        'section_windows': "Windows with translations",

        # Labels and hints
        'engine_label_short': "Engine:",
        'target_language_short': "Language:",
        'engine_hint': "(select translation service)",
        'language_hint': "(target translation language)",
        'windows_hint': "— right-click to remove",
        'windows_count': "({})",

        # Footer hotkeys hint
        'footer_hotkeys': "⌨️ F2 — screenshot | F3 — area | F1 — show/hide | F4 — clear | F5 — edit mode | F6 — auto-replace",

        # === MINI-BAR BUTTON STRINGS ===
        'mini_bar_toggle_tooltip': "Show/Hide mini-bar",
        'mini_bar_show_tooltip': "Show mini-bar",
        'mini_bar_hide_tooltip': "Hide mini-bar",
        'mini_bar_disabled_tooltip': "⏳ Available after initialization",

        # === STATUS STRINGS ===
        'status_ready': "Ready",
        'status_starting': "Starting...",
        'status_starting_browser': "Starting browser...",
        'status_capturing': "Capturing...",
        'status_translating': "Translating...",
        'status_error': "Error",

        # === NOTIFICATION STRINGS ===
        'notification_settings_saved': "Settings saved",
        'notification_language_changed': "🌐 Translation language: {}",
        'notification_engine_changed': "🔄 Engine switched to {}",
    }


def get_russian_button_strings():
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
        'menu_view': "Вид",
        'mini_bar_show': "Показать мини-бар",
        'mini_bar_hide': "Скрыть мини-бар",
    }


def get_english_menu_strings():
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
        'menu_view': "View",
        'mini_bar_show': "Show Mini Bar",
        'mini_bar_hide': "Hide Mini Bar",
    }


def get_russian_about_strings():
    return {
        'about_title': "О программе",
        'about_text': "📸 Google Screen Translate\n\nПрограмма для перевода скриншотов с помощью Google Translate.\n\nВерсия: 1.0",
    }


def get_english_about_strings():
    return {
        'about_title': "About",
        'about_text': "📸 Google Screen Translate\n\nProgram for translating screenshots using Google Translate.\n\nVersion: 1.0",
    }


def get_russian_shortcuts_strings():
    return {
        'shortcuts_title': "Горячие клавиши",
        'shortcuts_text': "📋 Горячие клавиши:\n\nF2 - Сделать скриншот окна\nF3 - Выделить область для перевода\nF1 - Показать/скрыть оверлей\nESC - Закрыть оверлей",
    }


def get_english_shortcuts_strings():
    return {
        'shortcuts_title': "Keyboard Shortcuts",
        'shortcuts_text': "📋 Keyboard shortcuts:\n\nF2 - Take window screenshot\nF3 - Select area to translate\nF1 - Show/Hide overlay\nESC - Close overlay",
    }


def get_russian_help_strings():
    return {
        'help_title': "Помощь и ссылки",
        'help_subtitle': "Перевод скриншотов через Google Translate",
        'help_info': "Полная инструкция и последняя версия доступны на GitHub:",
        'help_close': "Закрыть",
    }


def get_english_help_strings():
    return {
        'help_title': "Help & Links",
        'help_subtitle': "Screenshot translation via Google Translate",
        'help_info': "Full instructions and latest version available on GitHub:",
        'help_close': "Close",
    }


def get_russian_hotkeys_strings():
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
        'hotkey_fullscreen_ocr': "Авто-OCR всего окна",
        'hotkey_fullscreen_ocr_desc': "Длительное зажатие F3 (500мс) — скриншот всего окна, перевод и автоматическое создание оверлеев для всех текстовых зон",
    }


def get_english_hotkeys_strings():
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
        'hotkey_fullscreen_ocr': "Auto-OCR full window",
        'hotkey_fullscreen_ocr_desc': "Long press F3 (500ms) — screenshot of entire window, translation and automatic overlay creation for all text zones",
    }


def get_russian_settings_window_strings():
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
        'auto_windowed_fullscreen': "Автоматически переводить полноэкранные окна в оконный режим",
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
        'auto_windowed_fullscreen': "Automatically convert fullscreen windows to windowed mode",
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


def get_russian_translator_engine_strings():
    return {
        'settings_translator_engine_tab': "Движок перевода",
        'settings_translator_engine_header': "Выберите сервис для перевода изображений:",
        'settings_translator_engine_description': "При смене движка браузер будет перезапущен автоматически.",
        'settings_translator_engine_google': "Google Translate",
        'settings_translator_engine_yandex': "Яндекс.Переводчик (OCR)",
        'settings_translator_engine_google_desc': "",
        'settings_translator_engine_yandex_desc': "",
        'settings_translator_engine_warning': "⚠️ При переключении движка текущий браузер будет закрыт и перезапущен с новыми настройками.",
        'settings_translator_engine': "Движок перевода:",
        'settings_translator_engine_tooltip': "Выберите сервис для перевода изображений",
    }


def get_english_translator_engine_strings():
    return {
        'settings_translator_engine_tab': "Engine",
        'settings_translator_engine_header': "Select the service for image translation:",
        'settings_translator_engine_description': "The browser will be restarted automatically when changing the engine.",
        'settings_translator_engine_google': "Google Translate",
        'settings_translator_engine_yandex': "Yandex.Translator (OCR)",
        'settings_translator_engine_google_desc': "",
        'settings_translator_engine_yandex_desc': "",
        'settings_translator_engine_warning': "⚠️ When switching the engine, the current browser will be closed and restarted with new settings.",
        'settings_translator_engine': "Translation engine:",
        'settings_translator_engine_tooltip': "Select the service for image translation",
    }


def get_russian_tab_strings():
    return {
        'settings_browser_tab': "Браузер",
        'settings_ui_tab': "Интерфейс",
        'settings_engine_tab': "Движок",
        'settings_monitor_tab': "Монитор",
        'settings_hotkeys_tab': "Хоткеи",
    }


def get_english_tab_strings():
    return {
        'settings_browser_tab': "Browser",
        'settings_ui_tab': "Interface",
        'settings_engine_tab': "Engine",
        'settings_monitor_tab': "Monitor",
        'settings_hotkeys_tab': "Hotkeys",
    }


def get_russian_additional_strings():
    """Дополнительные русские строки (область выбора, оверлеи, уведомления, мини-бар, удаление)"""
    return {
        # Область выбора
        'area_selector_instruction': "Выделите область (ПКМ/ESC/Enter - выход)",
        'area_selector_counter': "Выделено: {}",
        'area_selector_error_title': "Ошибка",
        'area_selector_error_too_small': "Выделите область размером больше {min_size}x{min_size} пикселей",

        # Контекстное меню и оверлеи
        'context_menu_remove_overlays': "🗑️ Удалить оверлеи",
        'temporary_lifetime': "⏱ Время жизни временного оверлея:",
        'temporary_lifetime_tooltip': "Время в секундах, через которое временный оверлей автоматически удалится",
        'temporary_lifetime_tooltip_new': "Время в секундах, через которое временный оверлей, созданный через ПКМ в режиме F3, автоматически удалится",
        'overlay_toggle_no_overlays': "Нет оверлеев для переключения",
        'overlay_toggle_unknown_app': "Не удалось определить текущее приложение",
        'overlay_toggle_no_overlays_for_app': "Нет оверлеев для {app_name}",
        'overlay_toggle_status_shown': "показаны",
        'overlay_toggle_status_hidden': "скрыты",
        'overlay_toggle_notification': "Оверлеи для {app_name} {status}",
        'overlay_toggle_no_templates_found': "Не найдено шаблонов на экране",

        # Очистка
        'clear_all_no_app': "Не удалось определить текущее приложение",
        'clear_all_no_overlays': "Нет оверлеев для {app_name}",
        'clear_all_no_overlays_recent': "ℹ️ Нет оверлеев, созданных в последние 30 секунд для {app_name}",
        'clear_all_completed': "✅ Оверлеи для {app_name} удалены ({count} шт.)",

        # Удаление оверлеев
        'clear_all_deleted_dragged': "🗑️ Удалён перетащенный оверлей для {app_name}",
        'clear_all_deleted_under_cursor': "🗑️ Удалён оверлей для {app_name}",
        'clear_all_deleted_count': "🗑️ Удалено {count} оверлеев для {app_name}",
        'clear_all_deleted_single': "🗑️ Удалён оверлей для {app_name}",

        # Создание оверлеев
        'overlay_created': "✅ Оверлей создан",
        'overlay_created_single': "✅ Создан оверлей для {app_name}",
        'overlay_created_count': "✅ Создано {count} оверлеев для {app_name}",
        'overlay_creation_failed': "❌ Не удалось создать оверлей",
        'overlay_creation_error': "❌ Ошибка создания оверлея: {error}",

        # Шаблоны и мониторинг
        'template_added': "✅ Шаблон #{index} добавлен",
        'template_added_for_app': "✅ Шаблон #{index} добавлен для {app_name}",
        'template_added_temporary': "⏱ Временный шаблон #{index} добавлен, время жизни: {lifetime}с",
        'template_removed': "🗑️ Шаблон #{index} удалён",
        'templates_cleared': "🗑️ Все шаблоны очищены",
        'monitor_started': "🔍 Мониторинг запущен для {count} шаблонов",
        'monitor_stopped': "🔍 Мониторинг остановлен",

        # Перевод и уведомления
        'translation_status_translating': "Перевод...",
        'translation_status_ready': "✅ Готово!",
        'translation_error': "❌ Ошибка перевода",
        'notification_capturing': "Скриншот...",
        'notification_select_area': "Выберите область...",
        'notification_select_area_temporary': "Выберите область (временный перевод)...",
        'notification_translation_ready': "Перевод готов",
        'notification_remove_no_app': "Не удалось определить текущее приложение",
        'hotkey_area_temporary_hint': "💡 Временный перевод: ПКМ в режиме F3 — оверлей автоматически удалится через заданное время (настраивается в Настройках → Интерфейс)",

        # F3 Hold (OCR)
        'f3_hold_notification': "📸 Захват окна для OCR...",
        'f3_hold_ocr_processing': "🔄 Выполняется OCR анализ...",
        'f3_hold_no_text': "ℹ️ Текст не обнаружен на переведённом изображении",
        'f3_hold_overlays_created': "✅ Создано {count} оверлеев",
        'f3_hold_error_ocr': "❌ Ошибка OCR: {error}",
        'f3_hold_missing_easyocr': "❌ EasyOCR не установлен. Установите: pip install easyocr",
        'f3_hold_creating_overlays': "📝 Создание {count} оверлеев...",

        # Мини-бар
        'mini_bar_title': "Мини-бар",
        'mini_bar_tooltip_f1': "Показать/скрыть оверлей ({hotkey})",
        'mini_bar_tooltip_f2': "Скриншот окна ({hotkey})",
        'mini_bar_tooltip_f3': "Выделение области ({hotkey})",
        'mini_bar_tooltip_f3_hold': "OCR всего окна (зажатый {hotkey})",
        'mini_bar_tooltip_f4': "Удалить все оверлеи ({hotkey})",
        'mini_bar_tooltip_f5': "Режим редактирования ({hotkey})",
        'mini_bar_tooltip_f6': "Автозамена областей ({hotkey})",
        'mini_bar_close': "Закрыть мини-бар (ESC)",
        'mini_bar_drag_label': "⠿ Мини-бар",
    }


def get_english_additional_strings():
    """Additional English strings (area selector, overlays, notifications, mini-bar, removal)"""
    return {
        # Area selector
        'area_selector_instruction': "Select area (RMB/ESC/Enter - exit)",
        'area_selector_counter': "Selected: {}",
        'area_selector_error_title': "Error",
        'area_selector_error_too_small': "Select an area larger than {min_size}x{min_size} pixels",

        # Context menu and overlays
        'context_menu_remove_overlays': "🗑️ Remove overlays",
        'temporary_lifetime': "⏱ Temporary overlay lifetime:",
        'temporary_lifetime_tooltip': "Time in seconds after which the temporary overlay will be automatically removed",
        'temporary_lifetime_tooltip_new': "Time in seconds after which the temporary overlay created via RMB in F3 mode will be automatically removed",
        'overlay_toggle_no_overlays': "No overlays to toggle",
        'overlay_toggle_unknown_app': "Failed to determine current application",
        'overlay_toggle_no_overlays_for_app': "No overlays for {app_name}",
        'overlay_toggle_status_shown': "shown",
        'overlay_toggle_status_hidden': "hidden",
        'overlay_toggle_notification': "Overlays for {app_name} {status}",
        'overlay_toggle_no_templates_found': "No templates found on screen",

        # Clear
        'clear_all_no_app': "Failed to determine current application",
        'clear_all_no_overlays': "No overlays for {app_name}",
        'clear_all_no_overlays_recent': "ℹ️ No overlays created in the last 30 seconds for {app_name}",
        'clear_all_completed': "✅ Overlays for {app_name} removed ({count} pcs.)",

        # Overlay removal
        'clear_all_deleted_dragged': "🗑️ Removed dragged overlay for {app_name}",
        'clear_all_deleted_under_cursor': "🗑️ Removed overlay for {app_name}",
        'clear_all_deleted_count': "🗑️ Removed {count} overlays for {app_name}",
        'clear_all_deleted_single': "🗑️ Removed overlay for {app_name}",

        # Overlay creation
        'overlay_created': "✅ Overlay created",
        'overlay_created_single': "✅ Created overlay for {app_name}",
        'overlay_created_count': "✅ Created {count} overlays for {app_name}",
        'overlay_creation_failed': "❌ Failed to create overlay",
        'overlay_creation_error': "❌ Overlay creation error: {error}",

        # Templates and monitoring
        'template_added': "✅ Template #{index} added",
        'template_added_for_app': "✅ Template #{index} added for {app_name}",
        'template_added_temporary': "⏱ Temporary template #{index} added, lifetime: {lifetime}s",
        'template_removed': "🗑️ Template #{index} removed",
        'templates_cleared': "🗑️ All templates cleared",
        'monitor_started': "🔍 Monitoring started for {count} templates",
        'monitor_stopped': "🔍 Monitoring stopped",

        # Translation and notifications
        'translation_status_translating': "Translating...",
        'translation_status_ready': "✅ Ready!",
        'translation_error': "❌ Translation error",
        'notification_capturing': "Screenshotting...",
        'notification_select_area': "Select area...",
        'notification_select_area_temporary': "Select area (temporary translation)...",
        'notification_translation_ready': "Translation ready",
        'notification_remove_no_app': "Failed to determine current application",
        'hotkey_area_temporary_hint': "💡 Temporary translation: RMB in F3 mode — overlay will be automatically removed after specified time (adjustable in Settings → Interface)",

        # F3 Hold (OCR)
        'f3_hold_notification': "📸 Capturing window for OCR...",
        'f3_hold_ocr_processing': "🔄 Running OCR analysis...",
        'f3_hold_no_text': "ℹ️ No text detected on translated image",
        'f3_hold_overlays_created': "✅ Created {count} overlays",
        'f3_hold_error_ocr': "❌ OCR error: {error}",
        'f3_hold_missing_easyocr': "❌ EasyOCR not installed. Install: pip install easyocr",
        'f3_hold_creating_overlays': "📝 Creating {count} overlays...",

        # Mini-bar
        'mini_bar_title': "Mini Bar",
        'mini_bar_tooltip_f1': "Show/Hide overlay ({hotkey})",
        'mini_bar_tooltip_f2': "Window screenshot ({hotkey})",
        'mini_bar_tooltip_f3': "Select area ({hotkey})",
        'mini_bar_tooltip_f3_hold': "OCR full window (held {hotkey})",
        'mini_bar_tooltip_f4': "Clear all overlays ({hotkey})",
        'mini_bar_tooltip_f5': "Edit mode ({hotkey})",
        'mini_bar_tooltip_f6': "Auto-replace areas ({hotkey})",
        'mini_bar_close': "Close Mini Bar (ESC)",
        'mini_bar_drag_label': "⠿ Mini Bar",
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
    strings.update(get_russian_help_strings())
    strings.update(get_russian_hotkeys_strings())
    strings.update(get_russian_translator_engine_strings())
    strings.update(get_russian_tab_strings())
    strings.update(get_russian_additional_strings())
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
    strings.update(get_english_translator_engine_strings())
    strings.update(get_english_tab_strings())
    strings.update(get_english_additional_strings())
    return strings


def get_strings(language_code='ru'):
    if language_code == 'en':
        return get_english_all_strings()
    else:
        return get_russian_all_strings()


STRINGS = {
    'ru': get_russian_all_strings(),
    'en': get_english_all_strings(),
}
