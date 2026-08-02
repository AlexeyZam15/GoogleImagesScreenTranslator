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
        self._close_button_id = None
        self._close_button_visible = False
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
        # Поля для отслеживания позиции мыши
        self._last_mouse_x = -1
        self._last_mouse_y = -1
        self._mouse_position_known = False

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

    def show_for_window(self, image_path: Path, window_rect: tuple, target_hwnd: int = None,
                        is_fullscreen: bool = None, show_immediately: bool = True,
                        is_startup: bool = False):
        """
        Показывает оверлей для указанного окна.

        Args:
            is_startup: True если оверлей восстанавливается при запуске программы
        """
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

        # Сохраняем флаг запуска
        self._created_at_startup = is_startup

        # Если это запуск программы - загружаем изображение, но НЕ ПОКАЗЫВАЕМ
        if is_startup:
            self.logger.info("[DEBUG] Режим запуска: загружаем изображение, но НЕ показываем оверлей")
            self._load_and_show_image(image_path, window_rect, show_immediately=False, is_startup=is_startup)
            # Явно скрываем окно
            try:
                self.root.withdraw()
                self.visible = False
                self.logger.info("[DEBUG] Оверлей скрыт при запуске")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось скрыть оверлей: {e}")
            # Запускаем монитор видимости, который покажет оверлей когда окно станет активным
            if self.auto_hide_enabled:
                self.logger.info("[DEBUG] Запуск монитора для отслеживания активации окна")
                self.root.after(500, self._start_visibility_monitor)
            return

        # Обычный режим - показываем сразу
        self.logger.info("[DEBUG] Обычный режим: показываем оверлей")
        self._load_and_show_image(image_path, window_rect, show_immediately=show_immediately, is_startup=is_startup)

        if show_immediately:
            self.logger.info("[DEBUG] show_immediately=True, показываем оверлей")
            self._stop_visibility_monitor()
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

        try:
            x1, y1, x2, y2 = window_rect
            self.logger.info(f"[DEBUG] x1={x1}, y1={y1}, x2={x2}, y2={y2}")

            if x1 < 0:
                pos_x = 0
                win_width = x2
            else:
                pos_x = x1
                win_width = x2 - x1

            win_height = y2 - y1
            self.logger.info(f"[DEBUG] pos_x={pos_x}, win_width={win_width}, win_height={win_height}")

            saved_x = None
            saved_y = None

            if hasattr(self, '_user_moved') and self._user_moved:
                saved_position = self._get_saved_position()
                if saved_position:
                    saved_x, saved_y = saved_position
                    self.logger.info(
                        f"[DEBUG] Используем сохраненную позицию (пользователь переместил): ({saved_x}, {saved_y})")
            else:
                self.logger.info("[DEBUG] Оверлей еще не перемещен пользователем, используем позицию из window_rect")

            if saved_x is not None and saved_y is not None:
                pos_x = saved_x
                y1 = saved_y
                self.logger.info(f"[DEBUG] Используем сохраненную позицию: pos_x={pos_x}, y1={y1}")

            self.logger.info("[DEBUG] Открываем изображение")
            img = Image.open(image_path)
            self.logger.info(f"[DEBUG] Изображение открыто: {img.width}x{img.height}")

            ratio = min(win_width / img.width, win_height / img.height)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)
            self.logger.info(f"[DEBUG] ratio={ratio}, new_w={new_w}, new_h={new_h}")

            self.logger.info("[DEBUG] Изменяем размер изображения")
            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)
            self.logger.info("[DEBUG] Размер изменен")

            temp_img = self.temp_dir / "overlay.png"
            img.save(temp_img)
            self.logger.info(f"[DEBUG] Изображение сохранено во временный файл: {temp_img}")

            self.logger.info("[DEBUG] Создаем PhotoImage")
            pil_img = Image.open(temp_img)
            photo = ImageTk.PhotoImage(pil_img)
            self._images.append(photo)
            self.tk_image = photo
            self.logger.info("[DEBUG] PhotoImage создан")

            self.logger.info(f"[DEBUG] Устанавливаем геометрию: {win_width}x{win_height}+{pos_x}+{y1}")
            self.root.geometry(f"{win_width}x{win_height}+{pos_x}+{y1}")

            self.root.attributes('-topmost', True)
            self.root.attributes('-toolwindow', True)
            self.logger.info("[DEBUG] Атрибуты окна установлены")

            self.logger.info("[DEBUG] Очищаем canvas")
            self.canvas.delete("all")
            self.canvas.config(width=win_width, height=win_height)
            self.canvas.create_rectangle(0, 0, win_width, win_height, fill='#000000', outline='', tags=('bg_rect',))
            self.logger.info("[DEBUG] Canvas очищен")

            x = (win_width - new_w) // 2
            y = (win_height - new_h) // 2
            self.logger.info(f"[DEBUG] Позиция изображения на canvas: x={x}, y={y}")
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image)
            self.logger.info("[DEBUG] Изображение добавлено на canvas")

            self.visible = False  # По умолчанию скрыт
            self._show_time = time.time()
            self._monitor_stable_time = time.time() + 2.0
            self._image_loaded = True

            # Если это запуск программы - НЕ ПОКАЗЫВАЕМ окно
            if is_startup:
                self.logger.info("[DEBUG] Режим запуска: окно остается скрытым")
                try:
                    self.root.withdraw()
                    self.visible = False
                    self.logger.info("[DEBUG] Окно скрыто")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Не удалось скрыть окно: {e}")
                return

            if show_immediately:
                self.logger.info("[DEBUG] Показываем окно (асинхронно)")
                try:
                    self.visible = True
                    self.root.after(0, self._show_window_safe)
                    self.logger.info("[DEBUG] root.after(0, self._show_window_safe) выполнен")
                except Exception as e:
                    self.logger.error(f"[DEBUG] Ошибка при показе окна: {e}")
            else:
                self.logger.info("[DEBUG] show_immediately=False, окно скрыто")
                try:
                    self.root.withdraw()
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Не удалось скрыть окно: {e}")

            self._ensure_topmost()
            self.logger.info("[DEBUG] _ensure_topmost выполнен")

            overlay_hwnd = int(self.root.winfo_id())
            self.logger.info(f"[DEBUG] HWND оверлея: {overlay_hwnd}")

            try:
                ex_style = win32gui.GetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE)
                new_ex_style = ex_style | 0x08000000 | win32con.WS_EX_TOPMOST | 0x00000080
                win32gui.SetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE, new_ex_style)
                self.logger.info("[DEBUG] Установлены стили WS_EX_NOACTIVATE и WS_EX_TOPMOST")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось установить стили: {e}")

            if show_immediately:
                try:
                    win32gui.ShowWindow(overlay_hwnd, win32con.SW_SHOWNOACTIVATE)
                    win32gui.SetWindowPos(
                        overlay_hwnd,
                        win32con.HWND_TOPMOST,
                        0, 0, 0, 0,
                        win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                    )
                    self.logger.info("[DEBUG] Оверлей показан без активации (SW_SHOWNOACTIVATE)")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Не удалось показать оверлей без активации: {e}")

            def on_focus_in(event):
                self.logger.info("[DEBUG] Оверлей пытается получить фокус - блокируем")
                return "break"

            def block_activate(event):
                return "break"

            self.root.bind('<FocusIn>', on_focus_in, add=True)
            self.canvas.bind('<FocusIn>', on_focus_in, add=True)
            self.root.bind('<Button-1>', block_activate, add=True)
            self.root.bind('<ButtonRelease-1>', block_activate, add=True)
            self.canvas.bind('<Button-1>', block_activate, add=True)
            self.canvas.bind('<ButtonRelease-1>', block_activate, add=True)
            self.logger.info("[DEBUG] Обработчики фокуса установлены")

            self._enable_esc_hook()
            self.logger.info("[DEBUG] ESC хук включен")

            self.logger.info(f"[DEBUG] auto_hide_enabled={self.auto_hide_enabled}")

            self._monitor_initialized = False
            self._last_active_hwnd = None

            if self.auto_hide_enabled and show_immediately:
                self.logger.info("[DEBUG] Запуск монитора видимости с задержкой 1500мс")
                self.root.after(1500, self._start_visibility_monitor_delayed)
            elif not show_immediately:
                self.logger.info("[DEBUG] show_immediately=False, монитор не запущен")

            self.logger.info(
                f"[DEBUG] Изображение загружено и {'показано' if show_immediately else 'скрыто'}: {win_width}x{win_height}")

            if self._edit_mode_enabled and self._mouse_over and show_immediately:
                self._show_close_button()
                self.logger.info("[DEBUG] Кнопка закрытия показана")

            self.logger.info("[DEBUG] === _load_and_show_image ЗАВЕРШЕН ===")

        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка загрузки изображения: {e}")
            import traceback
            traceback.print_exc()
            self._image_loaded = False
            self.logger.info("[DEBUG] === _load_and_show_image ЗАВЕРШЕН С ОШИБКОЙ ===")

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

    def show(self):
        """Показывает оверлей с принудительным обновлением позиции."""
        self.logger.info("[DEBUG] show() вызван")

        if not self._last_image_path or not self._last_window_rect:
            self.logger.warning("[DEBUG] show() - нет сохраненного изображения или rect")
            return

        # === ЕСЛИ ИЗОБРАЖЕНИЕ НЕ ЗАГРУЖЕНО, ЗАГРУЖАЕМ ЕГО ===
        if not self._image_loaded or self.tk_image is None:
            self.logger.info("[DEBUG] show() - изображение не загружено, загружаем")
            self._load_and_show_image(self._last_image_path, self._last_window_rect, show_immediately=True)
            return

        if self.visible:
            self.logger.info("[DEBUG] show() - оверлей уже виден")
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

        # === ПРИНУДИТЕЛЬНО ОБНОВЛЯЕМ ПОЗИЦИЮ ПЕРЕД ПОКАЗОМ ===
        if self._last_window_rect:
            x1, y1, x2, y2 = self._last_window_rect
            width = x2 - x1
            height = y2 - y1
            self.root.geometry(f"{width}x{height}+{x1}+{y1}")
            self.logger.info(f"[DEBUG] show() - принудительно установлена позиция: ({x1}, {y1}) {width}x{height}")

        try:
            self._suppress_enter_events = True
            self.root.after(0, self._show_window_safe)
            self.visible = True
            self._ensure_topmost()
            self._is_visible_by_user = True
            self._enable_esc_hook()
            if self.auto_hide_enabled:
                self._start_visibility_monitor()
            self.root.after(300, lambda: setattr(self, '_suppress_enter_events', False))
            self.logger.info("[DEBUG] show() - оверлей показан")
        except Exception as e:
            self.logger.warning(f"[DEBUG] show() - ошибка при показе окна: {e}")

        if self._edit_mode_enabled and self._mouse_over:
            self._show_close_button()

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

    def _start_drag(self, event):
        """Начинает перетаскивание окна."""
        self.logger.info(f"[DEBUG] _start_drag вызван! event=({event.x}, {event.y})")

        # ДЛЯ F2 (СКРИНШОТ ОКНА) ВСЕГДА РАЗРЕШАЕМ ПЕРЕТАСКИВАНИЕ
        if self._is_window_screenshot:
            self.logger.info("[DEBUG] _start_drag: F2-оверлей, перетаскивание разрешено")
        else:
            # Для F3 (область) проверяем режим редактирования
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
                except Exception as e:
                    self.logger.warning(f"[DEBUG] _start_drag: ошибка проверки режима: {e}")

            if not is_edit_mode:
                self.logger.info("[DEBUG] _start_drag: режим редактирования ВЫКЛЮЧЕН - перетаскивание запрещено")
                return "break"

        if not self._is_visible_by_user or not self.visible:
            self.logger.info("[DEBUG] _start_drag - оверлей скрыт, перетаскивание запрещено")
            return "break"

        if self._drag_stop_timer:
            try:
                self.root.after_cancel(self._drag_stop_timer)
            except:
                pass
            self._drag_stop_timer = None

        # === НОВОЕ: СБРАСЫВАЕМ ФЛАГ _hidden_by_mouse И _mouse_over ===
        self._hidden_by_mouse = False
        self._mouse_over = False

        self._is_dragging = True
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self.logger.info("[DEBUG] Начало перетаскивания, флаг _is_dragging=True")

        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager.set_dragging(True)

    def _stop_drag(self, event):
        """Останавливает перетаскивание окна (только в режиме редактирования)."""
        self.logger.info("[DEBUG] _stop_drag вызван")
        self._is_dragging = False
        self._drag_data["x"] = 0
        self._drag_data["y"] = 0
        self.logger.info("[DEBUG] Конец перетаскивания, флаг _is_dragging=False")

        if self._edit_mode_enabled and self.visible and self._image_loaded:
            self._show_close_button()
            self.logger.debug("[DEBUG] _stop_drag: крестик показан после перетаскивания")

        try:
            if self.root and self.root.winfo_exists():
                overlay_x = self.root.winfo_x()
                overlay_y = self.root.winfo_y()

                self._user_moved = True

                if self._template_id and hasattr(self, '_overlay_manager') and self._overlay_manager:
                    self._overlay_manager._save_overlay_position(self._template_id, overlay_x, overlay_y)
                    self.logger.info(
                        f"[DEBUG] Сохранена позиция оверлея для шаблона {self._template_id[:8]}: ({overlay_x}, {overlay_y})")
                elif self._last_image_path and hasattr(self, '_overlay_manager') and self._overlay_manager:
                    overlay_id = str(self._last_image_path)
                    self._overlay_manager._save_overlay_position(overlay_id, overlay_x, overlay_y)
                    self.logger.info(f"[DEBUG] Сохранена позиция оверлея: {overlay_id} -> ({overlay_x}, {overlay_y})")

        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось сохранить позицию оверлея: {e}")

        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self._overlay_manager.set_dragging(False)
            self.logger.info("[DEBUG] Глобальный флаг перетаскивания сброшен")

        if self.root and self.root.winfo_exists():
            if self._drag_stop_timer:
                try:
                    self.root.after_cancel(self._drag_stop_timer)
                except:
                    pass
            self._drag_stop_timer = self.root.after(500, self._on_drag_stop_timeout)

        # === ПОСЛЕ ПЕРЕТАСКИВАНИЯ ВСЕГДА ПОКАЗЫВАЕМ ОВЕРЛЕЙ, ЕСЛИ ОН ДОЛЖЕН БЫТЬ ВИДЕН ===
        # Не проверяем позицию мыши — просто показываем оверлей
        self._hidden_by_mouse = False
        self._mouse_over = False
        self.logger.info("[DEBUG] _stop_drag: флаги _hidden_by_mouse и _mouse_over сброшены")

        if self._is_visible_by_user and not self._hidden_by_user:
            self.logger.info("[DEBUG] _stop_drag: показываем оверлей после перетаскивания")
            if not self.visible:
                self._show_internal()
                self.logger.info("[DEBUG] _stop_drag: оверлей показан")
            else:
                self.logger.info("[DEBUG] _stop_drag: оверлей уже виден")

    def _on_mouse_enter(self, event):
        """Обработчик входа мыши в область оверлея."""
        # === НОВОЕ: ПРОВЕРЯЕМ ФЛАГ ПЕРЕТАСКИВАНИЯ ===
        if self._is_dragging:
            self.logger.debug("[DEBUG] _on_mouse_enter: перетаскивание активно, игнорируем")
            return

        # Проверяем флаг подавления событий
        if self._suppress_enter_events:
            self.logger.debug("[DEBUG] _on_mouse_enter: событие подавлено (флаг _suppress_enter_events)")
            self._suppress_enter_events = False
            return

        # Проверяем, изменилась ли позиция мыши с момента выхода
        try:
            import win32api
            cursor_pos = win32api.GetCursorPos()
            current_x, current_y = cursor_pos
            self.logger.debug(
                f"[DEBUG] _on_mouse_enter: текущая позиция мыши ({current_x}, {current_y}), известна={self._mouse_position_known}")

            if self._mouse_position_known:
                self.logger.debug(
                    f"[DEBUG] _on_mouse_enter: сохраненная позиция ({self._last_mouse_x}, {self._last_mouse_y})")
                # Если позиция мыши не изменилась - это ложное событие (программный показ)
                if current_x == self._last_mouse_x and current_y == self._last_mouse_y:
                    self.logger.debug("[DEBUG] _on_mouse_enter: позиция мыши не изменилась, игнорируем ложное событие")
                    return
                else:
                    self.logger.debug("[DEBUG] _on_mouse_enter: позиция мыши изменилась, это реальное событие")
        except Exception as e:
            self.logger.debug(f"[DEBUG] _on_mouse_enter: ошибка получения позиции мыши: {e}")

        self._mouse_over = True

        if self._is_window_screenshot:
            self.logger.debug("[DEBUG] _on_mouse_enter: F2-оверлей, не скрываем")
            if self._edit_mode_enabled and self.visible:
                self._show_close_button()
            return

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

        if is_edit_mode and self.visible:
            self._show_close_button()
            self.logger.debug("[DEBUG] _on_mouse_enter: режим редактирования включен - оверлей не скрываем")
            return

        if is_edit_mode:
            self.logger.debug("[DEBUG] _on_mouse_enter: режим редактирования включен - оверлей не скрываем")
            return

        if not self.visible:
            return

        if hasattr(self, '_show_timer') and self._show_timer is not None:
            try:
                self.root.after_cancel(self._show_timer)
                self._show_timer = None
                self.logger.debug("[DEBUG] _on_mouse_enter: отменен запланированный показ оверлея")
            except:
                pass

        if self.visible and self._is_visible_by_user:
            self.logger.info("[DEBUG] _on_mouse_enter: скрываем оверлей (режим просмотра)")
            self._hidden_by_mouse = True
            self._hide_internal()
            if not self._monitor_timer and self.auto_hide_enabled:
                self.logger.info("[DEBUG] _on_mouse_enter: запускаем монитор для отслеживания выхода мыши")
                self._start_visibility_monitor()

    def _on_mouse_leave(self, event):
        """Обработчик выхода мыши из области оверлея."""
        # === НОВОЕ: ПРОВЕРЯЕМ ФЛАГ ПЕРЕТАСКИВАНИЯ ===
        if self._is_dragging:
            self.logger.debug("[DEBUG] _on_mouse_leave: перетаскивание активно, игнорируем")
            return

        self._mouse_over = False

        # Сохраняем позицию мыши при выходе ВСЕГДА, независимо от состояния _hidden_by_mouse
        try:
            import win32api
            cursor_pos = win32api.GetCursorPos()
            self._last_mouse_x, self._last_mouse_y = cursor_pos
            self._mouse_position_known = True
            self.logger.info(
                f"[DEBUG] _on_mouse_leave: сохранена позиция мыши ({self._last_mouse_x}, {self._last_mouse_y})")
        except Exception as e:
            self.logger.debug(f"[DEBUG] _on_mouse_leave: ошибка сохранения позиции мыши: {e}")
            self._mouse_position_known = False

        if self._edit_mode_enabled:
            self._hide_close_button()

        if self._is_window_screenshot:
            return

        # СБРАСЫВАЕМ ФЛАГ _hidden_by_mouse ПРИ ЛЮБОМ ВЫХОДЕ МЫШИ
        self.logger.info("[DEBUG] _on_mouse_leave: сбрасываем _hidden_by_mouse")
        self._hidden_by_mouse = False

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
            self.logger.debug("[DEBUG] _on_mouse_leave: режим редактирования, не показываем")
            return

        try:
            import win32gui
            import win32api

            active_hwnd = win32gui.GetForegroundWindow()

            cursor_pos = win32api.GetCursorPos()
            cursor_x, cursor_y = cursor_pos

            if self._last_window_rect:
                x1, y1, x2, y2 = self._last_window_rect
                if x1 <= cursor_x <= x2 and y1 <= cursor_y <= y2:
                    self.logger.debug("[DEBUG] _on_mouse_leave: курсор всё ещё внутри области оверлея - не показываем")
                    return

            is_target_active = (active_hwnd == self._target_hwnd)

            app_hwnd = None
            try:
                if hasattr(self.root, 'master'):
                    master = self.root.master
                    if master and master.winfo_exists():
                        app_hwnd = int(master.winfo_id())
            except:
                pass

            is_app_window = (active_hwnd == app_hwnd)

            # ВСЕГДА ПОКАЗЫВАЕМ ОВЕРЛЕЙ, ЕСЛИ ОН ДОЛЖЕН БЫТЬ ВИДЕН
            # Не проверяем активно ли целевое окно
            self.logger.info("[DEBUG] _on_mouse_leave: показываем оверлей (мышь вне области)")

            if hasattr(self, '_show_timer') and self._show_timer is not None:
                try:
                    self.root.after_cancel(self._show_timer)
                except:
                    pass
                self._show_timer = None

            if self._last_image_path and self._last_window_rect:
                if not self.visible and not self._hidden_by_mouse:
                    self._show_internal()

                    if self.auto_hide_enabled:
                        self._start_visibility_monitor()

        except Exception as e:
            self.logger.warning(f"[DEBUG] _on_mouse_leave: ошибка: {e}")
            self._hidden_by_mouse = False
            if self._last_image_path and self._last_window_rect:
                if not self.visible:
                    self._show_internal()

    def _show_window_safe(self):
        """Безопасно показывает окно (вызывается из root.after)."""
        try:
            if self.root and self.root.winfo_exists():
                self.root.deiconify()
                self.logger.info("[DEBUG] _show_window_safe: root.deiconify() выполнен")
                self.root.lift()
                self.logger.info("[DEBUG] _show_window_safe: root.lift() выполнен")
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
        """
        Внутренний метод для показа оверлея.

        Args:
            force: Если True, показываем оверлей принудительно, без проверки шаблона
        """
        if hasattr(self, '_showing_in_progress') and self._showing_in_progress:
            return
        self._showing_in_progress = True

        try:
            if hasattr(self, '_show_timer') and self._show_timer is not None:
                try:
                    self.root.after_cancel(self._show_timer)
                except:
                    pass
                self._show_timer = None

            if self._mouse_over or self._hidden_by_mouse:
                self.logger.debug("[DEBUG] _show_internal: мышь в зоне оверлея или оверлей скрыт мышью, не показываем")
                return

            if self._hidden_by_user:
                self.logger.debug("[DEBUG] _show_internal: оверлей скрыт пользователем, не показываем")
                return

            if not self._last_image_path or not self._last_window_rect:
                return

            if self.visible:
                self.logger.debug("[DEBUG] _show_internal: оверлей уже виден, пропускаем")
                return

            # === ДЛЯ АВТОЗАМЕНЫ: ПРОВЕРЯЕМ, НАЙДЕН ЛИ ШАБЛОН (только если не force) ===
            if self._is_auto_replace and not force:
                template_found = self._is_template_found()
                if not template_found:
                    self.logger.debug("[DEBUG] _show_internal: автозамена, шаблон не найден, не показываем оверлей")
                    return
                self.logger.debug("[DEBUG] _show_internal: автозамена, шаблон найден, показываем оверлей")

            # Устанавливаем флаг подавления событий
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
                    self.root.after(500, lambda: setattr(self, '_suppress_enter_events', False))
                    self.logger.info("[DEBUG] _show_internal: оверлей показан (уже загружен)")
                    return
                except Exception as e:
                    self.logger.warning(f"[DEBUG][_show_internal] ошибка при показе: {e}")

            self._load_and_show_image(self._last_image_path, self._last_window_rect)
            self._image_loaded = True
            self.logger.info("[DEBUG] _show_internal: оверлей загружен и показан")

        except Exception as e:
            self.logger.error(f"[DEBUG] _show_internal: ошибка: {e}")

        finally:
            self._showing_in_progress = False

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
        """Внутренний метод для скрытия оверлея (без изменения _is_visible_by_user) с защитой от рекурсии."""
        if hasattr(self, '_hiding_in_progress') and self._hiding_in_progress:
            return
        self._hiding_in_progress = True

        try:
            # Проверяем, не активно ли окно выбора области или режим захвата
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
            # ЯВНО УСТАНАВЛИВАЕМ флаг, что пользователь скрыл оверлей
            self.hide(by_user=True)
        else:
            self.logger.info("[DEBUG][toggle] оверлей скрыт -> показываем")
            # Сбрасываем флаг, что пользователь скрыл оверлей
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

    def hide(self, by_user: bool = True):
        """Скрывает оверлей.

        Args:
            by_user: True - если пользователь явно скрыл оверлей (через F1)
                    False - если оверлей скрывается автоматически (монитор автозамены)
        """
        self.logger.info(
            f"[DEBUG][hide] НАЧАЛО: visible={self.visible}, _is_visible_by_user={self._is_visible_by_user}, by_user={by_user}")

        # Устанавливаем флаг скрытия пользователем ТОЛЬКО если пользователь явно скрыл оверлей
        if by_user:
            self._hidden_by_user = True
            self._is_visible_by_user = False
        else:
            # Автоматическое скрытие - не меняем _hidden_by_user
            self._is_visible_by_user = False

        self._stop_visibility_monitor()
        self.visible = False
        self._disable_esc_hook()

        self._hide_close_button()

        try:
            self.root.withdraw()
            self.logger.info("[DEBUG][hide] оверлей скрыт (withdraw выполнен)")
        except Exception as e:
            self.logger.error(f"[DEBUG][hide] ОШИБКА: {e}")

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

        # Сначала скрываем кнопку закрытия
        self._hide_close_button()

        # === УВЕДОМЛЯЕМ МОНИТОР О ЗАКРЫТИИ ОВЕРЛЕЯ ===
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'translation_monitor') and parent.translation_monitor:
                # Ищем шаблон, связанный с этим оверлеем
                for template in parent.translation_monitor.templates:
                    if template.get('overlay') is self:
                        template['overlay'] = None
                        self.logger.info(
                            f"[MONITOR] Ссылка на оверлей сброшена для шаблона #{template.get('pair_index')}")
                        break

        # Очищаем Canvas от всех элементов
        try:
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.delete("all")
                self.canvas.update_idletasks()
                self.logger.info("[DEBUG] Canvas очищен при закрытии оверлея")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось очистить Canvas при закрытии: {e}")

        self._stop_visibility_monitor()
        self._disable_esc_hook()

        # Сбрасываем флаг контекстного меню
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

        try:
            overlay_hwnd = int(self.root.winfo_id())
            ctypes.windll.user32.SetWindowLongW(
                overlay_hwnd,
                -4,
                self._original_wndproc if hasattr(self, '_original_wndproc') else 0
            )
            self.logger.info("[DEBUG] Хук на сообщения окна восстановлен")
        except:
            pass

        if self._drag_stop_timer:
            try:
                self.root.after_cancel(self._drag_stop_timer)
            except:
                pass
            self._drag_stop_timer = None

        # Скрываем окно через withdraw (простой и надежный способ)
        try:
            if self.root and self.root.winfo_exists():
                self.root.withdraw()
                self.root.update_idletasks()
                self.logger.info("[DEBUG] Окно скрыто через withdraw")
                import time
                time.sleep(0.02)
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось скрыть окно: {e}")

        # Закрываем окно
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

        # Перерисовываем область, где был оверлей
        if rect:
            try:
                import win32gui
                import win32con

                target_hwnd = self._target_hwnd

                if target_hwnd and win32gui.IsWindow(target_hwnd):
                    self.logger.info(f"[DEBUG] Перерисовка области на целевом окне HWND={target_hwnd}")
                    win32gui.InvalidateRect(target_hwnd, (rect[0], rect[1], rect[2], rect[3]), True)
                    win32gui.UpdateWindow(target_hwnd)
                    win32gui.RedrawWindow(
                        target_hwnd,
                        (rect[0], rect[1], rect[2], rect[3]),
                        None,
                        win32con.RDW_INVALIDATE | win32con.RDW_UPDATENOW | win32con.RDW_ALLCHILDREN | win32con.RDW_FRAME | win32con.RDW_ERASE
                    )
                    self.logger.info(f"[DEBUG] Область перерисована на целевом окне: {rect}")
                else:
                    self.logger.info(f"[DEBUG] Целевое окно недоступно, используем десктоп")
                    hwnd_desktop = win32gui.GetDesktopWindow()
                    win32gui.InvalidateRect(hwnd_desktop, (rect[0], rect[1], rect[2], rect[3]), True)
                    win32gui.UpdateWindow(hwnd_desktop)
                    win32gui.RedrawWindow(
                        hwnd_desktop,
                        (rect[0], rect[1], rect[2], rect[3]),
                        None,
                        win32con.RDW_INVALIDATE | win32con.RDW_UPDATENOW | win32con.RDW_ALLCHILDREN | win32con.RDW_FRAME | win32con.RDW_ERASE
                    )
                    self.logger.info(f"[DEBUG] Область перерисована на десктопе: {rect}")

                try:
                    import win32api
                    monitor_info = win32api.GetMonitorInfo(win32api.MonitorFromPoint((rect[0], rect[1])))
                    monitor_rect = monitor_info.get('Monitor')
                    if monitor_rect:
                        hwnd_desktop = win32gui.GetDesktopWindow()
                        win32gui.InvalidateRect(hwnd_desktop, monitor_rect, True)
                        win32gui.UpdateWindow(hwnd_desktop)
                        win32gui.RedrawWindow(
                            hwnd_desktop,
                            monitor_rect,
                            None,
                            win32con.RDW_INVALIDATE | win32con.RDW_UPDATENOW | win32con.RDW_ALLCHILDREN | win32con.RDW_FRAME | win32con.RDW_ERASE
                        )
                        self.logger.info("[DEBUG] Монитор обновлен")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Не удалось обновить монитор: {e}")

            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось перерисовать область: {e}")

    def _remove_overlay(self):
        """Удаляет этот оверлей через OverlayManager."""
        self.logger.info("[DEBUG] _remove_overlay вызван")

        # Проверяем, что оверлей еще существует
        if not self.visible:
            self.logger.info("[DEBUG] _remove_overlay: оверлей не виден, пропускаем")
            return

        # Проверяем, является ли оверлей F2-оверлеем
        is_f2_overlay = False
        if hasattr(self, '_is_window_screenshot') and self._is_window_screenshot:
            is_f2_overlay = True
            self.logger.info("[DEBUG] _remove_overlay: F2-оверлей, удаление разрешено")

        # Для F3-оверлея проверяем режим редактирования через менеджер
        if not is_f2_overlay:
            if hasattr(self, '_overlay_manager') and self._overlay_manager:
                parent = self._overlay_manager.parent
                if parent and hasattr(parent, 'is_edit_mode_enabled') and not parent.is_edit_mode_enabled():
                    self.logger.info("[DEBUG] _remove_overlay: режим редактирования ВЫКЛЮЧЕН - удаление запрещено")
                    return
            else:
                self.logger.warning("[DEBUG] _remove_overlay: нет доступа к менеджеру, пропускаем")
                return

        # Закрываем контекстное меню, если оно открыто
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

        # Сбрасываем флаг контекстного меню
        self._context_menu_visible = False

        # Скрываем кнопку закрытия
        self._hide_close_button()

        # === УДАЛЯЕМ ШАБЛОН ИЗ МОНИТОРА ===
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'translation_monitor') and parent.translation_monitor:
                # Ищем шаблон, связанный с этим оверлеем
                for template in parent.translation_monitor.templates[:]:
                    if template.get('overlay') is self:
                        pair_index = template.get('pair_index')
                        self.logger.info(f"[MONITOR] Удаляем шаблон #{pair_index} при удалении оверлея")
                        parent.translation_monitor.remove_template(pair_index)
                        break

        # Удаляем через менеджер
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            self.logger.info(
                f"[DEBUG] Удаление оверлея через OverlayManager (всего оверлеев: {len(self._overlay_manager.overlays)})")
            self._overlay_manager.remove_overlay(self)
        else:
            self.logger.warning("[DEBUG] _remove_overlay: менеджер не найден, закрываем самостоятельно")
            self.close()

    def _on_close_click(self, event):
        """Обработчик клика по кнопке закрытия - удаляет оверлей."""
        self.logger.info("[DEBUG] _on_close_click вызван")

        # Проверяем режим редактирования через _overlay_manager
        is_edit_mode = False
        if hasattr(self, '_overlay_manager') and self._overlay_manager:
            parent = self._overlay_manager.parent
            if parent and hasattr(parent, 'is_edit_mode_enabled'):
                is_edit_mode = parent.is_edit_mode_enabled()

        if not is_edit_mode:
            self.logger.info("[DEBUG] _on_close_click: режим редактирования ВЫКЛЮЧЕН - удаление запрещено")
            return

        self._remove_overlay()

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

    def _show_close_button(self):
        """Показывает кнопку закрытия на Canvas оверлея."""
        # Проверяем, существует ли ещё окно
        if not self.root or not self.root.winfo_exists():
            self.logger.debug("[DEBUG] _show_close_button: окно уже закрыто, пропускаем")
            return

        if not self._edit_mode_enabled or not self.visible or not self._image_loaded:
            return

        if self._close_button_visible:
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

            # !!! ВЫЧИСЛЯЕМ ПРАВУЮ ГРАНИЦУ ВИДИМОЙ ОБЛАСТИ
            right_edge = min(overlay_x + canvas_width, screen_width)
            x_pos = (right_edge - overlay_x) - btn_size - padding
            if x_pos < 0:
                x_pos = padding

            # !!! ВЫЧИСЛЯЕМ ВЕРХНЮЮ ГРАНИЦУ ВИДИМОЙ ОБЛАСТИ
            # Если оверлей ушёл вверх за экран, крестик должен быть у верхнего края экрана
            top_edge = max(overlay_y, 0)
            y_pos = (top_edge - overlay_y) + padding

            # Если y_pos отрицательный или слишком большой - корректируем
            if y_pos < 0:
                y_pos = padding
            if y_pos + btn_size > canvas_height:
                y_pos = canvas_height - btn_size - padding

            self.logger.info(
                f"[DEBUG] _show_close_button: overlay_y={overlay_y}, screen_height={screen_height}, top_edge={top_edge}, y_pos={y_pos}")

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

            self._close_button_visible = True
            self.logger.info(f"[DEBUG] Кнопка закрытия показана на Canvas в позиции ({x_pos}, {y_pos})")

        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка создания кнопки закрытия: {e}")
            self._close_button_visible = False

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

    def _on_drag(self, event):
        """Перемещает окно во время перетаскивания (только в режиме редактирования)."""
        if self._is_dragging and self.root.winfo_exists():
            x = self.root.winfo_x() + (event.x - self._drag_data["x"])
            y = self.root.winfo_y() + (event.y - self._drag_data["y"])
            self.root.geometry(f"+{x}+{y}")
            self._saved_position = (x, y)

            # !!! СКРЫВАЕМ КРЕСТИК ВО ВРЕМЯ ПЕРЕТАСКИВАНИЯ
            if self._close_button_visible:
                self.canvas.delete('close_btn')
                self._close_button_visible = False
                self._close_button_id = None
                self.logger.debug("[DEBUG] _on_drag: крестик скрыт во время перетаскивания")

            self.logger.debug(f"Перемещение в ({x}, {y})")

    def _on_right_click(self, event):
        """Обработчик правой кнопки мыши - показывает контекстное меню через менеджер."""
        self.logger.info("[DEBUG] _on_right_click вызван")

        if self._right_click_processing:
            self.logger.info("[DEBUG] _on_right_click: уже обрабатывается, пропускаем")
            return

        if not self.visible:
            self.logger.info("[DEBUG] _on_right_click: оверлей не виден, пропускаем")
            return

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
            self.logger.info("[DEBUG] _on_right_click: режим редактирования ВЫКЛЮЧЕН - меню не показываем")
            return

        if not hasattr(self, '_overlay_manager') or not self._overlay_manager:
            self.logger.warning("[DEBUG] _on_right_click: менеджер не найден")
            return

        if self._overlay_manager and self not in self._overlay_manager.overlays:
            self.logger.info("[DEBUG] _on_right_click: оверлей уже удален, пропускаем")
            return

        self._right_click_processing = True
        self.logger.info("[DEBUG] _on_right_click: установлен флаг _right_click_processing = True")

        self._context_menu_visible = True
        self.logger.info("[DEBUG] _on_right_click: установлен флаг _context_menu_visible = True")

        # !!! ИСПРАВЛЕНИЕ: НЕ ОСТАНАВЛИВАЕМ МОНИТОР ВИДИМОСТИ
        # Монитор должен продолжать работать, чтобы оверлей автоскрывался как обычно
        # self._stop_visibility_monitor()  # <-- УБРАНО!

        self._overlay_manager.show_context_menu(self, event.x_root, event.y_root)
        self.logger.info("[DEBUG] Контекстное меню показано через менеджер")

        # Запускаем монитор закрытия меню
        self._start_menu_close_monitor()

        if self.root and self.root.winfo_exists():
            self.root.after(500, self._reset_right_click_flag)

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

    def _hide_close_button(self):
        """Скрывает кнопку закрытия на Canvas оверлея."""
        if not self._close_button_visible:
            return

        try:
            # Проверяем, существует ли Canvas
            if self.canvas and self.canvas.winfo_exists():
                self.canvas.delete('close_btn')
                self.canvas.update_idletasks()
            self._close_button_visible = False
            self._close_button_id = None
            self.logger.debug("[DEBUG] Кнопка закрытия скрыта")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось скрыть кнопку закрытия: {e}")
            self._close_button_visible = False
            self._close_button_id = None

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

    def update_edit_mode(self, edit_mode_enabled: bool):
        """Обновляет состояние режима редактирования для оверлея."""
        self._edit_mode_enabled = edit_mode_enabled
        self.logger.info(f"[DEBUG] Обновлен _edit_mode_enabled = {edit_mode_enabled}")
        if not self._edit_mode_enabled:
            self._hide_close_button()

    def _update_close_button_visibility(self):
        """Обновляет видимость кнопки закрытия в зависимости от режима редактирования."""
        should_be_visible = self._edit_mode_enabled and self.visible and self._image_loaded

        if should_be_visible and not self._close_button_visible:
            self._show_close_button()
        elif not should_be_visible and self._close_button_visible:
            self._hide_close_button()

        self.logger.debug(
            f"[DEBUG] Кнопка закрытия: видимость={should_be_visible}, текущее состояние={self._close_button_visible}")

    def _start_close_button_position_updater(self):
        """Запускает периодическое обновление позиции кнопки закрытия."""

        def update_position():
            if not self.root or not self.root.winfo_exists():
                return
            if self._close_button_visible and self._close_button is not None:
                try:
                    if self._close_button.winfo_exists():
                        self._update_close_button_position()
                except:
                    pass
            if self._close_button_visible and self.root and self.root.winfo_exists():
                self.root.after(100, update_position)

        if self.root and self.root.winfo_exists():
            self.root.after(100, update_position)


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
