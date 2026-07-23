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
    """Класс для оверлейного окна"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.visible = False
        self.temp_dir = Path(tempfile.gettempdir()) / "screenshot_translator"
        self.temp_dir.mkdir(exist_ok=True)
        self.tk_image = None
        self._target_rect = None
        self._esc_hook_active = False

        # Создаем окно
        self.root = tk.Toplevel()
        self.root.title("Перевод")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#000000')

        # Холст для изображения
        self.canvas = tk.Canvas(self.root, bg='#000000', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        # Кнопка закрытия
        self.close_btn = tk.Label(
            self.root,
            text="✕",
            bg='#000000',
            fg='#666666',
            font=("Arial", 16, "bold"),
            cursor="hand2"
        )
        self.close_btn.place(x=20, y=20)
        self.close_btn.bind('<Button-1>', lambda e: self.hide())
        self.close_btn.bind('<Enter>', lambda e: self.close_btn.config(fg='#ff0000'))
        self.close_btn.bind('<Leave>', lambda e: self.close_btn.config(fg='#666666'))

        # ESC через Tkinter (работает только когда окно в фокусе)
        self.root.bind('<Escape>', self._on_escape)

        # Скрываем
        self.root.withdraw()

    def _on_escape(self, event):
        """Обработчик ESC через Tkinter"""
        self.hide()
        return "break"

    def _global_esc_handler(self, event):
        """Глобальный обработчик ESC через keyboard"""
        if self.visible:
            self.hide()
            return False  # Блокируем дальнейшую обработку
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

    def show_for_window(self, image_path: Path, window_rect: tuple):
        """Показывает изображение поверх указанного окна"""
        try:
            self._target_rect = window_rect
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

            self.tk_image = ImageTk.PhotoImage(Image.open(temp_img))

            # Позиционируем окно поверх целевого окна
            self.root.geometry(f"{win_width}x{win_height}+{x1}+{y1}")
            self.root.attributes('-topmost', True)

            self.canvas.delete("all")
            self.canvas.config(width=win_width, height=win_height)
            self.canvas.create_rectangle(0, 0, win_width, win_height, fill='#000000', outline='')

            # Центрируем изображение в окне
            x = (win_width - new_w) // 2
            y = (win_height - new_h) // 2
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image)

            self.visible = True
            self.root.deiconify()
            self.root.lift()

            # Захватываем фокус для работы Tkinter событий
            self.root.focus_force()
            self.root.grab_set()

            # Включаем глобальный хук для ESC
            self._enable_esc_hook()

            self.logger.info(f"Оверлей показан поверх окна: {win_width}x{win_height}")

        except Exception as e:
            self.logger.error(f"Ошибка: {e}")

    def show_fullscreen(self, image_path: Path):
        """Показывает изображение на весь экран"""
        try:
            img = Image.open(image_path)

            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()

            ratio = min(sw / img.width, sh / img.height)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            temp_img = self.temp_dir / "overlay.png"
            img.save(temp_img)

            self.tk_image = ImageTk.PhotoImage(Image.open(temp_img))

            x = (sw - new_w) // 2
            y = (sh - new_h) // 2

            self.root.geometry(f"{sw}x{sh}+0+0")
            self.root.attributes('-topmost', True)

            self.canvas.delete("all")
            self.canvas.config(width=sw, height=sh)
            self.canvas.create_rectangle(0, 0, sw, sh, fill='#000000', outline='')
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image)

            self.visible = True
            self.root.deiconify()
            self.root.lift()

            self.root.focus_force()
            self.root.grab_set()

            # Включаем глобальный хук для ESC
            self._enable_esc_hook()

            self.logger.info(f"Оверлей показан на весь экран: {new_w}x{new_h}")

        except Exception as e:
            self.logger.error(f"Ошибка: {e}")

    def hide(self):
        """Скрывает оверлей и освобождает ресурсы"""
        self.visible = False

        # Отключаем глобальный хук ESC
        self._disable_esc_hook()

        try:
            self.root.grab_release()
        except:
            pass

        self.root.withdraw()

    def toggle(self):
        if self.visible:
            self.hide()
        else:
            self.show()

    def show(self):
        if self.tk_image:
            self.visible = True
            self.root.deiconify()
            self.root.lift()
            self.root.focus_force()
            self.root.grab_set()
            self._enable_esc_hook()

    def is_visible(self) -> bool:
        return self.visible

    def close(self):
        self._disable_esc_hook()
        try:
            self.root.grab_release()
        except:
            pass
        try:
            self.root.destroy()
        except:
            pass