"""
Модуль для окна настроек приложения
"""

"""
Модуль для окна настроек приложения
"""

import tkinter as tk
from tkinter import ttk
from tkinter import filedialog, messagebox
from pathlib import Path
import os
import logging  # <-- ДОБАВЛЯЕМ ИМПОРТ


class SettingsWindow:
    """Окно настроек программы"""

    def __init__(self, app_instance, settings, on_settings_changed):
        self.app = app_instance  # Сохраняем ссылку на экземпляр приложения
        self.parent = app_instance.root  # Родительское окно - главное окно приложения
        self.settings = settings
        self.on_settings_changed = on_settings_changed

        self.window = tk.Toplevel(self.parent)
        self.window.title(self.get_string('settings_title'))
        # Увеличиваем размер окна
        self.window.geometry("700x600")
        self.window.minsize(650, 550)
        self.window.resizable(True, True)
        self.window.configure(bg='#1e1e1e')

        # НЕ используем transient, чтобы окно было независимым
        # self.window.transient(self.parent)  # УБРАНО!
        self.window.grab_set()

        # Явно разрешаем максимизацию через системное меню
        try:
            import ctypes
            from ctypes import wintypes

            # Получаем HWND окна
            hwnd = int(self.window.winfo_id())

            # Константы Windows
            GWL_STYLE = -16
            WS_MAXIMIZEBOX = 0x00010000
            WS_MINIMIZEBOX = 0x00020000
            WS_SYSMENU = 0x00080000
            WS_CAPTION = 0x00C00000
            WS_THICKFRAME = 0x00040000

            # Получаем текущие стили окна
            style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_STYLE)

            # Добавляем все необходимые флаги для полноценного окна
            new_style = style | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_SYSMENU | WS_CAPTION | WS_THICKFRAME
            ctypes.windll.user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)

            # Обновляем окно, чтобы применить изменения
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
            # Если не удалось установить стиль, пробуем альтернативный метод
            try:
                # Альтернативный метод через tkinter
                self.window.attributes('-toolwindow', False)
                self.window.attributes('-topmost', False)

                # Принудительно показываем системное меню
                self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)
            except:
                pass

        # Скрываем окно до полной настройки
        self.window.withdraw()

        self.center_window()
        self.create_widgets()
        self.load_values()

        # Показываем окно после всех настроек
        self.window.deiconify()
        self.window.lift()
        self.window.focus_force()

    def save_settings(self):
        """Сохраняет настройки."""
        logger = logging.getLogger(__name__)

        # Проверяем, не идет ли захват клавиши
        for action in self.hotkey_capturing:
            if self.hotkey_capturing[action]:
                # Отменяем захват
                self.hotkey_capturing[action] = False
                self.hotkey_buttons[action].config(
                    bg='#2d2d2d',
                    text=self.hotkey_vars[action].get().upper() or "—"
                )
                self.window.unbind_all('<Key>')
                self.window.unbind_all('<Escape>')
                if hasattr(self, 'app') and hasattr(self.app, 'set_actions_blocked'):
                    self.app.set_actions_blocked(False)
                break

        # Сохраняем старый путь для сравнения
        old_browser_path = self.settings.get_browser_path()
        new_browser_path = self.browser_path_var.get().strip()

        if new_browser_path and not os.path.exists(new_browser_path):
            messagebox.showerror(
                "Ошибка",
                "Указанный файл не существует!\nПроверьте путь."
            )
            return

        # Сохраняем настройки
        self.settings.set_browser_path(new_browser_path)
        self.settings.set_show_translation_indicator(self.show_indicator_var.get())
        self.settings.set_auto_hide_overlay(self.auto_hide_var.get())
        self.settings.set_auto_windowed_fullscreen(self.auto_windowed_fullscreen_var.get())

        edit_mode = self.edit_mode_var.get()
        self.settings.set_edit_mode_enabled(edit_mode)

        # Сохраняем горячие клавиши
        if hasattr(self, 'hotkey_vars'):
            for action, var in self.hotkey_vars.items():
                key = var.get().strip()
                if key:
                    self.settings.set_hotkey(action, key)

        self.settings.save()

        # Проверяем, изменился ли путь к браузеру
        browser_path_changed = (old_browser_path != new_browser_path)
        if browser_path_changed:
            logger.info(f"[SETTINGS] Путь к браузеру изменен: {old_browser_path} -> {new_browser_path}")

            if hasattr(self.app, 'ready') and self.app.ready:
                logger.info("[SETTINGS] Браузер активен, выполняем перезапуск...")
                if hasattr(self.app, 'update_status'):
                    self.app.update_status("● " + self.app.get_string('starting_browser'), '#ff9800')
                    logger.info("[SETTINGS] Статус обновлен: Запуск браузера...")
                if hasattr(self.app, '_restart_translator'):
                    self.app._restart_translator()
                    logger.info("[SETTINGS] Перезапуск браузера инициирован")
                else:
                    logger.warning("[SETTINGS] Метод _restart_translator не найден")
                    if hasattr(self.app, 'update_status'):
                        self.app.update_status("● Ошибка: браузер не перезапущен", '#f44336')
            else:
                logger.info("[SETTINGS] Браузер не активен, перезапуск не требуется")
                if hasattr(self.app, 'update_status'):
                    self.app.update_status("● Настройки сохранены", '#4CAF50')

        # Обновляем состояние режима редактирования (без статуса)
        if hasattr(self, 'app') and hasattr(self.app, '_edit_mode_enabled'):
            self.app._edit_mode_enabled = edit_mode
            if hasattr(self.app, 'btn_edit_mode'):
                status_text = "ВКЛЮЧЕН" if edit_mode else "ВЫКЛЮЧЕН"
                self.app.btn_edit_mode.config(
                    text=f"✏️ Редактирование: {status_text} (F5)",
                    bg='#4CAF50' if edit_mode else '#ff9800'
                )
            # Убираем обновление статуса о режиме редактирования
            # if hasattr(self.app, 'update_status'):
            #     status_text = "ВКЛЮЧЕН" if edit_mode else "ВЫКЛЮЧЕН"
            #     status_color = '#4CAF50' if edit_mode else '#ff9800'
            #     self.app.update_status(f"● Режим редактирования: {status_text}", status_color)
            self.app.logger.info(f"Режим редактирования из настроек: {edit_mode}")

        # Перерегистрируем горячие клавиши (всегда)
        if hasattr(self, 'app') and hasattr(self.app, 'setup_hotkeys'):
            self.app.setup_hotkeys()

        # Показываем сообщение
        if not browser_path_changed:
            messagebox.showinfo(
                self.get_string('settings_title'),
                self.get_string('settings_saved')
            )
        else:
            messagebox.showinfo(
                self.get_string('settings_title'),
                self.get_string(
                    'settings_saved') + "\n\n🔄 Браузер перезапускается...\nСтатус будет обновлен автоматически."
            )

        if self.on_settings_changed:
            self.on_settings_changed()

        self.window.destroy()

    def find_chromium_browsers(self):
        """Находит установленные Яндекс Браузер и Google Chrome, показывает список для выбора."""
        logger = logging.getLogger(__name__)
        logger.info("=" * 70)
        logger.info("[BROWSER_FIND] ===== НАЧАЛО ПОИСКА БРАУЗЕРОВ =====")
        logger.info("[BROWSER_FIND] Поиск Яндекс Браузера и Google Chrome...")

        found_browsers = []

        # --- 1. ПОИСК ЧЕРЕЗ РЕЕСТР WINDOWS ---
        logger.info("[BROWSER_FIND] --- Поиск в реестре Windows ---")
        try:
            import winreg

            # Поиск Яндекс Браузера
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

            # Поиск Google Chrome
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

            # Поиск Chrome через Uninstall
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

        # --- 2. ПОИСК В СТАНДАРТНЫХ ПУТЯХ ---
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

        # --- 3. ПОИСК В ПОЛЬЗОВАТЕЛЬСКИХ ПУТЯХ (LOCALAPPDATA) ---
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

        # --- ПОКАЗЫВАЕМ РЕЗУЛЬТАТЫ ---
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

        # Удаляем дубликаты (по пути)
        unique_browsers = []
        seen_paths = set()
        for name, path in found_browsers:
            if path not in seen_paths:
                unique_browsers.append((name, path))
                seen_paths.add(path)

        logger.info(f"[BROWSER_FIND] Уникальных браузеров: {len(unique_browsers)}")
        for idx, (name, path) in enumerate(unique_browsers):
            logger.info(f"[BROWSER_FIND]   {idx + 1}. {name} -> {path}")

        # Создаем диалог выбора
        dialog = tk.Toplevel(self.window)
        dialog.title(self.get_string('browser_find_title'))
        dialog.geometry("700x500")
        dialog.minsize(600, 450)
        dialog.resizable(True, True)
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self.window)
        dialog.grab_set()

        # Центрируем окно
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (700 // 2)
        y = (dialog.winfo_screenheight() // 2) - (500 // 2)
        dialog.geometry(f"+{x}+{y}")

        # Заголовок
        tk.Label(
            dialog,
            text=self.get_string('browser_find_header'),
            bg='#1e1e1e',
            fg='white',
            font=('Segoe UI', 14, 'bold')
        ).pack(pady=(20, 5))

        # Рекомендация - ОРАНЖЕВЫЙ БЛОК
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

        # Подсказка
        tk.Label(
            dialog,
            text=self.get_string('browser_find_hint'),
            bg='#1e1e1e',
            fg='#888888',
            font=('Segoe UI', 10)
        ).pack(pady=(0, 10))

        # Список браузеров с отображением путей
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

        # Заполняем список с отображением путей
        for idx, (name, path) in enumerate(unique_browsers):
            display_text = f"{name}: {path}"
            listbox.insert(tk.END, display_text)
            # Если это Яндекс Браузер - выделяем его в списке
            if "Yandex" in name or "Яндекс" in name:
                listbox.itemconfig(idx, fg='#FFD700')
            logger.debug(f"[BROWSER_FIND] Добавлен в список: {display_text}")

        # Метка для отображения выбранного пути внизу
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
            """Обработчик одиночного клика по элементу списка - показывает путь внизу."""
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
            """Обработчик двойного клика - сразу выбирает браузер."""
            logger.info("[BROWSER_FIND] Двойной клик по списку")
            select_browser()

        # Привязываем события
        listbox.bind('<<ListboxSelect>>', on_select)
        listbox.bind('<Double-Button-1>', on_double_click)

        # --- КНОПКИ ---
        btn_frame = tk.Frame(dialog, bg='#1e1e1e')
        btn_frame.pack(fill=tk.X, padx=20, pady=(5, 20))

        def select_browser():
            """Выбирает браузер из списка"""
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

            # Устанавливаем путь
            self.browser_path_var.set(path)
            logger.info("[BROWSER_FIND] Путь установлен в поле ввода")

            # Обновляем статус в главном окне
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

            # Если статус не обновился, обновляем через прямое обращение
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
            """Отменяет выбор браузера"""
            logger.info("[BROWSER_FIND] Отмена выбора браузера")
            dialog.destroy()

        # Кнопка "Выбрать"
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

        # Кнопка "Отмена"
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

    def create_widgets(self):
        main_container = tk.Frame(self.window, bg='#1e1e1e')
        main_container.pack(fill=tk.BOTH, expand=True, padx=25, pady=20)

        title = tk.Label(main_container, text=self.get_string('settings_title'),
                         font=('Segoe UI', 18, 'bold'), bg='#1e1e1e', fg='white')
        title.pack(pady=(0, 20))

        # --- СОЗДАЕМ ВКЛАДКИ (NOTEBOOK) ---
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TNotebook', background='#1e1e1e', borderwidth=0)
        style.configure('TNotebook.Tab', background='#2d2d2d', foreground='#cccccc',
                        padding=[15, 8], font=('Segoe UI', 11))
        style.map('TNotebook.Tab', background=[('selected', '#3c3c3c')],
                  foreground=[('selected', 'white')])

        notebook = ttk.Notebook(main_container)
        notebook.pack(fill=tk.BOTH, expand=True, pady=(0, 15))

        # --- ВКЛАДКА 1: БРАУЗЕР ---
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
            font=('Segoe UI', 11, 'bold'),
            anchor='w'
        )
        status_label.pack(anchor=tk.W, pady=(0, 10), fill=tk.X)

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
            font=('Segoe UI', 10),
            relief=tk.FLAT
        )
        self.browser_path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5), ipady=4)

        # Кнопка "Обзор"
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
        browse_btn.pack(side=tk.RIGHT, padx=(0, 5))

        # НОВАЯ КНОПКА "Найти браузеры"
        find_btn = tk.Button(
            path_entry_frame,
            text="🔍 Найти",
            command=self.find_chromium_browsers,
            bg='#2196F3',
            fg='white',
            font=('Segoe UI', 9, 'bold'),
            relief=tk.FLAT,
            padx=10,
            pady=6,
            cursor='hand2',
            width=8
        )
        find_btn.pack(side=tk.RIGHT)

        # Подсказка для кнопки
        self._add_tooltip(find_btn, "Найти все установленные Chromium-браузеры")

        tk.Label(
            browser_inner,
            text=self.get_string('settings_browser_path_hint'),
            bg='#1e1e1e',
            fg='#666666',
            font=('Segoe UI', 9),
            wraplength=480,
            anchor='w',
            justify='left'
        ).pack(anchor=tk.W, pady=(5, 0), fill=tk.X)

        # --- ВКЛАДКА 2: ИНТЕРФЕЙС ---
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
            font=('Segoe UI', 11),
            padx=5,
            pady=5
        )
        indicator_cb.pack(anchor=tk.W, pady=6)

        self.auto_hide_var = tk.BooleanVar(value=self.settings.get_auto_hide_overlay())
        auto_hide_cb = tk.Checkbutton(
            ui_inner,
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
            ui_inner,
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

        self.edit_mode_var = tk.BooleanVar(value=self.settings.get_edit_mode_enabled())
        edit_mode_cb = tk.Checkbutton(
            ui_inner,
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
        self._add_tooltip(edit_mode_cb, self.get_string('edit_mode_tooltip'))

        # --- ВКЛАДКА 3: ГОРЯЧИЕ КЛАВИШИ ---
        hotkey_frame = tk.Frame(notebook, bg='#1e1e1e')
        notebook.add(hotkey_frame, text="  ⌨️ " + self.get_string('settings_hotkeys'))

        hotkey_inner = tk.Frame(hotkey_frame, bg='#1e1e1e')
        hotkey_inner.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Информационная метка
        tk.Label(
            hotkey_inner,
            text=self.get_string('settings_hotkeys_click_to_change'),
            bg='#1e1e1e',
            fg='#888888',
            font=('Segoe UI', 10),
            anchor='w'
        ).pack(anchor=tk.W, pady=(0, 15))

        self.hotkey_vars = {}
        self.hotkey_buttons = {}
        self.hotkey_capturing = {}

        hotkey_actions = [
            ("screenshot", "settings_hotkeys_action_screenshot"),
            ("area", "settings_hotkeys_action_area"),
            ("toggle_overlay", "settings_hotkeys_action_toggle_overlay"),
            ("clear_all", "settings_hotkeys_action_clear_all"),
            ("edit_mode", "settings_hotkeys_action_edit_mode"),
        ]

        for action, label_key in hotkey_actions:
            row_frame = tk.Frame(hotkey_inner, bg='#1e1e1e')
            row_frame.pack(fill=tk.X, pady=5)

            label = tk.Label(
                row_frame,
                text=self.get_string(label_key) + ":",
                bg='#1e1e1e',
                fg='#cccccc',
                font=('Segoe UI', 11),
                width=25,
                anchor='w'
            )
            label.pack(side=tk.LEFT)

            current_key = self.settings.get_hotkey(action)
            display_key = current_key.upper() if current_key else "—"

            btn = tk.Button(
                row_frame,
                text=display_key,
                command=lambda a=action: self._start_hotkey_capture(a),
                bg='#2d2d2d',
                fg='white',
                font=('Segoe UI', 10, 'bold'),
                relief=tk.FLAT,
                padx=20,
                pady=5,
                cursor='hand2',
                width=14
            )
            btn.pack(side=tk.RIGHT)

            self.hotkey_buttons[action] = btn
            self.hotkey_vars[action] = tk.StringVar(value=current_key)
            self.hotkey_capturing[action] = False

            self._add_tooltip(btn, self.get_string('settings_hotkeys_click_to_change'))

        # --- КНОПКИ ВНИЗУ ---
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

        self.window.bind('<Escape>', lambda e: self._cancel_hotkey_capture())

    def reset_settings(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        if messagebox.askyesno(self.get_string('settings_title'), self.get_string('settings_reset_confirm')):
            from src.settings import Settings

            # Сбрасываем все настройки к значениям по умолчанию
            for key, value in Settings.DEFAULT_SETTINGS.items():
                self.settings.set(key, value)

            # Сбрасываем горячие клавиши к значениям по умолчанию
            default_hotkeys = {
                "screenshot": "f2",
                "area": "f3",
                "toggle_overlay": "f1",
                "clear_all": "f4",
                "edit_mode": "f5"
            }
            for action, default_key in default_hotkeys.items():
                self.settings.set_hotkey(action, default_key)

            self.settings.save()

            # Загружаем значения в интерфейс
            self.load_values()

            # Обновляем переменные для новых настроек
            if hasattr(self, 'show_indicator_var'):
                self.show_indicator_var.set(self.settings.get_show_translation_indicator())
            if hasattr(self, 'auto_hide_var'):
                self.auto_hide_var.set(self.settings.get_auto_hide_overlay())
            if hasattr(self, 'edit_mode_var'):
                self.edit_mode_var.set(self.settings.get_edit_mode_enabled())
            if hasattr(self, 'hotkey_vars'):
                for action, var in self.hotkey_vars.items():
                    default_key = default_hotkeys.get(action, "")
                    var.set(default_key)
                    if action in self.hotkey_buttons:
                        self.hotkey_buttons[action].config(text=default_key.upper() if default_key else "—")

            # Перерегистрируем горячие клавиши в приложении
            if hasattr(self, 'app') and hasattr(self.app, 'setup_hotkeys'):
                self.app.setup_hotkeys()

            messagebox.showinfo(self.get_string('settings_title'), self.get_string('settings_reset_done'))

    def _on_hotkey_pressed(self, action, event):
        """Обработчик нажатия клавиши для переназначения."""
        logger = logging.getLogger(__name__)

        if not self.hotkey_capturing.get(action, False):
            return

        key = event.keysym.lower()
        logger.info(f"[HOTKEYS_SETTINGS] Нажата клавиша: {key} (действие: {action})")

        # Игнорируем клавиши-модификаторы
        if key in ['shift', 'control', 'alt', 'win', 'meta', 'super', 'hyper',
                   'alt_l', 'alt_r', 'control_l', 'control_r', 'shift_l', 'shift_r',
                   'caps_lock', 'num_lock', 'scroll_lock']:
            logger.debug(f"[HOTKEYS_SETTINGS] Игнорируем клавишу-модификатор: {key}")
            return

        # Игнорируем ESC (используется для отмены)
        if key == 'escape':
            logger.info(f"[HOTKEYS_SETTINGS] Нажат ESC - отменяем захват")
            self._cancel_hotkey_capture()
            return

        # Проверяем, не занята ли эта клавиша другим действием
        conflicting_action = None
        for a in self.hotkey_vars:
            if a != action and self.hotkey_vars[a].get() == key:
                conflicting_action = a
                logger.info(f"[HOTKEYS_SETTINGS] Клавиша '{key}' уже занята действием '{conflicting_action}'")
                break

        if conflicting_action is not None:
            # Меняем клавиши местами
            old_key = self.hotkey_vars[action].get()
            logger.info(f"[HOTKEYS_SETTINGS] Меняем местами: {action}={old_key} <-> {conflicting_action}={key}")

            # Назначаем новую клавишу текущему действию
            self.hotkey_vars[action].set(key)
            self.hotkey_buttons[action].config(text=key.upper(), bg='#4CAF50')

            # Назначаем старую клавишу конфликтующему действию
            if old_key:
                self.hotkey_vars[conflicting_action].set(old_key)
                self.hotkey_buttons[conflicting_action].config(text=old_key.upper(), bg='#4CAF50')
            else:
                # Если у текущего действия не было клавиши (пусто) - просто освобождаем
                self.hotkey_vars[conflicting_action].set("")
                self.hotkey_buttons[conflicting_action].config(text="—", bg='#2d2d2d')

            logger.info(
                f"[HOTKEYS_SETTINGS] ✅ Клавиши поменяны местами: {action} теперь {key}, {conflicting_action} теперь {old_key or '—'}")

            # Сбрасываем состояние захвата
            self.hotkey_capturing[action] = False
            self.window.unbind_all('<Key>')
            self.window.unbind_all('<Escape>')

            # Разблокируем действия горячих клавиш
            if hasattr(self, 'app') and hasattr(self.app, 'set_actions_blocked'):
                logger.info("[HOTKEYS_SETTINGS] Разблокируем действия горячих клавиш")
                self.app.set_actions_blocked(False)

            # Восстанавливаем цвет кнопок через 300 мс
            self.window.after(300, lambda a=action: self.hotkey_buttons[a].config(bg='#2d2d2d'))
            self.window.after(300, lambda a=conflicting_action: self.hotkey_buttons[a].config(bg='#2d2d2d'))

            logger.info(f"[HOTKEYS_SETTINGS] ✅ Захват завершен (клавиши поменяны местами)")
            return

        # Если клавиша свободна - просто назначаем
        logger.info(f"[HOTKEYS_SETTINGS] Назначаем клавишу '{key}' для действия '{action}'")
        self.hotkey_vars[action].set(key)
        self.hotkey_buttons[action].config(text=key.upper(), bg='#4CAF50')
        self.hotkey_capturing[action] = False
        logger.info(f"[HOTKEYS_SETTINGS] Кнопка для {action} обновлена: {key.upper()} (зеленая)")

        # Отвязываем обработчики
        self.window.unbind_all('<Key>')
        self.window.unbind_all('<Escape>')
        logger.info("[HOTKEYS_SETTINGS] Обработчики клавиш отвязаны")

        # РАЗБЛОКИРУЕМ ДЕЙСТВИЯ горячих клавиш
        if hasattr(self, 'app') and hasattr(self.app, 'set_actions_blocked'):
            logger.info("[HOTKEYS_SETTINGS] Разблокируем действия горячих клавиш")
            self.app.set_actions_blocked(False)

        # Восстанавливаем цвет кнопки через 300 мс
        self.window.after(300, lambda a=action: self.hotkey_buttons[a].config(bg='#2d2d2d'))
        logger.info(f"[HOTKEYS_SETTINGS] ✅ Захват завершен для действия: {action}")

    def _cancel_hotkey_capture(self):
        """Отменяет текущий захват горячей клавиши."""
        logger = logging.getLogger(__name__)
        logger.info("[HOTKEYS_SETTINGS] ===== ОТМЕНА ЗАХВАТА КЛАВИШИ =====")

        for action in self.hotkey_capturing:
            if self.hotkey_capturing[action]:
                logger.info(f"[HOTKEYS_SETTINGS] Отменяем захват для действия: {action}")
                self.hotkey_capturing[action] = False
                self.hotkey_buttons[action].config(
                    bg='#2d2d2d',
                    text=self.hotkey_vars[action].get().upper() or "—"
                )
                self.window.unbind_all('<Key>')
                # Разблокируем ДЕЙСТВИЯ горячих клавиш
                if hasattr(self, 'app') and hasattr(self.app, 'set_actions_blocked'):
                    logger.info("[HOTKEYS_SETTINGS] Разблокируем действия горячих клавиш")
                    self.app.set_actions_blocked(False)
                logger.info(f"[HOTKEYS_SETTINGS] ✅ Захват отменен для действия: {action}")
                break
        logger.info("[HOTKEYS_SETTINGS] ===== ОТМЕНА ЗАХВАТА ЗАВЕРШЕНА =====")

    def _start_hotkey_capture(self, action):
        """Начинает захват клавиши для переназначения."""
        logger = logging.getLogger(__name__)
        logger.info("[HOTKEYS_SETTINGS] ===== НАЧАЛО ЗАХВАТА КЛАВИШИ =====")
        logger.info(f"[HOTKEYS_SETTINGS] Действие: {action}")

        # Проверяем, не идет ли уже захват для этого действия
        if self.hotkey_capturing.get(action, False):
            logger.warning(f"[HOTKEYS_SETTINGS] Захват уже идет для действия {action}")
            return

        # Отменяем все активные захваты
        for a in self.hotkey_capturing:
            if self.hotkey_capturing[a]:
                logger.info(f"[HOTKEYS_SETTINGS] Отменяем предыдущий захват для: {a}")
                self.hotkey_capturing[a] = False
                self.hotkey_buttons[a].config(bg='#2d2d2d', text=self.hotkey_vars[a].get().upper() or "—")

        self.hotkey_capturing[action] = True
        btn = self.hotkey_buttons[action]
        btn.config(bg='#FF6B00', text=self.get_string('settings_hotkeys_press_key'))
        logger.info(f"[HOTKEYS_SETTINGS] Кнопка для {action} переключена в режим захвата (оранжевая)")

        # БЛОКИРУЕМ ДЕЙСТВИЯ горячих клавиш (но не сам перехват)
        if hasattr(self, 'app') and hasattr(self.app, 'set_actions_blocked'):
            logger.info("[HOTKEYS_SETTINGS] Блокируем действия горячих клавиш")
            self.app.set_actions_blocked(True)

        # Устанавливаем фокус на окно
        self.window.focus_force()
        logger.info("[HOTKEYS_SETTINGS] Фокус установлен на окно настроек")

        # Отвязываем старые обработчики
        self.window.unbind_all('<Key>')

        # Привязываем обработчик клавиш
        self.window.bind_all('<Key>', lambda e, a=action: self._on_hotkey_pressed(a, e))
        logger.info(f"[HOTKEYS_SETTINGS] Обработчик клавиш привязан для действия: {action}")
        logger.info("[HOTKEYS_SETTINGS] ===== ЗАХВАТ КЛАВИШИ НАЧАТ ======")

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
        if hasattr(self, 'hotkey_vars'):
            for action, var in self.hotkey_vars.items():
                key = self.settings.get_hotkey(action)
                var.set(key)
                if action in self.hotkey_buttons:
                    self.hotkey_buttons[action].config(text=key.upper() if key else "—")

    def browse_browser(self):
        """Открывает диалог выбора файла браузера"""
        file_path = filedialog.askopenfilename(
            title="Выберите исполняемый файл браузера",
            filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
        )
        if file_path:
            self.browser_path_var.set(file_path)
