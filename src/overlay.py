"""
Модуль для оверлейного окна с переведенным изображением
"""

import logging
import tempfile
from pathlib import Path
from PIL import Image, ImageTk
import tkinter as tk
import keyboard


class OverlayWindow:
    """Класс для оверлейного окна (Toplevel, работает в главном потоке)"""

    def __init__(self, parent=None):
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

            self.logger.info(f"Изображение загружено и показано: {win_width}x{win_height}")

        except Exception as e:
            self.logger.error(f"Ошибка загрузки изображения: {e}")
            import traceback
            traceback.print_exc()

    def show_for_window(self, image_path: Path, window_rect: tuple):
        """Показывает изображение поверх указанного окна"""
        self.logger.info(f"show_for_window вызван: image_path={image_path}, window_rect={window_rect}")

        # Сохраняем для повторного показа
        self._last_image_path = image_path
        self._last_window_rect = window_rect

        self._load_and_show_image(image_path, window_rect)

    def show_fullscreen(self, image_path: Path):
        """Показывает изображение на весь экран"""
        self.logger.info(f"show_fullscreen вызван: image_path={image_path}")

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        window_rect = (0, 0, sw, sh)

        # Сохраняем для повторного показа
        self._last_image_path = image_path
        self._last_window_rect = window_rect

        self._load_and_show_image(image_path, window_rect)

    def hide(self):
        """Скрывает оверлей и освобождает ресурсы"""
        self.logger.info("hide() вызван")
        self.visible = False

        # Отключаем глобальный хук ESC
        self._disable_esc_hook()

        try:
            self.root.withdraw()
            self.logger.info("Оверлей скрыт")

            # НЕ ОЧИЩАЕМ _images и tk_image - они нужны для повторного показа
            # Просто скрываем окно

        except Exception as e:
            self.logger.error(f"Ошибка при скрытии оверлея: {e}")

    def show(self):
        """Показывает ранее сохраненное изображение"""
        self.logger.info("show() вызван")

        if self._last_image_path and self._last_window_rect:
            self.logger.info(f"Повторный показ: {self._last_image_path}")
            self._load_and_show_image(self._last_image_path, self._last_window_rect)
        else:
            self.logger.warning("Нет сохраненного изображения для показа")

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