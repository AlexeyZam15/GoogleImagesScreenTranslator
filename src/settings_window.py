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

    def __init__(self, parent, settings, on_settings_changed):
        self.parent = parent
        self.settings = settings
        self.on_settings_changed = on_settings_changed

        self.window = tk.Toplevel(parent)
        self.window.title(self.get_string('settings_title'))
        self.window.geometry("500x400")
        self.window.minsize(450, 350)
        self.window.resizable(True, True)
        self.window.configure(bg='#1e1e1e')
        self.window.transient(parent)
        self.window.grab_set()

        self.center_window()
        self.create_widgets()
        self.load_values()

    def reset_settings(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        if messagebox.askyesno(self.get_string('settings_title'), self.get_string('settings_reset_confirm')):
            from src.settings import Settings
            for key, value in Settings.DEFAULT_SETTINGS.items():
                self.settings.set(key, value)
            self.load_values()
            self.update_labels()
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
        main = tk.Frame(self.window, bg='#1e1e1e')
        main.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)

        # Заголовок
        title = tk.Label(
            main,
            text=self.get_string('settings_title'),
            font=('Segoe UI', 16, 'bold'),
            bg='#1e1e1e',
            fg='white'
        )
        title.pack(pady=(0, 20))

        # --- НАСТРОЙКА БРАУЗЕРА ---
        browser_frame = tk.LabelFrame(
            main,
            text=self.get_string('settings_browser_section'),
            bg='#1e1e1e',
            fg='#4CAF50',
            font=('Segoe UI', 12, 'bold'),
            padx=15,
            pady=10
        )
        browser_frame.pack(fill=tk.X, pady=(0, 15))

        # Информация о текущем браузере
        current_path = self.settings.get_browser_path()

        # Определяем язык для названия браузера
        lang = self.settings.get_language()

        if current_path and os.path.exists(current_path):
            # Определяем имя браузера в зависимости от языка
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
            font=('Segoe UI', 11, 'bold')
        )
        status_label.pack(anchor=tk.W, pady=(0, 10))

        # Поле для пути
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
        self.browser_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        browse_btn = tk.Button(
            path_entry_frame,
            text=self.get_string('settings_browser_browse'),
            command=self.browse_browser,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 9),
            relief=tk.FLAT,
            padx=10,
            pady=4,
            cursor='hand2'
        )
        browse_btn.pack(side=tk.RIGHT)

        # Подсказка
        tk.Label(
            browser_frame,
            text=self.get_string('settings_browser_path_hint'),
            bg='#1e1e1e',
            fg='#666666',
            font=('Segoe UI', 9),
            wraplength=400
        ).pack(anchor=tk.W, pady=(5, 0))

        # --- КНОПКИ ---
        btn_frame = tk.Frame(main, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, pady=(20, 0))

        save_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_save'),
            command=self.save_settings,
            bg='#4CAF50',
            fg='white',
            font=('Segoe UI', 11, 'bold'),
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2'
        )
        save_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        cancel_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_cancel'),
            command=self.window.destroy,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 11),
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2'
        )
        cancel_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        # Привязка ESC
        self.window.bind('<Escape>', lambda e: self.window.destroy())

    def load_values(self):
        """Загружает текущие настройки в поля"""
        current_path = self.settings.get_browser_path()
        self.browser_path_var.set(current_path)

    def save_settings(self):
        """Сохраняет настройки"""
        # Сохраняем путь к браузеру
        browser_path = self.browser_path_var.get().strip()
        if browser_path and not os.path.exists(browser_path):
            messagebox.showerror(
                "Ошибка",
                "Указанный файл не существует!\nПроверьте путь."
            )
            return

        self.settings.set_browser_path(browser_path)
        self.settings.save()

        messagebox.showinfo(
            self.get_string('settings_title'),
            self.get_string('settings_saved')
        )

        # Уведомляем главное окно об изменении настроек
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
