"""
Главное окно приложения - содержит только UI элементы
"""

import tkinter as tk
from tkinter import ttk, Menu, Frame, Label, Button, Listbox, StringVar, BooleanVar, END, DISABLED, NORMAL, FLAT, Canvas
from pathlib import Path
import logging

LANGUAGES = {
    "af": "Afrikaans", "sq": "Albanian", "am": "Amharic", "ar": "Arabic", "hy": "Armenian",
    "az": "Azerbaijani", "eu": "Basque", "be": "Belarusian", "bn": "Bengali", "bs": "Bosnian",
    "bg": "Bulgarian", "ca": "Catalan", "ceb": "Cebuano", "ny": "Chichewa", "zh-cn": "Chinese (Simplified)",
    "zh-tw": "Chinese (Traditional)", "co": "Corsican", "hr": "Croatian", "cs": "Czech", "da": "Danish",
    "nl": "Dutch", "en": "English", "eo": "Esperanto", "et": "Estonian", "tl": "Filipino", "fi": "Finnish",
    "fr": "French", "fy": "Frisian", "gl": "Galician", "ka": "Georgian", "de": "German", "el": "Greek",
    "gu": "Gujarati", "ht": "Haitian Creole", "ha": "Hausa", "haw": "Hawaiian", "iw": "Hebrew", "hi": "Hindi",
    "hmn": "Hmong", "hu": "Hungarian", "is": "Icelandic", "ig": "Igbo", "id": "Indonesian", "ga": "Irish",
    "it": "Italian", "ja": "Japanese", "jw": "Javanese", "kn": "Kannada", "kk": "Kazakh", "km": "Khmer",
    "rw": "Kinyarwanda", "ko": "Korean", "ku": "Kurdish (Kurmanji)", "ky": "Kyrgyz", "lo": "Lao",
    "la": "Latin", "lv": "Latvian", "lt": "Lithuanian", "lb": "Luxembourgish", "mk": "Macedonian",
    "mg": "Malagasy", "ms": "Malay", "ml": "Malayalam", "mt": "Maltese", "mi": "Maori", "mr": "Marathi",
    "mn": "Mongolian", "my": "Myanmar (Burmese)", "ne": "Nepali", "no": "Norwegian", "or": "Odia (Oriya)",
    "ps": "Pashto", "fa": "Persian", "pl": "Polish", "pt": "Portuguese", "pa": "Punjabi", "ro": "Romanian",
    "ru": "Russian", "sm": "Samoan", "gd": "Scots Gaelic", "sr": "Serbian", "st": "Sesotho", "sn": "Shona",
    "sd": "Sindhi", "si": "Sinhala", "sk": "Slovak", "sl": "Slovenian", "so": "Somali", "es": "Spanish",
    "su": "Sundanese", "sw": "Swahili", "sv": "Swedish", "tg": "Tajik", "ta": "Tamil", "tt": "Tatar",
    "te": "Telugu", "th": "Thai", "tr": "Turkish", "tk": "Turkmen", "uk": "Ukrainian", "ur": "Urdu",
    "ug": "Uyghur", "uz": "Uzbek", "vi": "Vietnamese", "cy": "Welsh", "xh": "Xhosa", "yi": "Yiddish",
    "yo": "Yoruba", "zu": "Zulu"
}


class MainWindow:
    """Главное окно приложения - только UI"""

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.settings = app.settings

        self.root = tk.Tk()
        self.root.title(self.get_string('app_title'))
        self.root.withdraw()
        self.root.geometry("720x500")
        self.root.minsize(500, 380)
        self.root.maxsize(900, 700)
        self.root.resizable(True, True)
        self.root.configure(bg='#1e1e1e')

        # ============================================================
        # ДОБАВЛЯЕМ ПРИВЯЗКУ ЗАКРЫТИЯ ОКНА
        # ============================================================
        self.root.protocol("WM_DELETE_WINDOW", self.app.on_close)

        # ============================================================
        # ДОБАВЛЯЕМ ОБРАБОТЧИК ИЗМЕНЕНИЯ РАЗМЕРА ОКНА (ДЛЯ СВОРАЧИВАНИЯ/ВОССТАНОВЛЕНИЯ)
        # ============================================================
        self.root.bind('<Configure>', self._on_window_configure)

        self.target_lang_var = tk.StringVar(value=self.settings.get_target_language())
        self._all_lang_items = []

        self._window_hwnd_map = {}
        self.window_listbox = None
        self.status = None
        self.settings_btn = None
        self.lang_btn = None
        self.title_label = None
        self.target_lang_combo = None
        self.target_lang_label = None
        self.context_menu = None

        self._setup_icon()
        self.create_menu()
        self.create_widgets()
        self._create_context_menu()
        self.update_ui_language()
        self._center_window()

        # ============================================================
        # ОТКЛЮЧАЕМ СТАНДАРТНУЮ ОБРАБОТКУ F1 (СПРАВКА) В TKINTER
        # ============================================================
        self.root.bind('<F1>', lambda e: 'break')

        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _on_window_configure(self, event):
        """
        Обработчик изменения размера/состояния окна.
        Вызывается при сворачивании, восстановлении, изменении размера.
        """
        # Проверяем, что событие относится к нашему окну, а не к дочерним элементам
        if event.widget == self.root:
            try:
                state = self.root.winfo_state()

                if state == 'iconic':
                    # Окно свернуто - приостанавливаем мониторинг
                    self.logger.info("[WINDOW] Окно свернуто, приостанавливаем работу монитора...")
                    if hasattr(self.app, 'translation_monitor') and self.app.translation_monitor:
                        self.app.translation_monitor.stop()
                elif state == 'normal':
                    # Окно восстановлено - возобновляем мониторинг если нужно
                    self.logger.info("[WINDOW] Окно восстановлено, возобновляем работу монитора...")
                    if hasattr(self.app, 'translation_monitor') and self.app.translation_monitor:
                        if self.app.settings.get_auto_replace_translated():
                            self.app.translation_monitor.start()
            except Exception as e:
                self.logger.warning(f"[WINDOW] Ошибка обработки состояния окна: {e}")

    def _create_context_menu(self):
        """Создает контекстное меню для списка окон"""
        self.logger.info("[CONTEXT_MENU] Создание контекстного меню")

        self.context_menu = Menu(
            self.window_listbox,
            tearoff=0,
            bg='#2d2d2d',
            fg='white',
            activebackground='#4CAF50',
            activeforeground='white'
        )

        # Получаем локализованную строку
        menu_label = "🗑️ Удалить оверлеи"
        if hasattr(self.app, 'settings'):
            menu_label = self.app.settings.get_string('context_menu_remove_overlays')

        self.context_menu.add_command(
            label=menu_label,
            command=self.app._context_remove_overlays
        )

        self.logger.info("[CONTEXT_MENU] Контекстное меню создано")

        # Привязываем ПКМ к списку
        self.window_listbox.bind('<Button-3>', self._show_context_menu)
        self.logger.info("[CONTEXT_MENU] Привязка <Button-3> выполнена")

    def _show_context_menu(self, event):
        """Показывает контекстное меню"""
        self.logger.info(f"[CONTEXT_MENU] _show_context_menu вызван, event={event}")

        try:
            if self.context_menu is None:
                self.logger.warning("[CONTEXT_MENU] Контекстное меню не создано")
                self._create_context_menu()

            # Определяем, на каком элементе произошел клик
            index = self.window_listbox.nearest(event.y)
            self.logger.info(f"[CONTEXT_MENU] Индекс под курсором: {index}")

            if index >= 0:
                self.window_listbox.selection_clear(0, 'end')
                self.window_listbox.selection_set(index)
                self.logger.info(f"[CONTEXT_MENU] Выбран элемент {index}")
            else:
                self.logger.warning("[CONTEXT_MENU] Индекс под курсором отрицательный")

            self.context_menu.tk_popup(event.x_root, event.y_root)
            self.logger.info("[CONTEXT_MENU] Меню показано")
        except Exception as e:
            self.logger.error(f"[CONTEXT_MENU] Ошибка показа меню: {e}")
            import traceback
            traceback.print_exc()
        finally:
            self.context_menu.grab_release()

    def create_menu(self):
        """Создает главное меню"""
        menubar = Menu(self.root, bg='#1e1e1e', fg='white', activebackground='#333333', activeforeground='white')
        self.root.config(menu=menubar)

        file_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white', activebackground='#333333',
                         activeforeground='white')
        menubar.add_cascade(label=self.get_string('menu_file'), menu=file_menu)
        file_menu.add_command(label=self.get_string('menu_open_folder'), command=self.app.open_app_folder)
        file_menu.add_separator()
        file_menu.add_command(label=self.get_string('menu_exit'), command=self.app.on_close)

        settings_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white', activebackground='#333333',
                             activeforeground='white')
        menubar.add_cascade(label=self.get_string('menu_settings'), menu=settings_menu, state=DISABLED)
        settings_menu.add_command(label=self.get_string('menu_settings_item'), command=self.app.open_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label=self.get_string('menu_reset_settings'), command=self.app.reset_settings)

        hotkeys_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white', activebackground='#333333',
                            activeforeground='white')
        menubar.add_cascade(label=self.get_string('menu_hotkeys'), menu=hotkeys_menu, state=DISABLED)
        hotkeys_menu.add_command(label=self.get_string('menu_hotkeys_show'), command=self.show_hotkeys_window)

        help_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white', activebackground='#333333',
                         activeforeground='white')
        menubar.add_cascade(label=self.get_string('menu_help'), menu=help_menu)
        help_menu.add_command(label=self.get_string('menu_help_instruction'), command=self.app.show_help)

        self._menubar = menubar

    def create_widgets(self):
        """Создает все виджеты главного окна - упрощенный интерфейс"""
        main = Frame(self.root, bg='#1a1a1a')
        main.pack(expand=True, fill=tk.BOTH, padx=0, pady=0)

        header_frame = Frame(main, bg='#1a1a1a', height=70)
        header_frame.pack(fill=tk.X, pady=(0, 0))
        header_frame.pack_propagate(False)

        left_header = Frame(header_frame, bg='#1a1a1a')
        left_header.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(20, 0))

        icon_label = Label(
            left_header,
            text="📸",
            bg='#1a1a1a',
            fg='#4CAF50',
            font=("Segoe UI", 28)
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 12))

        self.title_label = Label(
            left_header,
            text=self.get_string('app_title'),
            bg='#1a1a1a',
            fg='#4CAF50',
            font=("Segoe UI", 18, "bold"),
            anchor='w'
        )
        self.title_label.pack(side=tk.LEFT)

        right_header = Frame(header_frame, bg='#1a1a1a')
        right_header.pack(side=tk.RIGHT, padx=(0, 20))

        current_lang = self.settings.get_language()
        lang_text = "EN" if current_lang == "ru" else "RU"

        self.lang_btn = Button(
            right_header,
            text=lang_text,
            command=self.app.toggle_language,
            font=("Segoe UI", 12, "bold"),
            bg='#2d2d2d',
            fg='#4CAF50',
            relief=FLAT,
            width=3,
            padx=8,
            pady=6,
            cursor="hand2",
            state=tk.NORMAL,
            borderwidth=0,
            highlightthickness=0
        )
        self.lang_btn.pack(side=tk.RIGHT, padx=(0, 10))

        def on_lang_enter(e):
            if self.lang_btn['state'] != DISABLED:
                self.lang_btn.config(bg='#3c3c3c', fg='white')

        def on_lang_leave(e):
            if self.lang_btn['state'] != DISABLED:
                self.lang_btn.config(bg='#2d2d2d', fg='#4CAF50')

        self.lang_btn.bind('<Enter>', on_lang_enter)
        self.lang_btn.bind('<Leave>', on_lang_leave)

        self.settings_btn = Button(
            right_header,
            text="⚙️",
            command=self.app.open_settings,
            font=("Segoe UI", 12),
            bg='#2d2d2d',
            fg='#888888',
            relief=FLAT,
            width=3,
            padx=8,
            pady=6,
            cursor="hand2",
            state=DISABLED,
            borderwidth=0,
            highlightthickness=0
        )
        self.settings_btn.pack(side=tk.RIGHT, padx=(0, 0))

        def on_settings_enter(e):
            if self.settings_btn['state'] != DISABLED:
                self.settings_btn.config(bg='#3c3c3c', fg='#4CAF50')

        def on_settings_leave(e):
            if self.settings_btn['state'] != DISABLED:
                self.settings_btn.config(bg='#2d2d2d', fg='#888888')
            else:
                self.settings_btn.config(bg='#2d2d2d', fg='#444444')

        self.settings_btn.bind('<Enter>', on_settings_enter)
        self.settings_btn.bind('<Leave>', on_settings_leave)

        separator = Frame(main, bg='#2d2d2d', height=1)
        separator.pack(fill=tk.X, padx=20)

        content_frame = Frame(main, bg='#1a1a1a')
        content_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)

        status_frame = Frame(content_frame, bg='#1a1a1a')
        status_frame.pack(fill=tk.X, pady=(0, 10))

        self.status = Label(
            status_frame,
            text="● " + self.get_string('starting'),
            fg='#ff9800',
            bg='#1a1a1a',
            font=("Segoe UI", 11),
            height=1
        )
        self.status.pack(anchor=tk.W)

        windows_header = Frame(content_frame, bg='#1a1a1a')
        windows_header.pack(fill=tk.X, pady=(5, 5))

        self.windows_label = Label(
            windows_header,
            text=self.get_string('windows_with_translations'),
            bg='#1a1a1a',
            fg='#aaaaaa',
            font=("Segoe UI", 10),
            anchor='w'
        )
        self.windows_label.pack(side=tk.LEFT)

        listbox_frame = Frame(content_frame, bg='#2d2d2d', bd=1, relief=tk.SOLID, highlightbackground='#3c3c3c',
                              highlightthickness=1)
        listbox_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 0))

        self.window_listbox = Listbox(
            listbox_frame,
            bg='#2d2d2d',
            fg='#cccccc',
            selectbackground='#4CAF50',
            selectforeground='white',
            font=("Segoe UI", 10),
            height=12,
            relief=FLAT,
            bd=0,
            highlightthickness=0
        )
        self.window_listbox.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

    def update_ui_language(self):
        """Обновляет язык интерфейса"""
        self.root.title(self.get_string('app_title'))
        if self.title_label:
            self.title_label.config(text=self.get_string('app_title'))
        if self.windows_label:
            self.windows_label.config(text=self.get_string('windows_with_translations'))

        # Обновляем состояние кнопки редактирования
        if hasattr(self, 'edit_mode_btn'):
            is_enabled = getattr(self.app, '_edit_mode_enabled', False)
            status_text = "ВКЛ" if is_enabled else "ВЫКЛ"
            self.edit_mode_btn.config(
                text=f"✏️ Редактирование: {status_text}",
                bg='#4CAF50' if is_enabled else '#3c3c3c'
            )

        # === НОВЫЙ КОД: ОБНОВЛЕНИЕ СТАТУСА ПРИ СМЕНЕ ЯЗЫКА ===
        # Проверяем, есть ли статусная строка и приложение инициализировано
        if self.status and hasattr(self.app, 'ready'):
            current_text = self.status.cget('text')

            # Получаем текущий цвет статуса, чтобы определить состояние
            current_color = self.status.cget('fg')

            # Если приложение ещё не готово (инициализация)
            if not self.app.ready:
                # Обновляем статус на локализованную версию "Запуск браузера..."
                if hasattr(self.app, 'initializing') and self.app.initializing:
                    self.status.config(
                        text="● " + self.get_string('starting_browser'),
                        fg='#ff9800'
                    )
                else:
                    # Если приложение не инициализируется, но и не готово
                    self.status.config(
                        text="● " + self.get_string('starting'),
                        fg='#ff9800'
                    )
            else:
                # Приложение готово — обновляем статус с учётом языка
                # Получаем текущий движок для отображения в статусе
                engine = self.app.settings.get_translator_engine()
                engine_name = "Google Translate" if engine == "google" else "Яндекс.Переводчик (OCR)"
                ready_text = self.get_string('ready')
                self.status.config(
                    text=f"● {ready_text} ({engine_name})",
                    fg='#4CAF50'
                )

        # Сохраняем состояние готовности приложения
        is_ready = False
        if hasattr(self.app, 'ready') and self.app.ready:
            is_ready = True

        self.create_menu()

        if is_ready:
            self.set_settings_menu_enabled(True)

        current_lang = self.settings.get_language()
        if self.lang_btn:
            lang_text = "EN" if current_lang == "ru" else "RU"
            self.lang_btn.config(text=lang_text)

    def update_windows_count(self, count):
        """Обновляет счетчик окон с переводами"""
        if hasattr(self, 'windows_count_label'):
            self.windows_count_label.config(text=f"({count})")

    def _setup_icon(self):
        """Устанавливает иконку приложения"""
        try:
            from PIL import Image, ImageDraw, ImageTk
            size = 64
            img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            bg_color = (33, 33, 33, 255)
            accent_color = (76, 175, 80, 255)
            white = (255, 255, 255, 255)

            draw.rounded_rectangle([(4, 4), (size - 4, size - 4)], radius=14, fill=bg_color, outline=accent_color,
                                   width=2)

            center_x, center_y = size // 2, size // 2 + 2
            cam_w, cam_h = 30, 22
            x1, y1 = center_x - cam_w // 2, center_y - cam_h // 2
            x2, y2 = center_x + cam_w // 2, center_y + cam_h // 2

            draw.rounded_rectangle([(x1, y1), (x2, y2)], radius=4, fill=white, outline=accent_color, width=2)

            lens_radius = 8
            draw.ellipse(
                [(center_x - lens_radius, center_y - lens_radius), (center_x + lens_radius, center_y + lens_radius)],
                fill=accent_color, outline=white, width=2)
            draw.ellipse([(center_x - 4, center_y - 5), (center_x - 1, center_y - 2)], fill=white)

            flash_x, flash_y = center_x + 12, center_y - cam_h // 2 - 2
            draw.rectangle([(flash_x - 2, flash_y - 2), (flash_x + 3, flash_y + 3)], fill=white, outline=accent_color,
                           width=1)

            photo = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, photo)
            self.root.tk.call('wm', 'iconphoto', self.root._w, photo)
            self._icon_photo = photo
        except Exception as e:
            self.logger.warning(f"Не удалось установить иконку: {e}")

    def show_hotkeys_window(self):
        """Показывает окно с информацией о горячих клавишах"""
        if hasattr(self.app, '_hotkeys_window') and self.app._hotkeys_window:
            try:
                self.app._hotkeys_window.window.lift()
                self.app._hotkeys_window.window.focus_force()
                return
            except:
                self.app._hotkeys_window = None

        from src.hotkeys_window import HotkeysWindow
        HotkeysWindow(self.app)

    def _center_window(self):
        """Центрирует окно"""
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def get_string(self, key):
        """Возвращает локализованную строку"""
        return self.settings.get_string(key)

    def update_status(self, text, color='white'):
        """Обновляет статус"""
        self.logger.info(f"[STATUS_UI] update_status вызван: text='{text}', color='{color}'")
        if self.status:
            try:
                self.status.config(text=text, fg=color)
                self.status.update_idletasks()
                self.logger.info(f"[STATUS_UI] Статус обновлён: '{text}'")
            except Exception as e:
                self.logger.error(f"[STATUS_UI] Ошибка обновления статуса: {e}")
        else:
            self.logger.warning("[STATUS_UI] self.status отсутствует!")

    def set_settings_menu_enabled(self, enabled):
        """Блокирует/разблокирует меню настроек и хоткеев"""
        try:
            state = tk.NORMAL if enabled else DISABLED
            if hasattr(self, '_menubar') and self._menubar:
                for index in range(self._menubar.index('end') + 1):
                    try:
                        label = self._menubar.entrycget(index, 'label')
                        if label == self.get_string('menu_settings'):
                            self._menubar.entryconfig(index, state=state)
                        elif label == self.get_string('menu_hotkeys'):
                            self._menubar.entryconfig(index, state=state)
                    except:
                        pass
        except Exception as e:
            self.logger.warning(f"[MENU] Ошибка при блокировке меню: {e}")

    def _on_lang_search(self, event):
        """Фильтрует список языков"""
        typed_text = self.target_lang_var.get().lower()
        filtered_items = [item for item in self._all_lang_items if
                          typed_text in item.lower()] if typed_text else self._all_lang_items
        self.target_lang_combo['values'] = filtered_items

    def _on_lang_enter(self, event):
        """Обработчик Enter в поле языка"""
        current_text = self.target_lang_var.get().strip()
        values = self.target_lang_combo['values']
        if not values:
            return "break"

        if current_text in values:
            self._apply_language(current_text)
            self.target_lang_combo['values'] = self._all_lang_items
            return "break"

        for item in values:
            if "(" in item and ")" in item:
                code = item.split("(")[-1].replace(")", "").strip()
                if code.lower() == current_text.lower():
                    self.target_lang_combo.set(item)
                    self._apply_language(item)
                    self.target_lang_combo['values'] = self._all_lang_items
                    return "break"

        if values:
            self.target_lang_combo.set(values[0])
            self._apply_language(values[0])
            self.target_lang_combo['values'] = self._all_lang_items
        return "break"

    def _apply_language(self, selected):
        """Применяет выбранный язык"""
        if "(" in selected and ")" in selected:
            lang_code = selected.split("(")[-1].replace(")", "").strip()
            self.settings.set_target_language(lang_code)
            if self.app.ready:
                self.app.browser_worker.update_language(lang_code)

    def _on_target_lang_changed(self, event):
        """Обработчик изменения языка"""
        self._apply_language(self.target_lang_combo.get())
