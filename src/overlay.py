"""
Модуль для оверлейного окна с переведенным изображением
"""

import logging
import tempfile
from pathlib import Path
from PIL import Image, ImageTk
import tkinter as tk


class OverlayWindow:
    """Класс для оверлейного окна"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.visible = False
        self.temp_dir = Path(tempfile.gettempdir()) / "screenshot_translator"
        self.temp_dir.mkdir(exist_ok=True)
        self.tk_image = None

        # Создаем окно
        self.root = tk.Toplevel()
        self.root.title("Перевод")
        self.root.overrideredirect(True)
        self.root.attributes('-topmost', True)
        self.root.configure(bg='#000000')

        # На весь экран
        self.root.geometry(f"{self.root.winfo_screenwidth()}x{self.root.winfo_screenheight()}+0+0")

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

        # ESC для закрытия
        self.root.bind('<Escape>', lambda e: self.hide())

        # Скрываем
        self.root.withdraw()

    def show_fullscreen(self, image_path: Path):
        """Показывает изображение на весь экран"""
        try:
            img = Image.open(image_path)

            # Размер экрана
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()

            # Масштабируем
            ratio = min(sw / img.width, sh / img.height)
            new_w = int(img.width * ratio)
            new_h = int(img.height * ratio)

            img = img.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Сохраняем
            temp_img = self.temp_dir / "overlay.png"
            img.save(temp_img)

            self.tk_image = ImageTk.PhotoImage(Image.open(temp_img))

            # Центрируем
            x = (sw - new_w) // 2
            y = (sh - new_h) // 2

            self.canvas.delete("all")
            self.canvas.config(width=sw, height=sh)
            self.canvas.create_rectangle(0, 0, sw, sh, fill='#000000', outline='')
            self.canvas.create_image(x, y, anchor=tk.NW, image=self.tk_image)

            self.visible = True
            self.root.deiconify()
            self.root.lift()

            self.logger.info(f"Оверлей показан: {new_w}x{new_h}")

        except Exception as e:
            self.logger.error(f"Ошибка: {e}")

    def hide(self):
        """Скрывает оверлей"""
        self.visible = False
        self.root.withdraw()

    def toggle(self):
        """Переключает видимость"""
        if self.visible:
            self.hide()
        else:
            self.show()

    def show(self):
        """Показывает оверлей"""
        if self.tk_image:
            self.visible = True
            self.root.deiconify()
            self.root.lift()

    def is_visible(self) -> bool:
        return self.visible

    def close(self):
        try:
            self.root.destroy()
        except:
            pass