"""
Модуль для оверлейного окна с переведенным изображением
"""

import logging
import tempfile
import time
from pathlib import Path
from typing import Optional, Tuple

# PIL
from PIL import Image, ImageTk

# Tkinter
import tkinter as tk

# Keyboard
import keyboard

# Windows API - ИСПРАВЛЕННЫЕ ИМПОРТЫ
import win32gui
import win32con
import win32api
from src.window_utils import find_window_by_app_name


class OverlayWindow:
    """Класс для оверлейного окна (Toplevel, работает в главном потоке)"""

    __slots__ = (
        'logger', 'visible', 'temp_dir', 'tk_image', '_target_rect',
        '_esc_hook_active', '_use_manager_esc', '_images', '_last_image_path',
        '_last_window_rect', '_target_hwnd', '_app_name',
        '_monitor_timer',
        '_is_visible_by_user', '_is_dragging', '_drag_stop_timer',
        '_saved_position', '_is_fullscreen_target', '_fullscreen_restore_needed',
        '_show_time', 'auto_hide_enabled', '_image_loaded', '_overlay_active',
        '_last_active_hwnd', '_monitor_initialized', '_monitor_stable_time',
        '_edit_mode_enabled', '_mouse_over', '_hidden_by_mouse',
        '_is_window_screenshot', '_context_menu_visible', '_right_click_processing',
        '_hidden_by_user', '_is_auto_replace', '_creation_time', '_template_id',
        '_suppress_enter_events', '_last_mouse_x', '_last_mouse_y',
        '_mouse_position_known', '_user_moved', '_created_at_startup',
        '_is_temporary', '_temp_timer', '_temp_created_at', '_temp_lifetime',
        '_edit_frame', '_edit_frame_visible',
        'root', 'canvas',
        '_drag_data', '_close_button_window', '_close_button_visible',
        '_showing_in_progress', '_hiding_in_progress', '_updating_visibility',
        '_overlay_manager', '_update_timer',
        '_offset_x', '_offset_y',
        '_drag_start_x', '_drag_start_y',
        '_title_bar_visible', '_title_bar_hide_timer',
        '_title_bar_hide_delay_ms', '_mouse_over_title_bar',
        '_image_offset_y', '_saved_window_height', '_saved_window_y',
        '_closing',
        '_save_timer', '_last_frame_update',
        '_is_f2_overlay'  # <-- ФЛАГ ДЛЯ F2-ОВЕРЛЕЯ
    )

    def __init__(self, parent=None, app_title="Перевод скриншотов", auto_hide_enabled=True):
        """Инициализация оверлейного окна"""
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
        self._app_name = None
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
        self._created_at_startup = False

        # ============================================================
        # ФЛАГ: идентифицирует F2-оверлей
        # ============================================================
        self._is_f2_overlay = False

        # Временный режим
        self._is_temporary = False
        self._temp_timer = None
        self._temp_created_at = 0
        self._temp_lifetime = 180

        # Рамка редактирования
        self._edit_frame = None
        self._edit_frame_visible = False

        # Атрибуты для смещения
        self._offset_x = 0
        self._offset_y = 0

        # Флаг закрытия
        self._closing = False

        # Атрибуты для перетаскивания
        self._drag_start_x = 0
        self._drag_start_y = 0

        # Атрибуты для заголовка (если используется)
        self._title_bar_visible = False
        self._title_bar_hide_timer = None
        self._title_bar_hide_delay_ms = 2000
        self._mouse_over_title_bar = False
        self._image_offset_y = 0
        self._saved_window_height = 0
        self._saved_window_y = 0

        # Таймер сохранения (для оптимизации)
        self._save_timer = None
        self._last_frame_update = 0

        # Создаем окно
        self.root = tk.Toplevel(parent) if parent else tk.Toplevel()
        self.root.title("Перевод")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#000000')
        self.root.withdraw()

        self.canvas = tk.Canvas(self.root, bg='#000000', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self._drag_data = {"x": 0, "y": 0}

        # Привязки событий
        self.canvas.bind('<ButtonPress-1>', self._start_drag)
        self.canvas.bind('<B1-Motion>', self._on_drag)
        self.canvas.bind('<ButtonRelease-1>', self._stop_drag)

        self.canvas.bind('<Button-3>', self._on_right_click)
        self.root.bind('<Button-3>', self._on_right_click)

        self.canvas.bind('<Enter>', self._on_mouse_enter)
        self.canvas.bind('<Leave>', self._on_mouse_leave)
        self.root.bind('<Enter>', self._on_mouse_enter)
        self.root.bind('<Leave>', self._on_mouse_leave)

        # ============================================================
        # ДОБАВЛЯЕМ ЛОКАЛЬНЫЙ ОБРАБОТЧИК ESC ДЛЯ ОВЕРЛЕЯ
        # ============================================================
        self.root.bind('<Escape>', self._on_escape_local)
        self.canvas.bind('<Escape>', self._on_escape_local)
        self.logger.info("[OVERLAY] Локальный обработчик ESC добавлен")

        self.logger.info("OverlayWindow инициализирован")

    def _on_escape_local(self, event):
        """Локальный обработчик ESC для оверлея."""
        self.logger.info("[OVERLAY][ESC] Локальный ESC перехвачен")

        # Проверяем, является ли этот оверлей F2-оверлеем
        is_f2_overlay = hasattr(self, '_is_f2_overlay') and self._is_f2_overlay

        if is_f2_overlay:
            # Пытаемся скрыть F2-оверлей через родительское приложение
            if hasattr(self, '_overlay_manager') and self._overlay_manager:
                parent = self._overlay_manager.parent
                if parent and hasattr(parent, 'hide_f2_overlay_under_cursor'):
                    if parent.hide_f2_overlay_under_cursor():
                        self.logger.info("[OVERLAY][ESC] F2-оверлей скрыт через родителя")
                        return "break"

        # Если не удалось скрыть через родителя, просто скрываем текущий оверлей
        self.logger.info("[OVERLAY][ESC] Скрываем текущий оверлей")
        self.hide(by_user=True)

        # Сохраняем состояние
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager.save_overlay_state(immediate=True)
            self.logger.info("[OVERLAY][ESC] Состояние сохранено")

        return "break"

    def _delayed_save_state(self):
        """Отложенное сохранение состояния после перетаскивания."""
        self._save_timer = None
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager.save_overlay_state()
            self.logger.info("[DEBUG] _delayed_save_state: состояние сохранено")

    def can_be_shown_by_monitor(self) -> bool:
        """
        Проверяет, можно ли показывать оверлей через монитор автозамены.
        Возвращает False, только если оверлей скрыт мышью или пользователем (F1).
        """
        # Если мышь над оверлеем — не показываем
        if self._hidden_by_mouse or self._mouse_over:
            return False
        # Если пользователь явно скрыл оверлей (F1) — не показываем
        if self._hidden_by_user:
            return False
        # Для автозамены НЕ проверяем _is_visible_by_user,
        # так как этот флаг используется для ручного управления (F1)
        return True

    def _update_target_hwnd(self) -> bool:
        """
        Обновляет _target_hwnd, ища окно по имени приложения.
        Возвращает True, если окно найдено.
        """
        if not self._app_name or self._app_name == "Неизвестно":
            return False

        # Если текущий HWND валиден, проверяем его
        if self._target_hwnd:
            try:
                import win32gui
                if win32gui.IsWindow(self._target_hwnd) and win32gui.IsWindowVisible(self._target_hwnd):
                    return True
            except:
                pass

        # Ищем окно по имени приложения
        from src.window_utils import find_window_by_app_name
        found_hwnd = find_window_by_app_name(self._app_name)

        if found_hwnd:
            self._target_hwnd = found_hwnd
            self.logger.info(f"[MONITOR] Найдено окно для {self._app_name}: HWND={found_hwnd}")
            return True

        return False

    def get_app_name(self) -> Optional[str]:
        """Возвращает имя приложения для этого оверлея."""
        return self._app_name

    def set_app_name(self, app_name: str):
        """Устанавливает имя приложения для этого оверлея."""
        self._app_name = app_name

    def get_target_hwnd(self) -> int:
        return self._target_hwnd

    def set_temporary_mode(self, enabled: bool, lifetime_seconds: int = 180):
        """
        Устанавливает режим временного оверлея.
        enabled: True - оверлей будет удалён через lifetime_seconds
        lifetime_seconds: время жизни в секундах (по умолчанию 180 = 3 минуты)
        """
        self._is_temporary = enabled
        if enabled:
            self._temp_created_at = time.time()
            self._temp_lifetime = lifetime_seconds
            self._start_temp_timer(lifetime_seconds)
            self.logger.info(f"[TEMP] Временный режим включен, время жизни: {lifetime_seconds}с")
        else:
            self._stop_temp_timer()
            self.logger.info("[TEMP] Временный режим выключен")

    def _start_temp_timer(self, lifetime_seconds: int):
        """Запускает таймер для автоматического удаления оверлея"""
        self._stop_temp_timer()
        if self.root and self.root.winfo_exists():
            self._temp_timer = self.root.after(
                lifetime_seconds * 1000,
                self._on_temp_timeout
            )
            self.logger.info(f"[TEMP] Таймер запущен: {lifetime_seconds}с, оверлей будет удалён")

    def _stop_temp_timer(self):
        """Останавливает таймер удаления"""
        if self._temp_timer is not None:
            try:
                if self.root and self.root.winfo_exists():
                    self.root.after_cancel(self._temp_timer)
            except Exception as e:
                self.logger.warning(f"[TEMP] Ошибка отмены таймера: {e}")
            self._temp_timer = None

    def _on_temp_timeout(self):
        """Обработчик таймаута - удаляет оверлей"""
        self.logger.info("[TEMP] Время жизни истекло, удаляем оверлей")
        self._stop_temp_timer()
        # Удаляем через менеджер
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager.remove_overlay(self)

    def _update_image_position(self):
        """Обновляет позицию изображения без смещения."""
        try:
            if not self._image_loaded or self.tk_image is None:
                return

            width = self.root.winfo_width()
            height = self.root.winfo_height()
            img_width = self.tk_image.width()
            img_height = self.tk_image.height()

            # Центрируем изображение
            x = (width - img_width) // 2
            y = (height - img_height) // 2

            # Удаляем старое изображение и создаём заново
            self.canvas.delete('image')
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image, tags=('image',))

            # Если есть рамка - обновляем её
            if self._edit_frame_visible:
                self._update_edit_frame_position()

            self.logger.debug(f"[DEBUG] _update_image_position: pos=({x}, {y})")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Ошибка обновления позиции изображения: {e}")

    def _show_edit_frame(self):
        """Показывает чёрную рамку вокруг оверлея (режим редактирования)."""
        if not self.root or not self.root.winfo_exists():
            return

        if not self._image_loaded:
            return

        if self._edit_frame_visible:
            return

        try:
            width = self.root.winfo_width()
            height = self.root.winfo_height()

            self._edit_frame = self.canvas.create_rectangle(
                0, 0, width, height,
                outline='#000000',
                width=3,
                tags=('edit_frame',)
            )
            self._edit_frame_visible = True
            self.logger.info("[DEBUG] _show_edit_frame: рамка показана")

        except Exception as e:
            self.logger.warning(f"[DEBUG] Ошибка показа рамки: {e}")

    def _hide_edit_frame(self):
        """Скрывает чёрную рамку."""
        if not self._edit_frame_visible:
            return

        try:
            self.canvas.delete('edit_frame')
            self._edit_frame = None
            self._edit_frame_visible = False
            self.logger.info("[DEBUG] _hide_edit_frame: рамка скрыта")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Ошибка скрытия рамки: {e}")

    def _update_edit_frame_position(self):
        """Обновляет размеры рамки при изменении размера оверлея (оптимизированно)."""
        if not self._edit_frame_visible or not self._edit_frame:
            return

        # Используем дебаунс, чтобы не обновлять рамку слишком часто
        current_time = time.time()
        if hasattr(self, '_last_frame_update') and current_time - self._last_frame_update < 0.05:
            return
        self._last_frame_update = current_time

        try:
            width = self.root.winfo_width()
            height = self.root.winfo_height()
            self.canvas.coords(self._edit_frame, 0, 0, width, height)
            self.canvas.tag_raise('edit_frame')
            if hasattr(self, '_title_bar_visible') and self._title_bar_visible:
                self.canvas.tag_raise('title_bar')
        except Exception as e:
            self.logger.warning(f"[DEBUG] Ошибка обновления рамки: {e}")

    def _on_mouse_enter(self, event):
        """Обработчик входа мыши в область оверлея."""
        if self._is_dragging:
            return

        # F2-оверлеи НЕ СКРЫВАЕМ при наведении
        if hasattr(self, '_is_f2_overlay') and self._is_f2_overlay:
            self.logger.debug("[DEBUG] _on_mouse_enter: F2-оверлей, не скрываем")
            self._mouse_over = True
            return

        # ============================================================
        # В РЕЖИМЕ РЕДАКТИРОВАНИЯ НЕ СКРЫВАЕМ ОВЕРЛЕЙ ПРИ НАВЕДЕНИИ
        # ============================================================
        if self._edit_mode_enabled:
            self.logger.debug("[DEBUG] _on_mouse_enter: режим редактирования, оверлей не скрываем")
            self._mouse_over = True
            return

        if self._suppress_enter_events:
            self._suppress_enter_events = False
            return

        if self._mouse_over:
            return

        self._mouse_over = True
        self.logger.debug(f"[DEBUG] _on_mouse_enter: mouse_over=True, edit_mode={self._edit_mode_enabled}")

        # Скрываем оверлей при наведении (только в режиме просмотра)
        if self.visible and self._is_visible_by_user:
            self.logger.debug("[DEBUG] _on_mouse_enter: скрываем оверлей (наведение мыши)")
            self._hidden_by_mouse = True
            self._hide_internal()
            if not self._monitor_timer and self.auto_hide_enabled:
                self._start_visibility_monitor()

    def _on_mouse_leave(self, event):
        """Обработчик выхода мыши из области оверлея."""
        if self._is_dragging:
            return

        # F2-оверлеи не скрываются и не показываются автоматически
        if hasattr(self, '_is_f2_overlay') and self._is_f2_overlay:
            self.logger.debug("[DEBUG] _on_mouse_leave: F2-оверлей, игнорируем")
            self._mouse_over = False
            return

        # ============================================================
        # В РЕЖИМЕ РЕДАКТИРОВАНИЯ НЕ ПОКАЗЫВАЕМ ОВЕРЛЕЙ АВТОМАТИЧЕСКИ
        # ============================================================
        if self._edit_mode_enabled:
            self.logger.debug("[DEBUG] _on_mouse_leave: режим редактирования, игнорируем")
            self._mouse_over = False
            return

        if not self._is_visible_by_user:
            self.logger.debug(f"[DEBUG] _on_mouse_leave: _is_visible_by_user=False, игнорируем")
            return

        if not self._mouse_over:
            return

        self._mouse_over = False
        self.logger.debug(f"[DEBUG] _on_mouse_leave: mouse_over=False, edit_mode={self._edit_mode_enabled}")

        self._hidden_by_mouse = False

        # Показываем оверлей при уходе мыши (только в режиме просмотра)
        if self._last_image_path and self._last_window_rect:
            if not self.visible and not self._hidden_by_mouse:
                self._show_internal()
                if self.auto_hide_enabled:
                    self._start_visibility_monitor()

    def hide(self, by_user: bool = True):
        """Скрывает оверлей."""
        self.logger.info(f"[DEBUG][hide] НАЧАЛО: visible={self.visible}, by_user={by_user}")

        self._created_at_startup = False

        # Скрываем рамку
        self._hide_edit_frame()

        # Освобождаем захват фокуса
        try:
            if self.root and self.root.winfo_exists():
                self.root.grab_release()
                self.logger.info("[DEBUG][hide] захват фокуса освобожден")
        except Exception as e:
            self.logger.warning(f"[DEBUG][hide] ошибка освобождения захвата: {e}")

        try:
            if self.root and self.root.winfo_exists():
                x = self.root.winfo_x()
                y = self.root.winfo_y()
                self._saved_position = (x, y)
                self._user_moved = True
        except Exception as e:
            self.logger.warning(f"[DEBUG][hide] Ошибка сохранения позиции: {e}")

        # ============================================================
        # F1: by_user=True означает, что пользователь нажал F1
        # В режиме редактирования F1 тоже должен работать
        # ============================================================
        if by_user:
            self._hidden_by_user = True
            self._is_visible_by_user = False
        else:
            # При системном скрытии (переключение окон) НЕ сбрасываем _is_visible_by_user,
            # чтобы оверлей мог быть показан автоматически при возврате в окно
            self._hidden_by_user = False

        self.visible = False

        self._stop_visibility_monitor()

        try:
            self.root.withdraw()
            self.logger.info("[DEBUG][hide] оверлей скрыт")
        except Exception as e:
            self.logger.error(f"[DEBUG][hide] ОШИБКА: {e}")

    def show(self):
        """Показывает оверлей."""
        self.logger.info("[DEBUG] show() вызван")

        if self._hidden_by_user:
            self.logger.info("[DEBUG] show() - оверлей скрыт пользователем (F1), пропускаем")
            return

        if hasattr(self, '_closing') and self._closing:
            self.logger.info("[DEBUG] show() - оверлей закрывается, пропускаем")
            return

        if not self._last_image_path or not self._last_window_rect:
            self.logger.warning("[DEBUG] show() - нет сохраненного изображения или rect")
            return

        if not self._image_loaded or self.tk_image is None:
            self.logger.info("[DEBUG] show() - изображение не загружено, загружаем")
            self._load_and_show_image(self._last_image_path, self._last_window_rect, show_immediately=True)
            return

        if self.visible:
            self.logger.info("[DEBUG] show() - оверлей уже виден")
            if self._last_window_rect:
                expected_x, expected_y, expected_x2, expected_y2 = self._last_window_rect
                try:
                    current_x = self.root.winfo_x()
                    current_y = self.root.winfo_y()
                    current_w = self.root.winfo_width()
                    current_h = self.root.winfo_height()

                    expected_w = expected_x2 - expected_x
                    expected_h = expected_y2 - expected_y

                    if (abs(current_x - expected_x) > 2 or
                            abs(current_y - expected_y) > 2 or
                            abs(current_w - expected_w) > 2 or
                            abs(current_h - expected_h) > 2):
                        self.logger.info(f"[DEBUG] show() - позиция изменилась, обновляем")
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

            # ============================================================
            # УБРАН АВТОФОКУС НА ОВЕРЛЕЙ
            # ============================================================

            if self.auto_hide_enabled:
                self._start_visibility_monitor()

            self.logger.info("[DEBUG] show() - оверлей показан")
        except Exception as e:
            self.logger.warning(f"[DEBUG] show() - ошибка: {e}")

    def update_edit_mode(self, edit_mode_enabled: bool):
        """Обновляет состояние режима редактирования для оверлея."""
        self.logger.info(f"[DEBUG] Обновлен _edit_mode_enabled = {edit_mode_enabled}")

        self._edit_mode_enabled = edit_mode_enabled

        # ============================================================
        # ТОЛЬКО РАМКА! Монитор видимости и F1 продолжают работать
        # ============================================================
        if edit_mode_enabled:
            # Показываем рамку
            self._show_edit_frame()

            # Сбрасываем флаг скрытия мышью (чтобы оверлей не был скрыт из-за мыши)
            # НО НЕ ВЛИЯЕМ НА F1 И АВТОСКРЫТИЕ ПРИ ПЕРЕКЛЮЧЕНИИ ОКОН
            if self._hidden_by_mouse:
                self._hidden_by_mouse = False
                if not self.visible and self._last_image_path and self._last_window_rect:
                    # Показываем только если оверлей НЕ скрыт пользователем (F1) и НЕ скрыт системой
                    if not self._hidden_by_user and self._is_visible_by_user:
                        self.show()

            self.logger.info("[DEBUG] Режим редактирования включен: рамка показана")
        else:
            # Скрываем рамку
            self._hide_edit_frame()
            self.logger.info("[DEBUG] Режим редактирования выключен: рамка скрыта")

    def _start_drag(self, event):
        """Начинает перетаскивание окна."""
        # Разрешаем перетаскивание если:
        # 1. Это F2-оверлей (всегда разрешено)
        # 2. ИЛИ включен глобальный режим редактирования (F5)
        is_f2_overlay = hasattr(self, '_is_f2_overlay') and self._is_f2_overlay
        can_drag = is_f2_overlay or self._edit_mode_enabled

        if not can_drag:
            self.logger.debug(
                "[DEBUG] _start_drag: перетаскивание запрещено (не F2-оверлей и редактирование выключено)")
            return "break"

        if not self.visible:
            self.logger.debug("[DEBUG] _start_drag - оверлей скрыт, перетаскивание запрещено")
            return "break"

        if self._is_dragging:
            self.logger.debug("[DEBUG] _start_drag - уже перетаскивается, пропускаем")
            return "break"

        # Отменяем предыдущий таймер сохранения
        if hasattr(self, '_save_timer') and self._save_timer:
            try:
                self.root.after_cancel(self._save_timer)
                self._save_timer = None
            except:
                pass

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

        self.logger.debug("[DEBUG] Начало перетаскивания, флаг _is_dragging=True")
        self._stop_visibility_monitor()
        self.logger.debug("[DEBUG] _start_drag: монитор видимости отключен")

        # Отключаем сохранение состояния во время перетаскивания
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager._suppress_save = True
            self.logger.debug("[DEBUG] _start_drag: сохранение состояния отключено")
            self._overlay_manager.set_dragging(True)

    def _stop_drag(self, event):
        """Останавливает перетаскивание окна."""
        if not self._is_dragging:
            self.logger.info("[DEBUG] _stop_drag - не в режиме перетаскивания, пропускаем")
            return

        self.logger.info("[DEBUG] _stop_drag вызван")

        self._is_dragging = False
        self._drag_data["x"] = 0
        self._drag_data["y"] = 0
        self.logger.info("[DEBUG] Конец перетаскивания, флаг _is_dragging=False")

        try:
            if self.root and self.root.winfo_exists():
                overlay_x = self.root.winfo_x()
                overlay_y = self.root.winfo_y()
                overlay_w = self.root.winfo_width()
                overlay_h = self.root.winfo_height()

                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()

                if overlay_x < -1000 or overlay_x > screen_width + 1000 or overlay_y < -1000 or overlay_y > screen_height + 1000:
                    self.logger.warning(f"[DEBUG] Оверлей улетел за экран: ({overlay_x}, {overlay_y})")
                    if self._saved_position:
                        prev_x, prev_y = self._saved_position
                        self.root.geometry(f"{overlay_w}x{overlay_h}+{prev_x}+{prev_y}")
                        return
                    return

                self._user_moved = True
                self._saved_position = (overlay_x, overlay_y)

                # ============================================================
                # ЗАПОМИНАЕМ ПЕРЕТАЩЕННЫЙ F2-ОВЕРЛЕЙ В APP
                # ============================================================
                if hasattr(self, '_is_f2_overlay') and self._is_f2_overlay:
                    if hasattr(self, '_overlay_manager') and self._overlay_manager:
                        parent = self._overlay_manager.parent
                        if parent:
                            parent._last_dragged_f2_overlay = self
                            self.logger.info(f"[F4] Запомнен перетащенный F2-оверлей: {self._app_name}")

                if self._template_id and hasattr(self, '_overlay_manager') and self._overlay_manager:
                    parent = self._overlay_manager.parent
                    if parent and hasattr(parent, 'translation_monitor'):
                        monitor = parent.translation_monitor
                        if monitor:
                            for template_data in monitor.templates:
                                if template_data.get('hash') == self._template_id:
                                    last_template_pos = template_data.get('last_template_position')
                                    if last_template_pos:
                                        template_x, template_y = last_template_pos
                                        new_offset_x = overlay_x - template_x
                                        new_offset_y = overlay_y - template_y
                                        template_data['offset_x'] = new_offset_x
                                        template_data['offset_y'] = new_offset_y
                                        template_data['overlay_width'] = overlay_w
                                        template_data['overlay_height'] = overlay_h
                                        template_data['offset_initialized'] = True
                                        self._offset_x = new_offset_x
                                        self._offset_y = new_offset_y
                                        self.logger.info(
                                            f"[DEBUG] Обновлено смещение для шаблона {self._template_id[:8]}: "
                                            f"({new_offset_x}, {new_offset_y})"
                                        )
                                    break

                            self._overlay_manager._save_overlay_position(self._template_id, overlay_x, overlay_y)
                            self.logger.info(
                                f"[DEBUG] Сохранена позиция оверлея для шаблона {self._template_id[:8]}: ({overlay_x}, {overlay_y})"
                            )

        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось сохранить позицию оверлея: {e}")

        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager.set_dragging(False)
            self.logger.info("[DEBUG] Глобальный флаг перетаскивания сброшен")

        if self._edit_frame_visible:
            self._update_edit_frame_position()

        self._hidden_by_mouse = False
        self._mouse_over = False
        self.logger.info("[DEBUG] _stop_drag: флаги _hidden_by_mouse и _mouse_over сброшены")

        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager._suppress_save = False
            if self.root and self.root.winfo_exists():
                if hasattr(self, '_save_timer') and self._save_timer:
                    try:
                        self.root.after_cancel(self._save_timer)
                    except:
                        pass
                self._save_timer = self.root.after(500, self._delayed_save_state)
                self.logger.info("[DEBUG] _stop_drag: сохранение состояния запланировано через 500мс")

        if self._edit_mode_enabled:
            self.logger.info("[DEBUG] _stop_drag: режим редактирования, монитор не запускаем")
            return

        if self.auto_hide_enabled:
            self._start_visibility_monitor()
            self.logger.info("[DEBUG] _stop_drag: монитор видимости перезапущен")

    def _on_drag(self, event):
        """Перемещает окно во время перетаскивания с оптимизацией."""
        if not self._is_dragging or not self.root or not self.root.winfo_exists():
            return

        # Оптимизация: обновляем позицию напрямую, без лишних операций
        x = self.root.winfo_x() + (event.x - self._drag_data["x"])
        y = self.root.winfo_y() + (event.y - self._drag_data["y"])

        # Применяем позицию сразу
        self.root.geometry(f"+{x}+{y}")

        # Сохраняем позицию без обновления рамки при каждом движении
        self._saved_position = (x, y)

        # Обновляем рамку только если она видна и прошло достаточно времени
        if self._edit_frame_visible:
            # Используем отложенное обновление рамки, чтобы не тормозить
            if not hasattr(self, '_last_frame_update') or time.time() - self._last_frame_update > 0.05:
                self._update_edit_frame_position()
                self._last_frame_update = time.time()

    def _on_right_click(self, event):
        """Обработчик правой кнопки мыши - показывает контекстное меню через менеджер."""
        self.logger.debug("[DEBUG] _on_right_click вызван")

        if self._right_click_processing:
            return

        if not self.visible:
            return

        # Разрешаем контекстное меню если:
        # 1. Это F2-оверлей (всегда разрешено)
        # 2. ИЛИ включен глобальный режим редактирования (F5)
        is_f2_overlay = hasattr(self, '_is_f2_overlay') and self._is_f2_overlay
        can_show_menu = is_f2_overlay or self._edit_mode_enabled

        if not can_show_menu:
            self.logger.debug(
                "[DEBUG] _on_right_click: контекстное меню запрещено (не F2-оверлей и редактирование выключено)")
            return

        if not hasattr(self, '_overlay_manager') or not self._overlay_manager:
            return

        if self not in self._overlay_manager.overlays:
            return

        if not self.root or not self.root.winfo_exists():
            return

        self._right_click_processing = True
        self._context_menu_visible = True

        self._overlay_manager.show_context_menu(self, event.x_root, event.y_root)
        self.logger.debug("[DEBUG] Контекстное меню показано через менеджер")

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

        # === УДАЛЯЕМ ТОЛЬКО СВОЙ ШАБЛОН ИЗ МОНИТОРА ===
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'translation_monitor') and parent.translation_monitor:
                monitor = parent.translation_monitor
                target_hwnd = self._target_hwnd
                template_id = self._template_id

                # Ищем шаблон с таким же hash (template_id)
                template_to_remove = None
                for template in monitor.templates:
                    if template.get('hash') == template_id:
                        template_to_remove = template
                        break

                if template_to_remove:
                    pair_index = template_to_remove.get('pair_index')
                    self.logger.info(
                        f"[MONITOR] Удаляем шаблон #{pair_index} для HWND={target_hwnd} (hash={template_id[:8]})")
                    monitor.remove_template(pair_index)
                else:
                    self.logger.info(
                        f"[MONITOR] Шаблон с hash {template_id[:8] if template_id else 'None'} не найден, пропускаем")

        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self.logger.info(
                f"[DEBUG] Удаление оверлея через OverlayManager (всего оверлеев: {len(self._overlay_manager.overlays)})")
            self._overlay_manager.remove_overlay(self)
        else:
            self.logger.warning("[DEBUG] _remove_overlay: менеджер не найден, закрываем самостоятельно")
            self.close()

    def _check_and_update_visibility(self):
        """Проверяет видимость оверлея."""
        if hasattr(self, '_updating_visibility') and self._updating_visibility:
            return
        self._updating_visibility = True

        try:
            # ============================================================
            # ИЗМЕНЕНИЕ: УДАЛЯЕМ ПРОВЕРКУ НА F2
            # Теперь ВСЕ оверлеи управляются через монитор видимости
            # ============================================================
            # is_f2_overlay = hasattr(self, '_is_f2_overlay') and self._is_f2_overlay
            # if is_f2_overlay:
            #     self._updating_visibility = False
            #     return

            if not self._is_visible_by_user:
                self._updating_visibility = False
                return

            if self._context_menu_visible:
                if self._is_visible_by_user and not self.visible and not self._hidden_by_mouse:
                    self._show_internal(force=False)
                return

            if not self.auto_hide_enabled or not self._is_visible_by_user:
                return

            if self._hidden_by_user:
                return

            if hasattr(self, '_overlay_manager') and self._overlay_manager:
                if self._overlay_manager.is_dragging():
                    return

            if time.time() < self._monitor_stable_time:
                return

            if self._edit_mode_enabled:
                self._updating_visibility = False
                return

            if self._mouse_over or self._hidden_by_mouse:
                if self.visible:
                    self._hide_internal()
                self._updating_visibility = False
                return

            try:
                import win32gui
                import win32api

                active_hwnd = win32gui.GetForegroundWindow()
                if active_hwnd == 0:
                    return

                if self._is_selection_window_active(active_hwnd):
                    if not self.visible and self._is_visible_by_user and not self._hidden_by_user:
                        self._show_internal(force=False)
                    return

                target_hwnd = self.get_target_hwnd()

                if not target_hwnd or not win32gui.IsWindow(target_hwnd):
                    if self._update_target_hwnd():
                        target_hwnd = self._target_hwnd
                        self.logger.info(f"[MONITOR] Обновлен target_hwnd: {target_hwnd}")

                if target_hwnd is None or active_hwnd != target_hwnd:
                    if self.visible:
                        self._hide_internal()
                    return

                if not self.visible and self._is_visible_by_user and not self._hidden_by_user:
                    self._show_internal(force=False)

            except Exception as e:
                self.logger.warning(f"Ошибка в _check_and_update_visibility: {e}")

        finally:
            self._updating_visibility = False

    def show_for_window(self, image_path: Path, window_rect: tuple, target_hwnd: int = None,
                        is_fullscreen: bool = None, show_immediately: bool = True,
                        is_startup: bool = False, is_temporary: bool = False,
                        lifetime_seconds: int = 180):
        """Показывает оверлей для указанного окна."""
        self.logger.info(f"[DEBUG] === show_for_window НАЧАЛО ===")
        self.logger.info(f"[DEBUG] image_path={image_path}")
        self.logger.info(f"[DEBUG] window_rect={window_rect}")
        self.logger.info(f"[DEBUG] target_hwnd={target_hwnd}")
        self.logger.info(f"[DEBUG] show_immediately={show_immediately}")
        self.logger.info(f"[DEBUG] is_startup={is_startup}")
        self.logger.info(f"[DEBUG] is_temporary={is_temporary}")
        self.logger.info(f"[DEBUG] lifetime_seconds={lifetime_seconds}")

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

        # Устанавливаем временный режим, если нужно
        if is_temporary:
            self.set_temporary_mode(True, lifetime_seconds)
            self.logger.info(f"[TEMP] Оверлей создан как временный ({lifetime_seconds} секунд)")

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

            # Если режим редактирования включён - сразу показываем рамку
            # ИСПРАВЛЕНИЕ: вызов _show_title_bar() заменён на _show_edit_frame()
            if self._edit_mode_enabled:
                self._show_edit_frame()
                self.logger.info("[DEBUG] Режим редактирования: рамка показана сразу")
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

            # Фон
            self.canvas.create_rectangle(0, 0, win_width, win_height, fill='#000000', outline='', tags=('bg_rect',))

            # Изображение
            x = (win_width - new_w) // 2
            y = (win_height - new_h) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image, tags=('image',))

            # Если режим редактирования включён - показываем рамку
            if self._edit_mode_enabled:
                self._show_edit_frame()

            self.root.update_idletasks()

            self.visible = False
            self._show_time = time.time()
            self._monitor_stable_time = time.time() + 2.0
            self._image_loaded = True
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

                # ============================================================
                # УБРАН АВТОФОКУС НА ОВЕРЛЕЙ
                # ============================================================

                if self._edit_frame_visible:
                    self._update_edit_frame_position()

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

        if not self._is_visible_by_user:
            self.logger.info(
                "[DEBUG][_start_visibility_monitor_delayed] оверлей не должен быть виден, отменяем запуск монитора")
            return

        # ============================================================
        # ИЗМЕНЕНИЕ: УДАЛЯЕМ ПРОВЕРКУ НА АВТОЗАМЕНУ
        # Теперь ВСЕ оверлеи получают монитор видимости, включая F3
        # ============================================================
        # if self._is_auto_replace:
        #     self.logger.info("автозамена, монитор управляется TranslationMonitor, пропускаем")
        #     return

        self.logger.info("[DEBUG][_start_visibility_monitor_delayed] запускаем монитор")

        is_startup = hasattr(self, '_created_at_startup') and self._created_at_startup

        if is_startup:
            self.logger.info("[DEBUG][_start_visibility_monitor_delayed] запуск при старте программы, задержка 3с")
            if self.root and self.root.winfo_exists():
                self.root.after(3000, self._start_visibility_monitor)
        else:
            self._start_visibility_monitor()

    def _start_visibility_monitor(self):
        """Запускает монитор видимости - унифицированная логика с защитой от дублирования."""
        if not self.auto_hide_enabled:
            return

        # ============================================================
        # ИЗМЕНЕНИЕ: УДАЛЯЕМ ПРОВЕРКУ НА АВТОЗАМЕНУ
        # Теперь ВСЕ оверлеи получают монитор видимости
        # ============================================================
        # if self._is_auto_replace:
        #     self.logger.debug("[DEBUG] _start_visibility_monitor: автозамена, пропускаем")
        #     return

        if hasattr(self, '_monitor_timer') and self._monitor_timer is not None:
            return

        self._monitor_initialized = False
        self._last_active_hwnd = None

        try:
            import win32gui

            if not self._target_hwnd and self._app_name and self._app_name != "Неизвестно":
                self._update_target_hwnd()

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

                self._monitor_timer = None

                if not self._target_hwnd or not win32gui.IsWindow(self._target_hwnd):
                    if self._update_target_hwnd():
                        self.logger.info(f"[MONITOR] Обновлен target_hwnd в мониторе: {self._target_hwnd}")

                self._check_and_update_visibility()

                if self._is_visible_by_user and self.root and self.root.winfo_exists():
                    self._monitor_timer = self.root.after(200, check_visibility)

            except Exception as e:
                self.logger.warning(f"Ошибка в мониторе видимости: {e}")
                if self._is_visible_by_user and self.root and self.root.winfo_exists():
                    self._monitor_timer = self.root.after(200, check_visibility)

        if self.root and self.root.winfo_exists():
            self._monitor_timer = self.root.after(200, check_visibility)

    def _show_window_safe(self):
        """Безопасно показывает окно."""
        try:
            if self.root and self.root.winfo_exists():
                if not (self._saved_position and hasattr(self, '_user_moved') and self._user_moved):
                    if self._last_window_rect:
                        x1, y1, x2, y2 = self._last_window_rect
                        width = x2 - x1
                        height = y2 - y1
                        current_x = self.root.winfo_x()
                        current_y = self.root.winfo_y()
                        if current_x != x1 or current_y != y1:
                            self.root.geometry(f"{width}x{height}+{x1}+{y1}")
                            self.root.update_idletasks()
                else:
                    self.logger.info("[DEBUG] _show_window_safe: сохраненная позиция есть, не корректируем")

                self.root.deiconify()
                self.root.lift()
                self.root.update_idletasks()

                # ============================================================
                # НЕ ЗАХВАТЫВАЕМ ФОКУС
                # ============================================================

                # Обновляем рамку после показа
                if self._edit_frame_visible:
                    self._update_edit_frame_position()
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
        """Внутренний метод для показа оверлея."""
        if hasattr(self, '_showing_in_progress') and self._showing_in_progress:
            return
        self._showing_in_progress = True

        try:
            if not self._is_visible_by_user:
                self.logger.debug("[DEBUG] _show_internal: _is_visible_by_user=False, пропускаем")
                return

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

                    # ============================================================
                    # УБРАН АВТОФОКУС НА ОВЕРЛЕЙ
                    # ============================================================

                    if self._saved_position:
                        x, y = self._saved_position
                        current_x = self.root.winfo_x()
                        current_y = self.root.winfo_y()
                        if abs(current_x - x) > 5 or abs(current_y - y) > 5:
                            self.root.geometry(f"+{x}+{y}")

                    if self.auto_hide_enabled:
                        self._start_visibility_monitor()

                    self.root.after(500, lambda: setattr(self, '_suppress_enter_events', False))
                    return
                except Exception as e:
                    self.logger.warning(f"[DEBUG][_show_internal] ошибка: {e}")

            self._load_and_show_image(self._last_image_path, self._last_window_rect)
            self._image_loaded = True

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
        """Внутренний метод для скрытия оверлея."""
        if hasattr(self, '_hiding_in_progress') and self._hiding_in_progress:
            return
        self._hiding_in_progress = True

        try:
            # F2-оверлеи НЕ СКРЫВАЕМ автоматически
            if hasattr(self, '_is_f2_overlay') and self._is_f2_overlay:
                self.logger.debug("[DEBUG] _hide_internal: F2-оверлей, не скрываем автоматически")
                return

            # ============================================================
            # УДАЛЯЕМ ЭТУ ПРОВЕРКУ! Она блокирует скрытие при наведении мыши
            # ============================================================
            # if self._is_visible_by_user:
            #     self.logger.debug("[DEBUG] _hide_internal: _is_visible_by_user=True, не скрываем")
            #     return

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

            # Скрываем рамку
            self._hide_edit_frame()

            self.visible = False
            try:
                self.root.withdraw()
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
        """Закрывает оверлей с быстрой очисткой."""
        import time

        self.logger.info("[OVERLAY] close() вызван")

        # Устанавливаем флаг закрытия
        self._closing = True

        # Останавливаем временный таймер
        self._stop_temp_timer()

        # Скрываем рамку
        self._hide_edit_frame()

        # Сбрасываем ссылку на оверлей в мониторе
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'translation_monitor') and parent.translation_monitor:
                for template in parent.translation_monitor.templates:
                    if template.get('overlay') is self:
                        template['overlay'] = None
                        self.logger.info(
                            f"[MONITOR] Ссылка на оверлей сброшена для шаблона #{template.get('pair_index')}"
                        )
                        break

        # Очищаем Canvas
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.delete("all")
                self.canvas.update_idletasks()
                self.logger.info("[OVERLAY] Canvas очищен")
        except Exception as e:
            self.logger.warning(f"[OVERLAY] Не удалось очистить Canvas: {e}")

        # Останавливаем мониторы
        self._stop_visibility_monitor()
        self._disable_esc_hook()
        self._context_menu_visible = False

        # Сохраняем координаты для перерисовки
        rect = None
        try:
            if self.root and self.root.winfo_exists():
                x = self.root.winfo_x()
                y = self.root.winfo_y()
                w = self.root.winfo_width()
                h = self.root.winfo_height()
                rect = (x, y, x + w, y + h)
        except:
            pass

        # Скрываем окно
        try:
            if self.root and self.root.winfo_exists():
                self.root.withdraw()
                self.root.update_idletasks()
        except Exception as e:
            self.logger.warning(f"[OVERLAY] Не удалось скрыть окно: {e}")

        # Очищаем память
        try:
            self._images.clear()
            self.tk_image = None
            self._last_image_path = None
            self._last_window_rect = None
            self._saved_position = None
            self._is_fullscreen_target = False

            # Быстрое уничтожение окна
            if self.root and self.root.winfo_exists():
                self.root.destroy()
            self.logger.info("[OVERLAY] Оверлей закрыт")
        except Exception as e:
            self.logger.warning(f"[OVERLAY] Не удалось уничтожить окно: {e}")

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
            except Exception as e:
                self.logger.warning(f"[OVERLAY] Не удалось перерисовать область: {e}")

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
