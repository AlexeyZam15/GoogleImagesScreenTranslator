"""
Модуль для оверлейного окна с переведенным изображением
"""

import logging
import tempfile
from pathlib import Path
from PIL import Image, ImageTk
import tkinter as tk
import keyboard
import win32gui
import win32con


class OverlayWindow:
    """Класс для оверлейного окна (Toplevel, работает в главном потоке)"""

    def __init__(self, parent=None, app_title="Перевод скриншотов", auto_hide_enabled=True):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Инициализация OverlayWindow")
        self.visible = False
        self.temp_dir = Path(tempfile.gettempdir()) / "screenshot_translator"
        self.temp_dir.mkdir(exist_ok=True)
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
        self._saved_position = None  # Добавляем сохранение позиции (x, y)

        self.auto_hide_enabled = auto_hide_enabled

        self.root = tk.Toplevel(parent) if parent else tk.Toplevel()
        self.root.title("Перевод")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#000000')
        self.root.withdraw()

        try:
            import win32gui
            hwnd = int(self.root.winfo_id())
            class_name = win32gui.GetClassName(hwnd)
            window_text = win32gui.GetWindowText(hwnd)
            self.logger.info(f"Оверлей создан: hwnd={hwnd}, class='{class_name}', title='{window_text}'")
        except Exception as e:
            self.logger.debug(f"Не удалось получить информацию об оверлее: {e}")

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

    def get_target_hwnd(self) -> int:
        return self._target_hwnd

    def _start_drag(self, event):
        """Начинает перетаскивание окна"""
        # Отменяем таймер если был
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
            # Сохраняем позицию при перетаскивании
            self._saved_position = (x, y)
            self.logger.debug(f"Перемещение в ({x}, {y}), сохранена позиция: {self._saved_position}")

    def _stop_drag(self, event):
        """Останавливает перетаскивание окна - НЕ скрывает оверлей!"""
        self.logger.info("[DEBUG] _stop_drag вызван")
        self._is_dragging = False
        self._drag_data["x"] = 0
        self._drag_data["y"] = 0

        # Проверяем какое окно стало активным после отпускания
        try:
            import win32gui
            active_hwnd = win32gui.GetForegroundWindow()
            if active_hwnd:
                class_name = win32gui.GetClassName(active_hwnd)
                window_text = win32gui.GetWindowText(active_hwnd)
                self.logger.info(
                    f"[DEBUG] После отпускания ЛКМ активное окно: hwnd={active_hwnd}, class='{class_name}', title='{window_text}'")
        except Exception as e:
            self.logger.info(f"[DEBUG] Ошибка получения активного окна после отпускания: {e}")

        # Увеличиваем задержку до 500мс для надежности
        if self.root and self.root.winfo_exists():
            if self._drag_stop_timer:
                try:
                    self.root.after_cancel(self._drag_stop_timer)
                except:
                    pass
            # Через 500мс сбрасываем флаг перетаскивания, чтобы монитор мог работать
            self._drag_stop_timer = self.root.after(500, self._on_drag_stop_timeout)

    def _on_drag_stop_timeout(self):
        """Таймаут после остановки перетаскивания"""
        self._drag_stop_timer = None
        self.logger.info("[DEBUG] Таймаут после перетаскивания (500мс), монитор может работать")
        # Проверяем какое окно активное после таймаута
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

    def set_auto_hide(self, enabled: bool):
        """Устанавливает режим автоскрытия"""
        self.logger.info(f"set_auto_hide вызван: enabled={enabled}, текущее значение={self.auto_hide_enabled}")

        # ВСЕГДА обновляем значение, независимо от состояния
        self.auto_hide_enabled = enabled
        self.logger.info(f"Режим автоскрытия установлен: {enabled}")

        if not enabled:
            # Если автоскрытие отключено - останавливаем монитор
            self._stop_visibility_monitor()
            self.logger.info("Автоскрытие отключено, монитор остановлен")
            # Если оверлей скрыт, но должен быть виден - показываем его
            if not self.visible and self._is_visible_by_user and self._last_image_path and self._last_window_rect:
                self.logger.info("Автоскрытие отключено, показываем оверлей")
                self._load_and_show_image(self._last_image_path, self._last_window_rect)
        else:
            # Если автоскрытие включено
            if self.visible and self._is_visible_by_user:
                # Оверлей виден и пользователь хочет его видеть - запускаем монитор
                self._start_visibility_monitor()
                self.logger.info("Автоскрытие включено, монитор запущен")
                # НЕМЕДЛЕННО проверяем активное окно
                self._check_and_update_visibility()
            elif not self.visible and self._is_visible_by_user and self._last_image_path and self._last_window_rect:
                # Оверлей скрыт, но пользователь хочет его видеть - показываем и запускаем монитор
                self.logger.info("Автоскрытие включено, показываем оверлей и запускаем монитор")
                self._load_and_show_image(self._last_image_path, self._last_window_rect)
            elif not self.visible and not self._is_visible_by_user and self._last_image_path and self._last_window_rect:
                # Оверлей скрыт пользователем - ничего не делаем, но сохраняем настройку
                self.logger.info("Автоскрытие включено, но оверлей скрыт пользователем")
                # Если оверлей скрыт пользователем, но настройка включена - ничего не делаем
                # При следующем показе оверлея через F1, монитор запустится автоматически
                pass

    def _check_and_update_visibility(self):
        """Немедленно проверяет активное окно и обновляет видимость оверлея"""
        if not self.auto_hide_enabled or not self._is_visible_by_user:
            return

        try:
            is_active = self._is_target_window_active()
            self.logger.info(f"[DEBUG] _check_and_update_visibility: is_active={is_active}, visible={self.visible}")

            if not is_active and self.visible:
                self.logger.info("Немедленное скрытие оверлея (окно неактивно)")
                self._hide_internal()
            elif is_active and not self.visible and self._is_visible_by_user:
                self.logger.info("Немедленное показ оверлея (окно активно)")
                self._show_internal()
        except Exception as e:
            self.logger.warning(f"Ошибка в _check_and_update_visibility: {e}")

    def _hide_internal(self):
        self.visible = False
        try:
            self.root.withdraw()
            self._disable_esc_hook()
            self.logger.info("Оверлей скрыт (внутренне)")
        except Exception as e:
            self.logger.error(f"Ошибка при скрытии оверлея: {e}")

    def hide(self):
        self.logger.info("hide() вызван")
        self._is_visible_by_user = False
        self._stop_visibility_monitor()
        self.visible = False
        self._disable_esc_hook()
        try:
            self.root.withdraw()
            self.logger.info("Оверлей скрыт")
        except Exception as e:
            self.logger.error(f"Ошибка при скрытии оверлея: {e}")

    def _start_visibility_monitor(self):
        """Запускает монитор видимости - ТОЛЬКО если включено автоскрытие"""
        if not self.auto_hide_enabled:
            self.logger.info("Автоскрытие отключено, монитор не запущен")
            return

        self._stop_visibility_monitor()

        def check_visibility():
            if not self.root or not self.root.winfo_exists():
                self._stop_visibility_monitor()
                return

            try:
                # Если оверлей перетаскивается - пропускаем проверку
                if self._is_dragging:
                    self.logger.debug("Оверлей перетаскивается, пропускаем проверку")
                    if self.root and self.root.winfo_exists():
                        self._monitor_timer = self.root.after(500, check_visibility)
                    return

                if not self._is_visible_by_user:
                    self.logger.debug("Пользователь скрыл оверлей, останавливаем монитор")
                    self._stop_visibility_monitor()
                    return

                is_active = self._is_target_window_active()
                self.logger.debug(
                    f"check_visibility: is_active={is_active}, visible={self.visible}, user_visible={self._is_visible_by_user}")

                if not is_active:
                    if self.visible:
                        self.logger.info("Целевое окно неактивно, скрываем оверлей")
                        self._hide_internal()
                else:
                    if not self.visible and self._is_visible_by_user:
                        self.logger.info("Целевое окно активно, показываем оверлей")
                        self._show_internal()

                if self._is_visible_by_user and self.root and self.root.winfo_exists():
                    self._monitor_timer = self.root.after(500, check_visibility)
                else:
                    self.logger.debug("Пользователь не хочет видеть оверлей, останавливаем монитор")
                    self._monitor_timer = None

            except Exception as e:
                self.logger.warning(f"Ошибка в мониторе видимости: {e}")
                if self._is_visible_by_user and self.root and self.root.winfo_exists():
                    self._monitor_timer = self.root.after(500, check_visibility)

        if self.root and self.root.winfo_exists():
            self._monitor_timer = self.root.after(500, check_visibility)
            self.logger.info("Монитор видимости запущен")

    def show(self):
        self.logger.info("show() вызван")
        if self._last_image_path and self._last_window_rect:
            self._is_visible_by_user = True
            self.logger.info(f"Повторный показ: {self._last_image_path}")
            self._load_and_show_image(self._last_image_path, self._last_window_rect)
        else:
            self.logger.warning("Нет сохраненного изображения для показа")

    def _show_internal(self):
        if not self._last_image_path or not self._last_window_rect:
            self.logger.warning("Нет сохраненного изображения для показа")
            return
        self.logger.info(f"_show_internal: показываем оверлей, image={self._last_image_path}")
        self._load_and_show_image(self._last_image_path, self._last_window_rect)

    def show_for_window(self, image_path: Path, window_rect: tuple, target_hwnd: int = None):
        self.logger.info(
            f"show_for_window вызван: image_path={image_path}, window_rect={window_rect}, target_hwnd={target_hwnd}")

        if target_hwnd is not None:
            self._target_hwnd = target_hwnd
            self.logger.info(f"Сохранен HWND целевого окна: {target_hwnd}")

        self._last_image_path = image_path
        self._last_window_rect = window_rect
        self._is_visible_by_user = True
        self._stop_visibility_monitor()
        self._load_and_show_image(image_path, window_rect)

    def _load_and_show_image(self, image_path: Path, window_rect: tuple):
        self.logger.info(f"_load_and_show_image: {image_path}")

        try:
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

            if self._saved_position is not None:
                pos_x, pos_y = self._saved_position
                self.logger.info(f"Восстановление позиции оверлея: ({pos_x}, {pos_y})")
                self.root.geometry(f"{win_width}x{win_height}+{pos_x}+{pos_y}")
            else:
                self._saved_position = (x1, y1)
                self.logger.info(f"Сохранена начальная позиция оверлея: ({x1}, {y1})")
                self.root.geometry(f"{win_width}x{win_height}+{x1}+{y1}")

            self.root.attributes('-topmost', True)

            self.canvas.delete("all")
            self.canvas.config(width=win_width, height=win_height)
            self.canvas.create_rectangle(0, 0, win_width, win_height, fill='#000000', outline='')

            x = (win_width - new_w) // 2
            y = (win_height - new_h) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image)

            self.visible = True
            self.root.deiconify()
            self.root.lift()
            self._enable_esc_hook()

            self.logger.info(f"_load_and_show_image: auto_hide_enabled={self.auto_hide_enabled}")

            if self.auto_hide_enabled:
                self._start_visibility_monitor()
                self.logger.info("Монитор видимости запущен (автоскрытие включено)")
            else:
                self.logger.info("Автоскрытие отключено, монитор не запущен")

            self.logger.info(f"Изображение загружено и показано: {win_width}x{win_height}")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки изображения: {e}")
            import traceback
            traceback.print_exc()

    def _is_target_window_active(self) -> bool:
        """
        Проверяет, активно ли целевое окно.
        Если активное окно - это оверлей или окно нашего приложения, возвращаем True.
        """
        if self._target_hwnd is None:
            self.logger.debug("_target_hwnd is None, считаем окно неактивным")
            return False

        try:
            active_hwnd = win32gui.GetForegroundWindow()
            if not active_hwnd:
                self.logger.debug("Нет активного окна")
                return False

            # Получаем информацию об активном окне
            try:
                class_name = win32gui.GetClassName(active_hwnd)
                window_text = win32gui.GetWindowText(active_hwnd)
                self.logger.info(
                    f"[DEBUG] Активное окно: hwnd={active_hwnd}, class='{class_name}', title='{window_text}'")
            except Exception as e:
                self.logger.debug(f"Ошибка получения информации об окне: {e}")

            # Получаем HWND оверлея
            overlay_hwnd = None
            if hasattr(self, 'root') and self.root.winfo_exists():
                try:
                    overlay_hwnd = int(self.root.winfo_id())
                    self.logger.info(f"[DEBUG] overlay_hwnd={overlay_hwnd}")
                except Exception as e:
                    self.logger.debug(f"Ошибка получения HWND оверлея: {e}")

            # Если активное окно - это сам оверлей - считаем что целевое окно активно
            if overlay_hwnd is not None and active_hwnd == overlay_hwnd:
                self.logger.info("[DEBUG] Активно окно оверлея, возвращаем True")
                return True

            # Если активное окно - TkTopLevel с заголовком "Перевод" (временное окно перетаскивания)
            if class_name == "TkTopLevel" and window_text == "Перевод":
                self.logger.info("[DEBUG] Активно временное окно перетаскивания, считаем целевое окно активным")
                return True

            # Если это главное окно приложения - возвращаем False
            if hasattr(self, '_app_title') and self._app_title:
                try:
                    if self._app_title in window_text:
                        self.logger.info(f"[DEBUG] Активно главное окно приложения: '{window_text}', возвращаем False")
                        return False
                except:
                    pass

            # Проверяем, является ли активное окно целевым
            if active_hwnd == self._target_hwnd:
                self.logger.info("[DEBUG] Активно целевое окно, возвращаем True")
                return True

            self.logger.info(
                f"[DEBUG] Активное окно {active_hwnd} не является оверлеем ({overlay_hwnd}) или целевым ({self._target_hwnd})")
            return False

        except Exception as e:
            self.logger.warning(f"Ошибка проверки активности окна: {e}")
            return False

    def _on_escape(self, event):
        self.hide()
        return "break"

    def _global_esc_handler(self, event):
        if self.visible:
            self.hide()
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

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def is_visible(self) -> bool:
        return self.visible

    def close(self):
        self.logger.info("close() вызван")
        self._stop_visibility_monitor()
        self._disable_esc_hook()
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
            self._saved_position = None  # Очищаем сохраненную позицию
            self.root.destroy()
        except:
            pass
        self.logger.info("Оверлей закрыт")
