"""
Модуль для отображения оверлея индикатора перевода
"""

import tkinter as tk
from tkinter import ttk
import threading
import time


class TranslationOverlay:
    """Оверлейный индикатор выполнения перевода с независимым циклом событий"""

    def __init__(self):
        self.root = None
        self.progress = None
        self.status_label = None
        self.visible = False
        self._stop_animation = False
        self._thread = None
        self._status_text = "Перевод..."

    def show(self, text="Перевод..."):
        """Показывает оверлей с индикатором в отдельном потоке"""
        try:
            # Если уже виден, не создаем новый
            if self.visible:
                print(f"[DEBUG] Оверлей уже виден")
                return

            self._stop_animation = False
            self._status_text = text
            self.visible = True

            # Запускаем окно в отдельном потоке
            self._thread = threading.Thread(target=self._run_window, daemon=True)
            self._thread.start()

            print(f"[DEBUG] TranslationOverlay.show() - запущен в отдельном потоке")
        except Exception as e:
            print(f"Ошибка при создании оверлея: {e}")

    def _run_window(self):
        """Создает и запускает окно в отдельном потоке"""
        try:
            self.root = tk.Tk()
            self.root.title("")
            self.root.overrideredirect(True)
            self.root.attributes('-topmost', True)
            self.root.attributes('-alpha', 0.95)
            self.root.configure(bg='#1e1e1e')

            width = 350
            height = 120
            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()
            x = (screen_width - width) // 2
            y = (screen_height - height) // 2
            self.root.geometry(f"{width}x{height}+{x}+{y}")
            self.root.lift()

            main = tk.Frame(self.root, bg='#1e1e1e', bd=2, relief=tk.RAISED)
            main.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

            self.status_label = tk.Label(
                main,
                text=self._status_text,
                bg='#1e1e1e',
                fg='#4CAF50',
                font=('Segoe UI', 14, 'bold')
            )
            self.status_label.pack(pady=(15, 10))

            progress_frame = tk.Frame(main, bg='#1e1e1e')
            progress_frame.pack(fill=tk.X, padx=20, pady=(5, 15))

            self.progress = ttk.Progressbar(
                progress_frame,
                mode='indeterminate',
                length=280,
                style='green.Horizontal.TProgressbar'
            )
            self.progress.pack()

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

            # Запускаем анимацию
            self.progress.start(10)

            # Запускаем обновление статуса
            self._update_status_animation()

            self.root.bind('<Escape>', self._on_escape)

            print(f"[DEBUG] Окно прогресса создано, запускаем mainloop")

            # Запускаем главный цикл
            self.root.mainloop()

            print(f"[DEBUG] Окно прогресса закрыто")
        except Exception as e:
            print(f"Ошибка в окне прогресса: {e}")
            import traceback
            traceback.print_exc()

    def _update_status_animation(self):
        """Обновляет текст статуса с точками для имитации активности"""
        if not self.visible or self._stop_animation or not self.root:
            return

        # Меняем количество точек для имитации работы
        dots_count = (int(time.time() * 1.5) % 4)
        dots = '.' * dots_count
        spaces = ' ' * (3 - dots_count)
        status_text = f"Перевод{dots}{spaces}"

        try:
            if self.status_label:
                self.status_label.config(text=status_text)

            # Планируем следующее обновление
            if self.visible and not self._stop_animation and self.root:
                self.root.after(300, self._update_status_animation)
        except Exception as e:
            print(f"Ошибка обновления статуса: {e}")

    def _on_escape(self, event):
        self.hide()
        return "break"

    def finish(self):
        """Завершает перевод - останавливает анимацию и закрывает окно"""
        print(f"[DEBUG] Перевод завершен, закрываем окно прогресса")
        self._stop_animation = True
        self.visible = False

        if self.root:
            try:
                self.root.after(0, self._set_finished_ui)
            except:
                pass

    def _set_finished_ui(self):
        """Устанавливает UI в состояние 'Готово' и закрывает окно"""
        if not self.root:
            return

        try:
            if self.progress:
                try:
                    self.progress.stop()
                except:
                    pass
                self.progress['mode'] = 'determinate'
                self.progress['value'] = 100

            if self.status_label:
                self.status_label.config(text="✅ Готово!")

            # Обновляем UI перед закрытием
            self.root.update_idletasks()
            self.root.update()

            # Закрываем окно через 1 секунду
            self.root.after(1000, self._close_window)

            print(f"[DEBUG] Прогресс установлен на 100%")
        except Exception as e:
            print(f"Ошибка установки завершения: {e}")
            self._close_window()

    def _close_window(self):
        """Закрывает окно и завершает mainloop"""
        try:
            self.visible = False
            if self.root:
                self.root.quit()
                self.root.destroy()
                self.root = None
                self.progress = None
                self.status_label = None
        except:
            pass

    def hide(self):
        """Скрывает оверлей"""
        self._stop_animation = True
        self.visible = False
        self._close_window()

    def is_visible(self):
        return self.visible