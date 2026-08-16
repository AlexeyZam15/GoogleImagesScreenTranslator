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
        self.root.geometry("820x520")
        self.root.minsize(600, 420)
        self.root.maxsize(1000, 750)
        self.root.resizable(True, True)
        self.root.configure(bg='#1e1e1e')

        self.root.protocol("WM_DELETE_WINDOW", self.app.on_close)
        self.root.bind('<Configure>', self._on_window_configure)

        self._setup_icon()
        self.create_menu()
        self.create_widgets()
        self._create_context_menu()
        self.update_ui_language()
        self._center_window()

        self._window_hwnd_map = {}
        self._window_app_map = {}

        self.root.bind('<F1>', lambda e: 'break')
        self.set_settings_menu_enabled(False)

        # ============================================================
        # ПОКАЗЫВАЕМ ОКНО И ПРИНУДИТЕЛЬНО ОБНОВЛЯЕМ
        # ============================================================
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        # Принудительная отрисовка окна
        self.root.update()
        self.root.update_idletasks()

        self.logger.info("[UI] Главное окно создано и отображено")

    def update_hotkey_labels(self):
        """
        Обновляет надписи с горячими клавишами F1 и F3 в верхней части окна.
        Использует актуальные значения из настроек и локализацию.
        """
        try:
            hotkeys = self.settings.get_all_hotkeys()

            # Получаем актуальные клавиши для F1 и F3
            f1_key = hotkeys.get('toggle_overlay', 'F1').upper()
            f3_key = hotkeys.get('area', 'F3').upper()

            # Если хоткей не задан — показываем "—"
            if not f1_key or f1_key == '':
                f1_display = "—"
            else:
                if '+' in f1_key:
                    parts = f1_key.split('+')
                    f1_display = '+'.join(p.upper() for p in parts)
                else:
                    f1_display = f1_key

            if not f3_key or f3_key == '':
                f3_display = "—"
            else:
                if '+' in f3_key:
                    parts = f3_key.split('+')
                    f3_display = '+'.join(p.upper() for p in parts)
                else:
                    f3_display = f3_key

            # Получаем локализованные описания
            f1_desc = self.get_string('hotkey_info_f1')
            f3_desc = self.get_string('hotkey_info_f3')
            separator = self.get_string('hotkey_info_separator')

            # Формируем текст надписи с использованием локализации
            text = f"⌨️ {f1_display} — {f1_desc}{separator}{f3_display} — {f3_desc}"

            if hasattr(self, 'hotkey_info_label') and self.hotkey_info_label:
                self.hotkey_info_label.config(text=text)
                self.logger.info(f"[HOTKEYS] Обновлены надписи: {text}")

        except Exception as e:
            self.logger.warning(f"[HOTKEYS] Ошибка обновления надписей: {e}")

    def _add_tooltip(self, widget, text):
        """Добавляет всплывающую подсказку при наведении на виджет."""

        def enter(event):
            if hasattr(widget, '_tooltip') and widget._tooltip:
                try:
                    widget._tooltip.destroy()
                except:
                    pass
                widget._tooltip = None

            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            tooltip.attributes('-topmost', True)

            x = event.x_root + 10
            y = event.y_root + 20
            screen_width = tooltip.winfo_screenwidth()
            screen_height = tooltip.winfo_screenheight()

            label = tk.Label(
                tooltip,
                text=text,
                bg='#2d2d2d',
                fg='white',
                font=('Segoe UI', 10),
                relief=tk.SOLID,
                borderwidth=1,
                padx=10,
                pady=6,
                wraplength=300,
                justify='left'
            )
            label.pack()
            tooltip.update_idletasks()

            tw = tooltip.winfo_width()
            th = tooltip.winfo_height()
            if x + tw > screen_width:
                x = screen_width - tw - 10
            if y + th > screen_height:
                y = screen_height - th - 10
            tooltip.wm_geometry(f"+{x}+{y}")
            widget._tooltip = tooltip

        def leave(event):
            if hasattr(widget, '_tooltip') and widget._tooltip:
                try:
                    widget._tooltip.destroy()
                except:
                    pass
                widget._tooltip = None

        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    def update_mini_bar_button(self):
        """
        Обновляет состояние кнопки мини-бара в зависимости от того,
        открыт ли мини-бар или скрыт, и готова ли инициализация.
        """
        if not hasattr(self, 'mini_bar_btn'):
            return

        # Проверяем, готова ли инициализация
        is_ready = False
        if hasattr(self.app, 'ready') and self.app.ready:
            is_ready = True

        try:
            if not is_ready:
                # Приложение не готово - кнопка заблокирована, подсказки нет
                self.mini_bar_btn.config(
                    state=tk.DISABLED,
                    text="📌",
                    fg='#444444',
                    bg='#2d2d2d'
                )
                # Удаляем подсказку, если она есть
                if hasattr(self.mini_bar_btn, '_tooltip') and self.mini_bar_btn._tooltip:
                    try:
                        self.mini_bar_btn._tooltip.destroy()
                    except:
                        pass
                    self.mini_bar_btn._tooltip = None
                self.logger.debug("[MINI_BAR] Кнопка заблокирована (инициализация не завершена), подсказка убрана")
                return

            # Приложение готово - кнопка активна
            if hasattr(self.app, '_mini_bar_window') and self.app._mini_bar_window:
                # Мини-бар открыт
                self.mini_bar_btn.config(
                    state=tk.NORMAL,
                    text="📌",
                    fg='#4CAF50',
                    bg='#2d2d2d'
                )
                self._add_tooltip(self.mini_bar_btn, self.get_string('mini_bar_hide_tooltip'))
                self.logger.debug("[MINI_BAR] Кнопка обновлена: мини-бар открыт")
            else:
                # Мини-бар скрыт
                self.mini_bar_btn.config(
                    state=tk.NORMAL,
                    text="📌",
                    fg='#888888',
                    bg='#2d2d2d'
                )
                self._add_tooltip(self.mini_bar_btn, self.get_string('mini_bar_show_tooltip'))
                self.logger.debug("[MINI_BAR] Кнопка обновлена: мини-бар скрыт")
        except Exception as e:
            self.logger.warning(f"[MINI_BAR] Ошибка обновления кнопки: {e}")

    def set_language_combo_enabled(self, enabled: bool):
        """
        Устанавливает доступность комбобокса выбора целевого языка.
        """
        state = tk.NORMAL if enabled else DISABLED
        if hasattr(self, 'target_lang_combo_main') and self.target_lang_combo_main:
            try:
                self.target_lang_combo_main.config(state=state)
                self.logger.info(f"[UI] Комбобокс языка {'разблокирован' if enabled else 'заблокирован'}")
            except Exception as e:
                self.logger.warning(f"[UI] Ошибка блокировки комбобокса языка: {e}")

    def set_engine_combo_enabled(self, enabled: bool):
        """
        Устанавливает доступность комбобокса выбора движка.
        Также блокирует/разблокирует комбобокс языка.
        """
        state = tk.NORMAL if enabled else DISABLED
        if self.engine_combo:
            self.engine_combo.config(state=state)
            self.logger.info(f"[UI] Комбобокс движка {'разблокирован' if enabled else 'заблокирован'}")

        # Одновременно блокируем/разблокируем комбобокс языка
        self.set_language_combo_enabled(enabled)

    def _on_language_changed_main(self, event):
        """
        Обработчик выбора целевого языка в главном окне.
        """
        selected = self.target_lang_var.get()
        if not selected:
            return

        # Извлекаем код языка из строки вида "Russian (ru)"
        if "(" in selected and ")" in selected:
            lang_code = selected.split("(")[-1].replace(")", "").strip()
        else:
            # Fallback: пробуем найти по названию
            for code, name in LANGUAGES.items():
                if name.lower() in selected.lower():
                    lang_code = code
                    break
            else:
                return

        current_lang = self.settings.get_target_language()
        if current_lang != lang_code:
            self.logger.info(f"[UI] Смена целевого языка в главном окне: {current_lang} -> {lang_code}")
            self.settings.set_target_language(lang_code)

            # Обновляем язык в браузере, если он готов
            if hasattr(self.app, 'ready') and self.app.ready:
                if hasattr(self.app, 'browser_worker') and self.app.browser_worker:
                    self.app.browser_worker.update_language(lang_code)

                # Обновляем статус
                engine = self.settings.get_translator_engine()
                engine_name = "Google Translate" if engine == "google" else "Яндекс.Переводчик (OCR)"
                ready_text = self.get_string('ready')
                self.update_status(
                    f"● {ready_text} ({engine_name}, {lang_code.upper()})",
                    '#4CAF50'
                )

                self.app.show_notification(f"🌐 Язык перевода: {lang_code.upper()}")

    def update_language_display(self, lang_code: str):
        """
        Обновляет отображение выбранного языка в комбобоксе.
        """
        if not hasattr(self, 'target_lang_combo_main') or not self.target_lang_combo_main:
            return

        for item in self._lang_display_names:
            if f"({lang_code})" in item:
                self.target_lang_var.set(item)
                self.logger.info(f"[UI] Обновлён язык в комбобоксе: {lang_code}")
                return

    def create_widgets(self):
        """Создает все виджеты главного окна - улучшенный интерфейс с разделением на секции"""
        main = tk.Frame(self.root, bg='#1a1a1a')
        main.pack(expand=True, fill=tk.BOTH, padx=0, pady=0)

        # ============================================================
        # ВЕРХНЯЯ ПАНЕЛЬ (логотип + управление)
        # ============================================================
        header_frame = tk.Frame(main, bg='#1a1a1a', height=75)
        header_frame.pack(fill=tk.X, pady=(0, 0))
        header_frame.pack_propagate(False)

        # ЛЕВАЯ ЧАСТЬ: логотип и название
        left_header = tk.Frame(header_frame, bg='#1a1a1a')
        left_header.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(20, 0))

        icon_label = tk.Label(
            left_header,
            text="📸",
            bg='#1a1a1a',
            fg='#4CAF50',
            font=("Segoe UI", 30)
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 12))

        self.title_label = tk.Label(
            left_header,
            text=self.get_string('app_title'),
            bg='#1a1a1a',
            fg='#4CAF50',
            font=("Segoe UI", 20, "bold"),
            anchor='w'
        )
        self.title_label.pack(side=tk.LEFT)

        # ПРАВАЯ ЧАСТЬ: кнопки управления
        right_header = tk.Frame(header_frame, bg='#1a1a1a')
        right_header.pack(side=tk.RIGHT, padx=(0, 20))

        # ---- КНОПКА МИНИ-БАР ----
        self.mini_bar_btn = tk.Button(
            right_header,
            text="📌",
            command=self.app.toggle_mini_bar,
            font=("Segoe UI", 14),
            bg='#2d2d2d',
            fg='#888888',
            relief=tk.FLAT,
            width=3,
            padx=10,
            pady=8,
            cursor="hand2",
            state=tk.NORMAL,
            borderwidth=0,
            highlightthickness=0
        )
        self.mini_bar_btn.pack(side=tk.LEFT, padx=(0, 10))

        def on_mini_bar_enter(e):
            self.mini_bar_btn.config(bg='#3c3c3c', fg='#4CAF50')

        def on_mini_bar_leave(e):
            self.mini_bar_btn.config(bg='#2d2d2d', fg='#888888')

        self.mini_bar_btn.bind('<Enter>', on_mini_bar_enter)
        self.mini_bar_btn.bind('<Leave>', on_mini_bar_leave)
        self._add_tooltip(self.mini_bar_btn, self.get_string('mini_bar_toggle_tooltip'))

        # ---- КНОПКА СМЕНЫ ЯЗЫКА ИНТЕРФЕЙСА ----
        current_lang_ui = self.settings.get_language()
        lang_text = "EN" if current_lang_ui == "ru" else "RU"

        self.lang_btn = tk.Button(
            right_header,
            text=lang_text,
            command=self.app.toggle_language,
            font=("Segoe UI", 12, "bold"),
            bg='#2d2d2d',
            fg='#4CAF50',
            relief=tk.FLAT,
            width=3,
            padx=10,
            pady=8,
            cursor="hand2",
            state=tk.NORMAL,
            borderwidth=0,
            highlightthickness=0
        )
        self.lang_btn.pack(side=tk.LEFT, padx=(0, 10))

        def on_lang_enter(e):
            if self.lang_btn['state'] != tk.DISABLED:
                self.lang_btn.config(bg='#3c3c3c', fg='white')

        def on_lang_leave(e):
            if self.lang_btn['state'] != tk.DISABLED:
                self.lang_btn.config(bg='#2d2d2d', fg='#4CAF50')

        self.lang_btn.bind('<Enter>', on_lang_enter)
        self.lang_btn.bind('<Leave>', on_lang_leave)

        # ---- КНОПКА НАСТРОЕК ----
        self.settings_btn = tk.Button(
            right_header,
            text="⚙️",
            command=self.app.open_settings,
            font=("Segoe UI", 14),
            bg='#2d2d2d',
            fg='#888888',
            relief=tk.FLAT,
            width=3,
            padx=10,
            pady=8,
            cursor="hand2",
            state=tk.DISABLED,
            borderwidth=0,
            highlightthickness=0
        )
        self.settings_btn.pack(side=tk.LEFT)

        def on_settings_enter(e):
            if self.settings_btn['state'] != tk.DISABLED:
                self.settings_btn.config(bg='#3c3c3c', fg='#4CAF50')

        def on_settings_leave(e):
            if self.settings_btn['state'] != tk.DISABLED:
                self.settings_btn.config(bg='#2d2d2d', fg='#888888')
            else:
                self.settings_btn.config(bg='#2d2d2d', fg='#444444')

        self.settings_btn.bind('<Enter>', on_settings_enter)
        self.settings_btn.bind('<Leave>', on_settings_leave)

        # ============================================================
        # ПАНЕЛЬ С ГОРЯЧИМИ КЛАВИШАМИ (F1 и F3) - ИСПОЛЬЗУЕТ ЛОКАЛИЗАЦИЮ
        # ============================================================
        hotkey_info_frame = tk.Frame(main, bg='#1a1a1a', height=28)
        hotkey_info_frame.pack(fill=tk.X, padx=20, pady=(2, 6))
        hotkey_info_frame.pack_propagate(False)

        self.hotkey_info_label = tk.Label(
            hotkey_info_frame,
            text="",
            bg='#1a1a1a',
            fg='#888888',
            font=("Segoe UI", 10),
            anchor='w'
        )
        self.hotkey_info_label.pack(side=tk.LEFT, fill=tk.X)

        # ============================================================
        # РАЗДЕЛИТЕЛЬ
        # ============================================================
        separator1 = tk.Frame(main, bg='#2d2d2d', height=1)
        separator1.pack(fill=tk.X, padx=20)

        # ============================================================
        # СЕКЦИЯ НАСТРОЕК ПЕРЕВОДА (движок + целевой язык)
        # ============================================================
        settings_section = tk.Frame(main, bg='#1a1a1a')
        settings_section.pack(fill=tk.X, padx=20, pady=12)

        # Заголовок секции
        self.section_label = tk.Label(
            settings_section,
            text=self.get_string('translation_settings_header'),
            bg='#1a1a1a',
            fg='#cccccc',
            font=("Segoe UI", 11, "bold"),
            anchor='w'
        )
        self.section_label.pack(anchor=tk.W, pady=(0, 8))

        # Контейнер для двух строк настроек
        settings_container = tk.Frame(settings_section, bg='#1a1a1a')
        settings_container.pack(fill=tk.X)

        # ---- Строка 1: Движок ----
        engine_row = tk.Frame(settings_container, bg='#1a1a1a')
        engine_row.pack(fill=tk.X, pady=3)

        self.engine_label = tk.Label(
            engine_row,
            text=self.get_string('engine_label_short'),
            bg='#1a1a1a',
            fg='#aaaaaa',
            font=("Segoe UI", 10),
            width=10,
            anchor='e'
        )
        self.engine_label.pack(side=tk.LEFT, padx=(0, 10))

        self.engine_var = tk.StringVar(value="Google Translate")
        self.engine_combo = ttk.Combobox(
            engine_row,
            textvariable=self.engine_var,
            values=[self.get_string('engine_google'), self.get_string('engine_yandex')],
            state='disabled',
            font=("Segoe UI", 10),
            width=28
        )
        self.engine_combo.pack(side=tk.LEFT)
        self.engine_combo.bind('<<ComboboxSelected>>', self._on_engine_changed)

        # Подсказка для движка
        self.engine_hint_label = tk.Label(
            engine_row,
            text=self.get_string('engine_hint'),
            bg='#1a1a1a',
            fg='#666666',
            font=("Segoe UI", 9),
            anchor='w'
        )
        self.engine_hint_label.pack(side=tk.LEFT, padx=(10, 0))

        # ---- Строка 2: Целевой язык ----
        lang_row = tk.Frame(settings_container, bg='#1a1a1a')
        lang_row.pack(fill=tk.X, pady=3)

        self.lang_label = tk.Label(
            lang_row,
            text=self.get_string('target_language_short'),
            bg='#1a1a1a',
            fg='#aaaaaa',
            font=("Segoe UI", 10),
            width=10,
            anchor='e'
        )
        self.lang_label.pack(side=tk.LEFT, padx=(0, 10))

        # Формируем список языков для отображения
        self._lang_display_names = [f"{name} ({code})" for code, name in LANGUAGES.items()]
        self._lang_display_names.sort()

        self.target_lang_var = tk.StringVar()
        self.target_lang_combo_main = ttk.Combobox(
            lang_row,
            textvariable=self.target_lang_var,
            values=self._lang_display_names,
            state='disabled',
            font=("Segoe UI", 10),
            width=28
        )
        self.target_lang_combo_main.pack(side=tk.LEFT)
        self.target_lang_combo_main.bind('<<ComboboxSelected>>', self._on_language_changed_main)

        # Подсказка для языка
        self.lang_hint_label = tk.Label(
            lang_row,
            text=self.get_string('language_hint'),
            bg='#1a1a1a',
            fg='#666666',
            font=("Segoe UI", 9),
            anchor='w'
        )
        self.lang_hint_label.pack(side=tk.LEFT, padx=(10, 0))

        # Устанавливаем текущий язык
        current_lang = self.settings.get_target_language()
        for item in self._lang_display_names:
            if f"({current_lang})" in item:
                self.target_lang_var.set(item)
                break

        # Устанавливаем текущий движок
        current_engine = self.settings.get_translator_engine()
        if current_engine == "google":
            self.engine_var.set(self.get_string('engine_google'))
        else:
            self.engine_var.set(self.get_string('engine_yandex'))

        # ============================================================
        # РАЗДЕЛИТЕЛЬ
        # ============================================================
        separator2 = tk.Frame(main, bg='#2d2d2d', height=1)
        separator2.pack(fill=tk.X, padx=20)

        # ============================================================
        # СЕКЦИЯ СТАТУСА
        # ============================================================
        status_section = tk.Frame(main, bg='#1a1a1a')
        status_section.pack(fill=tk.X, padx=20, pady=(10, 5))

        self.status = tk.Label(
            status_section,
            text="● " + self.get_string('starting'),
            fg='#ff9800',
            bg='#1a1a1a',
            font=("Segoe UI", 11),
            height=1
        )
        self.status.pack(anchor=tk.W)

        # ============================================================
        # РАЗДЕЛИТЕЛЬ
        # ============================================================
        separator3 = tk.Frame(main, bg='#2d2d2d', height=1)
        separator3.pack(fill=tk.X, padx=20)

        # ============================================================
        # СЕКЦИЯ СПИСКА ОКОН
        # ============================================================
        windows_section = tk.Frame(main, bg='#1a1a1a')
        windows_section.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 12))

        # Заголовок списка окон
        windows_header = tk.Frame(windows_section, bg='#1a1a1a')
        windows_header.pack(fill=tk.X, pady=(0, 6))

        windows_icon = tk.Label(
            windows_header,
            text="🖥️",
            bg='#1a1a1a',
            fg='#4CAF50',
            font=("Segoe UI", 14)
        )
        windows_icon.pack(side=tk.LEFT, padx=(0, 8))

        self.windows_label = tk.Label(
            windows_header,
            text=self.get_string('windows_header'),
            bg='#1a1a1a',
            fg='#cccccc',
            font=("Segoe UI", 11, "bold"),
            anchor='w'
        )
        self.windows_label.pack(side=tk.LEFT)

        # Счетчик окон
        self.windows_count_label = tk.Label(
            windows_header,
            text=self.get_string('windows_count').format(0),
            bg='#1a1a1a',
            fg='#666666',
            font=("Segoe UI", 10)
        )
        self.windows_count_label.pack(side=tk.LEFT, padx=(8, 0))

        # Подсказка для списка окон
        self.windows_hint_label = tk.Label(
            windows_header,
            text=self.get_string('windows_hint'),
            bg='#1a1a1a',
            fg='#666666',
            font=("Segoe UI", 9)
        )
        self.windows_hint_label.pack(side=tk.LEFT, padx=(10, 0))

        # ============================================================
        # СПИСОК ОКОН
        # ============================================================
        listbox_container = tk.Frame(
            windows_section,
            bg='#2d2d2d',
            bd=1,
            relief=tk.SOLID,
            highlightbackground='#3c3c3c',
            highlightthickness=1
        )
        listbox_container.pack(fill=tk.BOTH, expand=True)

        self.window_listbox = tk.Listbox(
            listbox_container,
            bg='#2d2d2d',
            fg='#cccccc',
            selectbackground='#4CAF50',
            selectforeground='white',
            font=("Segoe UI", 10),
            height=10,
            relief=tk.FLAT,
            bd=0,
            highlightthickness=0,
            activestyle='none'
        )
        self.window_listbox.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)

        # Обновляем надписи с хоткеями
        self.update_hotkey_labels()

    def update_windows_count(self, count):
        """Обновляет счетчик окон с переводами"""
        if hasattr(self, 'windows_count_label'):
            self.windows_count_label.config(text=self.get_string('windows_count').format(count))

    def update_view_menu(self):
        """Обновляет только пункт меню 'Вид' без пересоздания всего меню."""
        try:
            if not hasattr(self, '_menubar') or not self._menubar:
                return

            # Ищем индекс пункта "Вид" в меню
            view_index = None
            for index in range(self._menubar.index('end') + 1):
                try:
                    label = self._menubar.entrycget(index, 'label')
                    if label == self.get_string('menu_view'):
                        view_index = index
                        break
                except:
                    pass

            if view_index is None:
                return

            # Получаем меню "Вид"
            view_menu = self._menubar.entrycget(view_index, 'menu')
            if not view_menu:
                return

            # Проверяем, что view_menu - это объект Menu, а не строка
            if not isinstance(view_menu, Menu):
                # Если это не Menu, пересоздаём только меню "Вид"
                self._rebuild_view_menu()
                return

            # Очищаем меню
            view_menu.delete(0, 'end')

            # Добавляем актуальный пункт
            if hasattr(self.app, '_mini_bar_window') and self.app._mini_bar_window:
                view_menu.add_command(
                    label=self.get_string('mini_bar_hide'),
                    command=self.app.toggle_mini_bar
                )
            else:
                view_menu.add_command(
                    label=self.get_string('mini_bar_show'),
                    command=self.app.toggle_mini_bar
                )

            # Сохраняем состояние меню (разблокировано, если приложение готово)
            if hasattr(self.app, 'ready') and self.app.ready:
                self.set_settings_menu_enabled(True)

            self.logger.info("[MENU] Пункт 'Вид' обновлён")
        except Exception as e:
            self.logger.warning(f"[MENU] Ошибка обновления меню 'Вид': {e}")
            # В случае ошибки пересоздаём полностью
            try:
                self.create_menu()
                # Если приложение готово, разблокируем меню
                if hasattr(self.app, 'ready') and self.app.ready:
                    self.set_settings_menu_enabled(True)
            except:
                pass

    def _rebuild_view_menu(self):
        """Пересоздаёт только меню 'Вид' без пересоздания всего меню."""
        try:
            if not hasattr(self, '_menubar') or not self._menubar:
                return

            # Ищем индекс пункта "Вид"
            view_index = None
            for index in range(self._menubar.index('end') + 1):
                try:
                    label = self._menubar.entrycget(index, 'label')
                    if label == self.get_string('menu_view'):
                        view_index = index
                        break
                except:
                    pass

            if view_index is None:
                return

            # Удаляем старый пункт и создаём новый
            self._menubar.delete(view_index)

            view_menu = Menu(self._menubar, tearoff=0, bg='#1e1e1e', fg='white',
                             activebackground='#333333', activeforeground='white')

            if hasattr(self.app, '_mini_bar_window') and self.app._mini_bar_window:
                view_menu.add_command(
                    label=self.get_string('mini_bar_hide'),
                    command=self.app.toggle_mini_bar
                )
            else:
                view_menu.add_command(
                    label=self.get_string('mini_bar_show'),
                    command=self.app.toggle_mini_bar
                )

            self._menubar.insert_cascade(view_index, label=self.get_string('menu_view'), menu=view_menu)
            self._view_menu = view_menu

        except Exception as e:
            self.logger.warning(f"[MENU] Ошибка пересоздания меню 'Вид': {e}")
            # Fallback
            self.create_menu()

    def create_menu(self):
        """Создает главное меню"""
        menubar = tk.Menu(self.root, bg='#1e1e1e', fg='white', activebackground='#333333', activeforeground='white')
        self.root.config(menu=menubar)

        # === МЕНЮ ФАЙЛ ===
        file_menu = tk.Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white', activebackground='#333333',
                            activeforeground='white')
        menubar.add_cascade(label=self.get_string('menu_file'), menu=file_menu)
        file_menu.add_command(label=self.get_string('menu_open_folder'), command=self.app.open_app_folder)
        file_menu.add_separator()
        file_menu.add_command(label=self.get_string('menu_exit'), command=self.app.on_close)

        # === МЕНЮ ВИД (ЗАБЛОКИРОВАНО ДО ИНИЦИАЛИЗАЦИИ) ===
        view_menu = tk.Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white', activebackground='#333333',
                            activeforeground='white')
        menubar.add_cascade(label=self.get_string('menu_view'), menu=view_menu, state=tk.DISABLED)

        if hasattr(self.app, '_mini_bar_window') and self.app._mini_bar_window:
            view_menu.add_command(
                label=self.get_string('mini_bar_hide'),
                command=self.app.toggle_mini_bar
            )
        else:
            view_menu.add_command(
                label=self.get_string('mini_bar_show'),
                command=self.app.toggle_mini_bar
            )
        self._view_menu = view_menu

        # === МЕНЮ НАСТРОЕК (ЗАБЛОКИРОВАНО ДО ИНИЦИАЛИЗАЦИИ) ===
        settings_menu = tk.Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white', activebackground='#333333',
                                activeforeground='white')
        menubar.add_cascade(label=self.get_string('menu_settings'), menu=settings_menu, state=tk.DISABLED)
        settings_menu.add_command(label=self.get_string('menu_settings_item'), command=self.app.open_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label=self.get_string('menu_reset_settings'), command=self.app.reset_settings)

        # === МЕНЮ ГОРЯЧИХ КЛАВИШ (ЗАБЛОКИРОВАНО ДО ИНИЦИАЛИЗАЦИИ) ===
        hotkeys_menu = tk.Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white', activebackground='#333333',
                               activeforeground='white')
        menubar.add_cascade(label=self.get_string('menu_hotkeys'), menu=hotkeys_menu, state=tk.DISABLED)
        hotkeys_menu.add_command(label=self.get_string('menu_hotkeys_show'), command=self.show_hotkeys_window)

        # === МЕНЮ ПОМОЩИ (ВСЕГДА ДОСТУПНО) ===
        help_menu = tk.Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white', activebackground='#333333',
                            activeforeground='white')
        menubar.add_cascade(label=self.get_string('menu_help'), menu=help_menu)
        help_menu.add_command(label=self.get_string('menu_help_instruction'), command=self.app.show_help)

        self._menubar = menubar

        self.logger.info("[MENU] Меню создано, пункты 'Настройки', 'Хоткеи', 'Вид' заблокированы")

    def _on_window_configure(self, event):
        """
        Обработчик изменения размера/состояния окна.
        Вызывается при сворачивании, восстановлении, изменении размера.
        """
        # Проверяем, что событие относится к нашему окну
        if event.widget == self.root:
            try:
                # Дополнительная проверка существования окна
                if self.root and self.root.winfo_exists():
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
            except AttributeError:
                # Игнорируем ошибки отсутствия метода winfo_state
                pass
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

    def _on_engine_changed(self, event):
        """Обработчик выбора движка в комбобоксе"""
        selected = self.engine_var.get()
        google_label = self.get_string('engine_google')

        if selected == google_label:
            engine = "google"
        else:
            engine = "yandex"

        current = self.settings.get_translator_engine()
        if current != engine:
            self.logger.info(f"[UI] Выбран движок: {engine}")
            # Блокируем комбобокс на время переключения
            self.engine_combo.config(state='disabled')
            self.app.switch_translator_engine(engine)

    def update_engine_display(self, engine: str):
        """Обновляет отображение выбранного движка в комбобоксе"""
        if engine == "google":
            self.engine_var.set(self.get_string('engine_google'))
        else:
            self.engine_var.set(self.get_string('engine_yandex'))
        self.logger.info(f"[UI] Обновлён движок в комбобоксе: {engine}")

        # Также обновляем статус, если приложение готово
        if hasattr(self.app, 'ready') and self.app.ready:
            target_lang = self.settings.get_target_language()
            engine_name = "Google Translate" if engine == "google" else "Яндекс.Переводчик (OCR)"
            ready_text = self.get_string('ready')
            self.update_status(
                f"● {ready_text} ({engine_name}, {target_lang.upper()})",
                '#4CAF50'
            )

    def update_ui_language(self):
        """Обновляет язык интерфейса - все элементы"""
        self.root.title(self.get_string('app_title'))

        # 1. ЗАГОЛОВОК ОКНА
        if self.title_label:
            self.title_label.config(text=self.get_string('app_title'))

        # 2. СЕКЦИЯ НАСТРОЕК ПЕРЕВОДА
        if hasattr(self, 'section_label') and self.section_label:
            self.section_label.config(text=self.get_string('translation_settings_header'))

        # 3. ЛЕЙБЛЫ "ДВИЖОК:" И "ЯЗЫК:"
        if hasattr(self, 'engine_label') and self.engine_label:
            self.engine_label.config(text=self.get_string('engine_label_short'))
        if hasattr(self, 'lang_label') and self.lang_label:
            self.lang_label.config(text=self.get_string('target_language_short'))

        # 4. ПОДСКАЗКИ — ОБНОВЛЯЕМ НАПРЯМУЮ ПО ССЫЛКАМ
        if hasattr(self, 'engine_hint_label') and self.engine_hint_label:
            self.engine_hint_label.config(text=self.get_string('engine_hint'))
        if hasattr(self, 'lang_hint_label') and self.lang_hint_label:
            self.lang_hint_label.config(text=self.get_string('language_hint'))
        if hasattr(self, 'windows_hint_label') and self.windows_hint_label:
            self.windows_hint_label.config(text=self.get_string('windows_hint'))

        # 5. СЕКЦИЯ СПИСКА ОКОН
        if hasattr(self, 'windows_label') and self.windows_label:
            self.windows_label.config(text=self.get_string('windows_header'))
        if hasattr(self, 'windows_count_label') and self.windows_count_label:
            count = self.window_listbox.size() if hasattr(self, 'window_listbox') else 0
            self.windows_count_label.config(text=self.get_string('windows_count').format(count))

        # 6. ОБНОВЛЯЕМ ЗНАЧЕНИЯ КОМБОБОКСА ДВИЖКА
        if hasattr(self, 'engine_combo') and self.engine_combo:
            current_engine = self.settings.get_translator_engine()
            self.engine_combo['values'] = [self.get_string('engine_google'), self.get_string('engine_yandex')]
            if current_engine == "google":
                self.engine_var.set(self.get_string('engine_google'))
            else:
                self.engine_var.set(self.get_string('engine_yandex'))

        # 7. КНОПКА МИНИ-БАР (обновляем подсказку)
        if hasattr(self, 'mini_bar_btn') and self.mini_bar_btn:
            if hasattr(self.app, '_mini_bar_window') and self.app._mini_bar_window:
                self._add_tooltip(self.mini_bar_btn, self.get_string('mini_bar_hide_tooltip'))
            else:
                self._add_tooltip(self.mini_bar_btn, self.get_string('mini_bar_show_tooltip'))

        # 8. СТАТУС
        if self.status and hasattr(self.app, 'ready'):
            if not self.app.ready:
                if hasattr(self.app, 'initializing') and self.app.initializing:
                    self.status.config(
                        text="● " + self.get_string('starting_browser'),
                        fg='#ff9800'
                    )
                else:
                    self.status.config(
                        text="● " + self.get_string('starting'),
                        fg='#ff9800'
                    )
            else:
                engine = self.app.settings.get_translator_engine()
                engine_name = self.get_string('engine_google') if engine == "google" else self.get_string(
                    'engine_yandex')
                target_lang = self.app.settings.get_target_language()
                ready_text = self.get_string('ready')
                self.status.config(
                    text=f"● {ready_text} ({engine_name}, {target_lang.upper()})",
                    fg='#4CAF50'
                )

        # 9. КНОПКА СМЕНЫ ЯЗЫКА ИНТЕРФЕЙСА
        current_lang = self.settings.get_language()
        if self.lang_btn:
            lang_text = "EN" if current_lang == "ru" else "RU"
            self.lang_btn.config(text=lang_text)

        # 10. ОБНОВЛЯЕМ НАДПИСИ С ХОТКЕЯМИ
        self.update_hotkey_labels()

        # 11. МЕНЮ
        is_ready = False
        if hasattr(self.app, 'ready') and self.app.ready:
            is_ready = True

        self.create_menu()

        if is_ready:
            self.set_settings_menu_enabled(True)

    def _update_hints(self):
        """Обновляет все подсказки"""
        try:
            # Ищем и обновляем все подсказки
            for child in self.root.winfo_children():
                for subchild in child.winfo_children():
                    if isinstance(subchild, tk.Label):
                        current_text = subchild.cget('text')
                        # Подсказка для движка
                        if current_text in ['(выберите сервис перевода)', '(select translation service)']:
                            subchild.config(text=self.get_string('engine_hint'))
                        # Подсказка для языка
                        elif current_text in ['(язык, на который переводить)', '(target translation language)']:
                            subchild.config(text=self.get_string('language_hint'))
                        # Подсказка для списка окон
                        elif current_text in ['— нажмите правой кнопкой для удаления', '— right-click to remove']:
                            subchild.config(text=self.get_string('windows_hint'))
        except Exception as e:
            self.logger.warning(f"[UI] Ошибка обновления подсказок: {e}")

    def _update_section_labels(self):
        """Обновляет лейблы в секции настроек"""
        try:
            for child in self.root.winfo_children():
                for subchild in child.winfo_children():
                    if isinstance(subchild, Frame):
                        # Ищем лейблы "Движок:" и "Язык:"
                        for grandchild in subchild.winfo_children():
                            if isinstance(grandchild, Label):
                                current_text = grandchild.cget('text')
                                if current_text in ['Движок:', 'Engine:']:
                                    grandchild.config(text=self.get_string('engine_label_short'))
                                elif current_text in ['Язык:', 'Language:']:
                                    grandchild.config(text=self.get_string('target_language_short'))
        except Exception as e:
            self.logger.warning(f"[UI] Ошибка обновления лейблов: {e}")

    def _update_footer(self):
        """Обновляет футер с подсказкой по хоткеям"""
        try:
            for child in self.root.winfo_children():
                for subchild in child.winfo_children():
                    if isinstance(subchild, Label):
                        current_text = subchild.cget('text')
                        if 'F2 — скриншот' in current_text or 'F2 — screenshot' in current_text:
                            subchild.config(text=self.get_string('footer_hotkeys'))
        except Exception as e:
            self.logger.warning(f"[UI] Ошибка обновления футера: {e}")

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
        """
        Обновляет статус. Используется только для статуса готовности браузера.
        """
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
        """
        Блокирует/разблокирует меню настроек, хоткеев, вид и кнопку мини-бар.

        Args:
            enabled: True - разблокировать, False - заблокировать
        """
        try:
            state = tk.NORMAL if enabled else DISABLED

            # === БЛОКИРУЕМ/РАЗБЛОКИРУЕМ КНОПКУ ШЕСТЕРЕНКУ ===
            if hasattr(self, 'settings_btn'):
                if enabled:
                    self.settings_btn.config(state=tk.NORMAL, bg='#3c3c3c', fg='#cccccc')
                else:
                    self.settings_btn.config(state=tk.DISABLED, bg='#2d2d2d', fg='#444444')

            # === БЛОКИРУЕМ/РАЗБЛОКИРУЕМ КНОПКУ МИНИ-БАР ===
            if hasattr(self, 'mini_bar_btn'):
                if enabled:
                    self.mini_bar_btn.config(state=tk.NORMAL, bg='#2d2d2d', fg='#888888')
                    # Восстанавливаем нормальную подсказку
                    if hasattr(self.app, '_mini_bar_window') and self.app._mini_bar_window:
                        self._add_tooltip(self.mini_bar_btn, self.get_string('mini_bar_hide_tooltip'))
                    else:
                        self._add_tooltip(self.mini_bar_btn, self.get_string('mini_bar_show_tooltip'))
                else:
                    # Кнопка заблокирована - просто убираем подсказку через удаление tooltip
                    self.mini_bar_btn.config(state=tk.DISABLED, bg='#2d2d2d', fg='#444444')
                    if hasattr(self.mini_bar_btn, '_tooltip') and self.mini_bar_btn._tooltip:
                        try:
                            self.mini_bar_btn._tooltip.destroy()
                        except:
                            pass
                        self.mini_bar_btn._tooltip = None

            # === БЛОКИРУЕМ/РАЗБЛОКИРУЕМ МЕНЮ ===
            if hasattr(self, '_menubar') and self._menubar:
                for index in range(self._menubar.index('end') + 1):
                    try:
                        label = self._menubar.entrycget(index, 'label')
                        if label == self.get_string('menu_settings'):
                            self._menubar.entryconfig(index, state=state)
                        elif label == self.get_string('menu_hotkeys'):
                            self._menubar.entryconfig(index, state=state)
                        elif label == self.get_string('menu_view'):
                            self._menubar.entryconfig(index, state=state)
                    except:
                        pass

            self.logger.info(f"[UI] Меню и кнопки {'разблокированы' if enabled else 'заблокированы'}")
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
