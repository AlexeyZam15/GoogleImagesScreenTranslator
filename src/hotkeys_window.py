"""
Модуль для отображения окна с информацией о горячих клавишах.
"""

import tkinter as tk
from tkinter import ttk, messagebox
import logging
import keyboard
from src.hotkey_capture import HotkeyCaptureManager


class HotkeysWindow:
    """Окно с информацией о горячих клавишах."""

    def __init__(self, app):
        self.app = app
        self.settings = app.settings
        self.logger = logging.getLogger(__name__)

        # Если окно уже существует, просто поднимаем его
        if hasattr(app, '_hotkeys_window') and app._hotkeys_window:
            try:
                app._hotkeys_window.window.lift()
                app._hotkeys_window.window.focus_force()
                return
            except:
                app._hotkeys_window = None

        # Создаем окно
        self.window = tk.Toplevel(app.root)
        self.window.title(self.get_string('hotkeys_title'))
        self.window.geometry("650x700")
        self.window.minsize(550, 500)
        self.window.resizable(True, True)
        self.window.configure(bg='#1e1e1e')
        self.window.transient(app.root)
        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        # Сохраняем ссылку
        app._hotkeys_window = self

        # ОТКЛЮЧАЕМ ВСЕ ХУКИ КЛАВИШ
        try:
            keyboard.unhook_all()
            self.logger.info("[HOTKEYS_WINDOW] Все хуки клавиш отключены")
        except Exception as e:
            self.logger.warning(f"[HOTKEYS_WINDOW] Ошибка отключения хуков: {e}")

        # Блокируем действия горячих клавиш
        if hasattr(self.app, 'set_actions_blocked'):
            self.logger.info("[HOTKEYS_WINDOW] Блокируем действия горячих клавиш")
            self.app.set_actions_blocked(True)

        # Создаем менеджер захвата горячих клавиш
        self.hotkey_capture_manager = HotkeyCaptureManager(self.window, self.settings, self.app)

        # Словари для хранения кнопок и переменных
        self.hotkey_buttons = {}
        self.hotkey_vars = {}
        self.hotkey_capturing = {}

        # Создаем виджеты
        self.create_widgets()

        # Регистрируем кнопки в менеджере
        self.hotkey_capture_manager.set_hotkey_buttons(self.hotkey_buttons, self.hotkey_vars)

        # Центрируем и показываем
        self.center_window()
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def create_widgets(self):
        """Создает все виджеты окна."""
        main_frame = tk.Frame(self.window, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=25)

        header_frame = tk.Frame(main_frame, bg='#1e1e1e')
        header_frame.pack(fill=tk.X, pady=(0, 15))

        icon_label = tk.Label(
            header_frame,
            text="⌨️",
            bg='#1e1e1e',
            fg='white',
            font=("Segoe UI", 28)
        )
        icon_label.pack(side=tk.LEFT, padx=(0, 12))

        title_label = tk.Label(
            header_frame,
            text=self.get_string('hotkeys_title'),
            bg='#1e1e1e',
            fg='#4CAF50',
            font=("Segoe UI", 20, "bold")
        )
        title_label.pack(side=tk.LEFT)

        hint_label = tk.Label(
            main_frame,
            text=self.get_string('settings_hotkeys_click_to_change'),
            bg='#1e1e1e',
            fg='#888888',
            font=("Segoe UI", 10),
            anchor='w'
        )
        hint_label.pack(anchor=tk.W, pady=(0, 10))

        canvas_frame = tk.Frame(main_frame, bg='#1e1e1e')
        canvas_frame.pack(fill=tk.BOTH, expand=True)

        canvas = tk.Canvas(canvas_frame, bg='#1e1e1e', highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)

        # Привязываем скролл колесико к canvas
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        cards_frame = tk.Frame(canvas, bg='#1e1e1e')
        cards_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=cards_frame, anchor="nw", width=canvas_frame.winfo_width())
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        def on_configure(event):
            canvas.itemconfig(1, width=event.width)

        canvas.bind('<Configure>', on_configure)

        hotkey_data = [
            ('toggle_overlay', '🔄', 'hotkey_toggle_overlay', self.get_string('hotkey_toggle_overlay_desc')),
            ('screenshot', '📸', 'hotkey_screenshot', self.get_string('hotkey_screenshot_desc')),
            ('area', '✂️', 'hotkey_area', self.get_string('hotkey_area_desc')),
            ('clear_all', '🗑️', 'hotkey_clear_all', self.get_string('hotkey_clear_all_desc')),
            ('edit_mode', '✏️', 'hotkey_edit_mode', self.get_string('hotkey_edit_mode_desc')),
            ('auto_replace', '🔄', 'hotkey_auto_replace', self.get_string('hotkey_auto_replace_desc')),
        ]

        hotkeys = self.settings.get_all_hotkeys()

        for action, icon, name_key, description in hotkey_data:
            card = tk.Frame(
                cards_frame,
                bg='#2d2d2d',
                bd=0,
                relief=tk.FLAT
            )
            card.pack(fill=tk.X, pady=6)

            card_inner = tk.Frame(
                card,
                bg='#2d2d2d',
                bd=1,
                relief=tk.SOLID,
                highlightbackground='#3c3c3c',
                highlightthickness=1
            )
            card_inner.pack(fill=tk.X, padx=0)

            row_frame = tk.Frame(card_inner, bg='#2d2d2d')
            row_frame.pack(fill=tk.X, padx=15, pady=12)

            icon_label = tk.Label(
                row_frame,
                text=icon,
                bg='#2d2d2d',
                fg='#4CAF50',
                font=("Segoe UI", 20)
            )
            icon_label.pack(side=tk.LEFT, padx=(0, 12))

            name_label = tk.Label(
                row_frame,
                text=self.get_string(name_key),
                bg='#2d2d2d',
                fg='#ffffff',
                font=("Segoe UI", 12, "bold"),
                anchor='w'
            )
            name_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            self.hotkey_vars[action] = tk.StringVar(value=hotkeys.get(action, ''))

            key_text = hotkeys.get(action, '—').upper()
            key_color = '#4CAF50' if key_text != '—' else '#666666'

            key_btn = tk.Label(
                row_frame,
                text=key_text,
                bg='#3c3c3c',
                fg=key_color,
                font=("Segoe UI", 11, "bold"),
                padx=12,
                pady=4,
                relief=tk.FLAT,
                bd=0,
                cursor='hand2',
                wraplength=120
            )
            key_btn.pack(side=tk.RIGHT)

            self.hotkey_buttons[action] = key_btn

            key_btn.bind('<Button-1>', lambda e, a=action: self.hotkey_capture_manager.start_hotkey_capture(a))

            desc_label = tk.Label(
                card_inner,
                text=description,
                bg='#2d2d2d',
                fg='#888888',
                font=("Segoe UI", 10),
                anchor='w',
                wraplength=500,
                justify='left'
            )
            desc_label.pack(fill=tk.X, padx=15, pady=(0, 12))

        esc_card = tk.Frame(
            cards_frame,
            bg='#2d2d2d',
            bd=0,
            relief=tk.FLAT
        )
        esc_card.pack(fill=tk.X, pady=6)

        esc_card_inner = tk.Frame(
            esc_card,
            bg='#2d2d2d',
            bd=1,
            relief=tk.SOLID,
            highlightbackground='#3c3c3c',
            highlightthickness=1
        )
        esc_card_inner.pack(fill=tk.X, padx=0)

        esc_row_frame = tk.Frame(esc_card_inner, bg='#2d2d2d')
        esc_row_frame.pack(fill=tk.X, padx=15, pady=12)

        esc_icon = tk.Label(
            esc_row_frame,
            text="❌",
            bg='#2d2d2d',
            fg='#ff6b6b',
            font=("Segoe UI", 20)
        )
        esc_icon.pack(side=tk.LEFT, padx=(0, 12))

        esc_name = tk.Label(
            esc_row_frame,
            text=self.get_string('hotkey_esc'),
            bg='#2d2d2d',
            fg='#ffffff',
            font=("Segoe UI", 12, "bold"),
            anchor='w'
        )
        esc_name.pack(side=tk.LEFT, fill=tk.X, expand=True)

        esc_key = tk.Label(
            esc_row_frame,
            text="ESC",
            bg='#3c3c3c',
            fg='#ff6b6b',
            font=("Segoe UI", 12, "bold"),
            padx=12,
            pady=4,
            relief=tk.FLAT,
            bd=0
        )
        esc_key.pack(side=tk.RIGHT)

        esc_desc = tk.Label(
            esc_card_inner,
            text=self.get_string('hotkey_esc_desc'),
            bg='#2d2d2d',
            fg='#888888',
            font=("Segoe UI", 10),
            anchor='w',
            wraplength=500,
            justify='left'
        )
        esc_desc.pack(fill=tk.X, padx=15, pady=(0, 12))

        btn_frame = tk.Frame(main_frame, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        reset_btn = tk.Button(
            btn_frame,
            text="↺ Сбросить хоткеи",
            command=self.reset_hotkeys,
            bg='#3c3c3c',  # <-- ИЗМЕНЕНО: убран желтый цвет (#ff9800), теперь серый как у других кнопок
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2'
        )
        reset_btn.pack(side=tk.LEFT, padx=(0, 10), expand=True, fill=tk.X)

        close_btn = tk.Button(
            btn_frame,
            text="❌ Закрыть",
            command=self.on_close,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2'
        )
        close_btn.pack(side=tk.LEFT, padx=(10, 0), expand=True, fill=tk.X)

    def reset_hotkeys(self):
        """Сбрасывает горячие клавиши к значениям по умолчанию без уведомления."""
        default_hotkeys = {
            "screenshot": "f2",
            "area": "f3",
            "toggle_overlay": "f1",
            "clear_all": "f4",
            "edit_mode": "f5",
            "auto_replace": "f6"
        }

        for action, default_key in default_hotkeys.items():
            self.settings.set_hotkey(action, default_key)
            self.hotkey_vars[action].set(default_key)
            self.hotkey_buttons[action].config(text=default_key.upper(), bg='#2d2d2d')

        self.settings.save()

        # Перерегистрируем горячие клавиши в приложении
        if hasattr(self.app, 'setup_hotkeys'):
            self.app.setup_hotkeys()

    def center_window(self):
        """Центрирует окно на экране."""
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

    def get_string(self, key):
        """Возвращает локализованную строку."""
        return self.settings.get_string(key)

    def open_settings(self):
        """Открывает окно настроек."""
        self.app.open_settings()

    def update_language(self):
        """Обновляет язык интерфейса окна."""
        self.window.title(self.get_string('hotkeys_title'))
        # Пересоздаем виджеты для обновления текста
        for widget in self.window.winfo_children():
            widget.destroy()
        self.create_widgets()

    def on_close(self):
        """Закрывает окно и очищает ссылку."""
        try:
            self.window.grab_release()
            self.window.destroy()
        except:
            pass

        # ВОССТАНАВЛИВАЕМ ХУКИ КЛАВИШ
        try:
            if hasattr(self.app, 'hotkeys') and self.app.hotkeys:
                self.app.hotkeys.setup()
                self.logger.info("[HOTKEYS_WINDOW] Хуки клавиш восстановлены")
        except Exception as e:
            self.logger.warning(f"[HOTKEYS_WINDOW] Ошибка восстановления хуков: {e}")

        # Разблокируем действия горячих клавиш
        if hasattr(self.app, 'set_actions_blocked'):
            self.logger.info("[HOTKEYS_WINDOW] Разблокируем действия горячих клавиш")
            self.app.set_actions_blocked(False)

        if hasattr(self.app, '_hotkeys_window'):
            self.app._hotkeys_window = None
