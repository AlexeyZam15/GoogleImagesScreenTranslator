"""
Модуль для отображения оверлея индикатора перевода
"""

import tkinter as tk
from tkinter import ttk
import time
import win32gui
import win32con
import win32api


class TranslationOverlay:
    """Оверлейный индикатор выполнения перевода (Toplevel, работает в главном потоке)"""

    def __init__(self, parent=None):
        self.parent = parent
        self.root = None
        self.progress = None
        self.status_label = None
        self.visible = False
        self._stop_animation = False
        self._status_text = "Перевод..."
        self._close_after = None

    def _ensure_topmost(self):
        """Гарантирует, что оверлей находится поверх всех окон"""
        try:
            if not self.root or not self.root.winfo_exists():
                return

            self.root.lift()
            self.root.attributes('-topmost', True)

            try:
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

    def show(self, text="Перевод..."):
        """Показывает оверлей с индикатором"""
        try:
            if self.visible:
                print(f"[DEBUG] Оверлей уже виден")
                return

            self._stop_animation = False
            self._status_text = text
            self.visible = True

            self._create_window()
            print(f"[DEBUG] TranslationOverlay.show() - окно создано")

        except Exception as e:
            print(f"Ошибка при создании оверлея: {e}")
            import traceback
            traceback.print_exc()

    def _create_window(self):
        """Создает окно оверлея как Toplevel от главного окна"""
        try:
            import tkinter as tk
            print(f"[DEBUG] _create_window() - начат")
            print(f"[DEBUG] self.parent = {self.parent}")

            if not self.parent:
                root = tk._default_root
                if root:
                    self.parent = root
                    print(f"[DEBUG] Найден корневой Tk: {root}")
                else:
                    print(f"[DEBUG] Нет корневого Tk, создаем новый Tk")
                    self.parent = tk.Tk()

            if self.parent:
                print(f"[DEBUG] Родитель существует: {self.parent}")
                self.root = tk.Toplevel(self.parent)
                print(f"[DEBUG] Toplevel создан от родителя")
            else:
                print(f"[DEBUG] Нет родителя, создаем Tk")
                self.root = tk.Tk()
                print(f"[DEBUG] Tk создан")

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

            print(f"[DEBUG] Окно настроено: {width}x{height}+{x}+{y}")

            main = tk.Frame(self.root, bg='#1e1e1e', bd=2, relief=tk.RAISED)
            main.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
            main.config(takefocus=False)
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
            self.status_label.bind('<Button-1>', lambda e: "break")
            self.status_label.bind('<ButtonRelease-1>', lambda e: "break")

            progress_frame = tk.Frame(main, bg='#1e1e1e')
            progress_frame.pack(fill=tk.X, padx=20, pady=(5, 15))
            progress_frame.config(takefocus=False)
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

            self.root.bind('<Escape>', self._on_escape)
            self.root.bind('<Button-1>', lambda e: "break")
            self.root.bind('<ButtonRelease-1>', lambda e: "break")

            self.root.update_idletasks()
            self.root.update()

            print(f"[DEBUG] Окно прогресса создано и показано (Toplevel)")
            print(f"[DEBUG] root.winfo_exists() = {self.root.winfo_exists() if self.root else False}")
            print(f"[DEBUG] root.winfo_ismapped() = {self.root.winfo_ismapped() if self.root else False}")

        except Exception as e:
            print(f"[DEBUG] Ошибка при создании окна: {e}")
            import traceback
            traceback.print_exc()
            self.visible = False

    def _update_status_animation(self):
        """Обновляет текст статуса с точками для имитации активности"""
        if not self.visible or self._stop_animation or not self.root:
            return

        try:
            dots_count = (int(time.time() * 1.5) % 4)
            dots = '.' * dots_count
            spaces = ' ' * (3 - dots_count)
            status_text = f"Перевод{dots}{spaces}"

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

    def finish(self):
        """Завершает перевод - останавливает анимацию и закрывает окно"""
        print(f"[DEBUG] Перевод завершен, закрываем окно прогресса")
        self._stop_animation = True

        if self.root and self.root.winfo_exists():
            try:
                self.root.after(0, self._set_finished_ui)
            except Exception as e:
                print(f"[DEBUG] Ошибка при завершении: {e}")
                self._close_window()
        else:
            print("[DEBUG] Нет активного окна для завершения")
            self.visible = False

    def _set_finished_ui(self):
        """Устанавливает UI в состояние 'Готово' и закрывает окно"""
        if not self.root:
            return

        try:
            if not self.root.winfo_exists():
                print("[DEBUG] Окно уже закрыто, пропускаем")
                self.visible = False
                return

            if self.progress:
                try:
                    self.progress.stop()
                except:
                    pass
                self.progress['mode'] = 'determinate'
                self.progress['value'] = 100

            if self.status_label:
                self.status_label.config(text="✅ Готово!")

            self.root.update_idletasks()
            self._ensure_topmost()
            print(f"[DEBUG] Прогресс установлен на 100%")

            if self.root and self.root.winfo_exists():
                self.root.after(1000, self._close_window)

        except Exception as e:
            print(f"[DEBUG] Ошибка установки завершения: {e}")
            self._close_window()

    def _close_window(self):
        """Закрывает окно"""
        try:
            self.visible = False
            self._stop_animation = True

            if self.root and self.root.winfo_exists():
                print("[DEBUG] Закрытие окна прогресса...")
                self.root.destroy()
                print("[DEBUG] Окно прогресса закрыто")

            self.root = None
            self.progress = None
            self.status_label = None

        except Exception as e:
            print(f"[DEBUG] Ошибка при закрытии окна: {e}")
            self.root = None
            self.progress = None
            self.status_label = None

    def hide(self):
        """Скрывает оверлей"""
        self._stop_animation = True
        self.visible = False
        self._close_window()

    def is_visible(self):
        return self.visible