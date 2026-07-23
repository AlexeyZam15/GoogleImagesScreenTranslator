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
        self.initializing = False
        self._init_done = False
        self._translation_done = True

        # Оверлей индикатора перевода
        self.translation_overlay = None

        # Флаги для горячих клавиш
        self._key_states = {}
        self._key_last_time = {}
        self._debounce_ms = 500

        # Переменная для чекбокса показа браузера - будет создана в create_gui
        self.show_browser_var = None

        # Создание GUI
        self.create_gui()
        self.root.update_idletasks()
        self.root.update()

        # Обновление языка интерфейса
        self.update_ui_language()

        # Установка иконки приложения
        self._setup_app_icon()

        # Настройка горячих клавиш
        self.setup_hotkeys()

        # Запускаем инициализацию
        self.root.after(100, self._init_translator_step)

    def _setup_app_icon(self):
        """Устанавливает профессиональную иконку приложения для отображения в панели задач"""
        try:
            from PIL import Image, ImageDraw, ImageTk

            size = 64
            img = Image.new('RGBA', (size, size), color=(0, 0, 0, 0))
            draw = ImageDraw.Draw(img)

            bg_color = (33, 33, 33, 255)
            accent_color = (76, 175, 80, 255)
            white = (255, 255, 255, 255)

            radius = 14
            draw.rounded_rectangle(
                [(4, 4), (size - 4, size - 4)],
                radius=radius,
                fill=bg_color,
                outline=accent_color,
                width=2
            )

            center_x = size // 2
            center_y = size // 2 + 2

            cam_w = 30
            cam_h = 22

            x1 = center_x - cam_w // 2
            y1 = center_y - cam_h // 2
            x2 = center_x + cam_w // 2
            y2 = center_y + cam_h // 2

            draw.rounded_rectangle(
                [(x1, y1), (x2, y2)],
                radius=4,
                fill=white,
                outline=accent_color,
                width=2
            )

            lens_radius = 8
            draw.ellipse(
                [(center_x - lens_radius, center_y - lens_radius),
                 (center_x + lens_radius, center_y + lens_radius)],
                fill=accent_color,
                outline=white,
                width=2
            )

            draw.ellipse(
                [(center_x - 4, center_y - 5),
                 (center_x - 1, center_y - 2)],
                fill=white
            )

            flash_x = center_x + 12
            flash_y = center_y - cam_h // 2 - 2
            draw.rectangle(
                [(flash_x - 2, flash_y - 2),
                 (flash_x + 3, flash_y + 3)],
                fill=white,
                outline=accent_color,
                width=1
            )

            text_y = y2 + 6
            draw.rounded_rectangle(
                [(center_x - 12, text_y - 1),
                 (center_x + 12, text_y + 9)],
                radius=3,
                fill=accent_color
            )

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
                draw.text(
                    (center_x - 6, text_y + 1),
                    "SC",
                    fill=white
                )

            photo = ImageTk.PhotoImage(img)
            self.root.iconphoto(True, photo)
            self.root.tk.call('wm', 'iconphoto', self.root._w, photo)

            self._icon_photo = photo
            self.logger.info("Профессиональная иконка приложения установлена")

        except Exception as e:
            self.logger.warning(f"Не удалось установить иконку: {e}")
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

        self.update_ui_language()

        if hasattr(self, 'lang_btn'):
            self.lang_btn.config(text="EN" if new_lang == "ru" else "RU")

        status_text = self.get_string('ready') if self.ready else self.get_string('starting_browser')
        self.update_status("● " + status_text, '#4CAF50' if self.ready else '#ff9800')

        self.logger.info(f"Язык переключен на: {new_lang}")

    def update_ui_language(self):
        """Обновляет язык интерфейса"""
        self.root.title(self.get_string('app_title'))

        if hasattr(self, 'title_label'):
            self.title_label.config(text=self.get_string('app_title'))

        if hasattr(self, 'btn_capture'):
            self.btn_capture.config(text=self.get_string('btn_capture'))

        if hasattr(self, 'btn_toggle'):
            self.btn_toggle.config(text=self.get_string('btn_toggle'))

        if hasattr(self, 'hotkeys_label'):
            self.hotkeys_label.config(text=self.get_string('hotkeys_info'))

        if hasattr(self, 'show_browser_check'):
            self.show_browser_check.config(text=self.get_string('show_browser'))

    def create_gui(self):
        """Создает главное окно приложения с адаптивной версткой"""
        self.root = Tk()
        self.root.title(self.get_string('app_title'))
        self.root.geometry("520x400")
        self.root.minsize(480, 350)
        self.root.resizable(True, True)
        self.root.configure(bg='#1e1e1e')

        # Создаем переменную для чекбокса ПОСЛЕ создания root
        self.show_browser_var = BooleanVar(value=self.settings.get_show_browser())

        main = Frame(self.root, bg='#1e1e1e')
        main.pack(expand=True, fill=BOTH, padx=25, pady=20)

        # Верхняя панель
        header_frame = Frame(main, bg='#1e1e1e')
        header_frame.pack(fill=X, pady=(0, 15))

        title_frame = Frame(header_frame, bg='#1e1e1e')
        title_frame.pack(side=LEFT, expand=True, fill=X)

        icon_label = Label(title_frame, text="📸",
                           bg='#1e1e1e', fg='white', font=("Arial", 26))
        icon_label.pack(side=LEFT, padx=(0, 10))

        self.title_label = Label(title_frame, text=self.get_string('app_title'),
                                 bg='#1e1e1e', fg='#4CAF50', font=("Arial", 15, "bold"))
        self.title_label.pack(side=LEFT)

        # Кнопка языка
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
            width=6
        )
        self.lang_btn.pack()

        def on_enter(e):
            self.lang_btn.config(bg='#4CAF50', fg='white')

        def on_leave(e):
            self.lang_btn.config(bg='#3c3c3c', fg='#4CAF50')

        self.lang_btn.bind('<Enter>', on_enter)
        self.lang_btn.bind('<Leave>', on_leave)

        # Статус
        self.status = Label(main, text="● " + self.get_string('starting'),
                            fg='#ff9800', bg='#1e1e1e', font=("Arial", 11))
        self.status.pack(pady=(5, 18), fill=X)

        # Кнопки
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

        # Чекбокс для показа браузера
        checkbox_frame = Frame(main, bg='#1e1e1e')
        checkbox_frame.pack(fill=X, pady=(10, 5))

        self.show_browser_check = Checkbutton(
            checkbox_frame,
            text=self.get_string('show_browser'),
            variable=self.show_browser_var,
            command=self.toggle_browser_visibility,
            bg='#1e1e1e',
            fg='#cccccc',
            selectcolor='#1e1e1e',
            font=("Arial", 10),
            activebackground='#1e1e1e',
            activeforeground='#4CAF50'
        )
        self.show_browser_check.pack(anchor=W)

        # Подсказка внизу
        self.hotkeys_label = Label(
            main,
            text=self.get_string('hotkeys_info'),
            bg='#1e1e1e',
            fg='#888',
            font=("Arial", 10),
            wraplength=450
        )
        self.hotkeys_label.pack(pady=(15, 5), fill=X)

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
        width = self.root.winfo_width()

        if width < 460:
            self.title_label.config(font=("Arial", 13, "bold"))
            self.lang_btn.config(font=("Arial", 10, "bold"), padx=12, pady=4, width=5)
            self.btn_capture.config(font=("Arial", 10), padx=15, pady=10)
            self.btn_toggle.config(font=("Arial", 10), padx=15, pady=10)
            self.status.config(font=("Arial", 10))
            if hasattr(self, 'hotkeys_label'):
                self.hotkeys_label.config(font=("Arial", 9), wraplength=width - 60)
            if hasattr(self, 'show_browser_check'):
                self.show_browser_check.config(font=("Arial", 9))
        else:
            self.title_label.config(font=("Arial", 15, "bold"))
            self.lang_btn.config(font=("Arial", 12, "bold"), padx=18, pady=6, width=6)
            self.btn_capture.config(font=("Arial", 11), padx=20, pady=12)
            self.btn_toggle.config(font=("Arial", 11), padx=20, pady=12)
            self.status.config(font=("Arial", 11))
            if hasattr(self, 'hotkeys_label'):
                self.hotkeys_label.config(font=("Arial", 10), wraplength=min(width - 50, 480))
            if hasattr(self, 'show_browser_check'):
                self.show_browser_check.config(font=("Arial", 10))

    def toggle_browser_visibility(self):
        """Переключает видимость браузера"""
        show = self.show_browser_var.get()
        self.settings.set_show_browser(show)
        self.logger.info(f"Видимость браузера изменена: {'показывать' if show else 'скрывать'}")

        # Если переводчик уже инициализирован, перезапускаем его с новыми настройками
        if self._init_done and self.translator:
            self._restart_translator()

    def _restart_translator(self):
        """Перезапускает переводчик с новыми настройками"""

        def restart_task():
            try:
                self.logger.info("Перезапуск переводчика с новыми настройками...")
                self.update_status("● Перезапуск браузера...", '#ff9800')

                # Закрываем текущий браузер
                if self.translator:
                    self.translator.close_browser()

                # Создаем новый переводчик с обновленной настройкой
                show_browser = self.settings.get_show_browser()
                self.translator = GoogleTranslateDebug(headless=not show_browser)
                self.translator.start_browser()

                self.ready = True
                self.update_status("● " + self.get_string('ready'), '#4CAF50')
                self.logger.info("Переводчик перезапущен успешно")

            except Exception as e:
                self.logger.error(f"Ошибка перезапуска переводчика: {e}")
                self.update_status("● " + self.get_string('error') + ": " + str(e)[:50], '#f44336')

        threading.Thread(target=restart_task, daemon=True).start()

    def _init_translator_step(self):
        """Пошаговая инициализация переводчика"""
        if self._init_done:
            return

        self.initializing = True
        self.update_status("● " + self.get_string('starting_browser'), '#ff9800')
        self.root.update_idletasks()

        self.root.after(50, self._init_translator_async)

    def _init_translator_async(self):
        """Инициализация переводчика"""
        try:
            self.logger.info("Запуск инициализации браузера...")
            # Используем настройку show_browser для управления видимостью
            show_browser = self.settings.get_show_browser()
            self.translator = GoogleTranslateDebug(headless=not show_browser)
            self.translator.start_browser()
            self.overlay = OverlayWindow()
            self.ready = True
            self.initializing = False
            self._init_done = True

            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            self.update_status("● " + self.get_string('ready'), '#4CAF50')

            self.logger.info("Инициализация завершена успешно")

        except Exception as e:
            self.logger.error(f"Ошибка инициализации: {e}")
            self.initializing = False
            self._init_done = True
            self.update_status("● " + self.get_string('error') + ": " + str(e)[:50], '#f44336')
            self.btn_capture.config(state=DISABLED, bg='#333', fg='#888')

    def setup_hotkeys(self):
        """Настройка глобальных горячих клавиш"""
        try:
            keyboard.unhook_all()

            keyboard.block_key('f1')
            keyboard.block_key('f2')

            def on_key(event):
                if event.name == 'f1' and event.event_type == 'down':
                    if not self._key_states.get('f1', False):
                        current_time = time.time() * 1000
                        if current_time - self._key_last_time.get('f1', 0) >= self._debounce_ms:
                            self._key_states['f1'] = True
                            self._key_last_time['f1'] = current_time
                            self.root.after(0, self.toggle_overlay)
                            self.root.after(100, lambda: self._key_states.__setitem__('f1', False))
                    return False

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
            self.logger.info("Горячие клавиши зарегистрированы")

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
        if self.translating or not self.ready or self.initializing:
            return

        # Показываем оверлей индикатора ТОЛЬКО ОДИН РАЗ
        self._show_translation_overlay()

        # Блокируем кнопку
        self.btn_capture.config(state=DISABLED, bg='#333')
        self.translating = True

        def capture_task():
            """Захват скриншота в отдельном потоке"""
            try:
                self.update_status(self.get_string('capturing'), '#ff9800')

                img = self.screenshot.capture_active_window()
                if not img:
                    self.update_status(self.get_string('capture_error'), '#f44336')
                    self.translating = False
                    self._hide_translation_overlay()
                    self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
                    return

                path = self.temp_dir / f"scr_{int(time.time())}.png"
                img.save(path)

                # Возвращаемся в основной поток для перевода
                self.root.after(0, lambda: self._do_translate(path))

            except Exception as e:
                self.logger.error(f"Ошибка захвата: {e}")
                self.root.after(0, lambda: self._on_translate_error(str(e)))

        threading.Thread(target=capture_task, daemon=True).start()

    def _do_translate(self, image_path: Path):
        """Выполняет перевод в основном потоке"""
        try:
            # Выполняем перевод (блокирует поток)
            out = self.temp_dir / "translated"
            result = self.translator.translate_image(image_path, out)

            self._on_translate_finished(result)

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Ошибка перевода: {error_msg}")
            self._on_translate_error(error_msg)

    def _do_translate_async(self, image_path: Path):
        """Выполняет перевод в отдельном потоке"""

        def translate_task():
            try:
                out = self.temp_dir / "translated"
                result = self.translator.translate_image(image_path, out)
                # Возвращаем результат в основной поток
                self.root.after(0, lambda: self._on_translate_finished(result))
            except Exception as e:
                self.logger.error(f"Ошибка перевода: {e}")
                self.root.after(0, lambda: self._on_translate_error(str(e)))

        threading.Thread(target=translate_task, daemon=True).start()

    def _on_translate_finished(self, result):
        """Обработчик завершения перевода"""
        try:
            # Завершаем прогресс
            if self.translation_overlay:
                self.translation_overlay.finish()
                time.sleep(0.3)

            if result and self.overlay:
                window_rect = self.screenshot.get_last_window_rect()

                if window_rect and hasattr(self.overlay, 'show_for_window'):
                    self.overlay.show_for_window(result, window_rect)
                else:
                    self.overlay.show_fullscreen(result)

                self.update_status(self.get_string('ready'), '#4CAF50')
            else:
                self.update_status(self.get_string('translate_error'), '#f44336')

        except Exception as e:
            self.logger.error(f"Ошибка показа результата: {e}")
            self.update_status(self.get_string('error'), '#f44336')
        finally:
            self.translating = False
            self._hide_translation_overlay()
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')

    def _on_translate_error(self, error_msg):
        """Обработчик ошибки перевода"""
        self.logger.error(f"Ошибка перевода: {error_msg}")
        self.update_status(self.get_string('error'), '#f44336')
        self.translating = False
        self._hide_translation_overlay()
        self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')

    def _show_translation_overlay(self):
        """Показывает оверлей индикатора перевода"""
        try:
            if self.translation_overlay is None:
                from src.translation_overlay import TranslationOverlay
                self.translation_overlay = TranslationOverlay()

            self.translation_overlay.show(self.get_string('translating'))
        except Exception as e:
            self.logger.warning(f"Не удалось показать оверлей: {e}")

    def _hide_translation_overlay(self):
        """Скрывает оверлей индикатора перевода"""
        try:
            if self.translation_overlay:
                self.translation_overlay.hide()
        except:
            pass

    def toggle_overlay(self):
        """Переключает видимость оверлея переведенного скриншота"""
        if self.overlay:
            self.overlay.toggle()
            status = self.get_string('shown') if self.overlay.is_visible() else self.get_string('hidden')
            self.update_status(f"● {self.get_string('overlay')} {status}", '#2196F3')

    def on_close(self):
        """Обработчик закрытия приложения"""
        self._hide_translation_overlay()

        try:
            keyboard.unblock_key('f1')
            keyboard.unblock_key('f2')
            keyboard.unhook_all()
        except:
            pass

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