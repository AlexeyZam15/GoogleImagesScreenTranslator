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

    def __init__(self, parent=None, app_title="Перевод скриншотов"):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Инициализация OverlayWindow")
        self.visible = False
        self.temp_dir = Path(tempfile.gettempdir()) / "screenshot_translator"
        self.temp_dir.mkdir(exist_ok=True)
        self.tk_image = None
        self._target_rect = None
        self._esc_hook_active = False
        self._images = []  # Хранилище ссылок на PhotoImage
        self._last_image_path = None  # Сохраняем путь к последнему изображению
        self._last_window_rect = None  # Сохраняем последний прямоугольник окна
        self._target_hwnd = None  # HWND целевого окна
        self._app_title = app_title  # Заголовок главного окна приложения
        self._monitor_timer = None  # Таймер для проверки активности
        self._is_visible_by_user = False  # Пользователь показал оверлей вручную (F1)

        # Создаем окно как Toplevel от родителя
        self.root = tk.Toplevel(parent) if parent else tk.Toplevel()
        self.root.title("Перевод")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#000000')
        self.root.withdraw()

        # Холст для изображения
        self.canvas = tk.Canvas(self.root, bg='#000000', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # При клике на холст - скрываем оверлей
        self.canvas.bind('<Button-1>', lambda e: self.hide())
        self.root.bind('<Button-1>', lambda e: self.hide())

        # ESC через Tkinter
        self.root.bind('<Escape>', self._on_escape)

        self.logger.info("OverlayWindow инициализирован")

    def _hide_internal(self):
        """Внутреннее скрытие оверлея без изменения флага _is_visible_by_user"""
        self.visible = False
        # НЕ ОСТАНАВЛИВАЕМ МОНИТОР - он должен продолжать работать
        try:
            self.root.withdraw()
            self._disable_esc_hook()
            self.logger.info("Оверлей скрыт (внутренне)")
        except Exception as e:
            self.logger.error(f"Ошибка при скрытии оверлея: {e}")

    def hide(self):
        """Скрывает оверлей и освобождает ресурсы (вызывается пользователем через F1)"""
        self.logger.info("hide() вызван")

        # Сбрасываем флаг пользовательского показа - пользователь явно скрыл оверлей
        self._is_visible_by_user = False

        # Останавливаем монитор видимости
        self._stop_visibility_monitor()

        self.visible = False

        # Отключаем глобальный хук ESC
        self._disable_esc_hook()

        try:
            self.root.withdraw()
            self.logger.info("Оверлей скрыт")
        except Exception as e:
            self.logger.error(f"Ошибка при скрытии оверлея: {e}")

    def _start_visibility_monitor(self):
        """Запускает периодическую проверку активности целевого окна"""
        self._stop_visibility_monitor()

        def check_visibility():
            if not self.root or not self.root.winfo_exists():
                self._stop_visibility_monitor()
                return

            try:
                # Если пользователь явно скрыл оверлей - останавливаем монитор
                if not self._is_visible_by_user:
                    self.logger.debug("Пользователь скрыл оверлей, останавливаем монитор")
                    self._stop_visibility_monitor()
                    return

                is_active = self._is_target_window_active()
                self.logger.debug(
                    f"check_visibility: is_active={is_active}, visible={self.visible}, user_visible={self._is_visible_by_user}")

                if not is_active:
                    # Окно неактивно - скрываем оверлей, если он видим
                    if self.visible:
                        self.logger.info("Целевое окно неактивно, скрываем оверлей")
                        self._hide_internal()
                else:
                    # Окно активно - показываем оверлей, если он должен быть виден
                    if not self.visible and self._is_visible_by_user:
                        self.logger.info("Целевое окно активно, показываем оверлей")
                        self._show_internal()

                # Продолжаем проверку всегда, пока пользователь хочет видеть оверлей
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
        """Показывает ранее сохраненное изображение (вызывается пользователем через F1)"""
        self.logger.info("show() вызван")

        if self._last_image_path and self._last_window_rect:
            # Устанавливаем флаг, что пользователь явно показал оверлей
            self._is_visible_by_user = True
            self.logger.info(f"Повторный показ: {self._last_image_path}")
            self._load_and_show_image(self._last_image_path, self._last_window_rect)
        else:
            self.logger.warning("Нет сохраненного изображения для показа")

    def _show_internal(self):
        """Внутренний показ оверлея (вызывается монитором при возвращении в целевое окно)"""
        if not self._last_image_path or not self._last_window_rect:
            self.logger.warning("Нет сохраненного изображения для показа")
            return
        self.logger.info(f"_show_internal: показываем оверлей, image={self._last_image_path}")
        self._load_and_show_image(self._last_image_path, self._last_window_rect)

    def show_for_window(self, image_path: Path, window_rect: tuple, target_hwnd: int = None):
        """
        Показывает изображение поверх указанного окна.
        Сохраняет HWND целевого окна для отслеживания активности.
        """
        self.logger.info(
            f"show_for_window вызван: image_path={image_path}, window_rect={window_rect}, target_hwnd={target_hwnd}")

        # Сохраняем HWND целевого окна
        if target_hwnd is not None:
            self._target_hwnd = target_hwnd
            self.logger.info(f"Сохранен HWND целевого окна: {target_hwnd}")

        # Сохраняем для повторного показа
        self._last_image_path = image_path
        self._last_window_rect = window_rect

        # Устанавливаем флаг, что пользователь явно показал оверлей
        self._is_visible_by_user = True

        # Останавливаем старый монитор, если есть
        self._stop_visibility_monitor()

        self._load_and_show_image(image_path, window_rect)

    def _load_and_show_image(self, image_path: Path, window_rect: tuple):
        """Загружает изображение и показывает его"""
        self.logger.info(f"_load_and_show_image: {image_path}")

        try:
            x1, y1, x2, y2 = window_rect
            win_width = x2 - x1
            win_height = y2 - y1

            img = Image.open(image_path)

            # Масштабируем под размер окна
            ratio = min(win_width / img.width, win_height / img.height)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            temp_img = self.temp_dir / "overlay.png"
            img.save(temp_img)

            # СОЗДАЕМ И СОХРАНЯЕМ PhotoImage
            pil_img = Image.open(temp_img)
            photo = ImageTk.PhotoImage(pil_img)
            self._images.append(photo)
            self.tk_image = photo

            # Позиционируем окно
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
            self.root.focus_force()
            self._enable_esc_hook()

            # Запускаем мониторинг активности окна
            self._start_visibility_monitor()

            self.logger.info(f"Изображение загружено и показано: {win_width}x{win_height}")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки изображения: {e}")
            import traceback
            traceback.print_exc()

    def _is_target_window_active(self) -> bool:
        """
        Проверяет, активно ли целевое окно.
        Возвращает True, только если активное окно - это целевое окно.
        """
        if self._target_hwnd is None:
            self.logger.debug("_target_hwnd is None, считаем окно неактивным")
            return False

        try:
            active_hwnd = win32gui.GetForegroundWindow()
            if not active_hwnd:
                self.logger.debug("Нет активного окна")
                return False

            # Проверяем, является ли активное окно целевым
            if active_hwnd == self._target_hwnd:
                return True

            # ВСЕ ОСТАЛЬНЫЕ ОКНА считаем неактивными
            # (включая главное окно приложения, окно настроек и любые другие)
            return False

        except Exception as e:
            self.logger.warning(f"Ошибка проверки активности окна: {e}")
            return False

    def _on_escape(self, event):
        """Обработчик ESC через Tkinter"""
        self.hide()
        return "break"

    def _global_esc_handler(self, event):
        """Глобальный обработчик ESC через keyboard"""
        if self.visible:
            self.hide()
            return False
        return True

    def _enable_esc_hook(self):
        """Включает глобальный хук для ESC"""
        if not self._esc_hook_active:
            try:
                keyboard.on_press_key('esc', self._global_esc_handler)
                self._esc_hook_active = True
                self.logger.info("Глобальный хук ESC включен")
            except Exception as e:
                self.logger.warning(f"Не удалось включить глобальный хук ESC: {e}")

    def _disable_esc_hook(self):
        """Отключает глобальный хук для ESC"""
        if self._esc_hook_active:
            try:
                keyboard.unhook_key('esc')
                self._esc_hook_active = False
                self.logger.info("Глобальный хук ESC отключен")
            except Exception as e:
                self.logger.warning(f"Не удалось отключить глобальный хук ESC: {e}")

    def _stop_visibility_monitor(self):
        """Останавливает периодическую проверку"""
        if self._monitor_timer is not None:
            try:
                if self.root and self.root.winfo_exists():
                    self.root.after_cancel(self._monitor_timer)
            except Exception as e:
                self.logger.warning(f"Ошибка отмены таймера: {e}")
            self._monitor_timer = None
            self.logger.info("Монитор видимости остановлен")

    def show_fullscreen(self, image_path: Path):
        """Показывает изображение на весь экран"""
        self.logger.info(f"show_fullscreen вызван: image_path={image_path}")

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        window_rect = (0, 0, sw, sh)

        # Сохраняем для повторного показа
        self._last_image_path = image_path
        self._last_window_rect = window_rect

        # Устанавливаем флаг, что пользователь явно показал оверлей
        self._is_visible_by_user = True

        self._load_and_show_image(image_path, window_rect)

    def toggle(self):
        """Переключает видимость оверлея"""
        if self.visible:
            self.hide()
        else:
            self.show()

    def is_visible(self) -> bool:
        return self.visible

    def close(self):
        """Закрывает оверлей и освобождает ресурсы"""
        self.logger.info("close() вызван")

        # Останавливаем монитор видимости
        self._stop_visibility_monitor()

        self._disable_esc_hook()
        try:
            # Очищаем ресурсы
            self._images.clear()
            self.tk_image = None
            self._last_image_path = None
            self._last_window_rect = None
            self.root.destroy()
        except:
            pass
        self.logger.info("Оверлей закрыт")
