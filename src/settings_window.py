"""
Модуль для окна настроек приложения
"""

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from pathlib import Path
import os
import logging
import time
from src.hotkey_capture import HotkeyCaptureManager


class SettingsWindow:
    """Окно настроек программы"""

    def __init__(self, app_instance, settings, on_settings_changed):
        self.app = app_instance
        self.parent = app_instance.root
        self.settings = settings
        self.on_settings_changed = on_settings_changed

        self._is_reset_dialog_open = False
        self._reset_dialog = None

        self.window = tk.Toplevel(self.parent)
        self.window.title(self.get_string('settings_title'))
        self.window.geometry("750x750")
        self.window.minsize(700, 650)
        self.window.resizable(True, True)
        self.window.configure(bg='#1e1e1e')

        self.window.grab_set()
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)

        self.hotkey_capture_manager = HotkeyCaptureManager(self.window, self.settings, self.app)

        try:
            import ctypes
            from ctypes import wintypes

            hwnd = int(self.window.winfo_id())

            GWL_STYLE = -16
            WS_MAXIMIZEBOX = 0x00010000
            WS_MINIMIZEBOX = 0x00020000
            WS_SYSMENU = 0x00080000
            WS_CAPTION = 0x00C00000
            WS_THICKFRAME = 0x00040000

            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)
            new_style = style | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_SYSMENU | WS_CAPTION | WS_THICKFRAME
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)

            SWP_FRAMECHANGED = 0x0020
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_NOZORDER = 0x0004
            ctypes.windll.user32.SetWindowPos(
                hwnd, 0, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED
            )

            self.logger = logging.getLogger(__name__)
            self.logger.info("Установлены стили окна с кнопкой максимизации")

        except Exception as e:
            try:
                self.window.attributes('-toolwindow', False)
                self.window.attributes('-topmost', False)
            except:
                pass

        self.window.withdraw()

        self.center_window()
        self.create_widgets()
        self.load_values()

        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def reset_settings(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        import logging
        logger = logging.getLogger(__name__)

        if self._is_reset_dialog_open:
            if self._reset_dialog and self._reset_dialog.winfo_exists():
                logger.info("[SETTINGS] Диалог сброса уже открыт, поднимаем наверх")
                self._reset_dialog.lift()
                self._reset_dialog.focus_force()
                return
            else:
                self._is_reset_dialog_open = False
                self._reset_dialog = None

        self._is_reset_dialog_open = True

        dialog = tk.Toplevel(self.window)
        dialog.title(self.get_string('settings_title'))
        dialog.geometry("500x200")
        dialog.minsize(450, 180)
        dialog.resizable(False, False)
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self.window)
        dialog.attributes('-topmost', True)
        dialog.grab_set()

        self._reset_dialog = dialog

        dialog.update_idletasks()
        parent_x = self.window.winfo_x()
        parent_y = self.window.winfo_y()
        parent_w = self.window.winfo_width()
        parent_h = self.window.winfo_height()
        dlg_w = dialog.winfo_width()
        dlg_h = dialog.winfo_height()
        x = parent_x + (parent_w - dlg_w) // 2
        y = parent_y + (parent_h - dlg_h) // 2
        dialog.geometry(f"+{x}+{y}")

        def on_dialog_close():
            self._is_reset_dialog_open = False
            self._reset_dialog = None
            if hasattr(self.app, 'set_actions_blocked'):
                self.app.set_actions_blocked(False)
            dialog.destroy()

        dialog.protocol("WM_DELETE_WINDOW", on_dialog_close)

        header_frame = tk.Frame(dialog, bg='#1e1e1e')
        header_frame.pack(fill=tk.X, padx=20, pady=(20, 5))

        tk.Label(
            header_frame,
            text="⚠️",
            bg='#1e1e1e',
            fg='#ff9800',
            font=('Segoe UI', 24)
        ).pack(pady=(0, 5))

        tk.Label(
            header_frame,
            text=self.get_string('settings_reset_confirm'),
            bg='#1e1e1e',
            fg='white',
            font=('Segoe UI', 12)
        ).pack()

        btn_frame = tk.Frame(dialog, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=20, pady=(20, 20))

        def on_confirm():
            self._is_reset_dialog_open = False
            self._reset_dialog = None
            if hasattr(self.app, 'set_actions_blocked'):
                self.app.set_actions_blocked(False)
            dialog.destroy()
            self._do_reset()

        def on_cancel():
            self._is_reset_dialog_open = False
            self._reset_dialog = None
            if hasattr(self.app, 'set_actions_blocked'):
                self.app.set_actions_blocked(False)
            dialog.destroy()

        confirm_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_reset'),
            command=on_confirm,
            bg='#d32f2f',
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor='hand2'
        )
        confirm_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))

        cancel_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_cancel'),
            command=on_cancel,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 10),
            relief=tk.FLAT,
            padx=20,
            pady=8,
            cursor='hand2'
        )
        cancel_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        dialog.focus_force()
        confirm_btn.focus_set()
        dialog.bind('<Escape>', lambda e: on_cancel())
        dialog.bind('<Return>', lambda e: on_confirm())

    def save_settings(self):
        """Сохраняет настройки."""
        logger = logging.getLogger(__name__)

        for action in self.hotkey_capture_manager.hotkey_capturing:
            if self.hotkey_capture_manager.hotkey_capturing[action]:
                self.hotkey_capture_manager.hotkey_capturing[action] = False
                self.hotkey_capture_manager.hotkey_buttons[action].config(
                    bg='#2d2d2d',
                    text=self.hotkey_capture_manager.hotkey_vars[action].get().upper() or "—"
                )
                self.window.unbind_all('<Key>')
                self.window.unbind_all('<Escape>')
                if hasattr(self, 'app') and hasattr(self.app, 'set_actions_blocked'):
                    self.app.set_actions_blocked(False)
                break

        old_browser_path = self.settings.get_browser_path()
        new_browser_path = self.browser_path_var.get().strip()

        if new_browser_path and not os.path.exists(new_browser_path):
            messagebox.showerror(
                "Ошибка",
                "Указанный файл не существует!\nПроверьте путь."
            )
            return

        self.settings.set_browser_path(new_browser_path)
        self.settings.set_show_translation_indicator(self.show_indicator_var.get())
        self.settings.set_auto_hide_overlay(self.auto_hide_var.get())
        self.settings.set_auto_windowed_fullscreen(self.auto_windowed_fullscreen_var.get())
        self.settings.set_auto_replace_translated(self.auto_replace_translated_var.get())
        self.settings.set_confidence_threshold(self.confidence_var.get())
        self.settings.set_monitor_delay(self.monitor_delay_var.get())

        edit_mode = self.edit_mode_var.get()
        self.settings.set_edit_mode_enabled(edit_mode)

        if hasattr(self, 'hotkey_capture_manager'):
            for action, var in self.hotkey_capture_manager.hotkey_vars.items():
                key = var.get().strip()
                if key:
                    self.settings.set_hotkey(action, key)

        self.settings.save()

        if hasattr(self, 'app') and hasattr(self.app, 'translation_monitor'):
            monitor = self.app.translation_monitor
            if monitor:
                monitor.set_confidence(self.confidence_var.get())
                monitor.set_delay(self.monitor_delay_var.get())

                if self.auto_replace_translated_var.get() and monitor.templates:
                    if not monitor.is_running():
                        monitor.start()
                else:
                    if monitor.is_running():
                        monitor.stop()

        browser_path_changed = (old_browser_path != new_browser_path)
        if browser_path_changed:
            logger.info(f"[SETTINGS] Путь к браузеру изменен: {old_browser_path} -> {new_browser_path}")
            if hasattr(self.app, 'ready') and self.app.ready:
                logger.info("[SETTINGS] Браузер активен, выполняем перезапуск...")
                if hasattr(self.app, 'update_status'):
                    self.app.update_status("● " + self.app.get_string('starting_browser'), '#ff9800')
                if hasattr(self.app, '_restart_translator'):
                    self.app._restart_translator()
            else:
                logger.info("[SETTINGS] Браузер не активен, перезапуск не требуется")
                if hasattr(self.app, 'update_status'):
                    self.app.update_status("● Настройки сохранены", '#4CAF50')

        if hasattr(self, 'app') and hasattr(self.app, '_edit_mode_enabled'):
            self.app._edit_mode_enabled = edit_mode
            if hasattr(self.app, 'btn_edit_mode'):
                status_text = "ВКЛЮЧЕН" if edit_mode else "ВЫКЛЮЧЕН"
                self.app.btn_edit_mode.config(
                    text=f"✏️ Редактирование: {status_text} (F5)",
                    bg='#4CAF50' if edit_mode else '#ff9800'
                )
            self.app.logger.info(f"Режим редактирования из настроек: {edit_mode}")

        if hasattr(self, 'app') and hasattr(self.app, 'setup_hotkeys'):
            self.app.setup_hotkeys()

        if hasattr(self, 'app') and hasattr(self.app, 'update_hotkey_buttons'):
            self.app.update_hotkey_buttons()

        if self.on_settings_changed:
            self.on_settings_changed()

        if hasattr(self.app, 'set_actions_blocked'):
            self.app.set_actions_blocked(False)

        self.window.destroy()

    def on_close(self):
        """Закрывает окно настроек и разблокирует выполнение хоткеев"""
        if hasattr(self.app, 'set_actions_blocked'):
            self.app.set_actions_blocked(False)
        try:
            self.window.destroy()
        except:
            pass

    def _do_reset(self):
        """Реальная логика сброса настроек"""
        import logging
        logger = logging.getLogger(__name__)

        from src.settings import Settings

        current_lang = self.settings.get_language()
        current_show_browser = self.settings.get_show_browser()
        logger.info(f"[SETTINGS] Текущий язык: {current_lang}, show_browser: {current_show_browser}")

        for key, value in Settings.DEFAULT_SETTINGS.items():
            self.settings.set(key, value)

        self.settings.set_language(current_lang)
        self.settings.set_show_browser(current_show_browser)
        logger.info(f"[SETTINGS] Восстановлены: язык={current_lang}, show_browser={current_show_browser}")

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

        self.settings.save()
        self.load_values()

        if hasattr(self, 'show_indicator_var'):
            self.show_indicator_var.set(self.settings.get_show_translation_indicator())
        if hasattr(self, 'auto_hide_var'):
            self.auto_hide_var.set(self.settings.get_auto_hide_overlay())
        if hasattr(self, 'edit_mode_var'):
            self.edit_mode_var.set(self.settings.get_edit_mode_enabled())

        if hasattr(self, 'hotkey_capture_manager'):
            for action, var in self.hotkey_capture_manager.hotkey_vars.items():
                default_key = default_hotkeys.get(action, "")
                var.set(default_key)
                if action in self.hotkey_capture_manager.hotkey_buttons:
                    self.hotkey_capture_manager.hotkey_buttons[action].config(
                        text=default_key.upper() if default_key else "—"
                    )

        if hasattr(self, 'app') and hasattr(self.app, '_edit_mode_enabled'):
            edit_mode = self.settings.get_edit_mode_enabled()
            self.app._edit_mode_enabled = edit_mode
            if hasattr(self.app, 'btn_edit_mode'):
                status_text = "ВКЛЮЧЕН" if edit_mode else "ВЫКЛЮЧЕН"
                self.app.btn_edit_mode.config(
                    text=f"✏️ Редактирование: {status_text} (F5)",
                    bg='#4CAF50' if edit_mode else '#ff9800'
                )

        if hasattr(self, 'app') and hasattr(self.app, 'setup_hotkeys'):
            self.app.setup_hotkeys()

        if hasattr(self, 'app') and hasattr(self.app, 'update_hotkey_buttons'):
            self.app.update_hotkey_buttons()

        if hasattr(self, 'app') and hasattr(self.app, 'update_ui_language'):
            self.app.update_ui_language()

        if hasattr(self, 'app'):
            if hasattr(self.app, 'ready') and self.app.ready:
                logger.info("[SETTINGS] Сброс настроек, перезапуск браузера...")
                if hasattr(self.app, 'update_status'):
                    self.app.update_status("● " + self.app.get_string('starting_browser'), '#ff9800')
                if hasattr(self.app, '_restart_translator'):
                    self.app._restart_translator()
            else:
                if hasattr(self.app, 'update_status'):
                    self.app.update_status("● " + self.app.get_string('ready'), '#4CAF50')

        if self.on_settings_changed:
            self.on_settings_changed()

        self.window.destroy()

    def create_widgets(self):
        main_container = tk.Frame(self.window, bg='#1e1e1e')
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=15)

        title = tk.Label(main_container, text=self.get_string('settings_title'),
                         font=('Segoe UI', 16, 'bold'), bg='#1e1e1e', fg='white')
        title.pack(pady=(0, 15))

        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background='#1e1e1e', borderwidth=0)
        style.configure('TNotebook.Tab', background='#2d2d2d', foreground='#cccccc',
                        padding=[12, 6], font=('Segoe UI', 10))
        style.map('TNotebook.Tab', background=[('selected', '#3c3c3c')],
                  foreground=[('selected', 'white')])

        notebook = ttk.Notebook(main_container)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 12))

        # Вкладка 1: Браузер
        browser_frame = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(browser_frame, text="  🌐 " + self.get_string('settings_browser_section'))

        browser_inner = tk.Frame(browser_frame, bg='#1e1e1e')
        browser_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

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
            elif 'Opera' in current_path:
                browser_name = "Opera"
            elif 'Edge' in current_path or 'Microsoft' in current_path:
                browser_name = "Microsoft Edge"
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
            browser_inner,
            text=status_text,
            bg='#1e1e1e',
            fg=status_color,
            font=('Segoe UI', 10, 'bold'),
            anchor='w'
        )
        status_label.pack(anchor=tk.W, pady=(0, 8), fill=tk.X)

        path_frame = tk.Frame(browser_inner, bg='#1e1e1e')
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
            font=('Segoe UI', 9),
            relief=tk.FLAT
        )
        self.browser_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=3)

        browse_btn = tk.Button(
            path_entry_frame,
            text=self.get_string('settings_browser_browse'),
            command=self.browse_browser,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 9),
            relief=tk.FLAT,
            padx=8,
            pady=5,
            cursor='hand2',
            width=8
        )
        browse_btn.pack(side=tk.RIGHT, padx=(0, 5))

        find_btn = tk.Button(
            path_entry_frame,
            text="🔍 Найти",
            command=self.find_chromium_browsers,
            bg='#2196F3',
            fg='white',
            font=('Segoe UI', 9, 'bold'),
            relief=tk.FLAT,
            padx=8,
            pady=5,
            cursor='hand2',
            width=6
        )
        find_btn.pack(side=tk.RIGHT)

        self._add_tooltip(find_btn, "Найти все установленные Chromium-браузеры")

        tk.Label(
            browser_inner,
            text=self.get_string('settings_browser_path_hint'),
            bg='#1e1e1e',
            fg='#666666',
            font=('Segoe UI', 8),
            wraplength=480,
            anchor='w',
            justify='left'
        ).pack(anchor=tk.W, pady=(5, 0), fill=tk.X)

        # Вкладка 2: Интерфейс
        ui_frame = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(ui_frame, text="  🎨 " + self.get_string('settings_ui'))

        ui_inner = tk.Frame(ui_frame, bg='#1e1e1e')
        ui_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.show_indicator_var = tk.BooleanVar(value=self.settings.get_show_translation_indicator())
        indicator_cb = tk.Checkbutton(
            ui_inner,
            text=self.get_string('show_translation_indicator'),
            variable=self.show_indicator_var,
            bg='#1e1e1e',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Segoe UI', 10),
            padx=5,
            pady=4
        )
        indicator_cb.pack(anchor=tk.W, pady=4)

        self.auto_hide_var = tk.BooleanVar(value=self.settings.get_auto_hide_overlay())
        auto_hide_cb = tk.Checkbutton(
            ui_inner,
            text=self.get_string('auto_hide_overlay'),
            variable=self.auto_hide_var,
            bg='#1e1e1e',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Segoe UI', 10),
            padx=5,
            pady=4
        )
        auto_hide_cb.pack(anchor=tk.W, pady=4)

        self.auto_windowed_fullscreen_var = tk.BooleanVar(value=self.settings.get_auto_windowed_fullscreen())
        auto_fullscreen_cb = tk.Checkbutton(
            ui_inner,
            text=self.get_string('auto_windowed_fullscreen'),
            variable=self.auto_windowed_fullscreen_var,
            bg='#1e1e1e',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Segoe UI', 10),
            padx=5,
            pady=4
        )
        auto_fullscreen_cb.pack(anchor=tk.W, pady=4)

        self.auto_replace_translated_var = tk.BooleanVar(value=self.settings.get_auto_replace_translated())
        auto_replace_cb = tk.Checkbutton(
            ui_inner,
            text=self.get_string('auto_replace_translated'),
            variable=self.auto_replace_translated_var,
            bg='#1e1e1e',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Segoe UI', 10),
            padx=5,
            pady=4
        )
        auto_replace_cb.pack(anchor=tk.W, pady=4)
        self._add_tooltip(auto_replace_cb, self.get_string('auto_replace_translated_tooltip'))

        self.edit_mode_var = tk.BooleanVar(value=self.settings.get_edit_mode_enabled())
        edit_mode_cb = tk.Checkbutton(
            ui_inner,
            text=self.get_string('edit_mode'),
            variable=self.edit_mode_var,
            bg='#1e1e1e',
            fg='white',
            selectcolor='#1e1e1e',
            font=('Segoe UI', 10),
            padx=5,
            pady=4
        )
        edit_mode_cb.pack(anchor=tk.W, pady=4)
        self._add_tooltip(edit_mode_cb, self.get_string('edit_mode_tooltip'))

        # Вкладка 3: Мониторинг
        monitor_frame = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(monitor_frame, text="  🔍 " + self.get_string('settings_monitor'))

        monitor_inner = tk.Frame(monitor_frame, bg='#1e1e1e')
        monitor_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(
            monitor_inner,
            text=self.get_string('settings_confidence'),
            bg='#1e1e1e',
            fg='#cccccc',
            font=('Segoe UI', 10),
            anchor='w'
        ).pack(anchor=tk.W, pady=(0, 3))

        self.confidence_var = tk.DoubleVar(value=self.settings.get_confidence_threshold())
        confidence_scale = tk.Scale(
            monitor_inner,
            from_=0.5, to=1.0, resolution=0.01,
            orient=tk.HORIZONTAL,
            variable=self.confidence_var,
            bg='#3c3c3c',
            fg='white',
            highlightthickness=0,
            width=16,
            length=300
        )
        confidence_scale.pack(fill=tk.X, pady=(0, 8))

        confidence_label = tk.Label(
            monitor_inner,
            text=f"{self.confidence_var.get() * 100:.0f}%",
            bg='#1e1e1e',
            fg='#4CAF50',
            font=('Segoe UI', 11, 'bold')
        )
        confidence_label.pack(anchor=tk.W, pady=(0, 8))

        def update_confidence_label(val):
            confidence_label.config(text=f"{float(val) * 100:.0f}%")

        confidence_scale.configure(command=update_confidence_label)

        tk.Label(
            monitor_inner,
            text=self.get_string('settings_monitor_delay'),
            bg='#1e1e1e',
            fg='#cccccc',
            font=('Segoe UI', 10),
            anchor='w'
        ).pack(anchor=tk.W, pady=(8, 3))

        self.monitor_delay_var = tk.DoubleVar(value=self.settings.get_monitor_delay())
        delay_scale = tk.Scale(
            monitor_inner,
            from_=0.1, to=2.0, resolution=0.05,
            orient=tk.HORIZONTAL,
            variable=self.monitor_delay_var,
            bg='#3c3c3c',
            fg='white',
            highlightthickness=0,
            width=16,
            length=300
        )
        delay_scale.pack(fill=tk.X, pady=(0, 8))

        delay_label = tk.Label(
            monitor_inner,
            text=f"{self.monitor_delay_var.get():.2f} сек",
            bg='#1e1e1e',
            fg='#4CAF50',
            font=('Segoe UI', 11, 'bold')
        )
        delay_label.pack(anchor=tk.W, pady=(0, 8))

        def update_delay_label(val):
            delay_label.config(text=f"{float(val):.2f} сек")

        delay_scale.configure(command=update_delay_label)

        # Вкладка 4: Горячие клавиши
        hotkey_frame = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(hotkey_frame, text="  ⌨️ " + self.get_string('settings_hotkeys'))

        hotkey_inner = tk.Frame(hotkey_frame, bg='#1e1e1e')
        hotkey_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        tk.Label(
            hotkey_inner,
            text=self.get_string('settings_hotkeys_click_to_change'),
            bg='#1e1e1e',
            fg='#888888',
            font=('Segoe UI', 9),
            anchor='w'
        ).pack(anchor=tk.W, pady=(0, 10))

        hotkey_actions = [
            ("screenshot", "settings_hotkeys_action_screenshot"),
            ("area", "settings_hotkeys_action_area"),
            ("toggle_overlay", "settings_hotkeys_action_toggle_overlay"),
            ("clear_all", "settings_hotkeys_action_clear_all"),
            ("edit_mode", "settings_hotkeys_action_edit_mode"),
            ("auto_replace", "settings_hotkeys_action_auto_replace"),
        ]

        for action, label_key in hotkey_actions:
            row_frame = tk.Frame(hotkey_inner, bg='#1e1e1e')
            row_frame.pack(fill=tk.X, pady=3)

            label = tk.Label(
                row_frame,
                text=self.get_string(label_key) + ":",
                bg='#1e1e1e',
                fg='#cccccc',
                font=('Segoe UI', 10),
                width=22,
                anchor='w'
            )
            label.pack(side=tk.LEFT)

            current_key = self.settings.get_hotkey(action)
            display_key = current_key.upper() if current_key else "—"

            btn = tk.Button(
                row_frame,
                text=display_key,
                command=lambda a=action: self.hotkey_capture_manager.start_hotkey_capture(a),
                bg='#2d2d2d',
                fg='white',
                font=('Segoe UI', 9, 'bold'),
                relief=tk.FLAT,
                padx=14,
                pady=4,
                cursor='hand2',
                width=12
            )
            btn.pack(side=tk.RIGHT)

            self.hotkey_capture_manager.hotkey_buttons[action] = btn
            self.hotkey_capture_manager.hotkey_vars[action] = tk.StringVar(value=current_key)
            self.hotkey_capture_manager.hotkey_capturing[action] = False

            self._add_tooltip(btn, self.get_string('settings_hotkeys_click_to_change'))

        # Кнопки внизу
        btn_frame = tk.Frame(main_container, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, pady=(8, 0))

        save_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_save'),
            command=self.save_settings,
            bg='#4CAF50',
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            relief=tk.FLAT,
            height=1,
            pady=10,
            cursor='hand2'
        )
        save_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 4), ipady=1)

        reset_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_reset'),
            command=self.reset_settings,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 10),
            relief=tk.FLAT,
            height=1,
            pady=10,
            cursor='hand2'
        )
        reset_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 4), ipady=1)

        cancel_btn = tk.Button(
            btn_frame,
            text=self.get_string('settings_cancel'),
            command=self.window.destroy,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 10),
            relief=tk.FLAT,
            height=1,
            pady=10,
            cursor='hand2'
        )
        cancel_btn.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(4, 0), ipady=1)

        self.window.bind('<Escape>', lambda e: self.hotkey_capture_manager._cancel_hotkey_capture())

    def find_chromium_browsers(self):
        """Находит установленные Яндекс Браузер и Google Chrome, показывает список для выбора."""
        logger = logging.getLogger(__name__)
        logger.info("=" * 70)
        logger.info("[BROWSER_FIND] ===== НАЧАЛО ПОИСКА БРАУЗЕРОВ =====")
        logger.info("[BROWSER_FIND] Поиск Яндекс Браузера и Google Chrome...")

        found_browsers = []

        # Поиск через реестр Windows
        logger.info("[BROWSER_FIND] --- Поиск в реестре Windows ---")
        try:
            import winreg

            yandex_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\browser.exe",
                 "Yandex Browser"),
                (winreg.HKEY_CURRENT_USER, r"Software\Yandex\YandexBrowser", "Yandex Browser"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Yandex\YandexBrowser", "Yandex Browser"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Yandex\YandexBrowser", "Yandex Browser"),
            ]

            for hkey, path, name in yandex_paths:
                try:
                    key = winreg.OpenKey(hkey, path, 0, winreg.KEY_READ)
                    try:
                        browser_path = None
                        try:
                            browser_path = winreg.QueryValueEx(key, "")[0]
                        except:
                            try:
                                install_dir = winreg.QueryValueEx(key, "InstallDir")[0]
                                browser_path = os.path.join(install_dir, "browser.exe")
                            except:
                                pass

                        if browser_path and os.path.exists(browser_path) and browser_path.endswith('.exe'):
                            found_browsers.append((name, browser_path))
                            logger.info(f"[BROWSER_FIND] Найден Yandex Browser: {browser_path}")
                    finally:
                        winreg.CloseKey(key)
                except WindowsError:
                    pass

            chrome_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                 "Google Chrome"),
            ]

            for hkey, path, name in chrome_paths:
                try:
                    key = winreg.OpenKey(hkey, path, 0, winreg.KEY_READ)
                    try:
                        browser_path = winreg.QueryValueEx(key, "")[0]
                        if browser_path and os.path.exists(browser_path) and browser_path.endswith('.exe'):
                            found_browsers.append((name, browser_path))
                            logger.info(f"[BROWSER_FIND] Найден Google Chrome: {browser_path}")
                    finally:
                        winreg.CloseKey(key)
                except WindowsError:
                    pass

            try:
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                                     0, winreg.KEY_READ)
                i = 0
                while True:
                    try:
                        subkey_name = winreg.EnumKey(key, i)
                        subkey = winreg.OpenKey(key, subkey_name)
                        try:
                            display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                            if "Google Chrome" in display_name:
                                try:
                                    install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                    if install_location:
                                        chrome_path = os.path.join(install_location, "chrome.exe")
                                        if os.path.exists(chrome_path):
                                            found_browsers.append(("Google Chrome", chrome_path))
                                            logger.info(
                                                f"[BROWSER_FIND] Найден Google Chrome (Uninstall): {chrome_path}")
                                except:
                                    pass
                        except:
                            pass
                        finally:
                            winreg.CloseKey(subkey)
                        i += 1
                    except WindowsError:
                        break
                winreg.CloseKey(key)
            except:
                pass

        except Exception as e:
            logger.error(f"[BROWSER_FIND] Ошибка поиска в реестре: {e}")

        # Поиск в стандартных путях
        logger.info("[BROWSER_FIND] --- Поиск в стандартных путях ---")
        standard_paths = [
            (r"C:\Program Files\Google\Chrome\Application\chrome.exe", "Google Chrome"),
            (r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe", "Google Chrome"),
            (r"C:\Program Files\Yandex\YandexBrowser\Application\browser.exe", "Yandex Browser"),
            (r"C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe", "Yandex Browser"),
        ]

        for path, name in standard_paths:
            if os.path.exists(path):
                if not any(browser_path == path for _, browser_path in found_browsers):
                    found_browsers.append((name, path))
                    logger.info(f"[BROWSER_FIND] Найден (стандартный путь): {name} -> {path}")

        # Поиск в пользовательских путях
        logger.info("[BROWSER_FIND] --- Поиск в пользовательских путях ---")
        try:
            local_app_data = os.environ.get('LOCALAPPDATA', '')
            if local_app_data:
                user_paths = [
                    (os.path.join(local_app_data, 'Google', 'Chrome', 'Application', 'chrome.exe'), "Google Chrome"),
                    (os.path.join(local_app_data, 'Yandex', 'YandexBrowser', 'Application', 'browser.exe'),
                     "Yandex Browser"),
                ]
                for path, name in user_paths:
                    if os.path.exists(path):
                        if not any(browser_path == path for _, browser_path in found_browsers):
                            found_browsers.append((name, path))
                            logger.info(f"[BROWSER_FIND] Найден (пользовательский путь): {name} -> {path}")
        except:
            pass

        logger.info(f"[BROWSER_FIND] Всего найдено браузеров: {len(found_browsers)}")

        if not found_browsers:
            logger.warning("[BROWSER_FIND] Браузеры не найдены!")
            messagebox.showinfo(
                self.get_string('browser_find_title'),
                self.get_string('browser_find_not_found') + "\n\n" +
                self.get_string('browser_find_install_hint') + "\n\n" +
                self.get_string('browser_find_not_found_recommend')
            )
            return

        unique_browsers = []
        seen_paths = set()
        for name, path in found_browsers:
            if path not in seen_paths:
                unique_browsers.append((name, path))
                seen_paths.add(path)

        logger.info(f"[BROWSER_FIND] Уникальных браузеров: {len(unique_browsers)}")
        for idx, (name, path) in enumerate(unique_browsers):
            logger.info(f"[BROWSER_FIND]   {idx + 1}. {name} -> {path}")

        dialog = tk.Toplevel(self.window)
        dialog.title(self.get_string('browser_find_title'))
        dialog.geometry("700x500")
        dialog.minsize(600, 450)
        dialog.resizable(True, True)
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self.window)
        dialog.grab_set()

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (dialog.winfo_screenheight() // 2) - (500 // 2)
        dialog.geometry(f"+{x}+{y}")

        tk.Label(
            dialog,
            text=self.get_string('browser_find_header'),
            bg='#1e1e1e',
            fg='white',
            font=('Segoe UI', 14, 'bold')
        ).pack(pady=(20, 5))

        recommend_frame = tk.Frame(dialog, bg='#3d2a00', bd=1, relief=tk.SOLID)
        recommend_frame.pack(fill=tk.X, padx=20, pady=(5, 10))

        tk.Label(
            recommend_frame,
            text=self.get_string('browser_find_recommend'),
            bg='#3d2a00',
            fg='#FFD700',
            font=('Segoe UI', 11),
            padx=10,
            pady=8
        ).pack(anchor=tk.W)

        tk.Label(
            dialog,
            text=self.get_string('browser_find_hint'),
            bg='#1e1e1e',
            fg='#888888',
            font=('Segoe UI', 10)
        ).pack(pady=(0, 10))

        listbox_frame = tk.Frame(dialog, bg='#1e1e1e')
        listbox_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=5)

        scrollbar = tk.Scrollbar(listbox_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        listbox = tk.Listbox(
            listbox_frame,
            bg='#2d2d2d',
            fg='white',
            font=('Consolas', 10),
            selectbackground='#2196F3',
            selectforeground='white',
            relief=tk.FLAT,
            yscrollcommand=scrollbar.set
        )
        listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=listbox.yview)

        for idx, (name, path) in enumerate(unique_browsers):
            display_text = f"{name}: {path}"
            listbox.insert(tk.END, display_text)
            if "Yandex" in name or "Яндекс" in name:
                listbox.itemconfig(idx, fg='#FFD700')
            logger.debug(f"[BROWSER_FIND] Добавлен в список: {display_text}")

        path_var = tk.StringVar()
        path_var.set(self.get_string('browser_find_path_label'))

        path_label = tk.Label(
            dialog,
            textvariable=path_var,
            bg='#1e1e1e',
            fg='#4CAF50',
            font=('Segoe UI', 10),
            wraplength=660,
            anchor='w',
            justify='left',
            pady=8
        )
        path_label.pack(fill=tk.X, padx=20, pady=(5, 5))

        def on_select(event):
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                if index < len(unique_browsers):
                    name, path = unique_browsers[index]
                    path_var.set(
                        self.get_string('browser_find_selected').format(name) + "\n" +
                        self.get_string('browser_find_path_prefix').format(path)
                    )
                    logger.info(f"[BROWSER_FIND] Выбран для просмотра: {name} -> {path}")
                else:
                    path_var.set(self.get_string('browser_find_path_label'))
            else:
                path_var.set(self.get_string('browser_find_path_label'))

        def on_double_click(event):
            logger.info("[BROWSER_FIND] Двойной клик по списку")
            select_browser()

        listbox.bind('<<ListboxSelect>>', on_select)
        listbox.bind('<Double-Button-1>', on_double_click)

        btn_frame = tk.Frame(dialog, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=20, pady=(5, 20))

        def select_browser():
            logger.info("[BROWSER_FIND] ===== ВЫБОР БРАУЗЕРА =====")
            selection = listbox.curselection()
            if not selection:
                logger.warning("[BROWSER_FIND] Браузер не выбран!")
                messagebox.showwarning(
                    self.get_string('browser_find_warning_title'),
                    self.get_string('browser_find_warning_message')
                )
                return

            index = selection[0]
            name, path = unique_browsers[index]
            logger.info(f"[BROWSER_FIND] Выбран браузер: {name}")
            logger.info(f"[BROWSER_FIND] Путь: {path}")

            self.browser_path_var.set(path)
            logger.info("[BROWSER_FIND] Путь установлен в поле ввода")

            status_updated = False
            for child in self.window.winfo_children():
                for subchild in child.winfo_children():
                    if isinstance(subchild, tk.Label) and hasattr(subchild, 'cget'):
                        try:
                            text = subchild.cget('text')
                            if 'Используется' in text or 'Using' in text:
                                status_text = self.get_string('settings_browser_using').format(name)
                                subchild.config(text=status_text, fg='#4CAF50')
                                logger.info(f"[BROWSER_FIND] Статус обновлен: {status_text}")
                                status_updated = True
                                break
                        except:
                            pass
                if status_updated:
                    break

            if not status_updated:
                logger.warning(
                    "[BROWSER_FIND] Не удалось обновить статус через поиск, обновляем через прямое обращение")
                try:
                    for widget in self.window.winfo_children():
                        if hasattr(widget, 'winfo_children'):
                            for child in widget.winfo_children():
                                if isinstance(child, tk.Label) and hasattr(child, 'cget'):
                                    try:
                                        text = child.cget('text')
                                        if 'Используется' in text or 'Using' in text:
                                            status_text = self.get_string('settings_browser_using').format(name)
                                            child.config(text=status_text, fg='#4CAF50')
                                            logger.info(
                                                f"[BROWSER_FIND] Статус обновлен (прямой доступ): {status_text}")
                                            break
                                    except:
                                        pass
                except Exception as e:
                    logger.error(f"[BROWSER_FIND] Ошибка обновления статуса: {e}")

            dialog.destroy()
            logger.info(f"[BROWSER_FIND] ===== ВЫБОР ЗАВЕРШЕН: {name} =====")

        def cancel_selection():
            logger.info("[BROWSER_FIND] Отмена выбора браузера")
            dialog.destroy()

        select_btn = tk.Button(
            btn_frame,
            text=self.get_string('browser_find_select'),
            command=select_browser,
            bg='#4CAF50',
            fg='white',
            font=('Segoe UI', 10, 'bold'),
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2'
        )
        select_btn.pack(side=tk.LEFT, padx=(0, 10), expand=True, fill=tk.X)

        cancel_btn = tk.Button(
            btn_frame,
            text=self.get_string('browser_find_cancel'),
            command=cancel_selection,
            bg='#3c3c3c',
            fg='white',
            font=('Segoe UI', 10),
            relief=tk.FLAT,
            padx=20,
            pady=10,
            cursor='hand2'
        )
        cancel_btn.pack(side=tk.LEFT, padx=(10, 0), expand=True, fill=tk.X)

        logger.info("[BROWSER_FIND] Диалог выбора браузера создан и отображен")
        dialog.focus_force()

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

    def get_string(self, key):
        return self.settings.get_string(key)

    def center_window(self):
        self.window.update_idletasks()
        width = self.window.winfo_width()
        height = self.window.winfo_height()
        x = (self.window.winfo_screenwidth() // 2) - (width // 2)
        y = (self.window.winfo_screenheight() // 2) - (height // 2)
        self.window.geometry(f'{width}x{height}+{x}+{y}')

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
        if hasattr(self, 'hotkey_capture_manager'):
            for action, var in self.hotkey_capture_manager.hotkey_vars.items():
                key = self.settings.get_hotkey(action)
                var.set(key)
                if action in self.hotkey_capture_manager.hotkey_buttons:
                    self.hotkey_capture_manager.hotkey_buttons[action].config(text=key.upper() if key else "—")

    def browse_browser(self):
        """Открывает диалог выбора файла браузера"""
        file_path = filedialog.askopenfilename(
            title="Выберите исполняемый файл браузера",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        if file_path:
            self.browser_path_var.set(file_path)
