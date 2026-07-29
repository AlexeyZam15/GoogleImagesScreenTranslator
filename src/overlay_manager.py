"""
Модуль для управления множественными оверлейными окнами.
"""

import logging
import keyboard
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from src.overlay import OverlayWindow


class OverlayManager:
    """Управляет списком оверлеев."""

    def __init__(self, parent):
        self.logger = logging.getLogger(__name__)
        self.parent = parent
        self.overlays: List[OverlayWindow] = []
        self._is_dragging_any = False
        self._show_all_sync_pending = False
        self._show_all_sync_timer = None
        self._esc_hook_active = False
        self._context_menu = None
        self._context_menu_overlay = None
        self._create_context_menu()
        self.logger.info("OverlayManager инициализирован")

    def _create_context_menu(self):
        """Создает контекстное меню для оверлеев."""
        try:
            import tkinter as tk
            if hasattr(self.parent, 'root'):
                self._context_menu = tk.Menu(self.parent.root, tearoff=0, bg='#2d2d2d', fg='white',
                                             activebackground='#4CAF50', activeforeground='white')
                self._context_menu.add_command(label="🗑️ Удалить", command=self._remove_overlay_under_cursor)
                self.logger.info("[DEBUG] Контекстное меню создано в OverlayManager")
            else:
                self.logger.warning("[DEBUG] Не удалось создать контекстное меню: нет root")
        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка создания контекстного меню: {e}")

    def show_context_menu(self, overlay, x, y):
        """Показывает контекстное меню для указанного оверлея."""
        if overlay is None:
            self.logger.warning("[DEBUG] show_context_menu: оверлей None")
            return

        if overlay not in self.overlays:
            self.logger.warning("[DEBUG] show_context_menu: оверлей не в списке")
            return

        if not overlay.visible:
            self.logger.warning("[DEBUG] show_context_menu: оверлей не виден")
            return

        try:
            if not overlay.root or not overlay.root.winfo_exists():
                self.logger.warning("[DEBUG] show_context_menu: окно оверлея закрыто")
                return
        except:
            self.logger.warning("[DEBUG] show_context_menu: ошибка проверки окна оверлея")
            return

        if not self._context_menu:
            self._create_context_menu()
            if not self._context_menu:
                return

        self._context_menu_overlay = overlay

        try:
            self._context_menu.post(x, y)
            self.logger.info(f"[DEBUG] Контекстное меню показано в ({x}, {y})")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось показать контекстное меню: {e}")
            self._context_menu_overlay = None

    def _remove_overlay_under_cursor(self):
        """Удаляет оверлей, для которого было показано контекстное меню."""
        self.logger.info("[DEBUG] Удаление оверлея через контекстное меню")

        try:
            if self._context_menu:
                try:
                    self._context_menu.unpost()
                    self._context_menu.update_idletasks()
                    self.logger.info("[DEBUG] Контекстное меню закрыто (unpost)")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Ошибка при unpost: {e}")

                try:
                    if hasattr(self._context_menu, 'tk') and self._context_menu.tk:
                        self._context_menu.tk.call('destroy', self._context_menu)
                        self.logger.info("[DEBUG] Контекстное меню уничтожено через tk.call")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Ошибка при уничтожении меню: {e}")

                self._context_menu = None
                self._create_context_menu()
                self.logger.info("[DEBUG] Контекстное меню пересоздано")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось закрыть меню: {e}")

        overlay = None
        if hasattr(self, '_context_menu_overlay') and self._context_menu_overlay:
            overlay = self._context_menu_overlay
            self._context_menu_overlay = None
            self.logger.info("[DEBUG] Ссылка на оверлей сброшена")

        if overlay is None:
            self.logger.warning("[DEBUG] Нет оверлея для удаления")
            return

        try:
            if overlay in self.overlays:
                self.remove_overlay(overlay)
                self.logger.info("[DEBUG] Оверлей удален")
            else:
                self.logger.warning("[DEBUG] Оверлей уже удален из списка")
        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка при удалении оверлея: {e}")

    def create_overlay(self, image_path: Path, window_rect: tuple,
                       target_hwnd: int = None, is_fullscreen: bool = None,
                       show_immediately: bool = True, is_window_screenshot: bool = False) -> Optional[OverlayWindow]:
        """
        Создает новый оверлей на основе переданных данных.

        Args:
            image_path: Путь к изображению для отображения
            window_rect: Координаты окна (x1, y1, x2, y2)
            target_hwnd: HWND целевого окна
            is_fullscreen: Флаг полноэкранного режима
            show_immediately: Показывать сразу или сохранить для отложенного показа
            is_window_screenshot: True для F2 (скриншот окна), False для F3 (область)
        """
        self.logger.info(
            f"Создание нового оверлея: image_path={image_path}, is_window_screenshot={is_window_screenshot}")

        auto_hide_enabled = False
        if hasattr(self.parent, 'settings') and self.parent.settings:
            auto_hide_enabled = self.parent.settings.get_auto_hide_overlay()

        self.logger.info(f"[DEBUG] OverlayWindow class object: {OverlayWindow}")
        self.logger.info(f"[DEBUG] OverlayWindow module: {OverlayWindow.__module__}")

        new_overlay = None
        try:
            self.logger.info("[DEBUG] Attempting to create OverlayWindow with arguments...")
            new_overlay = OverlayWindow(
                parent=self.parent.root,
                app_title=self.parent.app_title if hasattr(self.parent, 'app_title') else "Перевод скриншотов",
                auto_hide_enabled=auto_hide_enabled
            )
            self.logger.info("[DEBUG] OverlayWindow created successfully with arguments")
        except TypeError as e:
            self.logger.warning(f"[DEBUG] OverlayWindow does not accept arguments: {e}")
            self.logger.info("[DEBUG] Attempting to create OverlayWindow without arguments...")
            try:
                new_overlay = OverlayWindow()
                self.logger.info("[DEBUG] OverlayWindow created without arguments (fallback)")

                import logging
                from pathlib import Path

                if not hasattr(new_overlay, 'logger'):
                    new_overlay.logger = logging.getLogger(__name__)
                    new_overlay.logger.info("[DEBUG] Added logger attribute to OverlayWindow (fallback)")

                if not hasattr(new_overlay, 'temp_dir'):
                    from src.utils import ensure_app_temp_dir
                    new_overlay.temp_dir = ensure_app_temp_dir()
                    new_overlay.logger.info("[DEBUG] Added temp_dir attribute (fallback)")

                if not hasattr(new_overlay, 'auto_hide_enabled'):
                    new_overlay.auto_hide_enabled = auto_hide_enabled
                    new_overlay.logger.info("[DEBUG] Added auto_hide_enabled attribute (fallback)")

                if not hasattr(new_overlay, '_app_title'):
                    new_overlay._app_title = self.parent.app_title if hasattr(self.parent,
                                                                              'app_title') else "Перевод скриншотов"
                    new_overlay.logger.info("[DEBUG] Added _app_title attribute (fallback)")

                if not hasattr(new_overlay, '_use_manager_esc'):
                    new_overlay._use_manager_esc = True
                    new_overlay.logger.info("[DEBUG] Added _use_manager_esc attribute (fallback)")

                if not hasattr(new_overlay, '_overlay_manager'):
                    new_overlay._overlay_manager = self
                    new_overlay.logger.info("[DEBUG] Added _overlay_manager attribute (fallback)")

                if not hasattr(new_overlay, '_images'):
                    new_overlay._images = []
                    new_overlay.logger.info("[DEBUG] Added _images attribute (fallback)")

                if not hasattr(new_overlay, 'tk_image'):
                    new_overlay.tk_image = None
                    new_overlay.logger.info("[DEBUG] Added tk_image attribute (fallback)")

                if not hasattr(new_overlay, '_last_image_path'):
                    new_overlay._last_image_path = None
                    new_overlay.logger.info("[DEBUG] Added _last_image_path attribute (fallback)")

                if not hasattr(new_overlay, '_last_window_rect'):
                    new_overlay._last_window_rect = None
                    new_overlay.logger.info("[DEBUG] Added _last_window_rect attribute (fallback)")

                if not hasattr(new_overlay, '_target_hwnd'):
                    new_overlay._target_hwnd = None
                    new_overlay.logger.info("[DEBUG] Added _target_hwnd attribute (fallback)")

                if not hasattr(new_overlay, '_is_fullscreen_target'):
                    new_overlay._is_fullscreen_target = False
                    new_overlay.logger.info("[DEBUG] Added _is_fullscreen_target attribute (fallback)")

                if not hasattr(new_overlay, '_is_visible_by_user'):
                    new_overlay._is_visible_by_user = False
                    new_overlay.logger.info("[DEBUG] Added _is_visible_by_user attribute (fallback)")

                if not hasattr(new_overlay, '_saved_position'):
                    new_overlay._saved_position = None
                    new_overlay.logger.info("[DEBUG] Added _saved_position attribute (fallback)")

                if not hasattr(new_overlay, '_show_time'):
                    new_overlay._show_time = 0
                    new_overlay.logger.info("[DEBUG] Added _show_time attribute (fallback)")

                if not hasattr(new_overlay, '_monitor_stable_time'):
                    new_overlay._monitor_stable_time = 0
                    new_overlay.logger.info("[DEBUG] Added _monitor_stable_time attribute (fallback)")

                if not hasattr(new_overlay, '_monitor_initialized'):
                    new_overlay._monitor_initialized = False
                    new_overlay.logger.info("[DEBUG] Added _monitor_initialized attribute (fallback)")

                if not hasattr(new_overlay, '_last_active_hwnd'):
                    new_overlay._last_active_hwnd = None
                    new_overlay.logger.info("[DEBUG] Added _last_active_hwnd attribute (fallback)")

                if not hasattr(new_overlay, '_monitor_timer'):
                    new_overlay._monitor_timer = None
                    new_overlay.logger.info("[DEBUG] Added _monitor_timer attribute (fallback)")

                if not hasattr(new_overlay, '_is_dragging'):
                    new_overlay._is_dragging = False
                    new_overlay.logger.info("[DEBUG] Added _is_dragging attribute (fallback)")

                if not hasattr(new_overlay, '_drag_stop_timer'):
                    new_overlay._drag_stop_timer = None
                    new_overlay.logger.info("[DEBUG] Added _drag_stop_timer attribute (fallback)")

                if not hasattr(new_overlay, '_drag_data'):
                    new_overlay._drag_data = {"x": 0, "y": 0}
                    new_overlay.logger.info("[DEBUG] Added _drag_data attribute (fallback)")

                if not hasattr(new_overlay, '_image_loaded'):
                    new_overlay._image_loaded = False
                    new_overlay.logger.info("[DEBUG] Added _image_loaded attribute (fallback)")

                if not hasattr(new_overlay, '_fullscreen_restore_needed'):
                    new_overlay._fullscreen_restore_needed = False
                    new_overlay.logger.info("[DEBUG] Added _fullscreen_restore_needed attribute (fallback)")

                if not hasattr(new_overlay, '_esc_hook_active'):
                    new_overlay._esc_hook_active = False
                    new_overlay.logger.info("[DEBUG] Added _esc_hook_active attribute (fallback)")

                if not hasattr(new_overlay, '_original_wndproc'):
                    new_overlay._original_wndproc = 0
                    new_overlay.logger.info("[DEBUG] Added _original_wndproc attribute (fallback)")

                if not hasattr(new_overlay, 'visible'):
                    new_overlay.visible = False
                    new_overlay.logger.info("[DEBUG] Added visible attribute (fallback)")

                if not hasattr(new_overlay, '_hidden_by_mouse'):
                    new_overlay._hidden_by_mouse = False
                    new_overlay.logger.info("[DEBUG] Added _hidden_by_mouse attribute (fallback)")

                if not hasattr(new_overlay, '_is_window_screenshot'):
                    new_overlay._is_window_screenshot = False
                    new_overlay.logger.info("[DEBUG] Added _is_window_screenshot attribute (fallback)")

                if not hasattr(new_overlay, '_edit_mode_enabled'):
                    if hasattr(self.parent, '_edit_mode_enabled'):
                        new_overlay._edit_mode_enabled = self.parent._edit_mode_enabled
                    else:
                        new_overlay._edit_mode_enabled = False
                    new_overlay.logger.info(
                        f"[DEBUG] Added _edit_mode_enabled attribute (fallback) = {new_overlay._edit_mode_enabled}")

                if not hasattr(new_overlay, '_mouse_over'):
                    new_overlay._mouse_over = False
                    new_overlay.logger.info("[DEBUG] Added _mouse_over attribute (fallback)")

                if not hasattr(new_overlay, '_close_button_id'):
                    new_overlay._close_button_id = None
                    new_overlay.logger.info("[DEBUG] Added _close_button_id attribute (fallback)")

                if not hasattr(new_overlay, '_close_button_visible'):
                    new_overlay._close_button_visible = False
                    new_overlay.logger.info("[DEBUG] Added _close_button_visible attribute (fallback)")

                if not hasattr(new_overlay, '_context_menu'):
                    import tkinter as tk
                    new_overlay._context_menu = tk.Menu(new_overlay.root, tearoff=0, bg='#2d2d2d', fg='white',
                                                        activebackground='#4CAF50', activeforeground='white')
                    new_overlay._context_menu.add_command(label="🗑️ Удалить", command=new_overlay._remove_overlay)
                    new_overlay.logger.info("[DEBUG] Added _context_menu attribute (fallback)")

                if not hasattr(new_overlay, 'root') or new_overlay.root is None:
                    import tkinter as tk
                    try:
                        if self.parent and hasattr(self.parent, 'root'):
                            new_overlay.root = tk.Toplevel(self.parent.root)
                            new_overlay.logger.info("[DEBUG] Created root Toplevel (fallback)")
                        else:
                            new_overlay.root = tk.Toplevel()
                            new_overlay.logger.info("[DEBUG] Created root Toplevel without parent (fallback)")
                        new_overlay.root.overrideredirect(True)
                        new_overlay.root.attributes('-topmost', True)
                        new_overlay.root.configure(bg='#000000')
                        new_overlay.root.withdraw()
                    except Exception as e:
                        new_overlay.logger.warning(f"[DEBUG] Could not create root: {e}")

                if not hasattr(new_overlay, 'canvas') or new_overlay.canvas is None:
                    if hasattr(new_overlay, 'root') and new_overlay.root:
                        import tkinter as tk
                        new_overlay.canvas = tk.Canvas(new_overlay.root, bg='#000000', highlightthickness=0)
                        new_overlay.canvas.pack(fill=tk.BOTH, expand=True)
                        new_overlay.logger.info("[DEBUG] Created canvas (fallback)")
                    else:
                        new_overlay.logger.warning("[DEBUG] Cannot create canvas - root is None")

                if hasattr(new_overlay, 'canvas') and new_overlay.canvas:
                    try:
                        new_overlay.canvas.bind('<ButtonPress-1>', new_overlay._start_drag)
                        new_overlay.canvas.bind('<B1-Motion>', new_overlay._on_drag)
                        new_overlay.canvas.bind('<ButtonRelease-1>', new_overlay._stop_drag)
                        new_overlay.canvas.bind('<Button-3>', new_overlay._on_right_click)
                        new_overlay.canvas.bind('<Enter>', new_overlay._on_mouse_enter)
                        new_overlay.canvas.bind('<Leave>', new_overlay._on_mouse_leave)
                        new_overlay.logger.info("[DEBUG] Bound drag events to canvas (fallback)")
                    except Exception as e:
                        new_overlay.logger.warning(f"[DEBUG] Could not bind canvas events: {e}")

                if hasattr(new_overlay, 'root') and new_overlay.root:
                    try:
                        new_overlay.root.bind('<ButtonPress-1>', new_overlay._start_drag)
                        new_overlay.root.bind('<B1-Motion>', new_overlay._on_drag)
                        new_overlay.root.bind('<ButtonRelease-1>', new_overlay._stop_drag)
                        new_overlay.root.bind('<Button-3>', new_overlay._on_right_click)
                        new_overlay.root.bind('<Enter>', new_overlay._on_mouse_enter)
                        new_overlay.root.bind('<Leave>', new_overlay._on_mouse_leave)
                        new_overlay.logger.info("[DEBUG] Bound drag events to root (fallback)")
                    except Exception as e:
                        new_overlay.logger.warning(f"[DEBUG] Could not bind root events: {e}")

                new_overlay.logger.info("[DEBUG] Fallback initialization complete")

            except Exception as e2:
                self.logger.error(f"[DEBUG] Failed to create OverlayWindow: {e2}")
                return None
        except Exception as e:
            self.logger.error(f"[DEBUG] Unexpected error creating OverlayWindow: {e}")
            return None

        if new_overlay is None:
            self.logger.error("[DEBUG] new_overlay is None after creation attempts")
            return None

        new_overlay._is_window_screenshot = is_window_screenshot
        self.logger.info(f"[DEBUG] Установлен _is_window_screenshot = {is_window_screenshot}")

        if hasattr(self.parent, '_edit_mode_enabled'):
            new_overlay._edit_mode_enabled = self.parent._edit_mode_enabled
            self.logger.info(f"[DEBUG] Установлен _edit_mode_enabled = {new_overlay._edit_mode_enabled}")

        new_overlay._use_manager_esc = True

        new_overlay._overlay_manager = self
        new_overlay.show_for_window(
            image_path, window_rect, target_hwnd, is_fullscreen, show_immediately
        )

        self._enable_esc_hook()

        self.overlays.append(new_overlay)
        self.logger.info(f"Оверлей создан. Всего активных оверлеев: {len(self.overlays)}")
        return new_overlay

    def update_edit_mode_for_all(self, edit_mode_enabled: bool):
        """
        Обновляет состояние режима редактирования для всех существующих оверлеев.
        """
        self.logger.info(
            f"Обновление режима редактирования для всех {len(self.overlays)} оверлеев: {edit_mode_enabled}")
        for overlay in self.overlays:
            try:
                if overlay is not None:
                    overlay.update_edit_mode(edit_mode_enabled)
            except Exception as e:
                self.logger.warning(f"Ошибка обновления режима редактирования для оверлея: {e}")

    def toggle_all_overlays(self):
        """Переключает видимость всех оверлеев одновременно."""
        if not self.overlays:
            self.logger.warning("Нет оверлеев для переключения.")
            return False

        first_visible = False
        for overlay in self.overlays:
            if overlay.is_visible():
                first_visible = True
                break

        new_state = not first_visible

        self.logger.info(
            f"Переключение всех {len(self.overlays)} оверлеев в состояние: {'показаны' if new_state else 'скрыты'}"
        )

        for overlay in self.overlays:
            try:
                if new_state:
                    overlay.show()
                else:
                    overlay.hide()
            except Exception as e:
                self.logger.error(f"Ошибка при переключении оверлея: {e}")

        self.logger.info(f"Все {len(self.overlays)} оверлеев {'показаны' if new_state else 'скрыты'}")
        return new_state

    def _global_esc_handler(self, event):
        """Глобальный обработчик ESC - отменяет перевод или скрывает/удаляет оверлей под мышью."""
        self.logger.info("[DEBUG] ESC нажат - проверка состояния перевода")

        # Проверяем, идет ли перевод
        if hasattr(self.parent, '_translation_in_progress') and self.parent._translation_in_progress:
            self.logger.info("[DEBUG] ESC: обнаружен активный перевод - отменяем")
            if hasattr(self.parent, '_cancel_translation'):
                self.parent._cancel_translation()
            return False

        # Если перевода нет - пытаемся найти оверлей под мышью
        overlay_to_remove = self._find_overlay_under_cursor()

        if overlay_to_remove is None:
            self.logger.info("[DEBUG] ESC: оверлей под мышью не найден - скрываем все оверлеи")
            self.hide_all_overlays()
            if self.overlays:
                last_overlay = self.overlays[-1]
                if last_overlay._target_hwnd:
                    try:
                        import win32gui
                        win32gui.SetForegroundWindow(last_overlay._target_hwnd)
                        self.logger.info(f"[DEBUG] Фокус возвращен на целевое окно: {last_overlay._target_hwnd}")
                    except Exception as e:
                        self.logger.warning(f"[DEBUG] Не удалось вернуть фокус: {e}")
            return False

        target_hwnd = overlay_to_remove._target_hwnd

        # === ГЛАВНОЕ ИЗМЕНЕНИЕ: ДЛЯ F2-ОВЕРЛЕЯ ВСЕГДА СКРЫВАЕМ ===
        if hasattr(overlay_to_remove, '_is_window_screenshot') and overlay_to_remove._is_window_screenshot:
            self.logger.info("[DEBUG] ESC: F2-оверлей (скриншот окна) - СКРЫВАЕМ, а не удаляем")
            # Скрываем оверлей
            overlay_to_remove.hide()
            # Убираем флаг, что оверлей должен быть виден
            overlay_to_remove._is_visible_by_user = False
            self.logger.info("[DEBUG] ESC: F2-оверлей скрыт")
            if target_hwnd:
                try:
                    import win32gui
                    win32gui.SetForegroundWindow(target_hwnd)
                    self.logger.info(f"[DEBUG] Фокус возвращен на целевое окно: {target_hwnd}")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Не удалось вернуть фокус: {e}")
            return False

        # Для F3-оверлея (область) проверяем режим редактирования
        if not self.parent.is_edit_mode_enabled():
            self.logger.info("[DEBUG] ESC: режим редактирования ВЫКЛЮЧЕН - удаление оверлеев запрещено")
            # Всё равно скрываем оверлей (но не удаляем)
            overlay_to_remove.hide()
            overlay_to_remove._is_visible_by_user = False
            self.logger.info("[DEBUG] ESC: F3-оверлей скрыт (режим редактирования выключен)")
            if target_hwnd:
                try:
                    import win32gui
                    win32gui.SetForegroundWindow(target_hwnd)
                    self.logger.info(f"[DEBUG] Фокус возвращен на целевое окно: {target_hwnd}")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Не удалось вернуть фокус: {e}")
            return False

        # Режим редактирования ВКЛЮЧЕН - удаляем оверлей
        self.logger.info("[DEBUG] ESC: режим редактирования ВКЛЮЧЕН - УДАЛЯЕМ оверлей")
        self.remove_overlay(overlay_to_remove)

        if target_hwnd:
            try:
                import win32gui
                win32gui.SetForegroundWindow(target_hwnd)
                self.logger.info(f"[DEBUG] Фокус возвращен на целевое окно: {target_hwnd}")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось вернуть фокус: {e}")

        return False

    def remove_overlay(self, overlay: OverlayWindow):
        """Удаляет конкретный оверлей из списка и закрывает его (только в режиме редактирования)."""
        # Проверяем режим редактирования
        if not self.parent.is_edit_mode_enabled():
            self.logger.info("[DEBUG] remove_overlay: режим редактирования ВЫКЛЮЧЕН - удаление запрещено")
            # Убираем статус
            # if hasattr(self.parent, 'update_status'):
            #     self.parent.update_status("● Режим редактирования выключен (F5 для включения)", '#ff9800')
            return

        self.logger.info(f"Удаление оверлея из списка (всего: {len(self.overlays)})")
        if overlay in self.overlays:
            self.overlays.remove(overlay)
            self.logger.info(f"Оверлей удален из списка. Осталось: {len(self.overlays)}")
            try:
                overlay.close()
            except Exception as e:
                self.logger.error(f"Ошибка при закрытии оверлея: {e}")
        else:
            self.logger.warning("Оверлей не найден в списке")

    def _find_overlay_under_cursor(self) -> Optional[OverlayWindow]:
        """Находит оверлей, под которым находится курсор мыши."""
        try:
            import win32gui
            import win32api

            # Получаем позицию курсора
            cursor_pos = win32api.GetCursorPos()
            cursor_x, cursor_y = cursor_pos

            self.logger.info(f"[DEBUG] _find_overlay_under_cursor: курсор в ({cursor_x}, {cursor_y})")

            # Проверяем все оверлеи в обратном порядке (последний созданный - самый верхний)
            for overlay in reversed(self.overlays):
                try:
                    if overlay is None:
                        continue

                    # Проверяем, существует ли окно
                    if not overlay.root or not overlay.root.winfo_exists():
                        continue

                    # Проверяем, виден ли оверлей
                    if not overlay.visible:
                        continue

                    # Получаем координаты окна оверлея
                    overlay_hwnd = int(overlay.root.winfo_id())
                    rect = win32gui.GetWindowRect(overlay_hwnd)
                    x1, y1, x2, y2 = rect

                    self.logger.info(f"[DEBUG] _find_overlay_under_cursor: оверлей rect=({x1},{y1})-({x2},{y2})")

                    # Проверяем, находится ли курсор внутри окна
                    if x1 <= cursor_x <= x2 and y1 <= cursor_y <= y2:
                        self.logger.info(f"[DEBUG] _find_overlay_under_cursor: найден оверлей под курсором")
                        return overlay

                except Exception as e:
                    self.logger.warning(f"[DEBUG] _find_overlay_under_cursor: ошибка проверки оверлея: {e}")
                    continue

            self.logger.info("[DEBUG] _find_overlay_under_cursor: оверлей под курсором не найден")
            return None

        except Exception as e:
            self.logger.warning(f"[DEBUG] _find_overlay_under_cursor: общая ошибка: {e}")
            return None

    def _enable_esc_hook(self):
        """Включает глобальный хук ESC."""
        if not self._esc_hook_active:
            try:
                keyboard.on_press_key('esc', self._global_esc_handler)
                self._esc_hook_active = True
                self.logger.info("Глобальный хук ESC включен (OverlayManager)")
            except Exception as e:
                self.logger.warning(f"Не удалось включить глобальный хук ESC: {e}")

    def _disable_esc_hook(self):
        """Отключает глобальный хук ESC."""
        if self._esc_hook_active:
            try:
                keyboard.unhook_key('esc')
                self._esc_hook_active = False
                self.logger.info("Глобальный хук ESC отключен (OverlayManager)")
            except Exception as e:
                self.logger.warning(f"Не удалось отключить глобальный хук ESC: {e}")

    def hide_all_overlays(self):
        """Скрывает все оверлеи, но НЕ УДАЛЯЕТ их из списка."""
        self.logger.info(f"Скрытие всех {len(self.overlays)} оверлеев")
        for overlay in self.overlays:
            try:
                overlay.hide()
            except Exception as e:
                self.logger.error(f"Ошибка при скрытии оверлея: {e}")

    def close_all(self):
        """Закрывает все оверлеи."""
        self.logger.info(f"Закрытие всех оверлеев. Количество: {len(self.overlays)}")
        self._disable_esc_hook()
        # Используем копию списка, так как remove_overlay изменяет оригинал
        for overlay in self.overlays[:]:
            try:
                self.remove_overlay(overlay)
            except Exception as e:
                self.logger.error(f"Ошибка при закрытии оверлея: {e}")
        self.logger.info("Все оверлеи закрыты.")

    def show_all_sync(self):
        """Показывает все оверлеи синхронно, без мигания."""
        if self._show_all_sync_pending:
            self.logger.debug("[DEBUG] show_all_sync уже запланирован, пропускаем")
            return

        if not self.overlays:
            return

        # Проверяем, все ли оверлеи уже видны
        all_visible = True
        for overlay in self.overlays:
            if overlay is not None and not overlay.visible:
                all_visible = False
                break

        if all_visible:
            self.logger.debug("[DEBUG] Все оверлеи уже видны, пропускаем")
            return

        self._show_all_sync_pending = True
        self.logger.debug(f"[DEBUG] Запланирован синхронный показ всех {len(self.overlays)} оверлеев")

        if self._show_all_sync_timer:
            try:
                if hasattr(self.parent, 'root') and self.parent.root.winfo_exists():
                    self.parent.root.after_cancel(self._show_all_sync_timer)
            except:
                pass
            self._show_all_sync_timer = None

        def do_show_all():
            self._show_all_sync_pending = False
            self._show_all_sync_timer = None
            self._show_all_sync_impl()

        if hasattr(self.parent, 'root') and self.parent.root.winfo_exists():
            self._show_all_sync_timer = self.parent.root.after(50, do_show_all)
        else:
            self._show_all_sync_pending = False
            self._show_all_sync_impl()

    def _show_all_sync_impl(self):
        """Реальная реализация синхронного показа."""
        self.logger.info(f"[DEBUG] Синхронный показ всех {len(self.overlays)} оверлеев")

        # Сначала собираем все данные о оверлеях
        windows_to_show = []
        windows_to_load = []

        for overlay in self.overlays:
            try:
                if overlay is None:
                    continue

                # Если оверлей уже виден - пропускаем
                if overlay.visible:
                    self.logger.info(f"[DEBUG] Оверлей уже виден, пропускаем")
                    continue

                if overlay._image_loaded and overlay.tk_image is not None:
                    # Изображение уже загружено - показываем
                    windows_to_show.append(overlay)
                elif overlay._last_image_path and overlay._last_window_rect:
                    # Изображение не загружено - загружаем
                    windows_to_load.append(overlay)
            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка при сборе данных оверлея: {e}")

        # --- ШАГ 1: Загружаем изображения для всех оверлеев, которым это нужно ---
        for overlay in windows_to_load:
            try:
                self.logger.info(f"[DEBUG] Загружаем изображение для оверлея")
                overlay._load_and_show_image(overlay._last_image_path, overlay._last_window_rect)
                overlay._image_loaded = True
            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка при загрузке изображения: {e}")

        # --- ШАГ 2: ПОКАЗЫВАЕМ ВСЕ ОВЕРЛЕИ ОДНОВРЕМЕННО ---
        # Сначала обновляем все окна
        for overlay in windows_to_show + windows_to_load:
            try:
                if not overlay.visible:
                    overlay.root.deiconify()
                    overlay.root.lift()
                    overlay.visible = True
                    overlay._enable_esc_hook()

                    # Восстанавливаем сохраненную позицию
                    if overlay._saved_position:
                        x, y = overlay._saved_position
                        current_x = overlay.root.winfo_x()
                        current_y = overlay.root.winfo_y()
                        if abs(current_x - x) > 5 or abs(current_y - y) > 5:
                            overlay.root.geometry(f"+{x}+{y}")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка при показе оверлея: {e}")

        self.logger.info(
            f"[DEBUG] Синхронный показ завершен, показано {len(windows_to_show) + len(windows_to_load)} оверлеев")

    def set_dragging(self, dragging: bool):
        """Устанавливает глобальный флаг перетаскивания для всех оверлеев."""
        self._is_dragging_any = dragging
        self.logger.info(f"[DEBUG] Глобальный флаг перетаскивания установлен: {dragging}")

    def is_dragging(self) -> bool:
        """Возвращает состояние глобального флага перетаскивания."""
        return self._is_dragging_any

    def _get_overlay_position_file(self) -> Path:
        """Возвращает путь к файлу с сохраненными позициями оверлеев."""
        import json
        from pathlib import Path
        # Используем ту же директорию, что и для других настроек
        config_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "overlay_positions.json"

    def _load_overlay_positions(self) -> dict:
        """Загружает сохраненные позиции оверлеев из файла."""
        import json
        pos_file = self._get_overlay_position_file()
        if pos_file.exists():
            try:
                with open(pos_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Ошибка загрузки позиций оверлеев: {e}")
        return {}

    def _save_overlay_position(self, overlay_id: str, x: int, y: int):
        """Сохраняет позицию конкретного оверлея в файл."""
        import json
        positions = self._load_overlay_positions()
        positions[overlay_id] = {'x': x, 'y': y}
        pos_file = self._get_overlay_position_file()
        try:
            with open(pos_file, 'w', encoding='utf-8') as f:
                json.dump(positions, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения позиции оверлея: {e}")

    def show_all_overlays(self):
        """Показывает все оверлеи."""
        self.logger.info(f"Показ всех {len(self.overlays)} оверлеев")
        for overlay in self.overlays:
            try:
                overlay.show()
            except Exception as e:
                self.logger.error(f"Ошибка при показе оверлея: {e}")

    def show_last_overlay(self):
        """Показывает последний созданный оверлей."""
        if not self.overlays:
            self.logger.warning("Нет оверлеев для отображения.")
            return

        last_overlay = self.overlays[-1]
        if last_overlay.is_visible():
            self.logger.info("Последний оверлей уже виден.")
            return

        self.logger.info("Показ последнего оверлея.")
        last_overlay.show()

    def hide_last_overlay(self):
        """Скрывает последний созданный оверлей."""
        if not self.overlays:
            self.logger.warning("Нет оверлеев для скрытия.")
            return

        last_overlay = self.overlays[-1]
        if not last_overlay.is_visible():
            self.logger.info("Последний оверлей уже скрыт.")
            return

        self.logger.info("Скрытие последнего оверлея.")
        last_overlay.hide()

    def toggle_last_overlay(self):
        """Переключает видимость последнего созданного оверлея."""
        if not self.overlays:
            self.logger.warning("Нет оверлеев для переключения.")
            return

        last_overlay = self.overlays[-1]
        self.logger.info("Переключение видимости последнего оверлея.")
        last_overlay.toggle()

    def get_last_overlay_hwnd(self) -> Optional[int]:
        """Возвращает HWND последнего созданного оверлея."""
        if not self.overlays:
            return None
        return self.overlays[-1].get_overlay_hwnd()

    def get_last_overlay(self) -> Optional[OverlayWindow]:
        """Возвращает последний созданный оверлей."""
        if not self.overlays:
            return None
        return self.overlays[-1]

    def is_last_overlay_visible(self) -> bool:
        """Проверяет, виден ли последний оверлей."""
        if not self.overlays:
            return False
        return self.overlays[-1].is_visible()

    def set_auto_hide_for_all(self, enabled: bool):
        """Устанавливает режим автоскрытия для всех оверлеев."""
        self.logger.info(f"Установка режима автоскрытия для всех оверлеев: {enabled}")
        for overlay in self.overlays:
            try:
                overlay.set_auto_hide(enabled)
            except Exception as e:
                self.logger.error(f"Ошибка установки автоскрытия для оверлея: {e}")