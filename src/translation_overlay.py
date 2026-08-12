"""
Модуль для отображения оверлея индикатора перевода
"""

import tkinter as tk
from tkinter import ttk
import time
import logging
import win32gui
import win32con
import win32api


class TranslationOverlay:
    """Оверлейный индикатор выполнения перевода (Toplevel, работает в главном потоке)"""

    def __init__(self, parent=None, settings=None):
        self.parent = parent
        self.settings = settings
        self.root = None
        self.progress = None
        self.status_label = None
        self.visible = False
        self._stop_animation = False
        self._status_text = self.get_string('translation_status_translating')
        self._close_after = None
        self.logger = logging.getLogger(__name__)
        self._app = None  # <-- ДОБАВЛЯЕМ ССЫЛКУ НА ПРИЛОЖЕНИЕ

    def set_app(self, app):
        """Устанавливает ссылку на приложение для отмены перевода"""
        self._app = app

    def _create_window(self):
        """Создает окно оверлея как Toplevel от главного окна"""
        try:
            import tkinter as tk

            if self.root is not None:
                try:
                    if self.root.winfo_exists():
                        self.root.destroy()
                except:
                    pass
                self.root = None
                self.progress = None
                self.status_label = None

            if not self.parent:
                root = tk._default_root
                if root:
                    self.parent = root
                else:
                    self.parent = tk.Tk()

            if self.parent:
                self.root = tk.Toplevel(self.parent)
            else:
                self.root = tk.Tk()

            self.root.title("")
            self.root.overrideredirect(True)
            self.root.attributes('-topmost', True)
            self.root.attributes('-alpha', 0.95)
            self.root.attributes('-disabled', True)
            self.root.attributes('-toolwindow', True)
            self.root.configure(bg='#1e1e1e')

            self.root.protocol("WM_DELETE_WINDOW", self.hide)

            width = 350
            height = 120
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")

            self.root.deiconify()
            self.root.lift()
            self._ensure_topmost()

            main = tk.Frame(self.root, bg='#1e1e1e', bd=2, relief=tk.RAISED)
            main.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            main.config(takefocus=False)

            if main.winfo_exists():
                main.bind('<Button-1>', lambda e: "break")
                main.bind('<ButtonRelease-1>', lambda e: "break")

            self.status_label = tk.Label(
                main,
                text=self._status_text,
                bg='#1e1e1e',
                fg='#4CAF50',
                font=('Segoe UI', 14, 'bold')
            )
            self.status_label.pack(pady=(15, 10))
            self.status_label.config(takefocus=False)

            if self.status_label.winfo_exists():
                self.status_label.bind('<Button-1>', lambda e: "break")
                self.status_label.bind('<ButtonRelease-1>', lambda e: "break")

            progress_frame = tk.Frame(main, bg='#1e1e1e')
            progress_frame.pack(fill=tk.X, padx=20, pady=(5, 15))
            progress_frame.config(takefocus=False)

            if progress_frame.winfo_exists():
                progress_frame.bind('<Button-1>', lambda e: "break")
                progress_frame.bind('<ButtonRelease-1>', lambda e: "break")

            self.progress = ttk.Progressbar(
                progress_frame,
                mode='indeterminate',
                length=280,
                style='green.Horizontal.TProgressbar'
            )
            self.progress.pack()
            self.progress.config(takefocus=False)

            if self.progress.winfo_exists():
                self.progress.bind('<Button-1>', lambda e: "break")
                self.progress.bind('<ButtonRelease-1>', lambda e: "break")

            style = ttk.Style()
            style.theme_use('clam')
            style.configure(
                'green.Horizontal.TProgressbar',
                background='#4CAF50',
                troughcolor='#3c3c3c',
                bordercolor='#1e1e1e',
                lightcolor='#4CAF50',
                darkcolor='#4CAF50'
            )

            self.progress.start(10)
            self._update_status_animation()

            # === НОВЫЙ ОБРАБОТЧИК ESC НАД ИНДИКАТОРОМ ===
            # Привязываем ESC к окну индикатора
            self.root.bind('<Escape>', self._on_esc_over_indicator)
            self.status_label.bind('<Escape>', self._on_esc_over_indicator)
            self.progress.bind('<Escape>', self._on_esc_over_indicator)
            main.bind('<Escape>', self._on_esc_over_indicator)

            if self.root.winfo_exists():
                self.root.bind('<Button-1>', lambda e: "break")
                self.root.bind('<ButtonRelease-1>', lambda e: "break")

            self.root.update_idletasks()
            self.root.update()

        except Exception as e:
            print(f"[DEBUG] Ошибка при создании окна: {e}")
            import traceback
            traceback.print_exc()
            self.visible = False

    def _on_esc_over_indicator(self, event):
        """
        Обработчик ESC, когда курсор мыши находится над индикатором перевода.
        Отменяет текущий перевод.
        """
        self.logger.info("[INDICATOR] ESC нажат над индикатором перевода")

        # Проверяем, находится ли курсор мыши над индикатором
        try:
            import win32api
            import win32gui

            cursor_pos = win32api.GetCursorPos()
            cursor_x, cursor_y = cursor_pos

            if self.root and self.root.winfo_exists():
                rect = win32gui.GetWindowRect(int(self.root.winfo_id()))
                x1, y1, x2, y2 = rect

                if x1 <= cursor_x <= x2 and y1 <= cursor_y <= y2:
                    self.logger.info("[INDICATOR] Курсор над индикатором, отменяем перевод")

                    # Отменяем перевод через приложение
                    if self._app and hasattr(self._app, '_cancel_translation'):
                        self._app._cancel_translation()
                        self.logger.info("[INDICATOR] Перевод отменён")
                        return "break"
                    else:
                        self.logger.warning("[INDICATOR] Не удалось отменить перевод: нет ссылки на приложение")
                else:
                    self.logger.info("[INDICATOR] Курсор не над индикатором, игнорируем ESC")
        except Exception as e:
            self.logger.warning(f"[INDICATOR] Ошибка проверки положения курсора: {e}")

        return "break"

    def get_string(self, key: str) -> str:
        """Возвращает локализованную строку через settings"""
        if self.settings:
            return self.settings.get_string(key)
        return key  # Fallback

    def show(self, text=None):
        """Показывает оверлей с индикатором"""
        # Если текст не передан, используем локализованный по умолчанию
        if text is None:
            text = self.get_string('translation_status_translating')

        try:
            if self.visible:
                self._status_text = text
                if self.status_label:
                    self.status_label.config(text=text)
                self._ensure_topmost()
                self.logger.info("[DEBUG] Индикатор уже виден, обновлен текст")
                return

            self._stop_animation = False
            self._status_text = text
            self.visible = True

            if self.root:
                try:
                    if self.root.winfo_exists():
                        self.logger.info("[DEBUG] Используем существующее окно индикатора")
                        if self.status_label:
                            self.status_label.config(text=text)
                        self.root.deiconify()
                        self.root.lift()
                        self._ensure_topmost()
                        self._update_status_animation()
                        return
                except:
                    self.root = None

            self._create_window()
            self.logger.info("[DEBUG] Индикатор перевода показан (новое окно)")

        except Exception as e:
            self.logger.error(f"Ошибка при создании индикатора: {e}")
            import traceback
            traceback.print_exc()

    def _ensure_topmost(self):
        """Гарантирует, что оверлей находится поверх всех окон"""
        try:
            if not self.root or not self.root.winfo_exists():
                return

            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.update_idletasks()

            try:
                import win32gui
                import win32con
                hwnd = int(self.root.winfo_id())
                win32gui.SetWindowPos(
                    hwnd,
                    win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                )
            except:
                pass

        except Exception as e:
            print(f"[DEBUG] _ensure_topmost ошибка: {e}")

    def finish(self):
        """Завершает перевод - останавливает анимацию и закрывает окно"""
        self.logger.info("[DEBUG] finish() - завершение индикатора")
        self._stop_animation = True
        self.visible = False

        if self.root:
            try:
                if self.root.winfo_exists():
                    # Сразу скрываем окно, без анимации
                    self.root.withdraw()
                    self.logger.info("[DEBUG] Индикатор скрыт")
                else:
                    self.root = None
            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка при завершении: {e}")
                self.root = None

    def _close_window(self):
        """Закрывает окно с полной очисткой всех ссылок"""
        try:
            self.visible = False
            self._stop_animation = True

            if self.root:
                try:
                    if self.root.winfo_exists():
                        self.logger.info("[DEBUG] Закрытие окна индикатора...")
                        self.root.withdraw()
                        self.logger.info("[DEBUG] Окно индикатора скрыто")
                    else:
                        self.root = None
                except Exception as e:
                    self.logger.info(f"[DEBUG] Ошибка при закрытии окна: {e}")
                    self.root = None
        except Exception as e:
            self.logger.info(f"[DEBUG] Ошибка при закрытии окна: {e}")
            self.root = None

    def hide(self):
        """Скрывает оверлей с полной очисткой"""
        self._stop_animation = True
        self.visible = False
        self._close_window()

    def _update_status_animation(self):
        """Обновляет текст статуса с точками для имитации активности"""
        if not self.visible or self._stop_animation or not self.root:
            return

        try:
            dots_count = (int(time.time() * 1.5) % 4)
            dots = '.' * dots_count
            spaces = ' ' * (3 - dots_count)
            # Используем локализованную строку как основу
            base_text = self.get_string('translation_status_translating')
            status_text = f"{base_text}{dots}{spaces}"

            if self.status_label and self.root.winfo_exists():
                self.status_label.config(text=status_text)

            if self.visible and not self._stop_animation and self.root:
                if self.root.winfo_exists():
                    self.root.after(300, self._update_status_animation)

        except Exception as e:
            print(f"[DEBUG] Ошибка обновления статуса: {e}")

    def _on_escape(self, event):
        self.hide()
        return "break"

    def is_visible(self):
        return self.visible
