"""
Модуль для захвата области экрана мышкой
Адаптирован из AutoArtReplacer для GoogleScreenTranslate
"""

import tkinter as tk
from tkinter import messagebox
from pathlib import Path
from PIL import ImageGrab
import time
import logging


class AreaSelector:
    """Класс для захвата области экрана мышкой"""

    def __init__(self, parent, callback, config=None):
        self.parent = parent
        self.callback = callback
        self.config = config or {}
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.canvas = None
        self.root = None
        self.selection_alpha = self.config.get("selection_alpha", 0.3)
        self.min_selection_size = self.config.get("min_selection_size", 10)
        self.logger = logging.getLogger(__name__)

    def on_escape(self, e):
        """Обработчик ESC"""
        self.logger.info("[DEBUG] AreaSelector.on_escape() вызван")
        self._close_capture(False)

    def start_capture(self):
        """Запуск режима выделения области на экране"""
        self.logger.info("[DEBUG] AreaSelector.start_capture() - начало")

        # Устанавливаем флаг в родителе, чтобы keyboard хук мог перехватывать ESC
        try:
            if self.parent:
                self.parent._capture_mode = True
                self.parent._area_selector = self
                self.logger.info("[DEBUG] Установлены флаги _capture_mode и _area_selector")
        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка установки флага захвата: {e}")

        # Создаем окно БЕЗ родителя, чтобы оно не зависело от главного окна
        self.root = tk.Toplevel()
        self.root.attributes('-fullscreen', True)
        self.root.attributes('-alpha', self.selection_alpha)
        self.root.attributes('-topmost', True)
        self.root.focus_force()
        self.root.configure(bg='gray')

        self.canvas = tk.Canvas(self.root, cursor="cross", bg='gray', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<ButtonPress-1>", self.on_mouse_down)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_mouse_up)

        def on_escape(e):
            self._close_capture(False)

        self.root.bind("<Escape>", on_escape)
        self.canvas.bind("<Escape>", on_escape)

        self.canvas.focus_set()
        self.root.focus_force()

        self.root.grab_set()
        self.root.lift()

        # Показываем инструкцию
        self.canvas.create_text(
            self.root.winfo_screenwidth() // 2,
            50,
            text="Выделите область для перевода (ESC для отмены)",
            fill="white",
            font=("Arial", 16, "bold")
        )

        self.logger.info("[DEBUG] AreaSelector.start_capture() - окно создано")

    def _close_capture(self, success):
        """Закрывает окно захвата и восстанавливает состояние"""
        self.logger.info(f"[DEBUG] AreaSelector._close_capture(success={success}) - начало")

        # Восстанавливаем главное окно
        try:
            if self.parent and hasattr(self.parent, 'root'):
                self.parent.root.deiconify()
                self.parent.root.lift()
                self.parent.root.focus_force()
                self.logger.info("[DEBUG] Главное окно восстановлено")
        except Exception as ex:
            self.logger.error(f"[DEBUG] Ошибка восстановления главного окна: {ex}")

        # Выключаем режим захвата в родителе
        try:
            if self.parent:
                self.parent._capture_mode = False
                self.parent._area_selector = None
                self.logger.info("[DEBUG] Флаги захвата сброшены")
        except Exception as ex:
            self.logger.error(f"[DEBUG] Ошибка сброса флагов захвата: {ex}")

        # Закрываем окно захвата
        try:
            if self.root:
                self.root.grab_release()
                self.root.destroy()
                self.logger.info("[DEBUG] Окно захвата закрыто")
        except Exception as ex:
            self.logger.error(f"[DEBUG] Ошибка закрытия окна захвата: {ex}")

        # Если успешный захват - вызываем колбэк с координатами
        if success and self.callback and hasattr(self, '_selected_rect'):
            self.logger.info(f"[DEBUG] Вызов callback с rect={self._selected_rect}")
            self.callback(self._selected_rect)

    def on_mouse_down(self, event):
        self.logger.debug(f"[DEBUG] on_mouse_down: ({event.x}, {event.y})")
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)

    def on_mouse_drag(self, event):
        if self.start_x is not None and self.start_y is not None:
            if self.rect:
                self.canvas.delete(self.rect)
            self.rect = self.canvas.create_rectangle(
                self.start_x,
                self.start_y,
                event.x,
                event.y,
                outline='red',
                width=2,
                fill='blue',
                stipple='gray50'
            )

    def on_mouse_up(self, event):
        self.logger.info(f"[DEBUG] on_mouse_up: ({event.x}, {event.y})")
        if self.start_x is not None and self.start_y is not None:
            x1, y1 = min(self.start_x, event.x), min(self.start_y, event.y)
            x2, y2 = max(self.start_x, event.x), max(self.start_y, event.y)

            min_size = self.min_selection_size
            if x2 - x1 > min_size and y2 - y1 > min_size:
                # Сохраняем координаты для колбэка
                self._selected_rect = (x1, y1, x2, y2)
                self.logger.info(f"[DEBUG] Выделена область: ({x1},{y1}) - ({x2},{y2})")
                self._close_capture(True)
            else:
                self.logger.warning(f"[DEBUG] Слишком маленькая область: {x2 - x1}x{y2 - y1}")
                messagebox.showwarning(
                    "Ошибка",
                    f"Выделите область размером больше {min_size}x{min_size} пикселей"
                )