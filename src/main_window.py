"""
Главное окно приложения - содержит только UI элементы
"""

import tkinter as tk
from tkinter import ttk, Menu, Frame, Label, Button, Listbox, StringVar, BooleanVar, END, DISABLED, NORMAL, FLAT
from pathlib import Path
import logging

from src.settings import Settings
from src.browser_worker import BrowserWorker
from src.screenshot import ScreenshotCapturer

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
        self.root.geometry("500x500")
        self.root.minsize(450, 400)
        self.root.maxsize(550, 600)
        self.root.resizable(True, True)
        self.root.configure(bg='#1e1e1e')

        self.target_lang_var = StringVar(value=self.settings.get_target_language())
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
        self.update_ui_language()
        self._center_window()

        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

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

    def create_menu(self):
        """Создает главное меню"""
        menubar = Menu(self.root, bg='#1e1e1e', fg='white')
        self.root.config(menu=menubar)

        file_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white')
        menubar.add_cascade(label=self.get_string('menu_file'), menu=file_menu)
        file_menu.add_command(label=self.get_string('menu_open_folder'), command=self.app.open_app_folder)
        file_menu.add_separator()
        file_menu.add_command(label=self.get_string('menu_exit'), command=self.app.on_close)

        settings_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white')
        menubar.add_cascade(label=self.get_string('menu_settings'), menu=settings_menu, state=DISABLED)
        settings_menu.add_command(label=self.get_string('menu_settings_item'), command=self.app.open_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label=self.get_string('menu_reset_settings'), command=self.app.reset_settings)

        help_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white')
        menubar.add_cascade(label=self.get_string('menu_help'), menu=help_menu)
        help_menu.add_command(label=self.get_string('menu_help_instruction'), command=self.app.show_help)

        self._menubar = menubar

    def create_widgets(self):
        """Создает все виджеты главного окна"""
        main = Frame(self.root, bg='#1e1e1e')
        main.pack(expand=True, fill=tk.BOTH, padx=20, pady=15)

        # Заголовок
        header_frame = Frame(main, bg='#1e1e1e', height=50)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        header_frame.pack_propagate(False)

        title_frame = Frame(header_frame, bg='#1e1e1e')
        title_frame.pack(side=tk.LEFT, expand=True, fill=tk.X)

        icon_label = Label(title_frame, text="📸", bg='#1e1e1e', fg='white', font=("Arial", 20))
        icon_label.pack(side=tk.LEFT, padx=(0, 8))

        self.title_label = Label(title_frame, text=self.get_string('app_title'),
                                 bg='#1e1e1e', fg='#4CAF50', font=("Arial", 13, "bold"))
        self.title_label.pack(side=tk.LEFT)

        header_right = Frame(header_frame, bg='#1e1e1e')
        header_right.pack(side=tk.RIGHT, padx=(5, 0))

        # Кнопка языка
        current_lang = self.settings.get_language()
        lang_text = "EN" if current_lang == "ru" else "RU"
        self.lang_btn = Button(header_right, text=lang_text, command=self.app.toggle_language,
                               font=("Arial", 10, "bold"), bg='#3c3c3c', fg='#4CAF50',
                               relief=FLAT, width=3, padx=0, pady=4, cursor="hand2", state=tk.NORMAL)
        self.lang_btn.pack(side=tk.RIGHT, padx=(0, 3))

        # Кнопка настроек
        self.settings_btn = Button(header_right, text="⚙️", command=self.app.open_settings,
                                   font=("Arial", 12), bg='#3c3c3c', fg='#cccccc',
                                   relief=FLAT, width=3, padx=0, pady=4, cursor="hand2", state=DISABLED)
        self.settings_btn.pack(side=tk.RIGHT, padx=(0, 5))

        def on_settings_enter(e):
            if self.settings_btn['state'] != DISABLED:
                self.settings_btn.config(bg='#4CAF50', fg='white')

        def on_settings_leave(e):
            if self.settings_btn['state'] != DISABLED:
                self.settings_btn.config(bg='#3c3c3c', fg='#cccccc')
            else:
                self.settings_btn.config(bg='#3c3c3c', fg='#666666')

        self.settings_btn.bind('<Enter>', on_settings_enter)
        self.settings_btn.bind('<Leave>', on_settings_leave)

        # Статус
        self.status = Label(main, text="● " + self.get_string('starting'),
                            fg='#ff9800', bg='#1e1e1e', font=("Arial", 10), height=1)
        self.status.pack(pady=(2, 8), fill=tk.X)

        # Выбор языка перевода
        lang_select_frame = Frame(main, bg='#1e1e1e')
        lang_select_frame.pack(fill=tk.X, pady=(0, 10))

        self.target_lang_label = Label(lang_select_frame, text=self.get_string('target_language'),
                                       bg='#1e1e1e', fg='#cccccc', font=("Arial", 9), anchor='w')
        self.target_lang_label.pack(anchor=tk.W, fill=tk.X)

        lang_combo_frame = Frame(lang_select_frame, bg='#1e1e1e')
        lang_combo_frame.pack(fill=tk.X, pady=(3, 0))

        lang_codes = sorted(LANGUAGES.keys())
        self._all_lang_items = [f"{LANGUAGES[code]} ({code})" for code in lang_codes]

        self.target_lang_combo = ttk.Combobox(lang_combo_frame, textvariable=self.target_lang_var,
                                              values=self._all_lang_items, font=("Arial", 9),
                                              state="disabled", width=45)
        self.target_lang_combo.pack(fill=tk.X)
        self.target_lang_combo.bind('<KeyRelease>', self._on_lang_search)
        self.target_lang_combo.bind('<Return>', self._on_lang_enter)
        self.target_lang_combo.bind('<<ComboboxSelected>>', self._on_target_lang_changed)

        current_lang_code = self.settings.get_target_language()
        current_display = f"{LANGUAGES.get(current_lang_code, 'Russian')} ({current_lang_code})"
        self.target_lang_combo.set(current_display)

        # Список окон
        windows_label = Label(main, text="Окна с переводами:",
                              bg='#1e1e1e', fg='#cccccc', font=("Arial", 9), anchor='w')
        windows_label.pack(anchor=tk.W, fill=tk.X, pady=(5, 3))

        self.window_listbox = Listbox(main, bg='#2d2d2d', fg='#cccccc',
                                      selectbackground='#4CAF50', selectforeground='white',
                                      font=("Arial", 10), height=12, relief=FLAT)
        self.window_listbox.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        # Создаем контекстное меню
        self._create_context_menu()

    def _create_context_menu(self):
        """Создает контекстное меню для списка окон"""
        self.context_menu = Menu(self.window_listbox, tearoff=0, bg='#2d2d2d', fg='white',
                                 activebackground='#4CAF50', activeforeground='white')
        self.context_menu.add_command(label="Показать", command=self.app._context_show_overlays)
        self.context_menu.add_separator()
        self.context_menu.add_command(label="🗑️ Удалить оверлеи", command=self.app._context_remove_overlays)
        self.window_listbox.bind('<Button-3>', self._show_context_menu)

    def _show_context_menu(self, event):
        """Показывает контекстное меню"""
        try:
            index = self.window_listbox.nearest(event.y)
            if index >= 0:
                self.window_listbox.selection_clear(0, END)
                self.window_listbox.selection_set(index)
                # Обновляем текст кнопки в зависимости от состояния
                hwnd = self._window_hwnd_map.get(index)
                if hwnd and self.app.overlay_manager:
                    overlays = self.app.overlay_manager.get_overlays_for_window(hwnd)
                    any_visible = any(o.visible for o in overlays)
                    if any_visible:
                        self.context_menu.entryconfig(0, label="🙈 Скрыть", command=self.app._context_hide_overlays)
                    else:
                        self.context_menu.entryconfig(0, label="👁️ Показать", command=self.app._context_show_overlays)
            self.context_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.context_menu.grab_release()

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

    def _center_window(self):
        """Центрирует окно"""
        self.root.update_idletasks()
        w, h = self.root.winfo_width(), self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def update_ui_language(self):
        """Обновляет язык интерфейса"""
        self.root.title(self.get_string('app_title'))
        if self.title_label:
            self.title_label.config(text=self.get_string('app_title'))
        if self.target_lang_label:
            self.target_lang_label.config(text=self.get_string('target_language'))
        # Обновляем меню
        self.create_menu()
        # Обновляем кнопку языка
        current_lang = self.settings.get_language()
        if self.lang_btn:
            self.lang_btn.config(text="EN" if current_lang == "ru" else "RU")

    def get_string(self, key):
        """Возвращает локализованную строку"""
        return self.settings.get_string(key)

    def update_status(self, text, color='white'):
        """Обновляет статус"""
        if self.status:
            self.status.config(text=text, fg=color)

    def set_settings_menu_enabled(self, enabled):
        """Блокирует/разблокирует меню настроек"""
        try:
            state = tk.NORMAL if enabled else DISABLED
            if hasattr(self, '_menubar') and self._menubar:
                for index in range(self._menubar.index('end') + 1):
                    try:
                        label = self._menubar.entrycget(index, 'label')
                        if label == self.get_string('menu_settings'):
                            self._menubar.entryconfig(index, state=state)
                            break
                    except:
                        pass
        except Exception as e:
            self.logger.warning(f"[MENU] Ошибка при блокировке меню: {e}")