"""
Модуль для окна настроек приложения
"""

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from pathlib import Path
import os


class SettingsWindow:
    """Окно настроек программы"""

    def __init__(self, app_instance, settings, on_settings_changed):
        self.app = app_instance  # Сохраняем ссылку на экземпляр приложения
        self.parent = app_instance.root  # Родительское окно - главное окно приложения
        self.settings = settings
        self.on_settings_changed = on_settings_changed

        self.window = tk.Toplevel(self.parent)
        self.window.title(self.get_string('settings_title'))
        self.window.geometry("580x650")
        self.window.minsize(550, 600)
        self.window.resizable(True, True)
        self.window.configure(bg='#1e1e1e')
        self.window.transient(self.parent)
        self.window.grab_set()

        # Скрываем окно до полной настройки
        self.window.withdraw()

        self.center_window()
        self.create_widgets()
        self.load_values()

        # Показываем окно после всех настроек
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def _add_tooltip(self, widget, text):
        """Добавляет всплывающую подсказку при наведении на виджет."""

        def enter(event):
            # Закрываем старую подсказку, если есть
            if hasattr(widget, '_tooltip') and widget._tooltip:
                try:
                    widget._tooltip.destroy()
                except:
                    pass
                widget._tooltip = None

            # Создаем новую подсказку
            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            # Позиционируем подсказку чуть ниже курсора
            x = event.x_root + 10
            y = event.y_root + 20
            # Проверяем, чтобы подсказка не выходила за экран
            screen_width = tooltip.winfo_screenwidth()
            screen_height = tooltip.winfo_screenheight()
            # Сначала вычисляем размеры подсказки
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
                wraplength=350,
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

    def reset_settings(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        if messagebox.askyesno(self.get_string('settings_title'), self.get_string('settings_reset_confirm')):
            from src.settings import Settings
            for key, value in Settings.DEFAULT_SETTINGS.items():
                self.settings.set(key, value)
            self.load_values()
            # Обновляем переменные для новых настроек
            if hasattr(self, 'show_indicator_var'):
                self.show_indicator_var.set(self.settings.get_show_translation_indicator())
            if hasattr(self, 'auto_hide_var'):
                self.auto_hide_var.set(self.settings.get_auto_hide_overlay())
            messagebox.showinfo(self.get_string('settings_title'), self.get_string('settings_reset_done'))

    def get_string(self, key):
        return self.settings.get_string(key)

    def center_window(self):
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

    def create_widgets(self):
        main_container = tk.Frame(self.window, bg='#1e1e1e')
        main_container.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)

        title = tk.Label(main_container, text=self.get_string('settings_title'),
                         font=('Segoe UI', 18, 'bold'), bg='#1e1e1e', fg='white')
        title.pack(pady=(0, 20))

        # --- НАСТРОЙКА БРАУЗЕРА ---
        browser_frame = tk.LabelFrame(
            main_container,
            text=self.get_string('settings_browser_section'),
            bg='#1e1e1e',
            fg='#4CAF50',
            font=('Segoe UI', 12, 'bold'),
            padx=15,
            pady=12
        )
        browser_frame.pack(fill=tk.X, pady=(0, 15))

        current_path = self.settings.get_browser_path()
        lang = self.settings.get_language()

        if current_path and os.path.exists(current_path):
            if 'Yandex' in current_path or 'Яндекс' in current_path:
                browser_name = "Yandex Browser" if lang == 'en' else "Яндекс Браузер"
            elif 'Google' in current_path or 'Chrome' in current_path:
                browser_name = "Google Chrome"
            elif 'Brave' in current_path:
                browser_name = "Brave"
            elif 'Vivaldi' in current_path:
                browser_name = "Vivaldi"
            elif 'Chromium' in current_path:
                browser_name = "Chromium"
            else:
                browser_name = Path(current_path).name

            status_text = self.get_string('settings_browser_using').format(browser_name)
            status_color = '#4CAF50'
        else:
            status_text = self.get_string('settings_browser_not_specified')
            status_color = '#ff9800'

        status_label = tk.Label(
            browser_frame,
            text=status_text,
            bg='#1e1e1e',
            fg=status_color,
            font=('Segoe UI', 11, 'bold'),
            anchor='w'
        )
        status_label.pack(anchor=tk.W, pady=(0, 10), fill=tk.X)

        path_frame = tk.Frame(browser_frame, bg='#1e1e1e')
        path_frame.pack(fill=tk.X, pady=5)

        self.browser_path_var = tk.StringVar()

        path_entry_frame = tk.Frame(path_frame, bg='#1e1e1e')
        path_entry_frame.pack(fill=tk.X)

        self.browser_path_entry = tk.Entry(
            path_entry_frame,
            textvariable=self.browser_path_var,
            bg='#2d2d2d',
            fg='white',
            insertbackground='white',
            font=('Segoe UI', 10),
            relief=tk.FLAT
        )
        self.browser_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=4)

        browse_btn = tk.Button(
            path_entry_frame,
            text=self.get_string('settings_browser_browse'),
            command=self.browse_browser,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 9),
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor='hand2',
            width=10
        )
        browse_btn.pack(side=tk.RIGHT)

        tk.Label(
            browser_frame,
            text=self.get_string('settings_browser_path_hint'),
            bg='#1e1e1e',
            fg='#666666',
            font=('Segoe UI', 9),
            wraplength=480,
            anchor='w',
            justify='left'
        ).pack(anchor=tk.W, pady=(5, 0), fill=tk.X)

        # --- НАСТРОЙКИ ИНДИКАТОРА И АВТОСКРЫТИЯ ---
        ui_frame = tk.LabelFrame(
            main_container,
            text=self.get_string('settings_ui'),
            bg='#1e1e1e',
            fg='white',
            font=('Segoe UI', 12, 'bold'),
            padx=15,
            pady=12
        )
        ui_frame.pack(fill=tk.X, pady=(0, 20))

        self.show_indicator_var = tk.BooleanVar(value=self.settings.get_show_translation_indicator())
        indicator_cb = tk.Checkbutton(
            ui_frame,
            text=self.get_string('show_translation_indicator'),
            variable=self.show_indicator_var,
            bg='#1e1e1e',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Segoe UI', 11),
            padx=5,
            pady=5
        )
        indicator_cb.pack(anchor=tk.W, pady=6)

        self.auto_hide_var = tk.BooleanVar(value=self.settings.get_auto_hide_overlay())
        auto_hide_cb = tk.Checkbutton(
            ui_frame,
            text=self.get_string('auto_hide_overlay'),
            variable=self.auto_hide_var,
            bg='#1e1e1e',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Segoe UI', 11),
            padx=5,
            pady=5
        )
        auto_hide_cb.pack(anchor=tk.W, pady=6)

        self.auto_windowed_fullscreen_var = tk.BooleanVar(value=self.settings.get_auto_windowed_fullscreen())
        auto_fullscreen_cb = tk.Checkbutton(
            ui_frame,
            text=self.get_string('auto_windowed_fullscreen'),
            variable=self.auto_windowed_fullscreen_var,
            bg='#1e1e1e',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Segoe UI', 11),
            padx=5,
            pady=5
        )
        auto_fullscreen_cb.pack(anchor=tk.W, pady=6)

        # === РЕЖИМ РЕДАКТИРОВАНИЯ (с подсказкой при наведении) ===
        self.edit_mode_var = tk.BooleanVar(value=self.settings.get_edit_mode_enabled())
        edit_mode_cb = tk.Checkbutton(
            ui_frame,
            text=self.get_string('edit_mode'),
            variable=self.edit_mode_var,
            bg='#1e1e1e',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Segoe UI', 11),
            padx=5,
            pady=5
        )
        edit_mode_cb.pack(anchor=tk.W, pady=6)
        # Подсказка при наведении
        self._add_tooltip(edit_mode_cb, self.get_string('edit_mode_tooltip'))

        # --- КНОПКИ ---
        btn_frame = tk.Frame(main_container, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, pady=(10, 0))

        save_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_save'),
            command=self.save_settings,
            bg='#4CAF50',
            fg='white',
            font=('Segoe UI', 11, 'bold'),
            relief=tk.FLAT,
            height=1,
            pady=12,
            cursor='hand2'
        )
        save_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5), ipady=2)

        reset_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_reset'),
            command=self.reset_settings,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 11),
            relief=tk.FLAT,
            height=1,
            pady=12,
            cursor='hand2'
        )
        reset_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 5), ipady=2)

        cancel_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_cancel'),
            command=self.window.destroy,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 11),
            relief=tk.FLAT,
            height=1,
            pady=12,
            cursor='hand2'
        )
        cancel_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0), ipady=2)

        self.window.bind('<Escape>', lambda e: self.window.destroy())

    def load_values(self):
        """Загружает текущие настройки в поля."""
        current_path = self.settings.get_browser_path()
        self.browser_path_var.set(current_path)
        if hasattr(self, 'show_indicator_var'):
            self.show_indicator_var.set(self.settings.get_show_translation_indicator())
        if hasattr(self, 'auto_hide_var'):
            self.auto_hide_var.set(self.settings.get_auto_hide_overlay())
        if hasattr(self, 'auto_windowed_fullscreen_var'):
            self.auto_windowed_fullscreen_var.set(self.settings.get_auto_windowed_fullscreen())
        if hasattr(self, 'edit_mode_var'):
            self.edit_mode_var.set(self.settings.get_edit_mode_enabled())

    def save_settings(self):
        """Сохраняет настройки."""
        browser_path = self.browser_path_var.get().strip()
        if browser_path and not os.path.exists(browser_path):
            messagebox.showerror(
                "Ошибка",
                "Указанный файл не существует!\nПроверьте путь."
            )
            return

        self.settings.set_browser_path(browser_path)
        self.settings.set_show_translation_indicator(self.show_indicator_var.get())
        self.settings.set_auto_hide_overlay(self.auto_hide_var.get())
        self.settings.set_auto_windowed_fullscreen(self.auto_windowed_fullscreen_var.get())

        # === НОВОЕ: сохраняем режим редактирования ===
        edit_mode = self.edit_mode_var.get()
        self.settings.set_edit_mode_enabled(edit_mode)

        # Обновляем состояние в главном приложении
        if hasattr(self, 'app') and hasattr(self.app, '_edit_mode_enabled'):
            self.app._edit_mode_enabled = edit_mode
            # Обновляем кнопку в главном окне
            if hasattr(self.app, 'btn_edit_mode'):
                status_text = "ВКЛЮЧЕН" if edit_mode else "ВЫКЛЮЧЕН"
                self.app.btn_edit_mode.config(
                    text=f"✏️ Редактирование: {status_text} (F5)",
                    bg='#4CAF50' if edit_mode else '#ff9800'
                )
            # Обновляем статус
            if hasattr(self.app, 'update_status'):
                status_text = "ВКЛЮЧЕН" if edit_mode else "ВЫКЛЮЧЕН"
                status_color = '#4CAF50' if edit_mode else '#ff9800'
                self.app.update_status(f"● Режим редактирования: {status_text}", status_color)
            self.app.logger.info(f"Режим редактирования из настроек: {edit_mode}")

        self.settings.save()

        print(f"[DEBUG] Сохранена настройка автоскрытия: {self.auto_hide_var.get()}")
        print(f"[DEBUG] Сохранена настройка оконного полноэкранного режима: {self.auto_windowed_fullscreen_var.get()}")
        print(f"[DEBUG] Сохранена настройка режима редактирования: {edit_mode}")

        if hasattr(self, 'app') and hasattr(self.app, 'overlay') and self.app.overlay:
            print(f"[DEBUG] Вызываем overlay.set_auto_hide({self.auto_hide_var.get()})")
            self.app.overlay.set_auto_hide(self.auto_hide_var.get())
            print(f"[DEBUG] Обновлен режим автоскрытия оверлея: {self.auto_hide_var.get()}")
        else:
            print(f"[DEBUG] app.overlay = {getattr(self.app, 'overlay', None)}")

        if hasattr(self, 'app') and hasattr(self.app, 'setup_hotkeys'):
            self.app.setup_hotkeys()

        messagebox.showinfo(
            self.get_string('settings_title'),
            self.get_string('settings_saved')
        )

        if self.on_settings_changed:
            self.on_settings_changed()

        self.window.destroy()

    def browse_browser(self):
        """Открывает диалог выбора файла браузера"""
        file_path = filedialog.askopenfilename(
            title="Выберите исполняемый файл браузера",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        if file_path:
            self.browser_path_var.set(file_path)