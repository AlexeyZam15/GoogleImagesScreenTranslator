"""

Модуль для оверлейного окна с переведенным изображением

"""

import logging
import tempfile
import time  # <--- ДОБАВИТЬ ЭТУ СТРОКУ
from pathlib import Path
from typing import Optional  # <--- ДОБАВИТЬ ЭТУ СТРОКУ
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
        # ИСПРАВЛЕНО: используем безопасную временную папку
        from src.utils import ensure_app_temp_dir
        self.temp_dir = ensure_app_temp_dir()
        self.tk_image = None
        self._target_rect = None
        self._esc_hook_active = False
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

        self._overlay_active = False
        self._last_active_hwnd = None
        self._monitor_initialized = False
        self._monitor_stable_time = 0  # Время стабилизации монитора

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

        self.root.bind('<Escape>', self._on_escape)

        self.logger.info("OverlayWindow инициализирован")

    def get_overlay_hwnd(self) -> Optional[int]:
        """Возвращает HWND окна оверлея"""
        try:
            if self.root and self.root.winfo_exists():
                return int(self.root.winfo_id())
        except:
            pass
        return None

    def _load_and_show_image(self, image_path: Path, window_rect: tuple):
        self.logger.info(f"_load_and_show_image: {image_path}")

        try:
            import time
            import win32gui
            import win32con
            import win32api

            x1, y1, x2, y2 = window_rect
            win_width = x2 - x1
            win_height = y2 - y1

            img = Image.open(image_path)

            ratio = min(win_width / img.width, win_height / img.height)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            temp_img = self.temp_dir / "overlay.png"
            img.save(temp_img)

            pil_img = Image.open(temp_img)
            photo = ImageTk.PhotoImage(pil_img)
            self._images.append(photo)
            self.tk_image = photo

            # Определяем позицию оверлея
            if self._is_fullscreen_target:
                pos_x, pos_y = 0, 0
                self.logger.info(f"Полноэкранный режим: позиция (0, 0)")
            else:
                pos_x, pos_y = x1, y1
                self.logger.info(f"Обычный режим: позиция ({pos_x}, {pos_y})")

            self.root.geometry(f"{win_width}x{win_height}+{pos_x}+{pos_y}")

            # Всегда поверх всех окон, даже если игра свернулась
            self.root.attributes('-topmost', True)
            # Не сворачиваться вместе с игрой
            self.root.attributes('-toolwindow', True)

            self.canvas.delete("all")
            self.canvas.config(width=win_width, height=win_height)
            self.canvas.create_rectangle(0, 0, win_width, win_height, fill='#000000', outline='')

            x = (win_width - new_w) // 2
            y = (win_height - new_h) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image)

            self.visible = True
            self._show_time = time.time()
            self._monitor_stable_time = time.time() + 2.0

            # Показываем окно
            self.root.deiconify()
            self.root.lift()

            # Получаем HWND оверлея
            overlay_hwnd = int(self.root.winfo_id())
            self.logger.info(f"[DEBUG] HWND оверлея: {overlay_hwnd}")

            # Устанавливаем расширенные стили окна
            try:
                ex_style = win32gui.GetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE)
                # WS_EX_NOACTIVATE (0x08000000) - не активируется
                # WS_EX_TOPMOST (0x00000008) - поверх всех окон
                # WS_EX_TOOLWINDOW (0x00000080) - не отображается в панели задач
                new_ex_style = ex_style | 0x08000000 | win32con.WS_EX_TOPMOST | 0x00000080
                win32gui.SetWindowLong(overlay_hwnd, win32con.GWL_EXSTYLE, new_ex_style)
                self.logger.info(f"[DEBUG] Установлены стили WS_EX_NOACTIVATE и WS_EX_TOPMOST")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось установить стили: {e}")

            # Показываем окно без активации
            try:
                win32gui.ShowWindow(overlay_hwnd, win32con.SW_SHOWNOACTIVATE)
                win32gui.SetWindowPos(
                    overlay_hwnd,
                    win32con.HWND_TOPMOST,
                    0, 0, 0, 0,
                    win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_NOACTIVATE | win32con.SWP_SHOWWINDOW
                )
                self.logger.info(f"[DEBUG] Оверлей показан без активации (SW_SHOWNOACTIVATE)")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось показать оверлей без активации: {e}")
                try:
                    win32gui.ShowWindow(overlay_hwnd, win32con.SW_SHOW)
                except:
                    pass

            # Блокируем активацию через Tkinter
            def on_focus_in(event):
                self.logger.info("[DEBUG] Оверлей пытается получить фокус - блокируем")
                return "break"

            def block_activate(event):
                # Просто блокируем событие, не возвращаем фокус игре
                return "break"

            # Привязываем обработчики для блокировки фокуса
            self.root.bind('<FocusIn>', on_focus_in, add=True)
            self.canvas.bind('<FocusIn>', on_focus_in, add=True)
            self.root.bind('<Button-1>', block_activate, add=True)
            self.root.bind('<ButtonRelease-1>', block_activate, add=True)
            self.canvas.bind('<Button-1>', block_activate, add=True)
            self.canvas.bind('<ButtonRelease-1>', block_activate, add=True)

            self._enable_esc_hook()

            self.logger.info(f"_load_and_show_image: auto_hide_enabled={self.auto_hide_enabled}")

            # Сбрасываем состояние монитора
            self._monitor_initialized = False
            self._last_active_hwnd = None

            # Запускаем монитор, но он НЕ будет скрывать оверлей для полноэкранных приложений
            if self.auto_hide_enabled:
                self.logger.info("Запуск монитора видимости с задержкой 1500мс")
                self.root.after(1500, self._start_visibility_monitor_delayed)
            else:
                self.logger.info("Автоскрытие отключено, монитор не запущен")

            self.logger.info(f"Изображение загружено и показано: {win_width}x{win_height}")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки изображения: {e}")
            import traceback
            traceback.print_exc()

    def _start_visibility_monitor_delayed(self):
        """Запускает монитор видимости с задержкой"""
        self.logger.info(
            f"[DEBUG][_start_visibility_monitor_delayed] НАЧАЛО: visible={self.visible}, _is_visible_by_user={self._is_visible_by_user}")

        if not self.visible or not self._is_visible_by_user:
            self.logger.info(
                "[DEBUG][_start_visibility_monitor_delayed] оверлей скрыт или не должен быть виден, отменяем запуск монитора")
            return

        if self._monitor_initialized:
            self.logger.info("[DEBUG][_start_visibility_monitor_delayed] монитор уже инициализирован, пропускаем")
            return

        self.logger.info("[DEBUG][_start_visibility_monitor_delayed] запускаем монитор")
        self._start_visibility_monitor()

    def _start_visibility_monitor(self):
        """Запускает монитор видимости - унифицированная логика"""
        if not self.auto_hide_enabled:
            self.logger.info("Автоскрытие отключено, монитор не запущен")
            return

        if self._monitor_initialized:
            self.logger.info("Монитор уже запущен, пропускаем")
            return

        self._stop_visibility_monitor()

        try:
            import win32gui
            current_hwnd = win32gui.GetForegroundWindow()

            # Если текущее окно 0 - пытаемся получить целевое окно
            if current_hwnd == 0:
                if self._target_hwnd:
                    current_hwnd = self._target_hwnd
                    self.logger.info(f"[DEBUG] Текущее активное окно = 0, используем целевое: {current_hwnd}")
                else:
                    self.logger.info("[DEBUG] Текущее активное окно = 0, ждем следующей проверки")
                    self._monitor_initialized = False
                    if self.root and self.root.winfo_exists():
                        self._monitor_timer = self.root.after(500, self._start_visibility_monitor)
                    return

            self._last_active_hwnd = current_hwnd
            self._monitor_initialized = True
            self.logger.info(f"[DEBUG] Монитор инициализирован, текущее активное окно: HWND={current_hwnd}")
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
                        self._monitor_timer = self.root.after(500, check_visibility)
                    return

                if not self._is_visible_by_user:
                    self._stop_visibility_monitor()
                    return

                self._check_and_update_visibility()

                if self._is_visible_by_user and self.root and self.root.winfo_exists():
                    self._monitor_timer = self.root.after(500, check_visibility)
                else:
                    self._monitor_timer = None

            except Exception as e:
                self.logger.warning(f"Ошибка в мониторе видимости: {e}")
                if self._is_visible_by_user and self.root and self.root.winfo_exists():
                    self._monitor_timer = self.root.after(500, check_visibility)

        if self.root and self.root.winfo_exists():
            self._monitor_timer = self.root.after(500, check_visibility)
            self.logger.info("Монитор видимости запущен")

    def _check_and_update_visibility(self):
        """Унифицированная проверка активного окна"""
        if not self.auto_hide_enabled or not self._is_visible_by_user:
            return

        # Защита от быстрых изменений после показа
        import time
        if time.time() < self._monitor_stable_time:
            return

        try:
            import win32gui
            import win32process

            active_hwnd = win32gui.GetForegroundWindow()

            # Игнорируем переходные состояния
            if active_hwnd == 0:
                return

            # Игнорируем системные окна переключения
            try:
                class_name = win32gui.GetClassName(active_hwnd)
                if class_name in ['MultitaskingViewFrame', 'ForegroundStaging']:
                    return
            except:
                pass

            # Проверяем, не является ли активное окно нашим оверлеем
            overlay_hwnd = None
            if hasattr(self, 'root') and self.root.winfo_exists():
                try:
                    overlay_hwnd = int(self.root.winfo_id())
                except:
                    pass

            # ЕСЛИ АКТИВНОЕ ОКНО - ОВЕРЛЕЙ, НИЧЕГО НЕ ДЕЛАЕМ
            if overlay_hwnd is not None and active_hwnd == overlay_hwnd:
                self._last_active_hwnd = active_hwnd
                self.logger.info(f"[DEBUG] Активное окно - оверлей, пропускаем проверку")
                return

            # Если активное окно не изменилось - ничего не делаем
            if active_hwnd == self._last_active_hwnd:
                return

            self._last_active_hwnd = active_hwnd
            self.logger.info(f"[DEBUG] Активное окно изменилось на HWND={active_hwnd}")

            # Проверяем, является ли новое окно нашим (целевым, оверлеем или главным окном)
            app_hwnd = None
            try:
                if hasattr(self.root, 'master'):
                    master = self.root.master
                    if master and master.winfo_exists():
                        app_hwnd = int(master.winfo_id())
            except:
                pass

            is_our_window = (
                    active_hwnd == self._target_hwnd or
                    (overlay_hwnd is not None and active_hwnd == overlay_hwnd) or
                    (app_hwnd is not None and active_hwnd == app_hwnd)
            )

            self.logger.info(f"[DEBUG] is_our_window={is_our_window}, visible={self.visible}")

            if not is_our_window and self.visible:
                self.logger.info("[DEBUG] Переключились на другое окно - скрываем оверлей")
                self._hide_internal()
            elif is_our_window and not self.visible and self._is_visible_by_user:
                self.logger.info("[DEBUG] Переключились на наше окно - показываем оверлей")
                self._show_internal()

        except Exception as e:
            self.logger.warning(f"Ошибка в _check_and_update_visibility: {e}")

    def _is_target_window_active(self) -> bool:
        """
        Проверяет, должен ли оверлей считаться активным.
        Для полноэкранных приложений: возвращает True если оверлей виден и пользователь хочет его видеть.
        Для обычных окон: проверяет активное окно.
        """
        self.logger.info("=" * 80)
        self.logger.info("[DEBUG][_is_target_window_active] ========== НАЧАЛО ПРОВЕРКИ ==========")
        self.logger.info(f"[DEBUG][_is_target_window_active] _target_hwnd={self._target_hwnd}")
        self.logger.info(f"[DEBUG][_is_target_window_active] _is_fullscreen_target={self._is_fullscreen_target}")
        self.logger.info(f"[DEBUG][_is_target_window_active] self.visible={self.visible}")
        self.logger.info(f"[DEBUG][_is_target_window_active] self._is_visible_by_user={self._is_visible_by_user}")

        if self._target_hwnd is None:
            self.logger.info("[DEBUG][_is_target_window_active] РЕЗУЛЬТАТ: False (_target_hwnd is None)")
            self.logger.info("=" * 80)
            return False

        # === ДЛЯ ПОЛНОЭКРАННЫХ ПРИЛОЖЕНИЙ ===
        if self._is_fullscreen_target:
            result = self.visible and self._is_visible_by_user
            self.logger.info(f"[DEBUG][_is_target_window_active] полноэкранный режим -> {result}")
            self.logger.info("=" * 80)
            return result

        # === ДЛЯ ОБЫЧНЫХ ОКОН ===
        try:
            import win32gui

            active_hwnd = win32gui.GetForegroundWindow()
            self.logger.info(f"[DEBUG][_is_target_window_active] active_hwnd={active_hwnd}")

            if not active_hwnd or active_hwnd == 0:
                self.logger.info("[DEBUG][_is_target_window_active] РЕЗУЛЬТАТ: False (нет активного окна)")
                self.logger.info("=" * 80)
                return False

            # Получаем HWND оверлея
            overlay_hwnd = None
            if hasattr(self, 'root') and self.root.winfo_exists():
                try:
                    overlay_hwnd = int(self.root.winfo_id())
                except:
                    pass

            # Получаем HWND главного окна приложения
            app_hwnd = None
            try:
                if hasattr(self.root, 'master'):
                    master = self.root.master
                    if master and master.winfo_exists():
                        app_hwnd = int(master.winfo_id())
            except:
                pass

            self.logger.info(f"[DEBUG][_is_target_window_active] overlay_hwnd={overlay_hwnd}, app_hwnd={app_hwnd}")

            # Если активное окно - оверлей
            if overlay_hwnd is not None and active_hwnd == overlay_hwnd:
                self.logger.info("[DEBUG][_is_target_window_active] РЕЗУЛЬТАТ: True (активное окно - оверлей)")
                self.logger.info("=" * 80)
                return True

            # Если активное окно - главное окно приложения
            if app_hwnd is not None and active_hwnd == app_hwnd:
                self.logger.info(
                    "[DEBUG][_is_target_window_active] РЕЗУЛЬТАТ: True (активное окно - главное приложение)")
                self.logger.info("=" * 80)
                return True

            # Если активное окно - игра
            if active_hwnd == self._target_hwnd:
                self.logger.info("[DEBUG][_is_target_window_active] РЕЗУЛЬТАТ: True (активное окно - игра)")
                self.logger.info("=" * 80)
                return True

            self.logger.info("[DEBUG][_is_target_window_active] РЕЗУЛЬТАТ: False (активное окно - другое приложение)")
            self.logger.info("=" * 80)
            return False

        except Exception as e:
            self.logger.warning(f"[DEBUG][_is_target_window_active] ОШИБКА: {e}")
            self.logger.info("=" * 80)
            return False

    def _hide_internal(self):
        self.logger.info(f"[DEBUG][_hide_internal] НАЧАЛО: visible={self.visible}")
        self.visible = False
        try:
            self.root.withdraw()
            self._disable_esc_hook()
            self.logger.info("[DEBUG][_hide_internal] оверлей скрыт (withdraw выполнен)")
        except Exception as e:
            self.logger.error(f"[DEBUG][_hide_internal] ОШИБКА: {e}")

    def _show_internal(self):
        self.logger.info(
            f"[DEBUG][_show_internal] НАЧАЛО: visible={self.visible}, _last_image_path={self._last_image_path is not None}")
        if not self._last_image_path or not self._last_window_rect:
            self.logger.warning("[DEBUG][_show_internal] нет сохраненного изображения или rect")
            return
        self.logger.info(f"[DEBUG][_show_internal] показываем оверлей, image={self._last_image_path}")
        self._load_and_show_image(self._last_image_path, self._last_window_rect)

    def hide(self):
        self.logger.info(
            f"[DEBUG][hide] НАЧАЛО: visible={self.visible}, _is_visible_by_user={self._is_visible_by_user}")
        self._is_visible_by_user = False
        self._stop_visibility_monitor()
        self.visible = False
        self._disable_esc_hook()

        try:
            self.root.withdraw()
            self.logger.info("[DEBUG][hide] оверлей скрыт (сброс состояния)")
        except Exception as e:
            self.logger.error(f"[DEBUG][hide] ОШИБКА: {e}")

    def toggle(self):
        """Переключает видимость оверлея и возвращает фокус на целевое окно"""
        self.logger.info(
            f"[DEBUG][toggle] НАЧАЛО: visible={self.visible}, _is_visible_by_user={self._is_visible_by_user}")

        if self.visible:
            self.logger.info("[DEBUG][toggle] оверлей виден -> скрываем")
            self.hide()
        else:
            self.logger.info("[DEBUG][toggle] оверлей скрыт -> показываем")
            if self._last_image_path and self._last_window_rect:
                self._is_visible_by_user = True
                self.logger.info(
                    f"[DEBUG][toggle] показываем оверлей с сохраненным изображением: {self._last_image_path}")
                self._load_and_show_image(self._last_image_path, self._last_window_rect)
            else:
                self.logger.warning("[DEBUG][toggle] нет сохраненного изображения для показа")

        self.logger.info("[DEBUG][toggle] возвращаем фокус на целевое окно")
        self.restore_target_window_focus()
        self.logger.info(f"[DEBUG][toggle] ЗАВЕРШЕНИЕ: visible={self.visible}")

    def restore_target_window_focus(self):
        """Возвращает фокус на целевое окно (игру)"""
        if self._target_hwnd is not None:
            try:
                self.logger.info(f"Возврат фокуса на целевое окно: {self._target_hwnd}")
                # Показываем окно, если оно свернуто
                win32gui.ShowWindow(self._target_hwnd, win32con.SW_RESTORE)
                # Устанавливаем фокус
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
                # Просто пытаемся вернуть фокус, без лишних манипуляций
                win32gui.SetForegroundWindow(self._target_hwnd)
                self.logger.info("Фокус восстановлен на полноэкранное приложение")
            except Exception as e:
                self.logger.warning(f"Не удалось восстановить фокус на игру: {e}")

    def show_for_window(self, image_path: Path, window_rect: tuple, target_hwnd: int = None,
                        is_fullscreen: bool = None, show_immediately: bool = True):
        self.logger.info(
            f"show_for_window вызван: image_path={image_path}, window_rect={window_rect}, "
            f"target_hwnd={target_hwnd}, is_fullscreen={is_fullscreen}, show_immediately={show_immediately}")

        if target_hwnd is not None:
            self._target_hwnd = target_hwnd
            if is_fullscreen is not None:
                self._is_fullscreen_target = is_fullscreen
                self.logger.info(f"Используем переданный флаг полноэкранности: {is_fullscreen}")
            else:
                self._is_fullscreen_target = self.is_fullscreen_window(target_hwnd)
                self.logger.info(f"Определен флаг полноэкранности автоматически: {self._is_fullscreen_target}")
            self.logger.info(f"Сохранен HWND целевого окна: {target_hwnd}, полноэкранный: {self._is_fullscreen_target}")
            self._fullscreen_restore_needed = False

            if self._is_fullscreen_target:
                self._saved_position = None
                self.logger.info("Полноэкранный режим: сброшена сохраненная позиция")

        self._last_image_path = image_path
        self._last_window_rect = window_rect
        self._is_visible_by_user = True

        if show_immediately:
            self.logger.info("[DEBUG] show_immediately=True, показываем оверлей")
            self._stop_visibility_monitor()
            self._load_and_show_image(image_path, window_rect)
        else:
            self.logger.info("[DEBUG] show_immediately=False, оверлей сохранен но НЕ показан")
            # Сохраняем состояние, но оверлей не показываем
            self.visible = False
            # Убеждаемся что окно скрыто
            try:
                self.root.withdraw()
            except:
                pass
            # Запускаем монитор, чтобы показать оверлей когда вернемся в игру
            if self.auto_hide_enabled:
                self.logger.info("[DEBUG] Запуск монитора для отложенного показа")
                self.root.after(1000, self._start_visibility_monitor_delayed)

    def get_target_hwnd(self) -> int:
        return self._target_hwnd

    def _start_drag(self, event):
        """Начинает перетаскивание окна"""
        if self._drag_stop_timer:
            try:
                self.root.after_cancel(self._drag_stop_timer)
            except:
                pass
            self._drag_stop_timer = None

        self._is_dragging = True
        self._drag_data["x"] = event.x
        self._drag_data["y"] = event.y
        self.logger.debug("Начало перетаскивания")

    def _on_drag(self, event):
        """Перемещает окно во время перетаскивания"""
        if self._is_dragging and self.root.winfo_exists():
            x = self.root.winfo_x() + (event.x - self._drag_data["x"])
            y = self.root.winfo_y() + (event.y - self._drag_data["y"])
            self.root.geometry(f"+{x}+{y}")
            self._saved_position = (x, y)
            self.logger.debug(f"Перемещение в ({x}, {y})")

    def _stop_drag(self, event):
        """Останавливает перетаскивание окна"""
        self.logger.info("[DEBUG] _stop_drag вызван")
        self._is_dragging = False
        self._drag_data["x"] = 0
        self._drag_data["y"] = 0

        # Не проверяем активное окно - это вызывает проблемы
        # Просто возвращаем фокус целевому окну, если оно есть
        if self._target_hwnd:
            try:
                import win32gui
                # Проверяем, не является ли активное окно нашим оверлеем
                active_hwnd = win32gui.GetForegroundWindow()
                overlay_hwnd = None
                if self.root and self.root.winfo_exists():
                    overlay_hwnd = int(self.root.winfo_id())

                # Если активное окно - оверлей, возвращаем фокус целевому окну
                if overlay_hwnd is not None and active_hwnd == overlay_hwnd:
                    self.logger.info(f"[DEBUG] Активное окно - оверлей, возвращаем фокус целевому: {self._target_hwnd}")
                    win32gui.SetForegroundWindow(self._target_hwnd)
            except Exception as e:
                self.logger.info(f"[DEBUG] Ошибка при возврате фокуса: {e}")

        if self.root and self.root.winfo_exists():
            if self._drag_stop_timer:
                try:
                    self.root.after_cancel(self._drag_stop_timer)
                except:
                    pass
            self._drag_stop_timer = self.root.after(500, self._on_drag_stop_timeout)

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

            # Проверяем, что окно занимает почти весь экран
            # Допускаем большие отклонения для окон с рамкой или выходящих за экран
            is_fullscreen = (win_width >= screen_width - 50 and win_height >= screen_height - 50)

            # Дополнительная проверка: если окно выходит за пределы экрана
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

    def set_auto_hide(self, enabled: bool):
        """Устанавливает режим автоскрытия"""
        self.logger.info(f"set_auto_hide вызван: enabled={enabled}, текущее значение={self.auto_hide_enabled}")

        self.auto_hide_enabled = enabled
        self.logger.info(f"Режим автоскрытия установлен: {enabled}")

        if not enabled:
            self._stop_visibility_monitor()
            self.logger.info("Автоскрытие отключено, монитор остановлен")
            if not self.visible and self._is_visible_by_user and self._last_image_path and self._last_window_rect:
                self.logger.info("Автоскрытие отключено, показываем оверлей")
                self._load_and_show_image(self._last_image_path, self._last_window_rect)
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

    def show(self):
        self.logger.info("show() вызван")
        if self._last_image_path and self._last_window_rect:
            self._is_visible_by_user = True
            self.logger.info(f"Повторный показ: {self._last_image_path}")
            self._load_and_show_image(self._last_image_path, self._last_window_rect)
        else:
            self.logger.warning("Нет сохраненного изображения для показа")

    def _on_escape(self, event):
        self.hide()
        self.restore_target_window_focus()
        return "break"

    def _global_esc_handler(self, event):
        if self.visible:
            self.hide()
            self.restore_target_window_focus()
            return False
        return True

    def _enable_esc_hook(self):
        if not self._esc_hook_active:
            try:
                keyboard.on_press_key('esc', self._global_esc_handler)
                self._esc_hook_active = True
                self.logger.info("Глобальный хук ESC включен")
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

    def _stop_visibility_monitor(self):
        if self._monitor_timer is not None:
            try:
                if self.root and self.root.winfo_exists():
                    self.root.after_cancel(self._monitor_timer)
            except Exception as e:
                self.logger.warning(f"Ошибка отмены таймера: {e}")
            self._monitor_timer = None
            self.logger.info("Монитор видимости остановлен")

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

    def close(self):
        self.logger.info("close() вызван")
        self._stop_visibility_monitor()
        self._disable_esc_hook()

        # Очищаем хук на сообщения окна
        try:
            overlay_hwnd = int(self.root.winfo_id())
            # Восстанавливаем оригинальную процедуру окна
            ctypes.windll.user32.SetWindowLongW(
                overlay_hwnd,
                -4,  # GWL_WNDPROC
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
        try:
            self._images.clear()
            self.tk_image = None
            self._last_image_path = None
            self._last_window_rect = None
            self._saved_position = None  # Сбрасываем сохраненную позицию при закрытии
            self._is_fullscreen_target = False  # Сбрасываем флаг полноэкранного режима
            self.root.destroy()
        except:
            pass
        self.logger.info("Оверлей закрыт")
