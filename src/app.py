"""
Главный модуль приложения для перевода скриншотов
"""

import logging
import tempfile
import time
import threading
import os
import sys
from pathlib import Path
from tkinter import *
from tkinter import ttk
from datetime import datetime

import keyboard

from src.translator import GoogleTranslateDebug
from src.screenshot import ScreenshotCapturer
from src.overlay import OverlayWindow
from src.settings import Settings
from src.strings import STRINGS


def setup_logging():
    """Настройка логирования в файл"""
    try:
        log_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        log_file = log_dir / f"app_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler(sys.stdout)
            ]
        )

        logging.getLogger("playwright").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)

        logging.info("=" * 70)
        logging.info(f"Запуск GoogleScreenTranslate")
        logging.info(f"Лог файл: {log_file}")
        logging.info("=" * 70)

        return log_file
    except Exception as e:
        print(f"Ошибка настройки логирования: {e}")
        return None


class ScreenshotTranslatorApp:
    """Главное окно приложения для перевода скриншотов"""

    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger(__name__)

        # Инициализация настроек
        self.settings = Settings()

        # Временная директория
        self.temp_dir = Path(tempfile.gettempdir()) / "screenshot_translator"
        self.temp_dir.mkdir(exist_ok=True)

        # Компоненты
        self.overlay = None
        self.screenshot = ScreenshotCapturer()
        self.translator = None
        self.ready = False
        self.translating = False

        # Флаги для горячих клавиш
        self._key_states = {}
        self._key_last_time = {}
        self._debounce_ms = 500

        # Создание GUI
        self.create_gui()

        # Инициализация переводчика
        self.root.after(100, self.init_translator)

        # Настройка горячих клавиш
        self.setup_hotkeys()

        # Обновление языка интерфейса
        self.update_ui_language()

        # Установка иконки приложения
        self._setup_app_icon()

    def _setup_app_icon(self):
        """Устанавливает профессиональную иконку приложения для отображения в панели задач"""
        try:
            from PIL import Image, ImageDraw, ImageTk

            # Создаем изображение 64x64 для лучшего качества
            size = 64
            img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            # Цвета
            bg_color = (33, 33, 33, 255)  # Темно-серый фон
            accent_color = (76, 175, 80, 255)  # Зеленый (как в интерфейсе)
            white = (255, 255, 255, 255)
            light_gray = (200, 200, 200, 255)

            # Рисуем закругленный прямоугольник как фон
            radius = 14
            draw.rounded_rectangle(
                [(4, 4), (size - 4, size - 4)],
                radius=radius,
                fill=bg_color,
                outline=accent_color,
                width=2
            )

            # === РИСУЕМ ЗНАЧОК КАМЕРЫ ===
            center_x = size // 2
            center_y = size // 2 + 2

            # Размеры камеры
            cam_w = 30
            cam_h = 22

            # Верхняя часть камеры (прямоугольник со скругленными углами)
            x1 = center_x - cam_w // 2
            y1 = center_y - cam_h // 2
            x2 = center_x + cam_w // 2
            y2 = center_y + cam_h // 2

            # Корпус камеры
            draw.rounded_rectangle(
                [(x1, y1), (x2, y2)],
                radius=4,
                fill=white,
                outline=accent_color,
                width=2
            )

            # Объектив (круг)
            lens_radius = 8
            draw.ellipse(
                [(center_x - lens_radius, center_y - lens_radius),
                 (center_x + lens_radius, center_y + lens_radius)],
                fill=accent_color,
                outline=white,
                width=2
            )

            # Блик на объективе (маленький белый круг)
            draw.ellipse(
                [(center_x - 4, center_y - 5),
                 (center_x - 1, center_y - 2)],
                fill=white
            )

            # Вспышка (маленький квадрат сверху справа)
            flash_x = center_x + 12
            flash_y = center_y - cam_h // 2 - 2
            draw.rectangle(
                [(flash_x - 2, flash_y - 2),
                 (flash_x + 3, flash_y + 3)],
                fill=white,
                outline=accent_color,
                width=1
            )

            # === ДОБАВЛЯЕМ ТЕКСТ "SC" (Screen Translate) ===
            # Рисуем маленькую плашку снизу
            text_y = y2 + 6
            draw.rounded_rectangle(
                [(center_x - 12, text_y - 1),
                 (center_x + 12, text_y + 9)],
                radius=3,
                fill=accent_color
            )

            # Пытаемся использовать шрифт, если нет - рисуем текстом
            try:
                from PIL import ImageFont
                font = ImageFont.truetype("arial.ttf", 8)
                draw.text(
                    (center_x - 7, text_y + 1),
                    "SC",
                    fill=white,
                    font=font
                )
            except:
                # Если шрифт не загрузился, рисуем простыми линиями
                draw.text(
                    (center_x - 6, text_y + 1),
                    "SC",
                    fill=white
                )

            # Конвертируем в PhotoImage и устанавливаем как иконку
            photo = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, photo)
            self.root.tk.call('wm', 'iconphoto', self.root._w, photo)

            # Сохраняем ссылку, чтобы не удалилась сборщиком мусора
            self._icon_photo = photo

            self.logger.info("Профессиональная иконка приложения установлена")

        except Exception as e:
            self.logger.warning(f"Не удалось установить иконку: {e}")
            # Запасной вариант - используем стандартную иконку Tkinter
            try:
                self.root.iconbitmap(default='')
            except:
                pass

    def get_string(self, key):
        """Возвращает локализованную строку"""
        return self.settings.get_string(key)

    def toggle_language(self):
        """Переключает язык интерфейса"""
        current_lang = self.settings.get_language()
        new_lang = "en" if current_lang == "ru" else "ru"
        self.settings.set_language(new_lang)

        # Обновляем интерфейс
        self.update_ui_language()

        # Обновляем текст на кнопке языка
        if hasattr(self, 'lang_btn'):
            self.lang_btn.config(text="EN" if new_lang == "ru" else "RU")

        # Обновляем статус
        self.update_status("● " + self.get_string('ready'), '#4CAF50')

        self.logger.info(f"Язык переключен на: {new_lang}")

    def update_ui_language(self):
        """Обновляет язык интерфейса"""
        self.root.title(self.get_string('app_title'))

        if hasattr(self, 'title_label'):
            self.title_label.config(text=self.get_string('app_title'))

        if hasattr(self, 'status'):
            status_text = self.get_string('ready') if self.ready else self.get_string('starting')
            self.status.config(text="● " + status_text)

        if hasattr(self, 'btn_capture'):
            self.btn_capture.config(text=self.get_string('btn_capture'))

        if hasattr(self, 'btn_toggle'):
            self.btn_toggle.config(text=self.get_string('btn_toggle'))

        if hasattr(self, 'hotkeys_label'):
            self.hotkeys_label.config(text=self.get_string('hotkeys_info'))

    def create_gui(self):
        """Создает главное окно приложения с адаптивной версткой"""
        self.root = Tk()
        self.root.title(self.get_string('app_title'))
        self.root.geometry("450x320")
        self.root.minsize(400, 280)  # Минимальный размер
        self.root.resizable(True, True)  # Разрешаем изменение размера
        self.root.configure(bg='#1e1e1e')

        # Не используем overrideredirect - окно отображается в панели задач

        # Основной контейнер с отступами
        main = Frame(self.root, bg='#1e1e1e')
        main.pack(expand=True, fill=BOTH, padx=25, pady=20)

        # ===== ВЕРХНЯЯ ПАНЕЛЬ =====
        header_frame = Frame(main, bg='#1e1e1e')
        header_frame.pack(fill=X, pady=(0, 15))

        # Заголовок слева
        title_frame = Frame(header_frame, bg='#1e1e1e')
        title_frame.pack(side=LEFT, expand=True, fill=X)

        # Иконка и текст заголовка в одной строке
        icon_label = Label(title_frame, text="📸",
                           bg='#1e1e1e', fg='white', font=("Arial", 26))
        icon_label.pack(side=LEFT, padx=(0, 10))

        self.title_label = Label(title_frame, text=self.get_string('app_title'),
                                 bg='#1e1e1e', fg='#4CAF50', font=("Arial", 15, "bold"))
        self.title_label.pack(side=LEFT)

        # Кнопка языка справа - увеличенная и читаемая
        lang_frame = Frame(header_frame, bg='#1e1e1e')
        lang_frame.pack(side=RIGHT, padx=(10, 0))

        current_lang = self.settings.get_language()
        lang_text = "EN" if current_lang == "ru" else "RU"

        self.lang_btn = Button(
            lang_frame,
            text=lang_text,
            command=self.toggle_language,
            font=("Arial", 12, "bold"),
            bg='#3c3c3c',
            fg='#4CAF50',
            relief=FLAT,
            padx=18,
            pady=6,
            cursor="hand2",
            width=6  # Увеличенная ширина
        )
        self.lang_btn.pack()

        # Добавляем эффект при наведении
        def on_enter(e):
            self.lang_btn.config(bg='#4CAF50', fg='white')

        def on_leave(e):
            self.lang_btn.config(bg='#3c3c3c', fg='#4CAF50')

        self.lang_btn.bind('<Enter>', on_enter)
        self.lang_btn.bind('<Leave>', on_leave)

        # ===== СТАТУС =====
        self.status = Label(main, text="● " + self.get_string('starting'),
                            fg='#ff9800', bg='#1e1e1e', font=("Arial", 11))
        self.status.pack(pady=(5, 20), fill=X)

        # ===== КНОПКИ =====
        btn_frame = Frame(main, bg='#1e1e1e')
        btn_frame.pack(fill=X, pady=5)

        self.btn_capture = Button(
            btn_frame,
            text=self.get_string('btn_capture'),
            command=self.process,
            font=("Arial", 11),
            bg='#333',
            fg='#888',
            relief=FLAT,
            padx=20,
            pady=12,
            state=DISABLED
        )
        self.btn_capture.pack(fill=X, pady=(0, 10))

        self.btn_toggle = Button(
            btn_frame,
            text=self.get_string('btn_toggle'),
            command=self.toggle_overlay,
            font=("Arial", 11),
            bg='#2196F3',
            fg='white',
            relief=FLAT,
            padx=20,
            pady=12
        )
        self.btn_toggle.pack(fill=X)

        # ===== ПОДСКАЗКА ВНИЗУ =====
        self.hotkeys_label = Label(main, text=self.get_string('hotkeys_info'),
                                   bg='#1e1e1e', fg='#666', font=("Arial", 9))
        self.hotkeys_label.pack(pady=(15, 0))

        # ===== ПРИВЯЗКА К ИЗМЕНЕНИЮ РАЗМЕРА =====
        # При изменении размера окна обновляем элементы
        self.root.bind('<Configure>', self._on_resize)

        # Центрируем окно
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _on_resize(self, event):
        """Обработчик изменения размера окна"""
        # Адаптируем размеры элементов при изменении окна
        width = self.root.winfo_width()

        # При маленьком окне уменьшаем шрифты
        if width < 420:
            self.title_label.config(font=("Arial", 13, "bold"))
            self.lang_btn.config(font=("Arial", 10, "bold"), padx=12, pady=4)
            self.btn_capture.config(font=("Arial", 10))
            self.btn_toggle.config(font=("Arial", 10))
        else:
            self.title_label.config(font=("Arial", 15, "bold"))
            self.lang_btn.config(font=("Arial", 12, "bold"), padx=18, pady=6)
            self.btn_capture.config(font=("Arial", 11))
            self.btn_toggle.config(font=("Arial", 11))

    def init_translator(self):
        """Инициализация переводчика в основном потоке"""
        try:
            self.update_status(self.get_string('starting_browser'), '#ff9800')
            self.translator = GoogleTranslateDebug(headless=True)
            self.translator.start_browser()
            self.ready = True
            self.overlay = OverlayWindow()
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            self.update_status(self.get_string('ready'), '#4CAF50')
        except Exception as e:
            self.logger.error(f"Ошибка: {e}")
            self.update_status(self.get_string('error'), '#f44336')

    def setup_hotkeys(self):
        """Настройка глобальных горячих клавиш"""
        try:
            # Отключаем предыдущие хуки
            keyboard.unhook_all()

            # Блокируем F1 и F2 от передачи в другие приложения
            keyboard.block_key('f1')
            keyboard.block_key('f2')

            def on_key(event):
                # Обработка F1
                if event.name == 'f1' and event.event_type == 'down':
                    if not self._key_states.get('f1', False):
                        current_time = time.time() * 1000
                        if current_time - self._key_last_time.get('f1', 0) >= self._debounce_ms:
                            self._key_states['f1'] = True
                            self._key_last_time['f1'] = current_time
                            self.root.after(0, self.toggle_overlay)
                            self.root.after(100, lambda: self._key_states.__setitem__('f1', False))
                    return False

                # Обработка F2
                if event.name == 'f2' and event.event_type == 'down':
                    if not self._key_states.get('f2', False):
                        current_time = time.time() * 1000
                        if current_time - self._key_last_time.get('f2', 0) >= self._debounce_ms:
                            self._key_states['f2'] = True
                            self._key_last_time['f2'] = current_time
                            self.root.after(0, self.process)
                            self.root.after(100, lambda: self._key_states.__setitem__('f2', False))
                    return False

                return True

            keyboard.hook(on_key, suppress=True)
            self.logger.info("Горячие клавиши зарегистрированы (F1, F2 заблокированы)")

        except Exception as e:
            self.logger.error(f"Ошибка регистрации горячих клавиш: {e}")
            self._setup_tkinter_hotkeys()

    def _setup_tkinter_hotkeys(self):
        """Запасной вариант через Tkinter bind_all"""

        def handle_hotkey(event):
            keysym = event.keysym
            if keysym == "F1" or keysym == "f1":
                self.toggle_overlay()
                return "break"
            if keysym == "F2" or keysym == "f2":
                self.process()
                return "break"

        self.root.bind_all("<Key>", handle_hotkey)
        self.root.focus_force()
        self.logger.info("Tkinter горячие клавиши зарегистрированы")

    def update_status(self, text, color='white'):
        """Обновляет статус в интерфейсе"""
        self.root.after(0, lambda: self.status.config(text=text, fg=color))

    def process(self):
        """Обработка скриншота"""
        if self.translating or not self.ready:
            return

        def capture():
            """Захват скриншота в отдельном потоке"""
            self.translating = True
            self.root.after(0, lambda: self.btn_capture.config(state=DISABLED, bg='#333'))

            try:
                self.update_status(self.get_string('capturing'), '#ff9800')
                img = self.screenshot.capture_active_window()
                if not img:
                    self.update_status(self.get_string('capture_error'), '#f44336')
                    self.translating = False
                    self.root.after(0, lambda: self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white'))
                    return

                path = self.temp_dir / f"scr_{int(time.time())}.png"
                img.save(path)

                # Передаем в основной поток для перевода
                self.root.after(0, lambda: self.do_translate(path))

            except Exception as e:
                self.logger.error(f"Ошибка захвата: {e}")
                self.update_status(self.get_string('error'), '#f44336')
                self.translating = False
                self.root.after(0, lambda: self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white'))

        threading.Thread(target=capture, daemon=True).start()

    def do_translate(self, image_path: Path):
        """Перевод в основном потоке (где создан браузер)"""
        try:
            self.update_status(self.get_string('translating'), '#ff9800')
            out = self.temp_dir / "translated"
            result = self.translator.translate_image(image_path, out)

            if result and self.overlay:
                self.overlay.show_fullscreen(result)
                self.update_status(self.get_string('ready'), '#4CAF50')
            else:
                self.update_status(self.get_string('translate_error'), '#f44336')

        except Exception as e:
            self.logger.error(f"Ошибка перевода: {e}")
            self.update_status(self.get_string('error'), '#f44336')
        finally:
            self.translating = False
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')

    def toggle_overlay(self):
        """Переключает видимость оверлея"""
        if self.overlay:
            self.overlay.toggle()
            status = self.get_string('shown') if self.overlay.is_visible() else self.get_string('hidden')
            self.update_status(f"● {self.get_string('overlay')} {status}", '#2196F3')

    def on_close(self):
        """Обработчик закрытия приложения"""
        # Отключаем горячие клавиши
        try:
            keyboard.unblock_key('f1')
            keyboard.unblock_key('f2')
            keyboard.unhook_all()
        except:
            pass

        # Сохраняем настройки
        if hasattr(self, 'settings'):
            self.settings.save()

        if self.translator:
            self.translator.close_browser()
        if self.overlay:
            self.overlay.close()
        self.root.destroy()

    def run(self):
        """Запускает главный цикл приложения"""
        print(f"{self.get_string('hotkeys_info')}")
        self.root.mainloop()