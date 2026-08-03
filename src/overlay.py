"""
Модуль для оверлейного окна с переведенным изображением
"""

import logging
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image, ImageTk
import tkinter as tk
import keyboard
import win32gui
import win32con
import win32api


class OverlayWindow:
    """Класс для оверлейного окна (Toplevel, работает в главном потоке)"""

    def __init__(self, parent=None, app_title="Перевод скриншотов", auto_hide_enabled=True):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Инициализация OverlayWindow")
        self.visible = False
        from src.utils import ensure_app_temp_dir
        self.temp_dir = ensure_app_temp_dir()
        self.tk_image = None
        self._target_rect = None
        self._esc_hook_active = False
        self._use_manager_esc = False
        self._images = []
        self._last_image_path = None
        self._last_window_rect = None
        self._target_hwnd = None
        self._app_title = app_title
        self._monitor_timer = None
        self._is_visible_by_user = False
        self._is_dragging = False
        self._drag_stop_timer = None
        self._saved_position = None
        self._is_fullscreen_target = False
        self._fullscreen_restore_needed = False
        self._show_time = 0
        self.auto_hide_enabled = auto_hide_enabled
        self._image_loaded = False
        self._overlay_active = False
        self._last_active_hwnd = None
        self._monitor_initialized = False
        self._monitor_stable_time = 0
        self._edit_mode_enabled = False
        self._mouse_over = False
        self._hidden_by_mouse = False
        self._is_window_screenshot = False
        self._context_menu_visible = False
        self._right_click_processing = False
        self._hidden_by_user = False
        self._is_auto_replace = False
        self._creation_time = time.time()
        self._template_id = None
        self._suppress_enter_events = False
        self._last_mouse_x = -1
        self._last_mouse_y = -1
        self._mouse_position_known = False
        self._user_moved = False

        # === ИНИЦИАЛИЗИРУЕМ АТРИБУТЫ ===
        self._close_button_window = None
        self._close_button_visible = False

        # Переменные для панели заголовка
        self._title_bar_window = None
        self._title_canvas = None
        self._title_bar_visible = False
        self._title_close_bg = None
        self._title_close_cross1 = None
        self._title_close_cross2 = None
        self._mouse_over_title_bar = False

        self.root = tk.Toplevel(parent) if parent else tk.Toplevel()
        self.root.title("Перевод")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#000000')
        self.root.withdraw()

        self.canvas = tk.Canvas(self.root, bg='#000000', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._drag_data = {"x": 0, "y": 0}

        self.canvas.bind('<ButtonPress-1>', self._start_drag)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._stop_drag)
        self.root.bind('<ButtonPress-1>', self._start_drag)
        self.root.bind('<B1-Motion>', self._on_drag)
        self.root.bind('<ButtonRelease-1>', self._stop_drag)

        self.canvas.bind('<Button-3>', self._on_right_click)
        self.root.bind('<Button-3>', self._on_right_click)

        self.canvas.bind('<Enter>', self._on_mouse_enter)
        self.canvas.bind('<Leave>', self._on_mouse_leave)
        self.root.bind('<Enter>', self._on_mouse_enter)
        self.root.bind('<Leave>', self._on_mouse_leave)

        self.logger.info("OverlayWindow инициализирован")

    def _on_title_bar_enter(self, event):
        """Обработчик входа мыши на панель заголовка."""
        self._mouse_over_title_bar = True
        self._mouse_over = True
        self.logger.debug("[DEBUG] _on_title_bar_enter: мышь на панели, удерживаем панель")

    def _on_title_bar_leave(self, event):
        """Обработчик выхода мыши с панели заголовка."""
        self._mouse_over_title_bar = False
        self.logger.debug("[DEBUG] _on_title_bar_leave: мышь покинула панель")
        # Проверяем, находится ли мышь над оверлеем
        try:
            import win32api
            cursor_x, cursor_y = win32api.GetCursorPos()
            if self.root and self.root.winfo_exists():
                rect = (self.root.winfo_x(), self.root.winfo_y(),
                        self.root.winfo_x() + self.root.winfo_width(),
                        self.root.winfo_y() + self.root.winfo_height())
                if rect[0] <= cursor_x <= rect[2] and rect[1] <= cursor_y <= rect[3]:
                    # Мышь над оверлеем - не скрываем панель
                    self.logger.debug("[DEBUG] _on_title_bar_leave: мышь над оверлеем, панель не скрываем")
                    return
        except:
            pass
        # Если мышь не над оверлеем - скрываем панель
        self._hide_title_bar()

    def _update_title_bar_position(self):
        """Обновляет позицию панели заголовка."""
        if not self._title_bar_window or not self._title_bar_window.winfo_exists():
            return
        if not self.root or not self.root.winfo_exists():
            return

        try:
            overlay_x = self.root.winfo_x()
            overlay_y = self.root.winfo_y()
            overlay_width = self.root.winfo_width()

            title_height = 24

            pos_x = overlay_x
            pos_y = overlay_y - title_height

            if pos_y < 0:
                pos_y = overlay_y + 2

            # Обновляем геометрию панели
            self._title_bar_window.geometry(f"{overlay_width}x{title_height}+{pos_x}+{pos_y}")

            # Обновляем canvas
            if self._title_canvas and self._title_canvas.winfo_exists():
                self._title_canvas.config(width=overlay_width)

                # Пересоздаём кнопку закрытия
                self._title_canvas.delete('title_close')

                btn_size = 18
                padding = 3
                close_x = overlay_width - btn_size - padding
                close_y = (title_height - btn_size) // 2

                close_bg = self._title_canvas.create_rectangle(
                    close_x, close_y,
                    close_x + btn_size, close_y + btn_size,
                    fill='#e74c3c',
                    outline='#c0392b',
                    width=1,
                    tags=('title_close',)
                )

                margin = 4
                self._title_canvas.create_line(
                    close_x + margin, close_y + margin,
                    close_x + btn_size - margin, close_y + btn_size - margin,
                    fill='white',
                    width=2,
                    tags=('title_close',)
                )
                self._title_canvas.create_line(
                    close_x + btn_size - margin, close_y + margin,
                    close_x + margin, close_y + btn_size - margin,
                    fill='white',
                    width=2,
                    tags=('title_close',)
                )

                # Привязываем события
                def on_close_enter(e):
                    self._title_bar_window.config(cursor='hand2')
                    self._title_canvas.itemconfig(close_bg, fill='#c0392b')

                def on_close_leave(e):
                    self._title_bar_window.config(cursor='')
                    self._title_canvas.itemconfig(close_bg, fill='#e74c3c')

                self._title_canvas.tag_bind('title_close', '<Enter>', on_close_enter)
                self._title_canvas.tag_bind('title_close', '<Leave>', on_close_leave)
                self._title_canvas.tag_bind('title_close', '<Button-1>', self._on_close_click)

            # Поднимаем панель
            self._title_bar_window.lift()

        except Exception as e:
            self.logger.debug(f"[DEBUG] Ошибка обновления позиции: {e}")

    def _on_mouse_enter(self, event):
        """Обработчик входа мыши в область оверлея."""
        if self._is_dragging:
            self.logger.debug("[DEBUG] _on_mouse_enter: перетаскивание активно, игнорируем")
            return

        if self._suppress_enter_events:
            self.logger.debug("[DEBUG] _on_mouse_enter: событие подавлено")
            self._suppress_enter_events = False
            return

        self._mouse_over = True
        self.logger.info(f"[DEBUG] _on_mouse_enter: mouse_over=True, edit_mode={self._edit_mode_enabled}")

        # В режиме редактирования панель уже видна постоянно, ничего не делаем
        if self._edit_mode_enabled:
            self.logger.debug("[DEBUG] _on_mouse_enter: режим редактирования, панель уже видна")
            # Убеждаемся, что панель видна
            if not self._title_bar_window or not self._title_bar_window.winfo_exists():
                self._show_title_bar()
            return

        if self._is_window_screenshot:
            self.logger.debug("[DEBUG] _on_mouse_enter: F2-оверлей, не скрываем")
            return

        if self.visible and self._is_visible_by_user:
            self.logger.info("[DEBUG] _on_mouse_enter: скрываем оверлей (режим просмотра)")
            self._hidden_by_mouse = True
            # === СКРЫВАЕМ ПАНЕЛЬ ВМЕСТЕ С ОВЕРЛЕЕМ ===
            self._hide_title_bar()
            self._hide_internal()
            if not self._monitor_timer and self.auto_hide_enabled:
                self._start_visibility_monitor()

    def _on_mouse_leave(self, event):
        """Обработчик выхода мыши из области оверлея."""
        if self._is_dragging:
            self.logger.debug("[DEBUG] _on_mouse_leave: перетаскивание активно, игнорируем")
            return

        # Проверяем, не перешла ли мышь на панель
        try:
            if self._title_bar_window and self._title_bar_window.winfo_exists():
                import win32api
                cursor_x, cursor_y = win32api.GetCursorPos()

                panel_x = self._title_bar_window.winfo_x()
                panel_y = self._title_bar_window.winfo_y()
                panel_w = self._title_bar_window.winfo_width()
                panel_h = self._title_bar_window.winfo_height()

                if panel_x <= cursor_x <= panel_x + panel_w and panel_y <= cursor_y <= panel_y + panel_h:
                    self.logger.debug("[DEBUG] _on_mouse_leave: курсор на панели, не скрываем")
                    self._mouse_over = True
                    return
        except Exception as e:
            self.logger.debug(f"[DEBUG] _on_mouse_leave: ошибка проверки: {e}")

        self._mouse_over = False
        self.logger.info("[DEBUG] _on_mouse_leave: mouse_over=False")

        # === ПОКАЗЫВАЕМ ПАНЕЛЬ ТОЛЬКО В РЕЖИМЕ РЕДАКТИРОВАНИЯ ===
        if self._edit_mode_enabled:
            self.logger.info("[DEBUG] _on_mouse_leave: режим редактирования, панель оставляем")
            if self._title_bar_window and self._title_bar_window.winfo_exists():
                self._title_bar_window.lift()
                self._update_title_bar_position()
            else:
                self._show_title_bar()
            return

        # === СТАНДАРТНОЕ ПОВЕДЕНИЕ: СКРЫВАЕМ ПАНЕЛЬ ===
        self.logger.info("[DEBUG] _on_mouse_leave: скрываем панель")
        self._hide_title_bar()

        if self._edit_mode_enabled:
            self.logger.debug("[DEBUG] _on_mouse_leave: режим редактирования, не скрываем оверлей")
            return

        if self._is_window_screenshot:
            return

        self._hidden_by_mouse = False

        if self._last_image_path and self._last_window_rect:
            if not self.visible and not self._hidden_by_mouse:
                self._show_internal()
                if self.auto_hide_enabled:
                    self._start_visibility_monitor()

    def _show_title_bar(self):
        """Показывает панель заголовка над оверлеем (отдельное окно с крестиком)."""
        self.logger.info(f"[DEBUG] _show_title_bar: НАЧАЛО")

        if not self.root or not self.root.winfo_exists():
            self.logger.warning("[DEBUG] _show_title_bar: root не существует")
            return

        if not self.visible:
            self.logger.warning("[DEBUG] _show_title_bar: оверлей не виден")
            return

        if not self._image_loaded:
            self.logger.warning("[DEBUG] _show_title_bar: изображение не загружено")
            return

        # === ПРОВЕРКА РЕЖИМА РЕДАКТИРОВАНИЯ ===
        if not self._edit_mode_enabled:
            self.logger.info(f"[DEBUG] _show_title_bar: режим редактирования выключен")
            self._hide_title_bar()
            return

        try:
            overlay_x = self.root.winfo_x()
            overlay_y = self.root.winfo_y()
            overlay_width = self.root.winfo_width()
            title_height = 24
            btn_size = 18
            padding = 3

            pos_x = overlay_x
            pos_y = overlay_y - title_height
            if pos_y < 0:
                pos_y = overlay_y + 2

            # === ЕСЛИ ПАНЕЛЬ УЖЕ СУЩЕСТВУЕТ ===
            if self._title_bar_window and self._title_bar_window.winfo_exists():
                self.logger.info("[DEBUG] _show_title_bar: панель уже существует, обновляем")
                self._title_bar_window.geometry(f"{overlay_width}x{title_height}+{pos_x}+{pos_y}")

                if self._title_canvas and self._title_canvas.winfo_exists():
                    self._title_canvas.delete("all")
                    self._title_canvas.config(width=overlay_width, height=title_height)

                    close_x = overlay_width - btn_size - padding
                    close_y = (title_height - btn_size) // 2

                    close_bg = self._title_canvas.create_rectangle(
                        close_x, close_y,
                        close_x + btn_size, close_y + btn_size,
                        fill='#e74c3c',
                        outline='#c0392b',
                        width=1,
                        tags=('title_close',)
                    )

                    margin = 4
                    self._title_canvas.create_line(
                        close_x + margin, close_y + margin,
                        close_x + btn_size - margin, close_y + btn_size - margin,
                        fill='white',
                        width=2,
                        tags=('title_close',)
                    )
                    self._title_canvas.create_line(
                        close_x + btn_size - margin, close_y + margin,
                        close_x + margin, close_y + btn_size - margin,
                        fill='white',
                        width=2,
                        tags=('title_close',)
                    )

                    def on_close_enter(e):
                        self._title_bar_window.config(cursor='hand2')
                        self._title_canvas.itemconfig(close_bg, fill='#c0392b')

                    def on_close_leave(e):
                        self._title_bar_window.config(cursor='')
                        self._title_canvas.itemconfig(close_bg, fill='#e74c3c')

                    def on_close_click(e):
                        self.logger.info("[DEBUG] _show_title_bar: нажат крестик!")
                        self._on_close_click(e)

                    self._title_canvas.tag_bind('title_close', '<Enter>', on_close_enter)
                    self._title_canvas.tag_bind('title_close', '<Leave>', on_close_leave)
                    self._title_canvas.tag_bind('title_close', '<Button-1>', on_close_click)

                    self._title_canvas.bind('<ButtonPress-1>', self._start_drag)
                    self._title_canvas.bind('<B1-Motion>', self._on_drag)
                    self._title_canvas.bind('<ButtonRelease-1>', self._stop_drag)

                self._title_bar_window.deiconify()
                self._title_bar_window.lift()
                self._title_bar_visible = True
                self.logger.info("[DEBUG] _show_title_bar: панель обновлена")
                return

            # === СОЗДАЁМ НОВУЮ ПАНЕЛЬ ===
            self.logger.info("[DEBUG] _show_title_bar: создаём новую панель")

            self._title_bar_window = tk.Toplevel(self.root)
            self._title_bar_window.overrideredirect(True)
            self._title_bar_window.attributes('-topmost', True)
            self._title_bar_window.attributes('-toolwindow', True)
            self._title_bar_window.configure(bg='#2d2d2d')
            self._title_bar_window.geometry(f"{overlay_width}x{title_height}+{pos_x}+{pos_y}")

            self._title_canvas = tk.Canvas(
                self._title_bar_window,
                width=overlay_width,
                height=title_height,
                bg='#2d2d2d',
                highlightthickness=0,
                bd=0
            )
            self._title_canvas.pack(fill=tk.BOTH, expand=True)

            close_x = overlay_width - btn_size - padding
            close_y = (title_height - btn_size) // 2

            self._title_close_bg = self._title_canvas.create_rectangle(
                close_x, close_y,
                close_x + btn_size, close_y + btn_size,
                fill='#e74c3c',
                outline='#c0392b',
                width=1,
                tags=('title_close',)
            )

            margin = 4
            self._title_canvas.create_line(
                close_x + margin, close_y + margin,
                close_x + btn_size - margin, close_y + btn_size - margin,
                fill='white',
                width=2,
                tags=('title_close',)
            )
            self._title_canvas.create_line(
                close_x + btn_size - margin, close_y + margin,
                close_x + margin, close_y + btn_size - margin,
                fill='white',
                width=2,
                tags=('title_close',)
            )

            def on_close_enter(e):
                self._title_bar_window.config(cursor='hand2')
                self._title_canvas.itemconfig(self._title_close_bg, fill='#c0392b')

            def on_close_leave(e):
                self._title_bar_window.config(cursor='')
                self._title_canvas.itemconfig(self._title_close_bg, fill='#e74c3c')

            def on_close_click(e):
                self.logger.info("[DEBUG] _show_title_bar (new): нажат крестик!")
                self._on_close_click(e)

            self._title_canvas.tag_bind('title_close', '<Enter>', on_close_enter)
            self._title_canvas.tag_bind('title_close', '<Leave>', on_close_leave)
            self._title_canvas.tag_bind('title_close', '<Button-1>', on_close_click)

            self._title_canvas.bind('<ButtonPress-1>', self._start_drag)
            self._title_canvas.bind('<B1-Motion>', self._on_drag)
            self._title_canvas.bind('<ButtonRelease-1>', self._stop_drag)
            self._title_bar_window.bind('<ButtonPress-1>', self._start_drag)
            self._title_bar_window.bind('<B1-Motion>', self._on_drag)
            self._title_bar_window.bind('<ButtonRelease-1>', self._stop_drag)

            self._title_bar_window.deiconify()
            self._title_bar_window.lift()

            self._title_bar_visible = True
            self.logger.info("[DEBUG] Панель заголовка показана над оверлеем")

        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка показа панели заголовка: {e}")
            import traceback
            traceback.print_exc()

    def _hide_title_bar(self):
        """Скрывает панель заголовка - полностью уничтожает окно."""
        # === НЕ СКРЫВАЕМ ПАНЕЛЬ В РЕЖИМЕ РЕДАКТИРОВАНИЯ ===
        if self._edit_mode_enabled:
            self.logger.debug("[DEBUG] _hide_title_bar: режим редактирования, не скрываем")
            if self._title_bar_window and self._title_bar_window.winfo_exists():
                self._title_bar_window.deiconify()
                self._title_bar_window.lift()
                self._update_title_bar_position()
            else:
                self._show_title_bar()
            return

        try:
            # === ПОЛНОСТЬЮ УНИЧТОЖАЕМ ОКНО ПАНЕЛИ ===
            if self._title_bar_window and self._title_bar_window.winfo_exists():
                self.logger.info("[DEBUG] _hide_title_bar: уничтожаем окно панели")
                self._title_bar_window.destroy()
            self._title_bar_window = None
            self._title_canvas = None
            self._title_bar_visible = False
            self.logger.info("[DEBUG] Панель заголовка полностью уничтожена")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Ошибка уничтожения панели заголовка: {e}")
            self._title_bar_window = None
            self._title_canvas = None
            self._title_bar_visible = False

    def _hide_close_button(self):
        """Скрывает кнопку закрытия."""
        # Проверяем существование окна закрытия
        if hasattr(self,
                   '_close_button_window') and self._close_button_window and self._close_button_window.winfo_exists():
            try:
                self._close_button_window.destroy()
            except:
                pass
            self._close_button_window = None
            self._close_button_visible = False
            self.logger.debug("[DEBUG] _hide_close_button: кнопка закрытия скрыта")
        else:
            self._close_button_window = None
            self._close_button_visible = False

    def hide(self, by_user: bool = True):
        """Скрывает оверлей и панель."""
        self.logger.info(
            f"[DEBUG][hide] НАЧАЛО: visible={self.visible}, by_user={by_user}, edit_mode={self._edit_mode_enabled}")

        # Сбрасываем флаг запуска, так как оверлей уже был показан
        self._created_at_startup = False

        # В режиме редактирования НЕ СКРЫВАЕМ оверлей автоматически
        if not by_user and self._edit_mode_enabled:
            self.logger.info("[DEBUG][hide] Режим редактирования, автоскрытие запрещено")
            return

        # === ВСЕГДА УНИЧТОЖАЕМ ПАНЕЛЬ ПРИ СКРЫТИИ ОВЕРЛЕЯ ===
        try:
            if self._title_bar_window and self._title_bar_window.winfo_exists():
                self._title_bar_window.destroy()
            self._title_bar_window = None
            self._title_canvas = None
            self._title_bar_visible = False
            self.logger.info("[DEBUG][hide] Панель заголовка уничтожена")
        except Exception as e:
            self.logger.warning(f"[DEBUG][hide] Ошибка уничтожения панели: {e}")
            self._title_bar_window = None
            self._title_canvas = None
            self._title_bar_visible = False

        # Сохраняем позицию
        try:
            if self.root and self.root.winfo_exists():
                x = self.root.winfo_x()
                y = self.root.winfo_y()
                self._saved_position = (x, y)
                self._user_moved = True
        except Exception as e:
            self.logger.warning(f"[DEBUG][hide] Ошибка сохранения позиции: {e}")

        if by_user:
            self._hidden_by_user = True
        self._is_visible_by_user = False
        self.visible = False

        self._stop_visibility_monitor()
        self._disable_esc_hook()

        try:
            self.root.withdraw()
            self.logger.info("[DEBUG][hide] оверлей скрыт")
        except Exception as e:
            self.logger.error(f"[DEBUG][hide] ОШИБКА: {e}")

    def show(self):
        """Показывает оверлей."""
        self.logger.info("[DEBUG] show() вызван")

        if not self._last_image_path or not self._last_window_rect:
            self.logger.warning("[DEBUG] show() - нет сохраненного изображения или rect")
            return

        if not self._image_loaded or self.tk_image is None:
            self.logger.info("[DEBUG] show() - изображение не загружено, загружаем")
            self._load_and_show_image(self._last_image_path, self._last_window_rect, show_immediately=True)
            return

        if self.visible:
            self.logger.info("[DEBUG] show() - оверлей уже виден")
            # === ПРОВЕРЯЕМ, НЕ ИЗМЕНИЛАСЬ ЛИ ПОЗИЦИЯ ===
            if self._last_window_rect:
                expected_x, expected_y, expected_x2, expected_y2 = self._last_window_rect
                try:
                    current_x = self.root.winfo_x()
                    current_y = self.root.winfo_y()
                    current_w = self.root.winfo_width()
                    current_h = self.root.winfo_height()

                    expected_w = expected_x2 - expected_x
                    expected_h = expected_y2 - expected_y

                    # Если позиция или размер изменились - обновляем
                    if (abs(current_x - expected_x) > 2 or
                            abs(current_y - expected_y) > 2 or
                            abs(current_w - expected_w) > 2 or
                            abs(current_h - expected_h) > 2):
                        self.logger.info(
                            f"[DEBUG] show() - позиция изменилась, обновляем: ({current_x},{current_y}) -> ({expected_x},{expected_y})")
                        self.root.geometry(f"{expected_w}x{expected_h}+{expected_x}+{expected_y}")
                        self.root.update_idletasks()
                        self.root.update()
                        self._saved_position = (expected_x, expected_y)
                except Exception as e:
                    self.logger.warning(f"[DEBUG] show() - ошибка проверки позиции: {e}")
            return

        self._hidden_by_user = False
        self._hidden_by_mouse = False
        self._monitor_initialized = False
        self._last_active_hwnd = None

        if self._monitor_timer is not None:
            try:
                if self.root and self.root.winfo_exists():
                    self.root.after_cancel(self._monitor_timer)
            except Exception as e:
                self.logger.warning(f"Ошибка отмены таймера при show: {e}")
            self._monitor_timer = None

        try:
            self.root.deiconify()
            self.root.lift()
            self.visible = True
            self._ensure_topmost()
            self._is_visible_by_user = True
            self._enable_esc_hook()

            if self._edit_mode_enabled:
                self._show_title_bar()
            elif self.auto_hide_enabled:
                self._start_visibility_monitor()

            self.logger.info("[DEBUG] show() - оверлей показан")
        except Exception as e:
            self.logger.warning(f"[DEBUG] show() - ошибка: {e}")

    def update_edit_mode(self, edit_mode_enabled: bool):
        """Обновляет состояние режима редактирования для оверлея."""
        self._edit_mode_enabled = edit_mode_enabled
        self.logger.info(f"[DEBUG] Обновлен _edit_mode_enabled = {edit_mode_enabled}")

        if self._edit_mode_enabled:
            # Включаем режим редактирования
            self.auto_hide_enabled = False
            self._stop_visibility_monitor()

            if self.visible and self._image_loaded:
                self.root.after(50, self._show_title_bar)
                self.logger.info("[DEBUG] update_edit_mode: панель будет показана через 50мс")
            elif self.visible:
                if self._last_image_path and self._last_window_rect:
                    self._load_and_show_image(self._last_image_path, self._last_window_rect, show_immediately=True)
                    self.root.after(100, self._show_title_bar)
                    self.logger.info("[DEBUG] update_edit_mode: изображение загружено, панель будет показана")
        else:
            # Выключаем режим редактирования
            self.auto_hide_enabled = True
            self._hide_title_bar()
            self.logger.info("[DEBUG] update_edit_mode: панель скрыта")
            if self.visible:
                self._start_visibility_monitor()

    def _start_drag(self, event):
        """Начинает перетаскивание окна."""
        self.logger.info(f"[DEBUG] _start_drag вызван! event=({event.x}, {event.y})")

        # Проверка: разрешено ли перетаскивание
        if not self._edit_mode_enabled:
            self.logger.info("[DEBUG] _start_drag: режим редактирования ВЫКЛЮЧЕН - перетаскивание запрещено")
            return "break"

        if not self.visible:
            self.logger.info("[DEBUG] _start_drag - оверлей скрыт, перетаскивание запрещено")
            return "break"

        if self._drag_stop_timer:
            try:
                self.root.after_cancel(self._drag_stop_timer)
            except:
                pass
            self._drag_stop_timer = None

        self._is_dragging = True
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y

        if self.root and self.root.winfo_exists():
            self._drag_start_x = self.root.winfo_x()
            self._drag_start_y = self.root.winfo_y()
        else:
            self._drag_start_x = 0
            self._drag_start_y = 0

        self.logger.info("[DEBUG] Начало перетаскивания, флаг _is_dragging=True")

        # Останавливаем монитор видимости на время перетаскивания
        self._stop_visibility_monitor()
        self.logger.info("[DEBUG] _start_drag: монитор видимости отключен")

        # === ОПТИМИЗАЦИЯ: Приостанавливаем монитор автозамены ===
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'translation_monitor'):
                monitor = parent.translation_monitor
                if monitor and monitor.is_running():
                    monitor.stop()
                    self.logger.info("[DEBUG] _start_drag: монитор автозамены приостановлен")

        # === ОПТИМИЗАЦИЯ: Отключаем сохранение состояния во время перетаскивания ===
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager._suppress_save = True
            self.logger.info("[DEBUG] _start_drag: сохранение состояния отключено")

        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager.set_dragging(True)

    def _stop_drag(self, event):
        """Останавливает перетаскивание окна."""
        self.logger.info("[DEBUG] _stop_drag вызван")
        self._is_dragging = False
        self._drag_data["x"] = 0
        self._drag_data["y"] = 0
        self.logger.info("[DEBUG] Конец перетаскивания, флаг _is_dragging=False")

        # Сохраняем позицию
        try:
            if self.root and self.root.winfo_exists():
                overlay_x = self.root.winfo_x()
                overlay_y = self.root.winfo_y()
                overlay_w = self.root.winfo_width()
                overlay_h = self.root.winfo_height()

                self._user_moved = True

                # === ОБНОВЛЯЕМ СМЕЩЕНИЕ В ШАБЛОНЕ ===
                if self._template_id and hasattr(self, '_overlay_manager') and self._overlay_manager:
                    parent = self._overlay_manager.parent
                    if parent and hasattr(parent, 'translation_monitor'):
                        monitor = parent.translation_monitor
                        if monitor:
                            for template_data in monitor.templates:
                                if template_data.get('hash') == self._template_id:
                                    # Получаем последнюю позицию шаблона
                                    last_template_pos = template_data.get('last_template_position')
                                    if last_template_pos:
                                        template_x, template_y = last_template_pos
                                        # Вычисляем новое смещение
                                        new_offset_x = overlay_x - template_x
                                        new_offset_y = overlay_y - template_y
                                        template_data['offset_x'] = new_offset_x
                                        template_data['offset_y'] = new_offset_y
                                        template_data['overlay_width'] = overlay_w
                                        template_data['overlay_height'] = overlay_h
                                        template_data['offset_initialized'] = True
                                        self.logger.info(
                                            f"[DEBUG] Обновлено смещение для шаблона {self._template_id[:8]}: "
                                            f"({new_offset_x}, {new_offset_y})"
                                        )
                                    break

                    self._overlay_manager._save_overlay_position(self._template_id, overlay_x, overlay_y)
                    self.logger.info(
                        f"[DEBUG] Сохранена позиция оверлея для шаблона {self._template_id[:8]}: ({overlay_x}, {overlay_y})")

                elif self._last_image_path and hasattr(self, '_overlay_manager') and self._overlay_manager:
                    overlay_id = str(self._last_image_path)
                    self._overlay_manager._save_overlay_position(overlay_id, overlay_x, overlay_y)
                    self.logger.info(f"[DEBUG] Сохранена позиция оверлея: {overlay_id} -> ({overlay_x}, {overlay_y})")

        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось сохранить позицию оверлея: {e}")

        # Сбрасываем глобальный флаг перетаскивания
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager.set_dragging(False)
            self.logger.info("[DEBUG] Глобальный флаг перетаскивания сброшен")

        # Синхронизируем панель заголовка
        if self._title_bar_window and self._title_bar_window.winfo_exists():
            try:
                overlay_x = self.root.winfo_x()
                overlay_y = self.root.winfo_y()
                overlay_width = self.root.winfo_width()
                title_height = 24

                pos_y_panel = overlay_y - title_height
                if pos_y_panel < 0:
                    pos_y_panel = overlay_y + 2

                self._title_bar_window.geometry(f"{overlay_width}x{title_height}+{overlay_x}+{pos_y_panel}")
                self._title_bar_window.lift()
                self.logger.info("[DEBUG] _stop_drag: панель синхронизирована")
            except Exception as e:
                self.logger.warning(f"[DEBUG] _stop_drag: ошибка синхронизации панели: {e}")

        # Сбрасываем флаги мыши
        self._hidden_by_mouse = False
        self._mouse_over = False
        self.logger.info("[DEBUG] _stop_drag: флаги _hidden_by_mouse и _mouse_over сброшены")

        # === ОПТИМИЗАЦИЯ: Восстанавливаем сохранение состояния с задержкой ===
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager._suppress_save = False
            # Отложенное сохранение состояния
            if self.root and self.root.winfo_exists():
                self.root.after(500, self._overlay_manager.save_overlay_state)
                self.logger.info("[DEBUG] _stop_drag: сохранение состояния запланировано через 500мс")

        # Перезапускаем монитор видимости (если нужно)
        if self.auto_hide_enabled and not self._edit_mode_enabled:
            self._start_visibility_monitor()
            self.logger.info("[DEBUG] _stop_drag: монитор видимости перезапущен")
        elif self._edit_mode_enabled:
            self.logger.info("[DEBUG] _stop_drag: режим редактирования, монитор не запускаем")
            # Убеждаемся, что панель видна
            if self.visible and self._image_loaded:
                self._show_title_bar()
                self.logger.info("[DEBUG] _stop_drag: панель заголовка обновлена")

        # === ОПТИМИЗАЦИЯ: Восстанавливаем монитор автозамены с задержкой ===
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'translation_monitor'):
                monitor = parent.translation_monitor
                if monitor and monitor.templates:
                    # Запускаем с задержкой, чтобы дать время GUI стабилизироваться
                    if self.root and self.root.winfo_exists():
                        self.root.after(300, monitor.start)
                        self.logger.info("[DEBUG] _stop_drag: монитор автозамены будет запущен через 300мс")

        # Таймаут для стабилизации
        if self.root and self.root.winfo_exists():
            if self._drag_stop_timer:
                try:
                    self.root.after_cancel(self._drag_stop_timer)
                except:
                    pass
            self._drag_stop_timer = self.root.after(500, self._on_drag_stop_timeout)

    def _on_drag(self, event):
        """Перемещает окно во время перетаскивания."""
        if self._is_dragging and self.root.winfo_exists():
            x = self.root.winfo_x() + (event.x - self._drag_data["x"])
            y = self.root.winfo_y() + (event.y - self._drag_data["y"])
            self.root.geometry(f"+{x}+{y}")
            self._saved_position = (x, y)

            # === ОПТИМИЗАЦИЯ: Уменьшаем частоту обновления панели ===
            if hasattr(self, '_drag_counter'):
                self._drag_counter += 1
            else:
                self._drag_counter = 0

            # Обновляем панель реже (каждый 5-й кадр вместо каждого 3-го)
            if self._drag_counter % 5 == 0:
                if self._title_bar_window and self._title_bar_window.winfo_exists():
                    try:
                        overlay_width = self.root.winfo_width()
                        title_height = 24
                        pos_y_panel = y - title_height
                        if pos_y_panel < 0:
                            pos_y_panel = y + 2

                        # Используем move вместо geometry (быстрее)
                        self._title_bar_window.geometry(f"{overlay_width}x{title_height}+{x}+{pos_y_panel}")
                        self._title_bar_window.lift()
                    except Exception as e:
                        self.logger.warning(f"[DEBUG] _on_drag: ошибка обновления панели: {e}")

    def _show_close_button_forced(self):
        """Показывает кнопку закрытия НАД оверлеем (для закрепленных оверлеев)."""
        if not self.root or not self.root.winfo_exists():
            self.logger.debug("[DEBUG] _show_close_button_forced: окно уже закрыто, пропускаем")
            return

        if self._close_button_visible:
            return

        if not self._image_loaded:
            self.logger.debug("[DEBUG] _show_close_button_forced: изображение не загружено, пропускаем")
            return

        try:
            overlay_x = self.root.winfo_x()
            overlay_y = self.root.winfo_y()
            overlay_width = self.root.winfo_width()

            btn_size = 20
            padding = 2

            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            # === ПРАВИЛЬНОЕ РАЗМЕЩЕНИЕ: НАД ПРАВЫМ ВЕРХНИМ УГЛОМ ===
            # Крестик должен быть над оверлеем, но если оверлей у верхнего края - внутри
            if overlay_y - btn_size - padding >= 0:
                # Место есть сверху - размещаем над оверлеем
                x_pos = overlay_x + overlay_width - btn_size - padding
                y_pos = overlay_y - btn_size - padding
            else:
                # Места сверху нет - размещаем внутри оверлея, в правом верхнем углу
                x_pos = overlay_x + overlay_width - btn_size - padding
                y_pos = overlay_y + padding

            # Проверяем, не вылезает ли за правый край экрана
            if x_pos + btn_size > screen_width:
                x_pos = overlay_x + overlay_width - btn_size - padding
                if x_pos + btn_size > screen_width:
                    x_pos = screen_width - btn_size - padding

            self.logger.info(
                f"[DEBUG] _show_close_button_forced: крестик в позиции ({x_pos}, {y_pos}), размер {btn_size}")

            # Создаем отдельное окно для крестика
            self._close_button_window = tk.Toplevel(self.root)
            self._close_button_window.overrideredirect(True)
            self._close_button_window.attributes('-topmost', True)
            self._close_button_window.attributes('-toolwindow', True)
            self._close_button_window.configure(bg='#ff0000')

            self._close_button_window.geometry(f"{btn_size}x{btn_size}+{x_pos}+{y_pos}")

            btn_canvas = tk.Canvas(
                self._close_button_window,
                width=btn_size,
                height=btn_size,
                bg='#ff0000',
                highlightthickness=0,
                cursor='hand2'
            )
            btn_canvas.pack(fill=tk.BOTH, expand=True)

            margin = 4
            btn_canvas.create_line(
                margin, margin,
                btn_size - margin, btn_size - margin,
                fill='white', width=2
            )
            btn_canvas.create_line(
                btn_size - margin, margin,
                margin, btn_size - margin,
                fill='white', width=2
            )

            def on_close_click(e):
                self._on_close_click(e)

            btn_canvas.bind('<Button-1>', on_close_click)
            self._close_button_window.bind('<Button-1>', on_close_click)

            self._close_button_window.deiconify()
            self._close_button_window.lift()

            self._start_close_button_position_updater()

            self._close_button_visible = True
            self.logger.info(f"[DEBUG] Кнопка закрытия показана в позиции ({x_pos}, {y_pos})")

        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка создания кнопки закрытия: {e}")
            self._close_button_visible = False

    def _start_close_button_position_updater(self):
        """Запускает обновление позиции кнопки закрытия при движении оверлея."""

        def update_position():
            if not self._close_button_visible:
                return
            if not self.root or not self.root.winfo_exists():
                self._hide_close_button()
                return
            if self._close_button_window and self._close_button_window.winfo_exists():
                try:
                    overlay_x = self.root.winfo_x()
                    overlay_y = self.root.winfo_y()
                    overlay_width = self.root.winfo_width()

                    btn_size = 20
                    padding = 2
                    screen_height = self.root.winfo_screenheight()
                    screen_width = self.root.winfo_screenwidth()

                    if overlay_y - btn_size - padding >= 0:
                        x_pos = overlay_x + overlay_width - btn_size - padding
                        y_pos = overlay_y - btn_size - padding
                    else:
                        x_pos = overlay_x + overlay_width - btn_size - padding
                        y_pos = overlay_y + padding

                    if x_pos + btn_size > screen_width:
                        x_pos = overlay_x + overlay_width - btn_size - padding
                        if x_pos + btn_size > screen_width:
                            x_pos = screen_width - btn_size - padding

                    self._close_button_window.geometry(f"+{x_pos}+{y_pos}")
                except Exception as e:
                    self.logger.debug(f"[DEBUG] Ошибка обновления позиции крестика: {e}")

            if self._close_button_visible and self.root and self.root.winfo_exists():
                self.root.after(100, update_position)

        if self.root and self.root.winfo_exists():
            self.root.after(100, update_position)

    def _show_close_button(self):
        """Показывает кнопку закрытия НАД оверлеем (для режима редактирования)."""
        if not self.root or not self.root.winfo_exists():
            return

        if not self._edit_mode_enabled or not self.visible or not self._image_loaded:
            return

        if self._close_button_visible:
            return

        try:
            overlay_x = self.root.winfo_x()
            overlay_y = self.root.winfo_y()
            overlay_width = self.root.winfo_width()

            btn_size = 20
            padding = 2
            screen_height = self.root.winfo_screenheight()
            screen_width = self.root.winfo_screenwidth()

            if overlay_y - btn_size - padding >= 0:
                x_pos = overlay_x + overlay_width - btn_size - padding
                y_pos = overlay_y - btn_size - padding
            else:
                x_pos = overlay_x + overlay_width - btn_size - padding
                y_pos = overlay_y + padding

            if x_pos + btn_size > screen_width:
                x_pos = overlay_x + overlay_width - btn_size - padding
                if x_pos + btn_size > screen_width:
                    x_pos = screen_width - btn_size - padding

            self.logger.info(
                f"[DEBUG] _show_close_button: крестик в позиции ({x_pos}, {y_pos})")

            self._close_button_window = tk.Toplevel(self.root)
            self._close_button_window.overrideredirect(True)
            self._close_button_window.attributes('-topmost', True)
            self._close_button_window.attributes('-toolwindow', True)
            self._close_button_window.configure(bg='#ff0000')

            self._close_button_window.geometry(f"{btn_size}x{btn_size}+{x_pos}+{y_pos}")

            btn_canvas = tk.Canvas(
                self._close_button_window,
                width=btn_size,
                height=btn_size,
                bg='#ff0000',
                highlightthickness=0,
                cursor='hand2'
            )
            btn_canvas.pack(fill=tk.BOTH, expand=True)

            margin = 4
            btn_canvas.create_line(
                margin, margin,
                btn_size - margin, btn_size - margin,
                fill='white', width=2
            )
            btn_canvas.create_line(
                btn_size - margin, margin,
                margin, btn_size - margin,
                fill='white', width=2
            )

            def on_close_click(e):
                self._on_close_click(e)

            btn_canvas.bind('<Button-1>', on_close_click)
            self._close_button_window.bind('<Button-1>', on_close_click)

            self._close_button_window.deiconify()
            self._close_button_window.lift()

            self._start_close_button_position_updater()

            self._close_button_visible = True
            self.logger.info(f"[DEBUG] Кнопка закрытия показана в позиции ({x_pos}, {y_pos})")

        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка создания кнопки закрытия: {e}")
            self._close_button_visible = False

    def _on_close_click(self, event):
        """Обработчик клика по кнопке закрытия - удаляет оверлей."""
        self.logger.info("[DEBUG] ========================================")
        self.logger.info("[DEBUG] === _on_close_click ВЫЗВАН ===")
        self.logger.info(f"[DEBUG] event: {event}")
        self.logger.info("[DEBUG] ========================================")

        # === КРЕСТИК ВСЕГДА УДАЛЯЕТ ОВЕРЛЕЙ ===
        self.logger.info("[DEBUG] _on_close_click: удаляем оверлей")
        self._hide_title_bar()
        self._remove_overlay()

    def _on_right_click(self, event):
        """Обработчик правой кнопки мыши - показывает контекстное меню через менеджер."""
        self.logger.info("[DEBUG] _on_right_click вызван")

        if self._right_click_processing:
            self.logger.info("[DEBUG] _on_right_click: уже обрабатывается, пропускаем")
            return

        if not self.visible:
            self.logger.info("[DEBUG] _on_right_click: оверлей не виден, пропускаем")
            return

        if not hasattr(self, '_overlay_manager') or not self._overlay_manager:
            self.logger.warning("[DEBUG] _on_right_click: менеджер не найден")
            return

        if self not in self._overlay_manager.overlays:
            self.logger.info("[DEBUG] _on_right_click: оверлей уже удален, пропускаем")
            return

        if not self.root or not self.root.winfo_exists():
            self.logger.info("[DEBUG] _on_right_click: окно оверлея закрыто, пропускаем")
            return

        # Проверяем режим редактирования
        is_edit_mode = False
        if self._edit_mode_enabled:
            is_edit_mode = True
        elif hasattr(self, '_overlay_manager') and self._overlay_manager:
            try:
                parent = self._overlay_manager.parent
                if parent and hasattr(parent, 'is_edit_mode_enabled'):
                    is_edit_mode = parent.is_edit_mode_enabled()
                elif parent and hasattr(parent, '_edit_mode_enabled'):
                    is_edit_mode = parent._edit_mode_enabled
            except:
                pass

        if not is_edit_mode:
            self.logger.info("[DEBUG] _on_right_click: режим редактирования ВЫКЛЮЧЕН")
            return

        self._right_click_processing = True
        self._context_menu_visible = True

        self._overlay_manager.show_context_menu(self, event.x_root, event.y_root)
        self.logger.info("[DEBUG] Контекстное меню показано через менеджер")

        self._start_menu_close_monitor()

        if self.root and self.root.winfo_exists():
            self.root.after(500, self._reset_right_click_flag)

    def _remove_overlay(self):
        """Удаляет этот оверлей через OverlayManager."""
        self.logger.info("[DEBUG] _remove_overlay вызван")

        if not self.visible:
            self.logger.info("[DEBUG] _remove_overlay: оверлей не виден, пропускаем")
            return

        is_f2_overlay = False
        if hasattr(self, '_is_window_screenshot') and self._is_window_screenshot:
            is_f2_overlay = True
            self.logger.info("[DEBUG] _remove_overlay: F2-оверлей, удаление разрешено")

        if not is_f2_overlay:
            if hasattr(self, '_overlay_manager') and self._overlay_manager:
                parent = self._overlay_manager.parent
                if parent and hasattr(parent, 'is_edit_mode_enabled') and not parent.is_edit_mode_enabled():
                    self.logger.info("[DEBUG] _remove_overlay: режим редактирования ВЫКЛЮЧЕН - удаление запрещено")
                    return
            else:
                self.logger.warning("[DEBUG] _remove_overlay: нет доступа к менеджеру, пропускаем")
                return

        try:
            if hasattr(self, '_overlay_manager') and self._overlay_manager:
                if hasattr(self._overlay_manager, '_context_menu') and self._overlay_manager._context_menu:
                    try:
                        self._overlay_manager._context_menu.unpost()
                        self._overlay_manager._context_menu.update_idletasks()
                        self.logger.info("[DEBUG] Контекстное меню закрыто перед удалением")
                    except Exception as e:
                        self.logger.warning(f"[DEBUG] Не удалось закрыть контекстное меню: {e}")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Ошибка при закрытии контекстного меню: {e}")

        self._context_menu_visible = False

        self._hide_title_bar()
        self.logger.info("[DEBUG] _remove_overlay: панель заголовка скрыта")

        # === УДАЛЯЕМ ВСЕ ШАБЛОНЫ ДЛЯ ЭТОГО HWND ИЗ МОНИТОРА ===
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'translation_monitor') and parent.translation_monitor:
                monitor = parent.translation_monitor
                target_hwnd = self._target_hwnd

                # Останавливаем монитор на время удаления
                was_running = monitor.is_running()
                if was_running:
                    monitor.stop()
                    self.logger.info(f"[MONITOR] Монитор остановлен для удаления шаблонов")

                # Удаляем все шаблоны для этого HWND
                templates_to_remove = []
                for template in monitor.templates:
                    if template.get('target_hwnd') == target_hwnd:
                        templates_to_remove.append(template.get('pair_index'))

                for pair_index in templates_to_remove:
                    self.logger.info(f"[MONITOR] Удаляем шаблон #{pair_index} для HWND={target_hwnd}")
                    monitor.remove_template(pair_index)

                # Перезапускаем монитор если он был запущен
                if was_running and monitor.templates:
                    monitor.start()
                    self.logger.info(f"[MONITOR] Монитор перезапущен, осталось {len(monitor.templates)} шаблонов")
                elif was_running:
                    self.logger.info(f"[MONITOR] Монитор остановлен, шаблонов не осталось")

        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self.logger.info(
                f"[DEBUG] Удаление оверлея через OverlayManager (всего оверлеев: {len(self._overlay_manager.overlays)})")
            self._overlay_manager.remove_overlay(self)
        else:
            self.logger.warning("[DEBUG] _remove_overlay: менеджер не найден, закрываем самостоятельно")
            self.close()

    def _check_and_update_visibility(self):
        """
        Проверяет видимость оверлея.
        Теперь с защитой от рекурсивных вызовов и проверкой состояния мыши.
        """

        # Защита от рекурсии
        if hasattr(self, '_updating_visibility') and self._updating_visibility:
            return
        self._updating_visibility = True

        try:
            # ===== РЕЖИМ 1: КОНТЕКСТНОЕ МЕНЮ =====
            if self._context_menu_visible:
                if self._is_visible_by_user and not self.visible and not self._hidden_by_mouse:
                    self._show_internal(force=False)
                return

            # ===== РЕЖИМ 2: БАЗОВЫЕ ПРОВЕРКИ =====
            if not self.auto_hide_enabled or not self._is_visible_by_user:
                return

            if self._hidden_by_user:
                return

            if hasattr(self, '_overlay_manager') and self._overlay_manager:
                if self._overlay_manager.is_dragging():
                    return

            if time.time() < self._monitor_stable_time:
                return

            # ===== ВАЖНО: ПРОВЕРЯЕМ, ЧТО МЫШЬ НЕ В ЗОНЕ ОВЕРЛЕЯ =====
            if self._mouse_over or self._hidden_by_mouse:
                is_edit_mode = False
                if hasattr(self, '_edit_mode_enabled'):
                    is_edit_mode = self._edit_mode_enabled
                elif hasattr(self, '_overlay_manager') and self._overlay_manager:
                    try:
                        parent = self._overlay_manager.parent
                        if parent and hasattr(parent, 'is_edit_mode_enabled'):
                            is_edit_mode = parent.is_edit_mode_enabled()
                        elif parent and hasattr(parent, '_edit_mode_enabled'):
                            is_edit_mode = parent._edit_mode_enabled
                    except:
                        pass

                if is_edit_mode:
                    if not self.visible and self._is_visible_by_user and not self._hidden_by_user:
                        self._hidden_by_mouse = False
                        self._show_internal(force=False)
                    return

                if self.visible:
                    self._hide_internal()
                return

            try:
                import win32gui
                import win32api

                active_hwnd = win32gui.GetForegroundWindow()
                if active_hwnd == 0:
                    return

                # ===== ПРОВЕРКА: АКТИВНО ЛИ ОКНО ВЫДЕЛЕНИЯ ОБЛАСТИ =====
                if self._is_selection_window_active(active_hwnd):
                    if not self.visible and self._is_visible_by_user and not self._hidden_by_user:
                        self._show_internal(force=False)
                    return

                # ===== ОСНОВНАЯ ПРОВЕРКА: активно ли окно этого оверлея =====
                target_hwnd = self.get_target_hwnd()

                # === ЕСЛИ ОКНО НЕ АКТИВНО — СКРЫВАЕМ ===
                if target_hwnd is None or active_hwnd != target_hwnd:
                    if hasattr(self, '_edit_mode_enabled') and self._edit_mode_enabled:
                        self.logger.debug(
                            "[DEBUG] _check_and_update_visibility: режим редактирования, не скрываем при смене окна")
                        return
                    if self.visible:
                        self._hide_internal()
                    return

                # ===== МЫ НА ЦЕЛЕВОМ ОКНЕ =====
                cursor_pos = win32api.GetCursorPos()
                cursor_x, cursor_y = cursor_pos

                # === ДЛЯ АВТОЗАМЕНЫ: ПРОВЕРЯЕМ СТАТУС ШАБЛОНА ===
                overlay_type, template_found = self._get_overlay_status()

                if overlay_type == 'auto_replace':
                    if template_found:
                        is_cursor_inside = False
                        if self._last_window_rect:
                            x1, y1, x2, y2 = self._last_window_rect
                            if x1 <= cursor_x <= x2 and y1 <= cursor_y <= y2:
                                is_cursor_inside = True

                        if is_cursor_inside and self.visible:
                            self._hidden_by_mouse = True
                            self._hide_internal()
                            return

                        if not is_cursor_inside and not self.visible and self._is_visible_by_user and not self._hidden_by_user:
                            self._hidden_by_mouse = False
                            self._show_internal(force=False)
                    else:
                        if self.visible:
                            self._hide_internal()
                    return

                # ===== ОБЫЧНЫЙ ОВЕРЛЕЙ =====
                is_cursor_inside = False
                if self._last_window_rect:
                    x1, y1, x2, y2 = self._last_window_rect
                    if x1 <= cursor_x <= x2 and y1 <= cursor_y <= y2:
                        is_cursor_inside = True

                if is_cursor_inside and self.visible:
                    is_edit_mode = False
                    if hasattr(self, '_edit_mode_enabled'):
                        is_edit_mode = self._edit_mode_enabled
                    elif hasattr(self, '_overlay_manager') and self._overlay_manager:
                        try:
                            parent = self._overlay_manager.parent
                            if parent and hasattr(parent, 'is_edit_mode_enabled'):
                                is_edit_mode = parent.is_edit_mode_enabled()
                            elif parent and hasattr(parent, '_edit_mode_enabled'):
                                is_edit_mode = parent._edit_mode_enabled
                        except:
                            pass

                    if not is_edit_mode:
                        if hasattr(self, '_user_moved') and self._user_moved:
                            self.logger.info(
                                "[DEBUG] _check_and_update_visibility: оверлей был перемещен пользователем, не скрываем")
                            return

                        self._hidden_by_mouse = True
                        self._hide_internal()
                        return
                    return

                if not is_cursor_inside and not self.visible and self._is_visible_by_user and not self._hidden_by_user:
                    self._hidden_by_mouse = False
                    self._show_internal(force=False)
                    return

            except Exception as e:
                self.logger.warning(f"Ошибка в _check_and_update_visibility: {e}")

        finally:
            self._updating_visibility = False

    def show_for_window(self, image_path: Path, window_rect: tuple, target_hwnd: int = None,
                        is_fullscreen: bool = None, show_immediately: bool = True,
                        is_startup: bool = False):
        """Показывает оверлей для указанного окна."""
        self.logger.info(f"[DEBUG] === show_for_window НАЧАЛО ===")
        self.logger.info(f"[DEBUG] image_path={image_path}")
        self.logger.info(f"[DEBUG] window_rect={window_rect}")
        self.logger.info(f"[DEBUG] target_hwnd={target_hwnd}")
        self.logger.info(f"[DEBUG] show_immediately={show_immediately}")
        self.logger.info(f"[DEBUG] is_startup={is_startup}")

        if target_hwnd is not None:
            self._target_hwnd = target_hwnd
            if is_fullscreen is not None:
                self._is_fullscreen_target = is_fullscreen
            else:
                self._is_fullscreen_target = self.is_fullscreen_window(target_hwnd)
            self.logger.info(
                f"[DEBUG] _target_hwnd={self._target_hwnd}, _is_fullscreen_target={self._is_fullscreen_target}")

            if self._is_fullscreen_target:
                self._saved_position = None
                self.logger.info("[DEBUG] Полноэкранный режим: сброшена сохраненная позиция")

        self._last_image_path = image_path
        self._last_window_rect = window_rect
        self._is_visible_by_user = True
        self.logger.info(f"[DEBUG] _last_image_path={self._last_image_path}")
        self.logger.info(f"[DEBUG] _last_window_rect={self._last_window_rect}")

        self._created_at_startup = is_startup

        if is_startup:
            self.logger.info("[DEBUG] Режим запуска: загружаем изображение, но НЕ показываем оверлей")
            self._load_and_show_image(image_path, window_rect, show_immediately=False, is_startup=is_startup)
            try:
                self.root.withdraw()
                self.visible = False
                self.logger.info("[DEBUG] Оверлей скрыт при запуске")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось скрыть оверлей: {e}")
            if self.auto_hide_enabled:
                self.logger.info("[DEBUG] Запуск монитора для отслеживания активации окна")
                self.root.after(500, self._start_visibility_monitor)
            return

        self.logger.info("[DEBUG] Обычный режим: показываем оверлей")
        self._load_and_show_image(image_path, window_rect, show_immediately=show_immediately, is_startup=is_startup)

        if show_immediately:
            self.logger.info("[DEBUG] show_immediately=True, показываем оверлей")
            self._stop_visibility_monitor()

            # Если режим редактирования включён - сразу показываем панель
            if self._edit_mode_enabled:
                self._show_title_bar()
                self.logger.info("[DEBUG] Режим редактирования: панель показана сразу")
        else:
            self.logger.info("[DEBUG] show_immediately=False, оверлей сохранен но НЕ показан")
            if self.auto_hide_enabled:
                self.logger.info("[DEBUG] Запуск монитора для отложенного показа")
                self.root.after(1000, self._start_visibility_monitor_delayed)

        self.logger.info("[DEBUG] === show_for_window ЗАВЕРШЕН ===")

    def _load_and_show_image(self, image_path: Path, window_rect: tuple, show_immediately: bool = True,
                             is_startup: bool = False):
        """Загружает изображение и показывает его в оверлее."""
        self.logger.info(f"[DEBUG] === _load_and_show_image НАЧАЛО ===")
        self.logger.info(f"[DEBUG] image_path={image_path}")
        self.logger.info(f"[DEBUG] window_rect={window_rect}")
        self.logger.info(f"[DEBUG] show_immediately={show_immediately}")
        self.logger.info(f"[DEBUG] is_startup={is_startup}")

        self._created_at_startup = is_startup

        try:
            x1, y1, x2, y2 = window_rect
            win_width = x2 - x1
            win_height = y2 - y1

            self.logger.info("[DEBUG] Открываем изображение")
            img = Image.open(image_path)
            self.logger.info(f"[DEBUG] Изображение открыто: {img.width}x{img.height}")

            ratio = min(win_width / img.width, win_height / img.height)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)
            self.logger.info(f"[DEBUG] ratio={ratio}, new_w={new_w}, new_h={new_h}")

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            temp_img = self.temp_dir / "overlay.png"
            img.save(temp_img)

            pil_img = Image.open(temp_img)
            photo = ImageTk.PhotoImage(pil_img)
            self._images.append(photo)
            self.tk_image = photo

            self.canvas.delete("all")
            self.canvas.config(width=win_width, height=win_height)
            self.canvas.create_rectangle(0, 0, win_width, win_height, fill='#000000', outline='', tags=('bg_rect',))

            x = (win_width - new_w) // 2
            y = (win_height - new_h) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image)

            self.root.update_idletasks()

            self.visible = False
            self._show_time = time.time()
            self._monitor_stable_time = time.time() + 2.0
            self._image_loaded = True

            # === ОБНОВЛЯЕМ _last_window_rect ===
            self._last_window_rect = window_rect

            if is_startup:
                self.logger.info("[DEBUG] Режим запуска: окно скрыто")
                self.root.withdraw()
                return

            if show_immediately:
                self.logger.info("[DEBUG] Показываем окно")
                self.root.deiconify()
                self.root.lift()
                self.visible = True
                self._ensure_topmost()
                self._enable_esc_hook()

                if self.auto_hide_enabled:
                    self.root.after(1500, self._start_visibility_monitor_delayed)

                self.logger.info(f"[DEBUG] Изображение загружено и показано: {win_width}x{win_height}")

        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка загрузки изображения: {e}")
            import traceback
            traceback.print_exc()
            self._image_loaded = False

    def _start_visibility_monitor_delayed(self):
        """Запускает монитор видимости с задержкой"""
        self.logger.info(
            f"[DEBUG][_start_visibility_monitor_delayed] НАЧАЛО: visible={self.visible}, _is_visible_by_user={self._is_visible_by_user}, _monitor_initialized={self._monitor_initialized}")

        # УБИРАЕМ ПРОВЕРКУ not self.visible — монитор должен работать даже когда оверлей скрыт
        if not self._is_visible_by_user:
            self.logger.info(
                "[DEBUG][_start_visibility_monitor_delayed] оверлей не должен быть виден, отменяем запуск монитора")
            return

        # === ДЛЯ АВТОЗАМЕНЫ: НЕ ЗАПУСКАЕМ ВНУТРЕННИЙ МОНИТОР, ТАК КАК ОН УПРАВЛЯЕТСЯ TranslationMonitor ===
        if self._is_auto_replace:
            self.logger.info(
                "[DEBUG][_start_visibility_monitor_delayed] автозамена, монитор управляется TranslationMonitor, пропускаем")
            return

        self.logger.info("[DEBUG][_start_visibility_monitor_delayed] запускаем монитор")

        # Увеличиваем задержку при запуске (при восстановлении из состояния)
        # Проверяем, был ли оверлей создан при запуске программы
        is_startup = hasattr(self, '_created_at_startup') and self._created_at_startup

        if is_startup:
            # При запуске программы даем больше времени на переключение окна
            self.logger.info("[DEBUG][_start_visibility_monitor_delayed] запуск при старте программы, задержка 3с")
            if self.root and self.root.winfo_exists():
                self.root.after(3000, self._start_visibility_monitor)
        else:
            # Обычная задержка
            self._start_visibility_monitor()

    def get_target_hwnd(self) -> int:
        return self._target_hwnd

    def _start_visibility_monitor(self):
        """Запускает монитор видимости - унифицированная логика с защитой от дублирования."""
        if not self.auto_hide_enabled:
            return

        # Для автозамены монитор управляется TranslationMonitor, не запускаем внутренний
        if self._is_auto_replace:
            self.logger.debug("[DEBUG] _start_visibility_monitor: автозамена, пропускаем")
            return

        # Предотвращаем создание нескольких мониторов
        if hasattr(self, '_monitor_timer') and self._monitor_timer is not None:
            return

        self._monitor_initialized = False
        self._last_active_hwnd = None

        try:
            import win32gui
            current_hwnd = win32gui.GetForegroundWindow()

            if current_hwnd == 0:
                if self._target_hwnd:
                    current_hwnd = self._target_hwnd
                else:
                    if self.root and self.root.winfo_exists():
                        self._monitor_timer = self.root.after(200, self._start_visibility_monitor)
                    return

            self._last_active_hwnd = current_hwnd
            self._monitor_initialized = True

        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось получить текущее активное окно: {e}")
            self._last_active_hwnd = None
            self._monitor_initialized = True

        def check_visibility():
            if not self.root or not self.root.winfo_exists():
                self._stop_visibility_monitor()
                return

            try:
                if self._is_dragging:
                    if self.root and self.root.winfo_exists():
                        self._monitor_timer = self.root.after(200, check_visibility)
                    return

                if not self._is_visible_by_user:
                    self._stop_visibility_monitor()
                    return

                # Сбрасываем флаг таймера перед вызовом
                self._monitor_timer = None
                self._check_and_update_visibility()

                # Перезапускаем таймер
                if self._is_visible_by_user and self.root and self.root.winfo_exists():
                    self._monitor_timer = self.root.after(200, check_visibility)

            except Exception as e:
                self.logger.warning(f"Ошибка в мониторе видимости: {e}")
                if self._is_visible_by_user and self.root and self.root.winfo_exists():
                    self._monitor_timer = self.root.after(200, check_visibility)

        if self.root and self.root.winfo_exists():
            self._monitor_timer = self.root.after(200, check_visibility)

    def _show_window_safe(self):
        """Безопасно показывает окно (вызывается из root.after)."""
        try:
            if self.root and self.root.winfo_exists():
                # ===== НЕ КОРРЕКТИРУЕМ ПОЗИЦИЮ, ЕСЛИ ЕСТЬ СОХРАНЕННАЯ =====
                if not (self._saved_position and hasattr(self, '_user_moved') and self._user_moved):
                    if self._last_window_rect:
                        x1, y1, x2, y2 = self._last_window_rect
                        width = x2 - x1
                        height = y2 - y1
                        current_x = self.root.winfo_x()
                        current_y = self.root.winfo_y()
                        if current_x != x1 or current_y != y1:
                            self.logger.info(
                                f"[DEBUG] _show_window_safe: корректируем позицию с {current_x},{current_y} на {x1},{y1}")
                            self.root.geometry(f"{width}x{height}+{x1}+{y1}")
                            self.root.update_idletasks()
                else:
                    self.logger.info("[DEBUG] _show_window_safe: сохраненная позиция есть, не корректируем")

                self.root.deiconify()
                self.logger.info("[DEBUG] _show_window_safe: root.deiconify() выполнен")
                self.root.lift()
                self.logger.info("[DEBUG] _show_window_safe: root.lift() выполнен")

                self.root.update_idletasks()
        except Exception as e:
            self.logger.error(f"[DEBUG] _show_window_safe: ошибка: {e}")

    def _lift_window_safe(self):
        """Безопасно поднимает окно (вызывается из root.after)."""
        try:
            if self.root and self.root.winfo_exists():
                self.root.lift()
                self.logger.info("[DEBUG] _lift_window_safe: root.lift() выполнен")
        except Exception as e:
            self.logger.error(f"[DEBUG] _lift_window_safe: ошибка: {e}")

    def _show_internal(self, force: bool = False):
        """Внутренний метод для показа оверлея и панели."""
        if hasattr(self, '_showing_in_progress') and self._showing_in_progress:
            return
        self._showing_in_progress = True

        try:
            if self._mouse_over or self._hidden_by_mouse:
                self.logger.debug("[DEBUG] _show_internal: мышь в зоне оверлея, не показываем")
                return

            if self._hidden_by_user:
                self.logger.debug("[DEBUG] _show_internal: оверлей скрыт пользователем")
                return

            if not self._last_image_path or not self._last_window_rect:
                return

            if self.visible:
                self.logger.debug("[DEBUG] _show_internal: оверлей уже виден")
                return

            self._suppress_enter_events = True

            if self._image_loaded and self.tk_image is not None:
                try:
                    self.root.after(0, self._show_window_safe)
                    self.visible = True
                    self._ensure_topmost()
                    if self._saved_position:
                        x, y = self._saved_position
                        current_x = self.root.winfo_x()
                        current_y = self.root.winfo_y()
                        if abs(current_x - x) > 5 or abs(current_y - y) > 5:
                            self.root.geometry(f"+{x}+{y}")
                    self._enable_esc_hook()
                    if self.auto_hide_enabled:
                        self._start_visibility_monitor()

                    if self._edit_mode_enabled:
                        self._show_title_bar()

                    self.root.after(500, lambda: setattr(self, '_suppress_enter_events', False))
                    return
                except Exception as e:
                    self.logger.warning(f"[DEBUG][_show_internal] ошибка: {e}")

            self._load_and_show_image(self._last_image_path, self._last_window_rect)
            self._image_loaded = True

            if self._edit_mode_enabled:
                self._show_title_bar()

        except Exception as e:
            self.logger.error(f"[DEBUG] _show_internal: ошибка: {e}")

        finally:
            self._showing_in_progress = False

    def _is_template_found(self) -> bool:
        """
        Проверяет, найден ли шаблон для этого оверлея в мониторе.
        Возвращает True если шаблон найден или это не автозамена.
        """
        if not self._is_auto_replace:
            return True

        if not self._template_id:
            return False

        # Ищем шаблон в мониторе
        try:
            if hasattr(self, '_overlay_manager') and self._overlay_manager:
                parent = self._overlay_manager.parent
                if parent and hasattr(parent, 'translation_monitor'):
                    monitor = parent.translation_monitor
                    if monitor:
                        for template in monitor.templates:
                            if template.get('hash') == self._template_id:
                                # Проверяем, найден ли шаблон
                                if template.get('found', False):
                                    return True
                                # Также проверяем, есть ли оверлей и виден ли он
                                overlay = template.get('overlay')
                                if overlay and overlay.visible:
                                    return True
                                break
        except Exception as e:
            self.logger.warning(f"[DEBUG] _is_template_found: ошибка: {e}")

        return False

    def _get_saved_position(self) -> Optional[Tuple[int, int]]:
        """Возвращает сохраненную позицию для этого оверлея."""
        # Используем сохраненную позицию только если оверлей был перемещен пользователем
        if not hasattr(self, '_user_moved') or not self._user_moved:
            return None

        if not hasattr(self, '_overlay_manager') or not self._overlay_manager:
            return None
        if not self._template_id:
            return None
        return self._overlay_manager.get_saved_position(self._template_id)

    def _hide_internal(self):
        """Внутренний метод для скрытия оверлея и панели."""
        if hasattr(self, '_hiding_in_progress') and self._hiding_in_progress:
            return
        self._hiding_in_progress = True

        try:
            # Проверяем, не активно ли окно выбора области
            try:
                import win32gui
                active_hwnd = win32gui.GetForegroundWindow()
                if self._is_selection_window_active(active_hwnd):
                    return
                if hasattr(self, '_overlay_manager') and self._overlay_manager:
                    parent = self._overlay_manager.parent
                    if parent and hasattr(parent, '_capture_mode') and parent._capture_mode:
                        return
            except:
                pass

            # === ВСЕГДА СКРЫВАЕМ ПАНЕЛЬ ===
            self._hide_title_bar()

            self.visible = False
            try:
                self.root.withdraw()
                self._disable_esc_hook()
            except Exception as e:
                self.logger.error(f"[DEBUG][_hide_internal] ОШИБКА: {e}")

        finally:
            self._hiding_in_progress = False

    def _stop_visibility_monitor(self):
        """Останавливает монитор видимости с очисткой таймера."""
        if self._monitor_timer is not None:
            try:
                if self.root and self.root.winfo_exists():
                    self.root.after_cancel(self._monitor_timer)
            except Exception as e:
                self.logger.warning(f"Ошибка отмены таймера: {e}")
            self._monitor_timer = None

    def _ensure_topmost(self):
        """Гарантирует, что оверлей находится поверх всех окон с проверкой на существование окна."""
        try:
            if not self.root or not self.root.winfo_exists():
                return

            overlay_hwnd = int(self.root.winfo_id())
            if overlay_hwnd == 0:
                return

            # Устанавливаем стиль WS_EX_TOPMOST только если его нет
            try:
                ex_style = win32gui.GetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE)
                if not (ex_style & win32con.WS_EX_TOPMOST):
                    new_ex_style = ex_style | win32con.WS_EX_TOPMOST
                    win32gui.SetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE, new_ex_style)
            except Exception as e:
                self.logger.warning(f"[DEBUG] _ensure_topmost: ошибка установки стиля: {e}")
                return

            # Перемещаем окно на самый верх с проверкой
            try:
                win32gui.SetWindowPos(
                    overlay_hwnd,
                    win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE
                )
            except Exception as e:
                self.logger.warning(f"[DEBUG] _ensure_topmost: ошибка SetWindowPos: {e}")
                # Пробуем через tkinter как fallback
                self.root.lift()
                self.root.attributes('-topmost', True)

        except Exception as e:
            self.logger.warning(f"[DEBUG] _ensure_topmost: общая ошибка: {e}")

    def _is_selection_window_active(self, active_hwnd: int) -> bool:
        """Проверяет, является ли активное окно окном выделения области."""
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent

            # Проверка по флагу
            if hasattr(parent, '_capture_mode') and parent._capture_mode:
                return True

            # Проверка по HWND
            if hasattr(parent, '_area_selector') and parent._area_selector:
                try:
                    selector_root = parent._area_selector.root
                    if selector_root and selector_root.winfo_exists():
                        selector_hwnd = int(selector_root.winfo_id())
                        if selector_hwnd == active_hwnd:
                            return True
                except:
                    pass

            # Проверка по тексту окна
            try:
                import win32gui
                window_text = win32gui.GetWindowText(active_hwnd)
                if window_text and "Выделите область" in window_text:
                    return True
            except:
                pass

        return False

    def toggle(self):
        """Переключает видимость оверлея и возвращает фокус на целевое окно"""
        self.logger.info(
            f"[DEBUG][toggle] НАЧАЛО: visible={self.visible}, _is_visible_by_user={self._is_visible_by_user}")

        if self.visible:
            self.logger.info("[DEBUG][toggle] оверлей виден -> скрываем")
            self.hide(by_user=True)
        else:
            self.logger.info("[DEBUG][toggle] оверлей скрыт -> показываем")
            self._hidden_by_user = False
            self._is_visible_by_user = True
            if self._last_image_path and self._last_window_rect:
                self.logger.info(
                    f"[DEBUG][toggle] показываем оверлей с сохраненным изображением: {self._last_image_path}")
                self._load_and_show_image(self._last_image_path, self._last_window_rect)
            else:
                self.logger.warning("[DEBUG][toggle] нет сохраненного изображения для показа")

        self.logger.info("[DEBUG][toggle] возвращаем фокус на целевое окно")
        self.restore_target_window_focus()
        self.logger.info(f"[DEBUG][toggle] ЗАВЕРШЕНИЕ: visible={self.visible}")

    def _get_overlay_status(self) -> tuple:
        """
        Определяет тип оверлея и статус шаблона.

        Returns:
            tuple: (overlay_type, template_found)
            - overlay_type: 'auto_replace' или 'normal'
            - template_found: True/False (для автозамены всегда True, если монитор выключен)
        """
        overlay_type = 'normal'
        template_found = True

        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'translation_monitor'):
                monitor = parent.translation_monitor
                if monitor:
                    # Проверяем, запущен ли монитор
                    monitor_running = monitor.is_running()
                    for template in monitor.templates:
                        if template.get('overlay') is self:
                            overlay_type = 'auto_replace'
                            # Если монитор выключен — считаем шаблон найденным (не скрываем)
                            if not monitor_running:
                                template_found = True
                            else:
                                template_found = template.get('found', False)
                            break

        return overlay_type, template_found

    def set_auto_replace_mode(self, enabled: bool):
        """
        Устанавливает режим автозамены для оверлея.
        В этом режиме оверлей не скрывается при наведении мыши.
        """
        self.logger.info(
            f"[DEBUG] set_auto_replace_mode: enabled={enabled}, overlay={self}, template_id={self._template_id}, image_path={self._last_image_path}")
        self._is_auto_replace = enabled
        self._creation_time = time.time()
        self.logger.info(f"[DEBUG] set_auto_replace_mode: _is_auto_replace установлен в {self._is_auto_replace}")
        if enabled:
            # Для автозамены увеличиваем стабильное время, чтобы дать монитору найти шаблон
            self._monitor_stable_time = time.time() + 3.0
            self.logger.info(f"[DEBUG] set_auto_replace_mode: _monitor_stable_time={self._monitor_stable_time}")

    def set_auto_hide(self, enabled: bool):
        """Устанавливает режим автоскрытия"""
        self.logger.info(f"set_auto_hide вызван: enabled={enabled}, текущее значение={self.auto_hide_enabled}")

        self.auto_hide_enabled = enabled
        self.logger.info(f"Режим автоскрытия установлен: {enabled}")

        if not enabled:
            self._stop_visibility_monitor()
            self.logger.info("Автоскрытие отключено, монитор остановлен")
            # Не показываем оверлей автоматически при отключении автоскрытия
            # Оверлей управляется монитором
        else:
            if self.visible and self._is_visible_by_user:
                self._start_visibility_monitor()
                self.logger.info("Автоскрытие включено, монитор запущен")
                self._check_and_update_visibility()
            elif not self.visible and self._is_visible_by_user and self._last_image_path and self._last_window_rect:
                self.logger.info("Автоскрытие включено, показываем оверлей и запускаем монитор")
                self._load_and_show_image(self._last_image_path, self._last_window_rect)
            elif not self.visible and not self._is_visible_by_user and self._last_image_path and self._last_window_rect:
                self.logger.info("Автоскрытие включено, но оверлей скрыт пользователем")
                pass

    def close(self):
        self.logger.info("close() вызван")

        # === ПРИНУДИТЕЛЬНО УНИЧТОЖАЕМ ПАНЕЛЬ ЗАГОЛОВКА ===
        try:
            if self._title_bar_window and self._title_bar_window.winfo_exists():
                self.logger.info("[DEBUG] close: уничтожаем панель заголовка")
                self._title_bar_window.destroy()
            self._title_bar_window = None
            self._title_canvas = None
            self._title_bar_visible = False
        except Exception as e:
            self.logger.warning(f"[DEBUG] close: ошибка уничтожения панели: {e}")
            self._title_bar_window = None
            self._title_canvas = None
            self._title_bar_visible = False

        self.logger.info("[DEBUG] Панель заголовка уничтожена при закрытии оверлея")

        # === УВЕДОМЛЯЕМ МОНИТОР ===
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'translation_monitor') and parent.translation_monitor:
                for template in parent.translation_monitor.templates:
                    if template.get('overlay') is self:
                        template['overlay'] = None
                        self.logger.info(
                            f"[MONITOR] Ссылка на оверлей сброшена для шаблона #{template.get('pair_index')}")
                        break

        # Очищаем Canvas
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.delete("all")
                self.canvas.update_idletasks()
                self.logger.info("[DEBUG] Canvas очищен при закрытии оверлея")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось очистить Canvas при закрытии: {e}")

        self._stop_visibility_monitor()
        self._disable_esc_hook()
        self._context_menu_visible = False

        # Получаем координаты оверлея до закрытия
        rect = None
        try:
            if self.root and self.root.winfo_exists():
                x = self.root.winfo_x()
                y = self.root.winfo_y()
                w = self.root.winfo_width()
                h = self.root.winfo_height()
                rect = (x, y, x + w, y + h)
                self.logger.info(f"[DEBUG] Координаты оверлея перед закрытием: {rect}")
        except:
            pass

        if self._drag_stop_timer:
            try:
                self.root.after_cancel(self._drag_stop_timer)
            except:
                pass
            self._drag_stop_timer = None

        # Скрываем и закрываем окно
        try:
            if self.root and self.root.winfo_exists():
                self.root.withdraw()
                self.root.update_idletasks()
                self.logger.info("[DEBUG] Окно скрыто через withdraw")
                import time
                time.sleep(0.02)
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось скрыть окно: {e}")

        try:
            self._images.clear()
            self.tk_image = None
            self._last_image_path = None
            self._last_window_rect = None
            self._saved_position = None
            self._is_fullscreen_target = False
            self.root.destroy()
            self.logger.info("Оверлей закрыт")
        except:
            pass

        # Перерисовываем область
        if rect:
            try:
                import win32gui
                import win32con

                target_hwnd = self._target_hwnd

                if target_hwnd and win32gui.IsWindow(target_hwnd):
                    win32gui.InvalidateRect(target_hwnd, (rect[0], rect[1], rect[2], rect[3]), True)
                    win32gui.UpdateWindow(target_hwnd)
                    win32gui.RedrawWindow(
                        target_hwnd,
                        (rect[0], rect[1], rect[2], rect[3]),
                        None,
                        win32con.RDW_INVALIDATE | win32con.RDW_UPDATENOW | win32con.RDW_ALLCHILDREN | win32con.RDW_FRAME | win32con.RDW_ERASE
                    )
                else:
                    hwnd_desktop = win32gui.GetDesktopWindow()
                    win32gui.InvalidateRect(hwnd_desktop, (rect[0], rect[1], rect[2], rect[3]), True)
                    win32gui.UpdateWindow(hwnd_desktop)
                    win32gui.RedrawWindow(
                        hwnd_desktop,
                        (rect[0], rect[1], rect[2], rect[3]),
                        None,
                        win32con.RDW_INVALIDATE | win32con.RDW_UPDATENOW | win32con.RDW_ALLCHILDREN | win32con.RDW_FRAME | win32con.RDW_ERASE
                    )
            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось перерисовать область: {e}")

    def _is_system_window(self, active_hwnd: int) -> bool:
        """Проверяет, является ли окно системным (не нашим)."""
        try:
            import win32gui
            class_name = win32gui.GetClassName(active_hwnd)
            return class_name in ['MultitaskingViewFrame', 'ForegroundStaging']
        except:
            return False

    def _is_target_window_active(self, active_hwnd: int) -> bool:
        """Проверяет, является ли активное окно целевым для оверлея."""
        # Проверяем через менеджер
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            for overlay in self._overlay_manager.overlays:
                if overlay is not None:
                    target_hwnd = overlay.get_target_hwnd()
                    if target_hwnd is not None and active_hwnd == target_hwnd:
                        return True

        # Проверяем напрямую
        if active_hwnd == self._target_hwnd:
            return True

        # Проверяем главное окно приложения
        try:
            if hasattr(self.root, 'master'):
                master = self.root.master
                if master and master.winfo_exists():
                    app_hwnd = int(master.winfo_id())
                    if active_hwnd == app_hwnd:
                        return True
        except:
            pass

        return False

    def _update_close_button_position(self):
        """Обновляет позицию кнопки закрытия после перетаскивания."""
        if not self._close_button_visible or not self.canvas or not self.canvas.winfo_exists():
            return

        # !!! НЕ ОБНОВЛЯЕМ ПОЗИЦИЮ, ЕСЛИ ИДЁТ ПЕРЕТАСКИВАНИЕ
        if self._is_dragging:
            self.logger.debug("[DEBUG] _update_close_button_position: пропускаем (идет перетаскивание)")
            return

        try:
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()

            if canvas_width < 50 or canvas_height < 50:
                return

            screen_width = self.root.winfo_screenwidth()
            screen_height = self.root.winfo_screenheight()

            overlay_x = self.root.winfo_x()
            overlay_y = self.root.winfo_y()

            btn_size = 28
            padding = 8

            right_edge = min(overlay_x + canvas_width, screen_width)
            x_pos = (right_edge - overlay_x) - btn_size - padding
            if x_pos < 0:
                x_pos = padding

            top_edge = max(overlay_y, 0)
            y_pos = (top_edge - overlay_y) + padding
            if y_pos < 0:
                y_pos = padding
            if y_pos + btn_size > canvas_height:
                y_pos = canvas_height - btn_size - padding

            # Удаляем старую кнопку и создаём заново
            self.canvas.delete('close_btn')
            self._close_button_id = None

            self._close_button_id = self.canvas.create_oval(
                x_pos, y_pos,
                x_pos + btn_size, y_pos + btn_size,
                fill='#ff0000',
                outline='#cc0000',
                width=2,
                tags=('close_btn',)
            )

            self.canvas.create_text(
                x_pos + btn_size // 2,
                y_pos + btn_size // 2 + 1,
                text='✕',
                fill='white',
                font=('Arial', 16, 'bold'),
                tags=('close_btn',)
            )

            self.canvas.tag_bind('close_btn', '<Button-1>', self._on_close_click)

            self.logger.debug(f"[DEBUG] Позиция кнопки закрытия обновлена: x={x_pos}, y={y_pos}")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Ошибка обновления позиции кнопки закрытия: {e}")

    def _reset_right_click_flag(self):
        """Сбрасывает флаг обработки правого клика."""
        self._right_click_processing = False
        self.logger.info("[DEBUG] _reset_right_click_flag: флаг _right_click_processing сброшен")

    def _start_menu_close_monitor(self):
        """Запускает мониторинг закрытия контекстного меню."""

        def check_menu_closed():
            if not self._context_menu_visible:
                return

            try:
                import win32gui

                active_hwnd = win32gui.GetForegroundWindow()

                # Если активное окно - целевое, значит меню закрыто
                if active_hwnd == self._target_hwnd or active_hwnd == 0:
                    self._context_menu_visible = False
                    self.logger.info("[DEBUG] Контекстное меню закрыто (фокус вернулся на целевое окно)")

                    # !!! ИСПРАВЛЕНИЕ: НЕ ПЕРЕЗАПУСКАЕМ МОНИТОР, ОН УЖЕ РАБОТАЕТ
                    # Монитор видимости продолжает работать непрерывно
                    # Убираем вызов _start_visibility_monitor() чтобы не создавать дублирующиеся таймеры
                    return

                # Иначе проверяем через 100мс
                if self.root and self.root.winfo_exists():
                    self.root.after(100, check_menu_closed)

            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка в мониторе меню: {e}")
                self._context_menu_visible = False

        if self.root and self.root.winfo_exists():
            self.root.after(50, check_menu_closed)

    def _start_menu_monitor(self):
        """Запускает мониторинг контекстного меню."""

        def check_menu():
            if not self._context_menu_visible:
                return

            try:
                import win32gui
                active_hwnd = win32gui.GetForegroundWindow()

                # Проверяем, является ли активное окно меню (класс "Menu")
                class_name = win32gui.GetClassName(active_hwnd)

                if class_name != "Menu":
                    # Если активное окно не меню - меню закрыто
                    self._context_menu_visible = False
                    self.logger.info("[DEBUG] Контекстное меню закрыто (активное окно не Menu)")
                    return
                else:
                    # Меню всё ещё открыто, проверяем снова через 100мс
                    self.logger.debug(f"[DEBUG] Контекстное меню всё ещё открыто (class={class_name})")
                    self.root.after(100, check_menu)

            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка в мониторе меню: {e}")
                self._context_menu_visible = False

        if self.root and self.root.winfo_exists():
            self.root.after(50, check_menu)

    def _update_close_button_visibility(self):
        """Обновляет видимость кнопки закрытия в зависимости от режима редактирования."""
        should_be_visible = self._edit_mode_enabled and self.visible and self._image_loaded

        if should_be_visible and not self._close_button_visible:
            self._show_close_button()
        elif not should_be_visible and self._close_button_visible:
            self._hide_close_button()

        self.logger.debug(
            f"[DEBUG] Кнопка закрытия: видимость={should_be_visible}, текущее состояние={self._close_button_visible}")

    def _on_escape(self, event):
        """Обработчик ESC для оверлея - скрывает оверлей (не удаляет)."""
        self.logger.info("[DEBUG][_on_escape] ESC нажат - скрываем оверлей")
        # В режиме редактирования ESC обрабатывается через OverlayManager для удаления
        # Поэтому здесь просто скрываем оверлей (менеджер сам решит, удалять или нет)
        self._stop_visibility_monitor()
        self.visible = False
        self._disable_esc_hook()
        try:
            self.root.withdraw()
            self.logger.info("[DEBUG][_on_escape] оверлей скрыт")
        except Exception as e:
            self.logger.error(f"[DEBUG][_on_escape] ОШИБКА: {e}")
        self.restore_target_window_focus()
        return "break"

    def _global_esc_handler(self, event):
        """Глобальный обработчик ESC - используется как fallback."""
        # В режиме редактирования - удаляем оверлей под мышью через менеджер
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            return self._overlay_manager._global_esc_handler(event)
        # Иначе просто скрываем
        if self.visible:
            self.hide()
            self.restore_target_window_focus()
            return False
        return True

    def reset(self):
        """Полностью сбрасывает состояние оверлея"""
        self.logger.info("[DEBUG] reset() - сброс состояния оверлея")

        if self.visible:
            self.hide()

        self._last_image_path = None
        self._last_window_rect = None
        self._target_hwnd = None
        self._is_fullscreen_target = False
        self._is_visible_by_user = False
        self.visible = False
        self._show_time = 0

        self._stop_visibility_monitor()
        self._disable_esc_hook()

        self._images.clear()
        self.tk_image = None

        self.logger.info("[DEBUG] reset() - состояние оверлея сброшено")

    def get_overlay_hwnd(self) -> Optional[int]:
        """Возвращает HWND окна оверлея"""
        try:
            if self.root and self.root.winfo_exists():
                return int(self.root.winfo_id())
        except:
            pass
        return None

    def restore_target_window_focus(self):
        """Возвращает фокус на целевое окно (игру)"""
        if self._target_hwnd is not None:
            try:
                self.logger.info(f"Возврат фокуса на целевое окно: {self._target_hwnd}")
                win32gui.ShowWindow(self._target_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self._target_hwnd)
                self.logger.info("Фокус возвращен на целевое окно")
                return True
            except Exception as e:
                self.logger.warning(f"Не удалось вернуть фокус на целевое окно: {e}")
                return False
        return False

    def _check_if_window_minimized(self, hwnd: int) -> bool:
        """Проверяет, свернуто ли окно"""
        try:
            return win32gui.IsIconic(hwnd)
        except:
            return False

    def _restore_fullscreen_window(self):
        """Восстанавливает фокус на полноэкранное приложение - упрощенная версия"""
        if self._is_fullscreen_target and self._target_hwnd:
            try:
                self.logger.info("Восстановление фокуса на полноэкранное приложение")
                win32gui.SetForegroundWindow(self._target_hwnd)
                self.logger.info("Фокус восстановлен на полноэкранное приложение")
            except Exception as e:
                self.logger.warning(f"Не удалось восстановить фокус на игру: {e}")

    def _on_drag_stop_timeout(self):
        """Таймаут после остановки перетаскивания"""
        self._drag_stop_timer = None
        self.logger.info("[DEBUG] Таймаут после перетаскивания (500мс), монитор может работать")
        try:
            import win32gui
            active_hwnd = win32gui.GetForegroundWindow()
            if active_hwnd:
                class_name = win32gui.GetClassName(active_hwnd)
                window_text = win32gui.GetWindowText(active_hwnd)
                self.logger.info(
                    f"[DEBUG] После таймаута активное окно: hwnd={active_hwnd}, class='{class_name}', title='{window_text}'")
        except Exception as e:
            self.logger.info(f"[DEBUG] Ошибка получения активного окна после таймаута: {e}")

    def is_fullscreen_window(self, hwnd: int) -> bool:
        """Проверяет, находится ли окно в полноэкранном режиме"""
        if hwnd is None:
            return False

        try:
            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect
            win_width = x2 - x1
            win_height = y2 - y1

            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

            is_fullscreen = (win_width >= screen_width - 50 and win_height >= screen_height - 50)

            if not is_fullscreen:
                if x1 <= -10 and y1 <= -10 and x2 >= screen_width - 1 and y2 >= screen_height - 1:
                    is_fullscreen = True

            if is_fullscreen:
                self.logger.info(
                    f"Окно {hwnd} определено как полноэкранное (размеры: {win_width}x{win_height}, позиция: {x1},{y1}-{x2},{y2})")

            return is_fullscreen

        except Exception as e:
            self.logger.warning(f"Ошибка проверки полноэкранного режима: {e}")
            return False

    def _enable_esc_hook(self):
        """Включает хук ESC через менеджер."""
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._use_manager_esc = True
            self.logger.info("ESC управляется через OverlayManager")
        else:
            if not self._esc_hook_active:
                try:
                    keyboard.on_press_key('esc', self._global_esc_handler)
                    self._esc_hook_active = True
                    self.logger.info("Глобальный хук ESC включен (fallback)")
                except Exception as e:
                    self.logger.warning(f"Не удалось включить глобальный хук ESC: {e}")

    def _disable_esc_hook(self):
        if self._esc_hook_active:
            try:
                keyboard.unhook_key('esc')
                self._esc_hook_active = False
                self.logger.info("Глобальный хук ESC отключен")
            except Exception as e:
                self.logger.warning(f"Не удалось отключить глобальный хук ESC: {e}")

    def show_fullscreen(self, image_path: Path):
        self.logger.info(f"show_fullscreen вызван: image_path={image_path}")

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        window_rect = (0, 0, sw, sh)

        self._last_image_path = image_path
        self._last_window_rect = window_rect
        self._is_visible_by_user = True

        self._load_and_show_image(image_path, window_rect)

    def is_visible(self) -> bool:
        return self.visible
