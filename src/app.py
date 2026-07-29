"""

Главный модуль приложения для перевода скриншотов

"""

import logging
import tempfile
import time
import threading
import os
import sys
import tkinter.messagebox as messagebox
from pathlib import Path
from tkinter import *
from tkinter import ttk
from datetime import datetime
import keyboard
from src.translator import GoogleTranslateDebug
from src.screenshot import ScreenshotCapturer
from src.overlay import OverlayWindow
from src.settings import Settings
from src.strings import get_strings
from src.browser_worker import BrowserWorker
from src.area_selector import AreaSelector

LANGUAGES = {"af": "Afrikaans", "sq": "Albanian", "am": "Amharic", "ar": "Arabic", "hy": "Armenian",
             "az": "Azerbaijani", "eu": "Basque", "be": "Belarusian", "bn": "Bengali", "bs": "Bosnian",
             "bg": "Bulgarian", "ca": "Catalan", "ceb": "Cebuano", "ny": "Chichewa", "zh-cn": "Chinese (Simplified)",
             "zh-tw": "Chinese (Traditional)", "co": "Corsican", "hr": "Croatian", "cs": "Czech", "da": "Danish",
             "nl": "Dutch", "en": "English", "eo": "Esperanto", "et": "Estonian", "tl": "Filipino", "fi": "Finnish",
             "fr": "French", "fy": "Frisian", "gl": "Galician", "ka": "Georgian", "de": "German", "el": "Greek",
             "gu": "Gujarati", "ht": "Haitian Creole", "ha": "Hausa", "haw": "Hawaiian", "iw": "Hebrew", "hi": "Hindi",
             "hmn": "Hmong", "hu": "Hungarian", "is": "Icelandic", "ig": "Igbo", "id": "Indonesian", "ga": "Irish",
             "it": "Italian", "ja": "Japanese", "jw": "Javanese", "kn": "Kannada", "kk": "Kazakh", "km": "Khmer",
             "rw": "Kinyarwanda", "ko": "Korean", "ku": "Kurdish (Kurmanji)", "ky": "Kyrgyz", "lo": "Lao",
             "la": "Latin", "lv": "Latvian", "lt": "Lithuanian", "lb": "Luxembourgish", "mk": "Macedonian",
             "mg": "Malagasy", "ms": "Malay", "ml": "Malayalam", "mt": "Maltese", "mi": "Maori", "mr": "Marathi",
             "mn": "Mongolian", "my": "Myanmar (Burmese)", "ne": "Nepali", "no": "Norwegian", "or": "Odia (Oriya)",
             "ps": "Pashto", "fa": "Persian", "pl": "Polish", "pt": "Portuguese", "pa": "Punjabi", "ro": "Romanian",
             "ru": "Russian", "sm": "Samoan", "gd": "Scots Gaelic", "sr": "Serbian", "st": "Sesotho", "sn": "Shona",
             "sd": "Sindhi", "si": "Sinhala", "sk": "Slovak", "sl": "Slovenian", "so": "Somali", "es": "Spanish",
             "su": "Sundanese", "sw": "Swahili", "sv": "Swedish", "tg": "Tajik", "ta": "Tamil", "tt": "Tatar",
             "te": "Telugu", "th": "Thai", "tr": "Turkish", "tk": "Turkmen", "uk": "Ukrainian", "ur": "Urdu",
             "ug": "Uyghur", "uz": "Uzbek", "vi": "Vietnamese", "cy": "Welsh", "xh": "Xhosa", "yi": "Yiddish",
             "yo": "Yoruba", "zu": "Zulu"}


def cleanup_old_logs(log_dir, keep_count=5):
    """
    Очищает старые логи, оставляя только указанное количество последних
    Args:
        log_dir: Путь к папке с логами
        keep_count: Количество последних лог-файлов для сохранения
    """
    try:
        if not log_dir.exists():
            return
        log_files = list(log_dir.glob("app_*.log"))
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        if len(log_files) > keep_count:
            files_to_delete = log_files[keep_count:]
            deleted_count = 0
            for file_path in files_to_delete:
                try:
                    file_path.unlink()
                    deleted_count += 1
                except Exception as e:
                    print(f"Не удалось удалить {file_path.name}: {e}")
            if deleted_count > 0:
                print(f"Очистка логов: удалено {deleted_count} старых файлов, оставлено {keep_count}")
    except Exception as e:
        print(f"Ошибка при очистке старых логов: {e}")


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
        cleanup_old_logs(log_dir, keep_count=5)
        return log_file
    except Exception as e:
        print(f"Ошибка настройки логирования: {e}")
        return None


class ScreenshotTranslatorApp:
    """Главное окно приложения для перевода скриншотов"""

    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.settings = Settings()
        from src.utils import ensure_app_temp_dir
        self.temp_dir = ensure_app_temp_dir()
        self.overlay_manager = None
        self.screenshot = ScreenshotCapturer()
        self.ready = False
        self.translating = False
        self.initializing = False
        self._init_done = False
        self._translation_done = True
        self.translation_overlay = None
        self._key_states = {}
        self._key_last_time = {}
        self._debounce_ms = 500
        self._restarting = False
        self._processor_running = False
        self.show_browser_var = None
        self.target_lang_var = None
        self.show_indicator_var = None
        self.auto_hide_var = None
        self.app_title = None
        self.browser_worker = BrowserWorker(self.settings)
        self.browser_worker.start()
        self._pending_command_ids = {}
        self._translation_in_progress = False
        self._edit_mode_enabled = self.settings.get_edit_mode_enabled()
        self._init_attempts = 0
        self._max_init_attempts = 3
        self._init_retry_delay = 2000
        self._actions_blocked = False
        self._hotkey_hook_active = True
        self._capture_mode = False
        self._area_selector = None
        self._selection_window = None
        self._pressed_keys = set()

        # === НОВАЯ ОЧЕРЕДЬ ПЕРЕВОДОВ ===
        self.translation_queue = []
        self.is_processing_queue = False
        # ================================

        self.create_gui()
        self.update_ui_language()
        self.app_title = self.get_string('app_title')
        self.logger.info(f"Заголовок приложения: {self.app_title}")
        self._setup_app_icon()
        self.setup_hotkeys()
        self.update_hotkey_buttons()
        self.root.after(100, self._init_translator_step)

    def capture_area(self):
        """Захват области экрана (F3) - добавляет задачу в очередь."""
        self.logger.info("[DEBUG] capture_area() вызван")

        # УБИРАЕМ БЛОКИРОВКУ self.translating
        if not self.ready or self.initializing:
            self.logger.warning("[DEBUG] capture_area пропущен: не готов или инициализируется")
            return

        # Блокируем только кнопку, чтобы предотвратить спам, но не блокируем логику
        # Кнопка будет разблокирована в _process_area_selection, когда задача будет добавлена в очередь
        self.btn_capture.config(state=DISABLED, bg='#333')

        try:
            self.root.iconify()
            self.logger.info("[DEBUG] Главное окно свернуто")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось свернуть окно: {e}")

        self.root.after(500, self._capture_window_for_area)

    def _process_area_selection(self, x1, y1, x2, y2, screenshot_path):
        """Обрабатывает выделенную область - добавляет задачу в очередь."""
        self.logger.info(f"[DEBUG] _process_area_selection: ({x1},{y1})-({x2},{y2})")

        self._capture_mode = False
        self._selection_window = None
        self._selection_window_on_escape = None

        # Разблокируем кнопку, так как область выбрана и задача будет добавлена в очередь
        self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')

        self.logger.info(
            f"[DEBUG] _process_area_selection: текущее количество оверлеев: {len(self.overlay_manager.overlays) if self.overlay_manager else 0}")

        self._area_rect = (x1, y1, x2, y2)

        def process_task():
            try:
                self.update_status("● Вырезание области...", '#ff9800')

                from PIL import Image

                full_img = Image.open(screenshot_path)
                cropped = full_img.crop((x1, y1, x2, y2))

                if not cropped:
                    self.logger.error("[DEBUG] Не удалось вырезать область")
                    self.update_status(self.get_string('capture_error'), '#f44336')
                    self.root.deiconify()
                    return

                self.logger.info(f"[DEBUG] Область вырезана: {cropped.size}")

                path = self.temp_dir / f"area_{int(time.time())}.png"
                cropped.save(path)
                self.logger.info(f"[DEBUG] Область сохранена: {path}")

                try:
                    os.remove(screenshot_path)
                except:
                    pass

                target_hwnd = getattr(self, '_area_target_hwnd', None)
                is_fullscreen = getattr(self, '_area_is_fullscreen', False)

                if target_hwnd:
                    self.logger.info(
                        f"[DEBUG] Для оверлея будет использован HWND: {target_hwnd}, полноэкранный: {is_fullscreen}")
                    self.screenshot._last_hwnd = target_hwnd
                    self.screenshot._is_fullscreen = is_fullscreen

                self._area_rect_for_overlay = (x1, y1, x2, y2)

                # === ДОБАВЛЯЕМ ЗАДАЧУ В ОЧЕРЕДЬ ВМЕСТО ПРЯМОГО ВЫЗОВА _do_translate ===
                task = {
                    'type': 'area',
                    'image_path': path,
                    'area_rect': (x1, y1, x2, y2),
                    'target_hwnd': target_hwnd,
                    'is_fullscreen': is_fullscreen
                }
                self.translation_queue.append(task)
                self.logger.info(f"[QUEUE] Задача добавлена в очередь. Размер очереди: {len(self.translation_queue)}")

                # Запускаем обработку очереди, если она не запущена
                if not self.is_processing_queue:
                    self._process_next_in_queue()
                # ============================

            except Exception as e:
                self.logger.error(f"Ошибка обработки области: {e}")
                self.update_status(self.get_string('error'), '#f44336')

        threading.Thread(target=process_task, daemon=True).start()

    def process(self):
        """Обработка скриншота (F2) - удаляет старые оверлеи и добавляет задачу в очередь."""
        if self.translating or not self.ready or self.initializing:
            return

        if self.overlay_manager and self.overlay_manager.overlays:
            count = len(self.overlay_manager.overlays)
            self.logger.info(f"[DEBUG] F2: удаляем {count} старых оверлеев перед созданием нового")
            self.overlay_manager.close_all()
            self.logger.info(f"[DEBUG] Старые оверлеи удалены")

        self.btn_capture.config(state=DISABLED, bg='#333')
        self.translating = True

        try:
            import win32gui
            current_hwnd = win32gui.GetForegroundWindow()
            if current_hwnd:
                self.screenshot._last_hwnd = current_hwnd
                self.screenshot._is_fullscreen = self.screenshot.is_window_fullscreen(current_hwnd)
                self.logger.info(
                    f"[DEBUG] Сохранен HWND активного окна для скриншота: {current_hwnd}, полноэкранный: {self.screenshot._is_fullscreen}")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось сохранить HWND активного окна: {e}")

        def capture_task():
            """Захват скриншота в отдельном потоке"""
            try:
                self.update_status(self.get_string('capturing'), '#ff9800')
                img = self.screenshot.capture_active_window()

                if not img:
                    self.update_status(self.get_string('capture_error'), '#f44336')
                    self.translating = False
                    self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
                    return

                self.root.after(0, self._show_translation_overlay)

                path = self.temp_dir / f"scr_{int(time.time())}.png"
                img.save(path)

                # === ДОБАВЛЯЕМ ЗАДАЧУ В ОЧЕРЕДЬ ===
                task = {
                    'type': 'screenshot',
                    'image_path': path,
                    'area_rect': None
                }
                self.translation_queue.append(task)
                self.logger.info(
                    f"[QUEUE] Задача скриншота добавлена в очередь. Размер очереди: {len(self.translation_queue)}")

                self.translating = False  # Освобождаем флаг для следующего F2

                # Запускаем обработку очереди, если она не запущена
                if not self.is_processing_queue:
                    self._process_next_in_queue()
                # ============================

            except Exception as e:
                self.logger.error(f"Ошибка захвата: {e}")
                self.root.after(0, lambda: self._on_translate_error(str(e)))

        threading.Thread(target=capture_task, daemon=True).start()

    def _process_next_in_queue(self):
        """Обрабатывает следующую задачу в очереди переводов."""
        if self.is_processing_queue:
            self.logger.info("[QUEUE] Обработка очереди уже выполняется")
            return

        if not self.translation_queue:
            self.logger.info("[QUEUE] Очередь пуста")
            self.is_processing_queue = False
            # Разблокируем кнопку, если она заблокирована
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            return

        self.is_processing_queue = True
        self.logger.info(f"[QUEUE] Начинаем обработку задачи. Осталось: {len(self.translation_queue)}")

        task = self.translation_queue.pop(0)
        self.logger.info(f"[QUEUE] Обработка задачи типа: {task.get('type')}")

        # Показываем индикатор перевода
        self.root.after(0, self._show_translation_overlay)

        if task.get('type') == 'screenshot':
            # Для скриншота окна
            self._pending_area_rect = None
            self._do_translate(task['image_path'])
        else:
            # Для области
            self._pending_area_rect = task.get('area_rect')
            self._do_translate(task['image_path'], area_rect=task.get('area_rect'))

    def _on_translate_finished(self, result, error):
        """Обработчик завершения перевода - запускает следующую задачу из очереди."""
        self.logger.info(f"_on_translate_finished вызван: result={result}, error={error}")

        self._translation_in_progress = False

        try:
            if error and "отменен" in str(error):
                self.logger.info("[DEBUG] _on_translate_finished: перевод был отменен")
                self.translating = False
                self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
                self._pending_command_ids = {}
                self._pending_area_rect = None
                # Переходим к следующей задаче
                self.is_processing_queue = False
                self._process_next_in_queue()
                return

            if error:
                self.logger.error(f"Ошибка перевода: {error}")
                self._on_translate_error(error)
                return

            if result:
                self.logger.info(f"Результат перевода получен: {result}")
                if isinstance(result, Path) and result.exists():
                    self.logger.info(f"Файл перевода существует: {result}, размер: {result.stat().st_size} байт")
                else:
                    self.logger.warning(f"Результат не является файлом или не существует: {result}")

                if self.translation_overlay:
                    self.logger.info("Закрываем окно прогресса ДО показа основного оверлея")
                    self.translation_overlay.finish()
                    time.sleep(0.3)
                    self.translation_overlay = None

                self.logger.info(f"Попытка показать оверлей с результатом")
                self.logger.info(f"self.overlay_manager = {self.overlay_manager}")

                if self.overlay_manager:
                    window_rect = self.screenshot.get_last_window_rect()
                    target_hwnd = self.screenshot.get_last_hwnd()
                    is_fullscreen = self.screenshot.is_last_window_fullscreen()
                    self.logger.info(
                        f"window_rect = {window_rect}, target_hwnd = {target_hwnd}, is_fullscreen = {is_fullscreen}")

                    area_rect = getattr(self, '_pending_area_rect', None)
                    if area_rect:
                        self.logger.info(f"[DEBUG] Используем область для оверлея: {area_rect}")
                        x1, y1, x2, y2 = area_rect
                        area_window_rect = (x1, y1, x2, y2)
                    else:
                        area_window_rect = window_rect
                        self.logger.info(f"[DEBUG] Используем стандартный window_rect: {window_rect}")

                    is_target_active = False
                    if target_hwnd:
                        try:
                            import win32gui
                            active_hwnd = win32gui.GetForegroundWindow()
                            is_target_active = (active_hwnd == target_hwnd)
                            self.logger.info(
                                f"[DEBUG] Активное окно: {active_hwnd}, целевое: {target_hwnd}, is_target_active={is_target_active}")
                        except Exception as e:
                            self.logger.warning(f"[DEBUG] Не удалось проверить активное окно: {e}")

                    is_window_screenshot = (area_rect is None)
                    self.logger.info(
                        f"[DEBUG] is_window_screenshot = {is_window_screenshot} (area_rect={area_rect is not None})")

                    self.overlay_manager.create_overlay(
                        image_path=result,
                        window_rect=area_window_rect,
                        target_hwnd=target_hwnd,
                        is_fullscreen=is_fullscreen,
                        show_immediately=is_target_active,
                        is_window_screenshot=is_window_screenshot
                    )
                    self.logger.info("create_overlay выполнен")
                    if not is_target_active:
                        self.logger.info("[DEBUG] Целевое окно не активно, оверлей сохранен но скрыт")
                        self.update_status(f"● Перевод готов (вернитесь в игру)", '#ff9800')
                    else:
                        self.logger.info("[DEBUG] Целевое окно активно, оверлей показан")

                    self.root.update_idletasks()
                    self.root.update()
                    self.logger.info("Результат перевода показан")
                else:
                    self.logger.error("self.overlay_manager is None! Менеджер не создан.")

                self.update_status(self.get_string('ready'), '#4CAF50')
            else:
                self.logger.warning("Результат перевода пустой (None)")
                self.update_status(self.get_string('translate_error'), '#f44336')

        except Exception as e:
            self.logger.error(f"Ошибка показа результата: {e}")
            import traceback
            traceback.print_exc()
            self.update_status(self.get_string('error'), '#f44336')
        finally:
            self.translating = False
            self._hide_translation_overlay()
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            self._pending_command_ids = {}
            self._pending_area_rect = None

            # === ПЕРЕХОДИМ К СЛЕДУЮЩЕЙ ЗАДАЧЕ В ОЧЕРЕДИ ===
            self.is_processing_queue = False
            self._process_next_in_queue()
            # =============================================

    def _do_translate(self, image_path: Path, area_rect=None):
        """Выполняет перевод в фоновом режиме через BrowserWorker."""
        self.logger.info(f"[DEBUG] _do_translate: image_path={image_path}, area_rect={area_rect}")

        self._translation_in_progress = True

        if self.overlay_manager:
            self.overlay_manager._enable_esc_hook()
            self.logger.info("[DEBUG] _do_translate: глобальный хук ESC включен")

        self._pending_area_rect = area_rect

        out = self.temp_dir / "translated"
        cmd_id = self.browser_worker.translate_image(
            image_path,
            out,
            callback=self._on_translate_finished
        )
        self._pending_command_ids[cmd_id] = 'translate'
        self._check_results()

    def toggle_edit_mode(self):
        """Переключает режим редактирования оверлеев (F5)."""
        self._edit_mode_enabled = not self._edit_mode_enabled
        self.settings.set_edit_mode_enabled(self._edit_mode_enabled)

        status_text = self.get_string('edit_mode_on') if self._edit_mode_enabled else self.get_string('edit_mode_off')
        self.logger.info(f"Режим редактирования переключен: {status_text}")

        # Обновляем состояние режима редактирования для всех существующих оверлеев
        if hasattr(self, 'overlay_manager') and self.overlay_manager:
            self.overlay_manager.update_edit_mode_for_all(self._edit_mode_enabled)
            self.logger.info(f"Обновлен режим редактирования для всех оверлеев: {self._edit_mode_enabled}")

        if hasattr(self, 'btn_edit_mode'):
            hotkeys = self.settings.get_all_hotkeys()
            edit_key = hotkeys.get('edit_mode', 'f5').upper()
            self.btn_edit_mode.config(
                text=f"✏️ {self.get_string('edit_mode')}: {status_text} ({edit_key})",
                bg='#4CAF50' if self._edit_mode_enabled else '#ff9800'
            )
            self.update_hotkey_buttons()
        return self._edit_mode_enabled

    def update_hotkey_buttons(self):
        """Обновляет текст на кнопках в соответствии с текущими горячими клавишами."""
        hotkeys = self.settings.get_all_hotkeys()

        # Обновляем кнопку скриншота
        screenshot_key = hotkeys.get('screenshot', 'f2').upper()
        if hasattr(self, 'btn_capture'):
            is_disabled = (self.btn_capture['state'] == DISABLED)
            self.btn_capture.config(
                text=f"{self.get_string('btn_capture')} ({screenshot_key})",
                bg='#333' if is_disabled else '#4CAF50',
                fg='#888' if is_disabled else 'white'
            )

        # Обновляем кнопку области (если есть)
        area_key = hotkeys.get('area', 'f3').upper()
        if hasattr(self, 'btn_area'):
            is_disabled = (self.btn_area['state'] == DISABLED)
            self.btn_area.config(
                text=f"{self.get_string('btn_area')} ({area_key})",
                bg='#333' if is_disabled else '#2196F3',
                fg='#888' if is_disabled else 'white'
            )

        # Обновляем кнопку оверлея
        toggle_key = hotkeys.get('toggle_overlay', 'f1').upper()
        if hasattr(self, 'btn_toggle'):
            is_disabled = (self.btn_toggle['state'] == DISABLED)
            self.btn_toggle.config(
                text=f"{self.get_string('btn_toggle')} ({toggle_key})",
                bg='#333' if is_disabled else '#2196F3',
                fg='#888' if is_disabled else 'white'
            )

        # Обновляем кнопку очистки
        clear_key = hotkeys.get('clear_all', 'f4').upper()
        if hasattr(self, 'btn_clear_all'):
            is_disabled = (self.btn_clear_all['state'] == DISABLED)
            self.btn_clear_all.config(
                text=f"🗑️ {self.get_string('clear_all')} ({clear_key})",
                bg='#333' if is_disabled else '#d32f2f',
                fg='#888' if is_disabled else 'white'
            )

        # Обновляем кнопку режима редактирования
        edit_key = hotkeys.get('edit_mode', 'f5').upper()
        status_text = self.get_string('edit_mode_on') if self._edit_mode_enabled else self.get_string('edit_mode_off')
        if hasattr(self, 'btn_edit_mode'):
            is_disabled = (self.btn_edit_mode['state'] == DISABLED)
            if is_disabled:
                self.btn_edit_mode.config(
                    text=f"✏️ {self.get_string('edit_mode')}: {status_text} ({edit_key})",
                    bg='#333',
                    fg='#888'
                )
            else:
                self.btn_edit_mode.config(
                    text=f"✏️ {self.get_string('edit_mode')}: {status_text} ({edit_key})",
                    bg='#4CAF50' if self._edit_mode_enabled else '#ff9800',
                    fg='white'
                )

        self.logger.info(f"[HOTKEYS] Кнопки обновлены: {hotkeys}")

    def show_help(self):
        """Показывает окно со ссылками на GitHub и Discord."""
        import tkinter as tk
        import webbrowser

        # Создаем окно и СРАЗУ СКРЫВАЕМ
        help_window = tk.Toplevel(self.root)
        help_window.withdraw()
        help_window.title(self.get_string('help_title'))
        help_window.configure(bg='#1e1e1e')
        help_window.transient(self.root)
        help_window.grab_set()

        # Основной контейнер
        main_frame = tk.Frame(help_window, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=25)

        # Заголовок
        title = tk.Label(
            main_frame,
            text="📸 Google Screen Translate",
            bg='#1e1e1e',
            fg='#4CAF50',
            font=("Segoe UI", 16, "bold")
        )
        title.pack(pady=(0, 5))

        # Подзаголовок
        subtitle = tk.Label(
            main_frame,
            text=self.get_string('help_subtitle'),
            bg='#1e1e1e',
            fg='#888888',
            font=("Segoe UI", 10)
        )
        subtitle.pack(pady=(0, 20))

        # Разделитель
        separator = tk.Frame(main_frame, bg='#3c3c3c', height=1)
        separator.pack(fill=tk.X, pady=5)

        # Текст с ссылками
        info_label = tk.Label(
            main_frame,
            text=self.get_string('help_info'),
            bg='#1e1e1e',
            fg='#aaaaaa',
            font=("Segoe UI", 10)
        )
        info_label.pack(pady=(15, 8))

        def open_link(url):
            webbrowser.open(url)

        # Стиль для кнопок-ссылок
        link_style = {
            'bg': '#1e1e1e',
            'font': ("Segoe UI", 10, "underline"),
            'relief': tk.FLAT,
            'cursor': "hand2",
            'pady': 5
        }

        # Ссылка на GitHub
        github_btn = tk.Button(
            main_frame,
            text="🐙 GitHub: AlexeyZam15/GoogleImagesScreenTranslator",
            command=lambda: open_link("https://github.com/AlexeyZam15/GoogleImagesScreenTranslator"),
            fg='#4CAF50',
            **link_style
        )
        github_btn.pack(pady=3)

        # Ссылка на Discord
        discord_btn = tk.Button(
            main_frame,
            text="💬 Discord: discord.gg/TSRFfRUwn",
            command=lambda: open_link("https://discord.gg/TSRFfRUwn"),
            fg='#5865F2',
            **link_style
        )
        discord_btn.pack(pady=3)

        # Кнопка закрытия
        close_btn = tk.Button(
            main_frame,
            text=self.get_string('help_close'),
            command=help_window.destroy,
            bg='#4CAF50',
            fg='white',
            font=("Segoe UI", 10, "bold"),
            relief=tk.FLAT,
            padx=30,
            pady=8,
            cursor="hand2"
        )
        close_btn.pack(pady=(20, 0))

        # Настраиваем размер и центрируем
        help_window.update_idletasks()
        width = 600
        height = 320
        help_window.geometry(f"{width}x{height}")
        x = (help_window.winfo_screenwidth() - width) // 2
        y = (help_window.winfo_screenheight() - height) // 2
        help_window.geometry(f"{width}x{height}+{x}+{y}")
        help_window.resizable(False, False)

        # Показываем окно
        help_window.deiconify()
        help_window.lift()
        help_window.focus_force()

    def set_settings_menu_enabled(self, enabled: bool):
        """Блокирует или разблокирует пункт меню 'Настройки'."""
        try:
            if hasattr(self, '_settings_menu') and self._settings_menu is not None:
                state = NORMAL if enabled else DISABLED
                # Настраиваем состояние через сам объект меню
                # Для Tkinter нужно использовать menubar.entryconfig()
                if hasattr(self, '_menubar') and self._menubar is not None:
                    # Находим индекс пункта "Настройки" и меняем его состояние
                    for index in range(self._menubar.index('end') + 1):
                        try:
                            label = self._menubar.entrycget(index, 'label')
                            if label == self.get_string('menu_settings'):
                                self._menubar.entryconfig(index, state=state)
                                self.logger.info(
                                    f"[MENU] Меню 'Настройки' {'разблокировано' if enabled else 'заблокировано'}")
                                break
                        except:
                            pass
                else:
                    self.logger.warning("[MENU] _menubar не инициализирован")
        except Exception as e:
            self.logger.warning(f"[MENU] Ошибка при блокировке меню: {e}")

    def create_menu(self):
        """Создает главное меню приложения"""
        self._menubar = Menu(self.root, bg='#1e1e1e', fg='white')
        self.root.config(menu=self._menubar)

        # Файл
        file_menu = Menu(self._menubar, tearoff=0, bg='#1e1e1e', fg='white')
        self._menubar.add_cascade(label=self.get_string('menu_file'), menu=file_menu)
        file_menu.add_command(label=self.get_string('menu_open_folder'), command=self.open_app_folder)
        file_menu.add_separator()
        file_menu.add_command(label=self.get_string('menu_exit'), command=self.on_close)

        # Настройки
        settings_menu = Menu(self._menubar, tearoff=0, bg='#1e1e1e', fg='white')
        self._settings_menu = settings_menu  # Сохраняем сам объект меню
        self._menubar.add_cascade(
            label=self.get_string('menu_settings'),
            menu=settings_menu,
            state=DISABLED
        )
        settings_menu.add_command(
            label=self.get_string('menu_settings_item'),
            command=self.open_settings
        )
        settings_menu.add_separator()
        settings_menu.add_command(
            label=self.get_string('menu_reset_settings'),
            command=self.reset_settings
        )

        # Помощь
        help_menu = Menu(self._menubar, tearoff=0, bg='#1e1e1e', fg='white')
        self._menubar.add_cascade(label=self.get_string('menu_help'), menu=help_menu)
        help_menu.add_command(
            label=self.get_string('menu_help_instruction'),
            command=self.show_help
        )

    def update_menu_language(self):
        """Обновляет язык главного меню"""
        self.create_menu()  # Просто пересоздаём меню

        # Обновляем состояние после пересоздания
        if hasattr(self, '_init_done') and self._init_done:
            self.set_settings_menu_enabled(True)

    def set_actions_blocked(self, blocked: bool):
        """Устанавливает флаг блокировки ДЕЙСТВИЙ горячих клавиш."""
        old_state = self._actions_blocked
        self._actions_blocked = blocked
        self.logger.info(f"[HOTKEYS] 🔒 Блокировка действий: {old_state} → {blocked}")

        if blocked:
            self.logger.info("[HOTKEYS] ⚠️ ДЕЙСТВИЯ ГОРЯЧИХ КЛАВИШ ЗАБЛОКИРОВАНЫ")
            # ПОЛНОСТЬЮ ОТКЛЮЧАЕМ ВСЕ ХУКИ
            try:
                keyboard.unhook_all()
                self._hotkey_hook_active = False
                self.logger.info("[HOTKEYS] ✅ Все хуки отключены для захвата клавиши")
            except Exception as e:
                self.logger.error(f"[HOTKEYS] Ошибка отключения хуков: {e}")
        else:
            self.logger.info("[HOTKEYS] ✅ ДЕЙСТВИЯ ГОРЯЧИХ КЛАВИШ РАЗБЛОКИРОВАНЫ")
            # ВОССТАНАВЛИВАЕМ ХУКИ
            try:
                self.setup_hotkeys()
                self.logger.info("[HOTKEYS] ✅ Хуки восстановлены")
            except Exception as e:
                self.logger.error(f"[HOTKEYS] Ошибка восстановления хуков: {e}")

    def setup_hotkeys(self):
        """Настройка глобальных горячих клавиш с использованием настроек."""
        self.logger.info("=" * 60)
        self.logger.info("[HOTKEYS] НАСТРОЙКА ГОРЯЧИХ КЛАВИШ")
        self.logger.info("=" * 60)

        try:
            keyboard.unhook_all()
            self.logger.info("[HOTKEYS] Старые хуки отключены")

            self._capture_mode = False
            self._area_selector = None
            self._selection_window = None
            self._hotkey_hook_active = True
            self.logger.info(f"[HOTKEYS] _actions_blocked = {self._actions_blocked}")

            hotkeys = self.settings.get_all_hotkeys()
            self.logger.info(f"[HOTKEYS] Загружены настройки хоткеев: {hotkeys}")

            self._hotkey_actions = {
                'toggle_overlay': hotkeys.get('toggle_overlay', 'f1'),
                'screenshot': hotkeys.get('screenshot', 'f2'),
                'area': hotkeys.get('area', 'f3'),
                'clear_all': hotkeys.get('clear_all', 'f4'),
                'edit_mode': hotkeys.get('edit_mode', 'f5')
            }
            self.logger.info(f"[HOTKEYS] Назначенные действия: {self._hotkey_actions}")

            # === ОДИНОЧНЫЕ КЛАВИШИ ===
            single_keys = ['f1', 'f2', 'f3', 'f4', 'f5']

            def make_single_handler(action):
                def handler(e):
                    # _actions_blocked больше не проверяем - хуки физически отключаются
                    current_time = time.time() * 1000
                    if current_time - self._key_last_time.get(action, 0) >= self._debounce_ms:
                        self._key_last_time[action] = current_time
                        self.logger.info(f"[HOTKEYS] ДЕЙСТВИЕ: {action}")
                        if action == 'toggle_overlay':
                            self.root.after(0, self.toggle_overlay)
                        elif action == 'screenshot':
                            self.root.after(0, self.process)
                        elif action == 'area':
                            self.root.after(0, self.capture_area)
                        elif action == 'clear_all':
                            self.root.after(0, self.clear_all_overlays)
                        elif action == 'edit_mode':
                            self.root.after(0, self.toggle_edit_mode)
                    return False

                return handler

            for action, hotkey in self._hotkey_actions.items():
                if hotkey in single_keys:
                    keyboard.on_press_key(hotkey, make_single_handler(action), suppress=True)
                    self.logger.info(f"[HOTKEYS] Зарегистрирована одиночная клавиша {hotkey} -> {action}")

            # === СОЧЕТАНИЯ КЛАВИШ ===
            combinations = {}
            for action, hotkey in self._hotkey_actions.items():
                if hotkey not in single_keys:
                    combinations[action] = hotkey

            if combinations:
                self.logger.info(f"[HOTKEYS] Обнаружены комбинации: {combinations}")

                self._pressed_keys = set()

                def on_combination_key(event):
                    if not self._hotkey_hook_active:
                        return True

                    # _actions_blocked больше не проверяем - хуки физически отключаются

                    if event.event_type == 'down':
                        self._pressed_keys.add(event.name)
                    elif event.event_type == 'up':
                        self._pressed_keys.discard(event.name)
                        return True

                    if event.name == 'esc' and event.event_type == 'down':
                        if self._capture_mode:
                            # ... обработка ESC ...
                            return False
                        return True

                    if event.event_type == 'down':
                        current_pressed = set(self._pressed_keys)

                        for action, hotkey in combinations.items():
                            hotkey_parts = [p.lower().strip() for p in hotkey.split('+') if p.strip()]
                            if not hotkey_parts:
                                continue

                            all_pressed = True
                            pressed_lower = [p.lower() for p in current_pressed]

                            for part in hotkey_parts:
                                found = False
                                for pressed in pressed_lower:
                                    if part in pressed or pressed in part:
                                        found = True
                                        break
                                if not found:
                                    all_pressed = False
                                    break

                            if all_pressed:
                                pressed_count = len(current_pressed)
                                hotkey_count = len(hotkey_parts)
                                if pressed_count > hotkey_count:
                                    continue

                                current_time = time.time() * 1000
                                combo_key = f"{action}_{hotkey}"
                                if current_time - self._key_last_time.get(combo_key, 0) >= self._debounce_ms:
                                    self._key_last_time[combo_key] = current_time
                                    self.logger.info(f"[HOTKEYS] ✅ Комбинация сработала: {action} ({hotkey})")
                                    if action == 'toggle_overlay':
                                        self.root.after(0, self.toggle_overlay)
                                    elif action == 'screenshot':
                                        self.root.after(0, self.process)
                                    elif action == 'area':
                                        self.root.after(0, self.capture_area)
                                    elif action == 'clear_all':
                                        self.root.after(0, self.clear_all_overlays)
                                    elif action == 'edit_mode':
                                        self.root.after(0, self.toggle_edit_mode)
                                    self._pressed_keys.clear()
                                    return False

                    return True

                keyboard.hook(on_combination_key, suppress=True)
                self.logger.info("[HOTKEYS] Хук для комбинаций установлен")

            self._hotkey_hook_active = True
            self.logger.info("=" * 60)
            self.logger.info(
                f"[HOTKEYS] ✅ Горячие клавиши зарегистрированы:\n"
                f"  toggle_overlay: {self._hotkey_actions['toggle_overlay']}\n"
                f"  screenshot:     {self._hotkey_actions['screenshot']}\n"
                f"  area:           {self._hotkey_actions['area']}\n"
                f"  clear_all:      {self._hotkey_actions['clear_all']}\n"
                f"  edit_mode:      {self._hotkey_actions['edit_mode']}"
            )
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"[HOTKEYS] ❌ Ошибка регистрации горячих клавиш: {e}")
            import traceback
            self.logger.error(traceback.format_exc())
            self._setup_tkinter_hotkeys()

    def _hotkey_wrapper(self, action):
        """Возвращает функцию-обертку для обработки горячей клавиши с debounce."""

        def wrapper():
            if self._actions_blocked:
                self.logger.debug(f"[HOTKEYS] Действие {action} заблокировано")
                return
            current_time = time.time() * 1000
            if current_time - self._key_last_time.get(action, 0) >= self._debounce_ms:
                self._key_last_time[action] = current_time
                if action == 'toggle_overlay':
                    self.logger.info(f"[HOTKEYS] ДЕЙСТВИЕ: toggle_overlay")
                    self.root.after(0, self.toggle_overlay)
                elif action == 'screenshot':
                    self.logger.info(f"[HOTKEYS] ДЕЙСТВИЕ: screenshot")
                    self.root.after(0, self.process)
                elif action == 'area':
                    self.logger.info(f"[HOTKEYS] ДЕЙСТВИЕ: area")
                    self.root.after(0, self.capture_area)
                elif action == 'clear_all':
                    self.logger.info(f"[HOTKEYS] ДЕЙСТВИЕ: clear_all")
                    self.root.after(0, self.clear_all_overlays)
                elif action == 'edit_mode':
                    self.logger.info(f"[HOTKEYS] ДЕЙСТВИЕ: edit_mode")
                    self.root.after(0, self.toggle_edit_mode)
            else:
                self.logger.debug(f"[HOTKEYS] {action} пропущен (debounce)")

        return wrapper

    def _setup_fallback_hotkey_hook(self):
        """Fallback метод регистрации горячих клавиш через хук с блокировкой."""
        self.logger.info("[HOTKEYS] Используем fallback метод через хук")

        # Храним состояние зажатых клавиш
        self._fallback_pressed_keys = set()

        def on_key(event):
            if not self._hotkey_hook_active:
                return True

            # Если действия заблокированы (режим захвата) - пропускаем
            if self._actions_blocked:
                return True

            # Обновляем состояние зажатых клавиш
            if event.event_type == 'down':
                self._fallback_pressed_keys.add(event.name)
            elif event.event_type == 'up':
                self._fallback_pressed_keys.discard(event.name)
                return True

            # Обработка ESC
            if event.name == 'esc' and event.event_type == 'down':
                if self._capture_mode:
                    # ... обработка ESC ...
                    return False
                return True

            # Проверяем комбинации
            if event.event_type == 'down':
                current_pressed = set(self._fallback_pressed_keys)

                for action, hotkey in self._hotkey_actions.items():
                    hotkey_parts = [p.lower().strip() for p in hotkey.split('+') if p.strip()]
                    if not hotkey_parts:
                        continue

                    all_pressed = True
                    pressed_lower = [p.lower() for p in current_pressed]

                    for part in hotkey_parts:
                        found = False
                        for pressed in pressed_lower:
                            if part in pressed or pressed in part:
                                found = True
                                break
                        if not found:
                            all_pressed = False
                            break

                    if all_pressed:
                        pressed_count = len(current_pressed)
                        hotkey_count = len(hotkey_parts)
                        if pressed_count > hotkey_count:
                            continue

                        current_time = time.time() * 1000
                        combo_key = f"{action}_{hotkey}"
                        if current_time - self._key_last_time.get(combo_key, 0) >= self._debounce_ms:
                            self._key_last_time[combo_key] = current_time
                            self.logger.info(f"[FALLBACK] ✅ Сработал {action} ({hotkey})")
                            if action == 'toggle_overlay':
                                self.root.after(0, self.toggle_overlay)
                            elif action == 'screenshot':
                                self.root.after(0, self.process)
                            elif action == 'area':
                                self.root.after(0, self.capture_area)
                            elif action == 'clear_all':
                                self.root.after(0, self.clear_all_overlays)
                            elif action == 'edit_mode':
                                self.root.after(0, self.toggle_edit_mode)
                            self._fallback_pressed_keys.clear()
                            # Возвращаем False, чтобы заблокировать клавишу в fallback режиме
                            return False

            return True

        # Регистрируем хук БЕЗ suppress=True, чтобы не блокировать все клавиши
        keyboard.hook(on_key, suppress=False)
        self._hotkey_hook_active = True

    def _setup_tkinter_hotkeys(self):
        """Запасной вариант через Tkinter bind_all с использованием настроек."""
        self.logger.warning("Используется запасной метод горячих клавиш (Tkinter)")

        hotkeys = self.settings.get_all_hotkeys()

        def handle_hotkey(event):
            keysym = event.keysym.lower()

            if keysym == hotkeys.get('toggle_overlay', 'f1').lower():
                self.toggle_overlay()
                return "break"
            if keysym == hotkeys.get('screenshot', 'f2').lower():
                self.process()
                return "break"
            if keysym == hotkeys.get('area', 'f3').lower():
                self.capture_area()
                return "break"
            if keysym == hotkeys.get('clear_all', 'f4').lower():
                self.clear_all_overlays()
                return "break"
            if keysym == hotkeys.get('edit_mode', 'f5').lower():
                self.toggle_edit_mode()
                return "break"
            return None

        self.root.bind_all("<Key>", handle_hotkey)
        self.root.focus_force()
        self.logger.info("Tkinter горячие клавиши зарегистрированы")

    def _on_init_error(self, error_msg):
        """Обработчик ошибки инициализации - без всплывающих окон, только логирование."""
        self.initializing = False

        # Логируем ошибку
        self.logger.error(f"❌ Ошибка инициализации: {error_msg}")

        # Обновляем статус в интерфейсе
        self.update_status("● " + self.get_string('error') + ": " + error_msg[:50], '#f44336')

        # Блокируем кнопки
        self.btn_capture.config(state=DISABLED, bg='#333', fg='#888')
        self.btn_toggle.config(state=DISABLED, bg='#333', fg='#888')
        self.btn_clear_all.config(state=DISABLED, bg='#333', fg='#888')
        self.btn_edit_mode.config(state=DISABLED, bg='#333', fg='#888')

        if hasattr(self, 'settings_btn'):
            self.settings_btn.config(state=DISABLED, bg='#3c3c3c', fg='#666666')
            self.logger.info("Кнопка настроек заблокирована (ошибка инициализации)")

        self.set_settings_menu_enabled(False)

        # Автоматически планируем повторную попытку
        self.logger.info(f"Планируем повторную попытку инициализации через {self._init_retry_delay}мс...")
        self.root.after(self._init_retry_delay, self._init_translator_step)

    def _init_translator_step(self):
        """Инициализация переводчика в фоновом режиме с автоматическим повторением."""
        # Если инициализация уже завершена успешно - пропускаем
        if self._init_done:
            self.logger.info("[DEBUG] _init_translator_step: инициализация уже завершена, пропускаем")
            return

        if self.initializing:
            self.logger.info("[DEBUG] _init_translator_step: инициализация уже идет, пропускаем")
            return

        self._init_attempts += 1
        self.logger.info(f"Попытка инициализации #{self._init_attempts} из {self._max_init_attempts}")

        if self._init_attempts > self._max_init_attempts:
            self.logger.error(f"❌ Инициализация не удалась после {self._max_init_attempts} попыток")
            self.update_status("● Ошибка инициализации (превышено число попыток, перезапуск...)", '#f44336')
            self.btn_capture.config(state=DISABLED, bg='#333', fg='#888')
            # Сбрасываем счётчик и продолжаем попытки в фоне
            self._init_attempts = 0
            self._init_done = False
            self.logger.info("Сброс счётчика попыток, продолжаем попытки в фоновом режиме...")
            # Увеличиваем задержку перед следующей попыткой
            self.root.after(5000, self._init_translator_step)
            return

        self.initializing = True
        self.update_status("● " + self.get_string('starting_browser'), '#ff9800')
        self.root.update_idletasks()
        self._start_result_processor()
        show_browser = self.settings.get_show_browser()
        target_lang = self.settings.get_target_language()
        cmd_id = self.browser_worker.init_browser(
            show_browser,
            target_lang,
            callback=self._on_init_complete
        )
        self._pending_command_ids[cmd_id] = 'init'

    def _handle_browser_not_found(self, error_msg: str):
        """Обрабатывает ситуацию, когда браузер не найден - без всплывающих окон."""
        self.logger.error(f"Браузер не найден: {error_msg}")
        self.update_status("● Браузер не найден, поиск...", '#f44336')
        self.btn_capture.config(state=DISABLED, bg='#333', fg='#888')

        if hasattr(self, 'settings_btn'):
            self.settings_btn.config(state=DISABLED, bg='#3c3c3c', fg='#666666')
            self.logger.info("Кнопка настроек заблокирована (браузер не найден)")

        self.set_settings_menu_enabled(False)

        # Пробуем найти браузер автоматически через translator
        try:
            from src.translator import GoogleTranslateDebug
            translator = GoogleTranslateDebug(
                headless=not self.settings.get_show_browser(),
                target_lang=self.settings.get_target_language(),
                settings=self.settings
            )
            found_path = translator._find_any_browser()
            if found_path:
                self.logger.info(f"✅ Автоматически найден браузер: {found_path}")
                self.settings.set_browser_path(found_path)
                self.update_status("● Браузер найден, повторная инициализация...", '#ff9800')
                # Перезапускаем инициализацию
                self._init_done = False
                self.ready = False
                self.initializing = False
                self._init_attempts = 0
                self.root.after(1000, self._init_translator_step)
            else:
                self.logger.warning("❌ Браузер не найден автоматически")
                self.update_status("● Браузер не найден, установите Яндекс Браузер или Chrome", '#f44336')
                # Продолжаем попытки с увеличенной задержкой
                self.root.after(5000, self._init_translator_step)
        except Exception as e:
            self.logger.error(f"Ошибка при поиске браузера: {e}")
            self.root.after(5000, self._init_translator_step)

    def _on_init_complete(self, result, error):
        """Обработчик завершения инициализации."""
        self.logger.info(f"_on_init_complete вызван: result={result}, error={error}")
        if error:
            self.logger.error(f"Ошибка инициализации: {error}")
            self._on_init_error(error)
            self.logger.info(f"Планируем повторную попытку через {self._init_retry_delay}мс...")
            self.root.after(self._init_retry_delay, self._init_translator_step)
        else:
            self.logger.info("Инициализация завершена успешно, обновляем UI")
            self.ready = True
            self.initializing = False
            self._init_done = True
            self._init_attempts = 0

            if self.overlay_manager is None:
                self.logger.info("Создание OverlayManager")
                from src.overlay_manager import OverlayManager
                self.overlay_manager = OverlayManager(self)
                self.logger.info(f"OverlayManager создан: {self.overlay_manager}")
            else:
                self.logger.info(f"OverlayManager уже существует: {self.overlay_manager}")

            # Разблокируем все кнопки с правильными цветами
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            self.btn_clear_all.config(state=NORMAL, bg='#d32f2f', fg='white')
            self.btn_toggle.config(state=NORMAL, bg='#2196F3', fg='white')

            # Разблокируем кнопку настроек
            if hasattr(self, 'settings_btn'):
                self.settings_btn.config(state=NORMAL, bg='#3c3c3c', fg='#cccccc')
                self.logger.info("Кнопка настроек разблокирована")

            # Разблокируем меню "Настройки"
            self.set_settings_menu_enabled(True)

            # Разблокируем кнопку редактирования с правильным цветом
            status_text = self.get_string('edit_mode_on') if self._edit_mode_enabled else self.get_string(
                'edit_mode_off')
            hotkeys = self.settings.get_all_hotkeys()
            edit_key = hotkeys.get('edit_mode', 'f5').upper()
            self.btn_edit_mode.config(
                state=NORMAL,
                text=f"✏️ {self.get_string('edit_mode')}: {status_text} ({edit_key})",
                bg='#4CAF50' if self._edit_mode_enabled else '#ff9800',
                fg='white'
            )

            self.update_status("● " + self.get_string('ready'), '#4CAF50')
            self.logger.info("UI обновлен: статус 'Готово'")

            self._restarting = False
        self._pending_command_ids = {}

    def _update_overlay_alpha(self):
        """Обновляет прозрачность всех оверлеев в зависимости от режима редактирования."""
        if not self.overlay_manager:
            return
        alpha = 1.0 if self._edit_mode_enabled else 0.7
        self.logger.info(
            f"[DEBUG] Установка прозрачности оверлеев: {alpha} (режим редактирования: {self._edit_mode_enabled})")
        for overlay in self.overlay_manager.overlays:
            try:
                if overlay and overlay.root and overlay.root.winfo_exists():
                    overlay.root.attributes('-alpha', alpha)
                    overlay.logger.info(f"[DEBUG] Установлена прозрачность {alpha} для оверлея")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось установить прозрачность: {e}")

    def is_edit_mode_enabled(self) -> bool:
        """Возвращает состояние режима редактирования."""
        return self._edit_mode_enabled

    def create_gui(self):
        """Создает главное окно приложения с адаптивной версткой"""
        self.root = Tk()
        self.root.title(self.get_string('app_title'))
        self.root.withdraw()
        self.root.geometry("520x600")
        self.root.minsize(520, 600)
        self.root.maxsize(520, 600)
        self.root.resizable(False, False)
        self.root.configure(bg='#1e1e1e')
        self.create_menu()
        self.show_browser_var = BooleanVar(value=self.settings.get_show_browser())
        self.target_lang_var = StringVar(value=self.settings.get_target_language())
        self.show_indicator_var = BooleanVar(value=self.settings.get_show_translation_indicator())
        self.auto_hide_var = BooleanVar(value=self.settings.get_auto_hide_overlay())
        self.app_title = None
        self.browser_worker = BrowserWorker(self.settings)
        self.browser_worker.start()
        self._pending_command_ids = {}
        self._translation_in_progress = False
        self._edit_mode_enabled = self.settings.get_edit_mode_enabled()
        self._init_attempts = 0
        self._max_init_attempts = 3
        self._init_retry_delay = 2000

        main = Frame(self.root, bg='#1e1e1e')
        main.pack(expand=True, fill=BOTH, padx=25, pady=20)

        header_frame = Frame(main, bg='#1e1e1e', height=60)
        header_frame.pack(fill=X, pady=(0, 15))
        header_frame.pack_propagate(False)

        title_frame = Frame(header_frame, bg='#1e1e1e')
        title_frame.pack(side=LEFT, expand=True, fill=X)

        icon_label = Label(title_frame, text="📸", bg='#1e1e1e', fg='white', font=("Arial", 26))
        icon_label.pack(side=LEFT, padx=(0, 10))

        self.title_label = Label(title_frame, text=self.get_string('app_title'),
                                 bg='#1e1e1e', fg='#4CAF50', font=("Arial", 15, "bold"))
        self.title_label.pack(side=LEFT)

        header_right = Frame(header_frame, bg='#1e1e1e')
        header_right.pack(side=RIGHT, padx=(10, 0))

        current_lang = self.settings.get_language()
        lang_text = "EN" if current_lang == "ru" else "RU"
        self.lang_btn = Button(
            header_right,
            text=lang_text,
            command=self.toggle_language,
            font=("Arial", 12, "bold"),
            bg='#3c3c3c',
            fg='#4CAF50',
            relief=FLAT,
            width=4,
            padx=0,
            pady=6,
            cursor="hand2"
        )
        self.lang_btn.pack(side=RIGHT, padx=(0, 5))

        self.settings_btn = Button(
            header_right,
            text="⚙️",
            command=self.open_settings,
            font=("Arial", 14),
            bg='#3c3c3c',
            fg='#cccccc',
            relief=FLAT,
            width=4,
            padx=0,
            pady=6,
            cursor="hand2",
            state=DISABLED
        )
        self.settings_btn.pack(side=RIGHT, padx=(0, 5))

        def on_settings_enter(e):
            if self.settings_btn['state'] != DISABLED:
                self.settings_btn.config(bg='#4CAF50', fg='white')

        def on_settings_leave(e):
            if self.settings_btn['state'] != DISABLED:
                self.settings_btn.config(bg='#3c3c3c', fg='#cccccc')
            else:
                self.settings_btn.config(bg='#3c3c3c', fg='#666666')

        self.settings_btn.bind('<Enter>', on_settings_enter)
        self.settings_btn.bind('<Leave>', on_settings_leave)

        self.status = Label(main, text="● " + self.get_string('starting'),
                            fg='#ff9800', bg='#1e1e1e', font=("Arial", 11), height=1)
        self.status.pack(pady=(5, 10), fill=X)

        lang_select_frame = Frame(main, bg='#1e1e1e')
        lang_select_frame.pack(fill=X, pady=(5, 10))

        self.target_lang_label = Label(
            lang_select_frame,
            text=self.get_string('target_language'),
            bg='#1e1e1e',
            fg='#cccccc',
            font=("Arial", 10),
            anchor='w'
        )
        self.target_lang_label.pack(anchor=W, fill=X)

        lang_combo_frame = Frame(lang_select_frame, bg='#1e1e1e')
        lang_combo_frame.pack(fill=X, pady=(5, 0))

        lang_codes = sorted(LANGUAGES.keys())
        self._all_lang_items = [f"{LANGUAGES[code]} ({code})" for code in lang_codes]
        self.target_lang_combo = ttk.Combobox(
            lang_combo_frame,
            textvariable=self.target_lang_var,
            values=self._all_lang_items,
            font=("Arial", 10),
            state="normal",
            width=45
        )
        self.target_lang_combo.pack(fill=X)
        self.target_lang_combo.bind('<KeyRelease>', self._on_lang_search)
        self.target_lang_combo.bind('<Return>', self._on_lang_enter)
        self.target_lang_combo.bind('<<ComboboxSelected>>', self._on_target_lang_changed)

        current_lang_code = self.settings.get_target_language()
        current_display = f"{LANGUAGES.get(current_lang_code, 'Russian')} ({current_lang_code})"
        self.target_lang_combo.set(current_display)

        btn_frame = Frame(main, bg='#1e1e1e')
        btn_frame.pack(fill=X, pady=5)

        # Кнопка скриншота
        screenshot_key = self.settings.get_hotkey('screenshot').upper()
        self.btn_capture = Button(
            btn_frame,
            text=f"{self.get_string('btn_capture')} ({screenshot_key})",
            command=self.process,
            font=("Arial", 11),
            bg='#333',
            fg='#888',
            relief=FLAT,
            height=1,
            pady=12,
            state=DISABLED
        )
        self.btn_capture.pack(fill=X, pady=(0, 10), ipady=2)

        # Кнопка очистки
        clear_key = self.settings.get_hotkey('clear_all').upper()
        self.btn_clear_all = Button(
            btn_frame,
            text=f"🗑️ {self.get_string('clear_all')} ({clear_key})",
            command=self.clear_all_overlays,
            font=("Arial", 11),
            bg='#333',
            fg='#888',
            relief=FLAT,
            height=1,
            pady=12,
            state=DISABLED
        )
        self.btn_clear_all.pack(fill=X, pady=(0, 10), ipady=2)

        # Кнопка показа/скрытия
        toggle_key = self.settings.get_hotkey('toggle_overlay').upper()
        self.btn_toggle = Button(
            btn_frame,
            text=f"{self.get_string('btn_toggle')} ({toggle_key})",
            command=self.toggle_overlay,
            font=("Arial", 11),
            bg='#333',
            fg='#888',
            relief=FLAT,
            height=1,
            pady=12,
            state=DISABLED
        )
        self.btn_toggle.pack(fill=X, ipady=2)

        # Кнопка режима редактирования - СЕРАЯ ПРИ СОЗДАНИИ
        edit_key = self.settings.get_hotkey('edit_mode').upper()
        status_text = self.get_string('edit_mode_on') if self._edit_mode_enabled else self.get_string('edit_mode_off')
        self.btn_edit_mode = Button(
            btn_frame,
            text=f"✏️ {self.get_string('edit_mode')}: {status_text} ({edit_key})",
            command=self.toggle_edit_mode,
            font=("Arial", 11),
            bg='#333',  # <-- СЕРЫЙ ДЛЯ ЗАБЛОКИРОВАННОГО СОСТОЯНИЯ
            fg='#888',
            relief=FLAT,
            height=1,
            pady=12,
            state=DISABLED
        )
        self.btn_edit_mode.pack(fill=X, pady=(10, 10), ipady=2)

        self.hotkeys_label = Label(
            main,
            text=self.get_string('hotkeys_info'),
            bg='#1e1e1e',
            fg='#888',
            font=("Arial", 10),
            wraplength=470,
            justify='left'
        )
        self.hotkeys_label.pack(pady=(15, 5), fill=X)

        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

        self.update_ui_language()
        self.app_title = self.get_string('app_title')
        self.logger.info(f"Заголовок приложения: {self.app_title}")
        self._setup_app_icon()
        self.setup_hotkeys()
        self.update_hotkey_buttons()
        self.root.after(100, self._init_translator_step)

    def _cancel_translation(self):
        """Отменяет текущий перевод"""
        self.logger.info("[DEBUG] _cancel_translation() - отмена перевода")

        if not self._translation_in_progress:
            self.logger.info("[DEBUG] _cancel_translation: перевод не идет, пропускаем")
            return

        self.logger.info("[DEBUG] _cancel_translation: отменяем перевод")

        if self.browser_worker:
            self.browser_worker.cancel_translation()
            self.logger.info("[DEBUG] _cancel_translation: отправлена команда отмены")

        self._translation_in_progress = False
        self._hide_translation_overlay()
        self.translating = False
        self.update_status("● Перевод отменен", '#ff9800')
        self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')

        self.logger.info("[DEBUG] _cancel_translation: перевод отменен")

    def clear_all_overlays(self):
        """Удаляет все оверлеи (F4)."""
        self.logger.info("[DEBUG] clear_all_overlays вызван")

        if not self.overlay_manager:
            self.logger.warning("clear_all_overlays: менеджер оверлеев не инициализирован")
            return

        if not self.overlay_manager.overlays:
            self.logger.info("clear_all_overlays: нет активных оверлеев")
            return

        count = len(self.overlay_manager.overlays)
        self.logger.info(f"clear_all_overlays: удаляем {count} оверлеев")

        self.overlay_manager.close_all()
        self.logger.info(f"Удалено {count} оверлеев (F4)")

    def _capture_window_for_area(self):
        """Захватывает скриншот всего экрана и показывает для выделения области"""
        self.logger.info("[DEBUG] _capture_window_for_area() - начало")

        try:
            import win32gui
            from PIL import ImageGrab

            current_hwnd = win32gui.GetForegroundWindow()
            if current_hwnd:
                self.screenshot._last_hwnd = current_hwnd
                self.screenshot._is_fullscreen = self.screenshot.is_window_fullscreen(current_hwnd)
                self.logger.info(
                    f"[DEBUG] Сохранен HWND активного окна: {current_hwnd}, полноэкранный: {self.screenshot._is_fullscreen}")
                self._area_target_hwnd = current_hwnd
                self._area_is_fullscreen = self.screenshot._is_fullscreen
            else:
                self._area_target_hwnd = None
                self._area_is_fullscreen = False

            if self._area_is_fullscreen and self.settings.get_auto_windowed_fullscreen():
                self.logger.info("[DEBUG] Обнаружен НАСТОЯЩИЙ полноэкранный режим, преобразуем в windowed fullscreen")
                try:
                    from src.window_utils import send_alt_enter_to_window
                    result = send_alt_enter_to_window(current_hwnd)
                    if result:
                        self.logger.info("[DEBUG] Преобразование окна в windowed fullscreen УСПЕШНО")
                        self.screenshot._is_fullscreen = False
                        self._area_is_fullscreen = False
                        time.sleep(0.3)
                    else:
                        self.logger.warning("[DEBUG] Преобразование окна не удалось")
                except Exception as e:
                    self.logger.error(f"[DEBUG] Ошибка при преобразовании в оконный полноэкранный режим: {e}")
            else:
                if self._area_is_fullscreen:
                    self.logger.info("[DEBUG] Автоматический оконный полноэкранный режим отключен")
                else:
                    self.logger.info("[DEBUG] Окно уже в оконном режиме (windowed fullscreen или обычное)")

            self.logger.info("[DEBUG] Захват всего экрана для выбора области...")
            img = ImageGrab.grab()
            self.logger.info(f"[DEBUG] Скриншот всего экрана: {img.size}")

            if not img:
                self.logger.error("[DEBUG] Не удалось захватить скриншот экрана")
                self.update_status(self.get_string('capture_error'), '#f44336')
                self.translating = False
                self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
                self.root.deiconify()
                return

            screenshot_path = self.temp_dir / f"area_screenshot_{int(time.time())}.png"
            img.save(screenshot_path)
            self.logger.info(f"[DEBUG] Скриншот сохранен: {screenshot_path}")

            self._show_area_selection_window(screenshot_path)

        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка захвата экрана: {e}")
            self.update_status(self.get_string('capture_error'), '#f44336')
            self.translating = False
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            self.root.deiconify()

    def _show_area_selection_window(self, screenshot_path):
        """Показывает полноэкранное окно с изображением для выделения области"""
        self.logger.info("[DEBUG] _show_area_selection_window()")

        from PIL import Image, ImageTk
        import tkinter as tk
        from tkinter import messagebox

        img = Image.open(screenshot_path)
        img_width, img_height = img.size

        selection_window = tk.Toplevel()
        selection_window.attributes('-fullscreen', True)
        selection_window.attributes('-topmost', True)
        selection_window.configure(bg='black')
        selection_window.focus_force()

        canvas = tk.Canvas(selection_window, cursor="cross", bg='black', highlightthickness=0)
        canvas.pack(fill=tk.BOTH, expand=True)

        screen_width = selection_window.winfo_screenwidth()
        screen_height = selection_window.winfo_screenheight()

        scale = min(screen_width / img_width, screen_height / img_height)
        display_w = int(img_width * scale)
        display_h = int(img_height * scale)

        resized = img.resize((display_w, display_h), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized)

        img_x = (screen_width - display_w) // 2
        img_y = (screen_height - display_h) // 2

        canvas.create_image(img_x, img_y, anchor=tk.NW, image=photo)
        canvas.image = photo

        selection_data = {
            'img': img,
            'screenshot_path': screenshot_path,
            'scale_x': img_width / display_w,
            'scale_y': img_height / display_h,
            'img_x': img_x,
            'img_y': img_y,
            'start_x': None,
            'start_y': None,
            'rect': None
        }

        canvas.create_text(
            screen_width // 2,
            50,
            text="Выделите область для перевода (ESC для отмены)",
            fill="white",
            font=("Arial", 16, "bold")
        )

        def on_mouse_down(event):
            selection_data['start_x'] = event.x
            selection_data['start_y'] = event.y
            if selection_data['rect']:
                canvas.delete(selection_data['rect'])

        def on_mouse_drag(event):
            if selection_data['start_x'] is not None:
                if selection_data['rect']:
                    canvas.delete(selection_data['rect'])
                selection_data['rect'] = canvas.create_rectangle(
                    selection_data['start_x'],
                    selection_data['start_y'],
                    event.x,
                    event.y,
                    outline='red',
                    width=2,
                    fill='blue',
                    stipple='gray50'
                )

        def on_mouse_up(event):
            if selection_data['start_x'] is not None:
                x1, y1 = min(selection_data['start_x'], event.x), min(selection_data['start_y'], event.y)
                x2, y2 = max(selection_data['start_x'], event.x), max(selection_data['start_y'], event.y)

                min_size = 10
                if x2 - x1 > min_size and y2 - y1 > min_size:
                    orig_x1 = int((x1 - selection_data['img_x']) * selection_data['scale_x'])
                    orig_y1 = int((y1 - selection_data['img_y']) * selection_data['scale_y'])
                    orig_x2 = int((x2 - selection_data['img_x']) * selection_data['scale_x'])
                    orig_y2 = int((y2 - selection_data['img_y']) * selection_data['scale_y'])

                    orig_x1 = max(0, min(orig_x1, img_width))
                    orig_y1 = max(0, min(orig_y1, img_height))
                    orig_x2 = max(0, min(orig_x2, img_width))
                    orig_y2 = max(0, min(orig_y2, img_height))

                    self.logger.info(f"[DEBUG] Выделена область: ({orig_x1},{orig_y1})-({orig_x2},{orig_y2})")

                    selection_window.destroy()
                    self._capture_mode = False
                    self._selection_window = None

                    self._process_area_selection(orig_x1, orig_y1, orig_x2, orig_y2, screenshot_path)
                else:
                    messagebox.showwarning(
                        "Ошибка",
                        f"Выделите область размером больше {min_size}x{min_size} пикселей"
                    )

        def on_escape(event):
            self.logger.info("[DEBUG] ESC - отмена выделения")
            self._capture_mode = False
            self._selection_window = None
            self.translating = False
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            self.root.deiconify()
            self.update_status("● Отменено", '#ff9800')
            try:
                selection_window.destroy()
            except:
                pass

        self._selection_window_on_escape = on_escape

        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)
        selection_window.bind("<Escape>", on_escape)
        canvas.bind("<Escape>", on_escape)

        def on_escape_bind_all(event):
            if self._capture_mode and self._selection_window is not None:
                self.logger.info("[DEBUG] ESC через bind_all - отмена выделения")
                on_escape(event)
                return "break"
            return None

        self._selection_window_bind_id = selection_window.bind_all("<Escape>", on_escape_bind_all)

        self._capture_mode = True
        self._selection_window = selection_window

        def on_close():
            self._capture_mode = False
            self._selection_window = None
            self._selection_window_on_escape = None
            if hasattr(self, '_selection_window_bind_id'):
                try:
                    selection_window.unbind_all("<Escape>", self._selection_window_bind_id)
                except:
                    pass
                self._selection_window_bind_id = None
            self.translating = False
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            self.root.deiconify()
            try:
                selection_window.destroy()
            except:
                pass

        selection_window.protocol("WM_DELETE_WINDOW", on_close)

    def toggle_overlay(self):
        """Переключает видимость всех оверлеев (F1)."""
        self.logger.info("[DEBUG] toggle_overlay вызван")
        if not self.overlay_manager:
            self.logger.warning("toggle_overlay: менеджер оверлеев не инициализирован")
            return

        if not self.overlay_manager.overlays:
            self.logger.info("toggle_overlay: нет активных оверлеев")
            return

        auto_hide_enabled = self.settings.get_auto_hide_overlay()
        self.logger.info(f"[DEBUG] toggle_overlay: auto_hide_enabled={auto_hide_enabled}")

        if auto_hide_enabled:
            try:
                import win32gui
                active_hwnd = win32gui.GetForegroundWindow()
                self.logger.info(f"[DEBUG] toggle_overlay: active_hwnd={active_hwnd}")

                is_target_active = False
                target_hwnd_found = None
                for overlay in self.overlay_manager.overlays:
                    target_hwnd = overlay.get_target_hwnd()
                    if target_hwnd is not None and active_hwnd == target_hwnd:
                        is_target_active = True
                        target_hwnd_found = target_hwnd
                        break

                if is_target_active:
                    self.logger.info(
                        f"[DEBUG] toggle_overlay: активное окно {active_hwnd} является целевым для оверлея")
                    new_state = self.overlay_manager.toggle_all_overlays()
                    self.logger.info(f"F1: все оверлеи {'показаны' if new_state else 'скрыты'}")
                    return
                else:
                    self.logger.info("[DEBUG] toggle_overlay: активное окно не является целевым для любого оверлея")
                    return

            except Exception as e:
                self.logger.warning(f"toggle_overlay: ошибка проверки активного окна: {e}")
                new_state = self.overlay_manager.toggle_all_overlays()
                return

        else:
            new_state = self.overlay_manager.toggle_all_overlays()
            self.logger.info(f"F1: все оверлеи {'показаны' if new_state else 'скрыты'}")

    def on_close(self):
        """Обработчик закрытия приложения"""
        self._hide_translation_overlay()
        self._processor_running = False
        try:
            keyboard.unhook_all()
        except:
            pass
        if hasattr(self, 'settings'):
            self.settings.save()
        if hasattr(self, 'browser_worker'):
            self.browser_worker.stop()
        if self.overlay_manager:
            self.overlay_manager.close_all()
        self.root.destroy()

    def _start_key_monitor(self):
        """Запускает периодическую проверку обработчика (без блокировки клавиш)"""

        def check_handler():
            try:
                pass
            except:
                pass
            if hasattr(self, 'root') and self.root:
                self.root.after(5000, check_handler)

        if hasattr(self, 'root') and self.root:
            self.root.after(1000, check_handler)

    def _start_result_processor(self):
        """Запускает постоянную проверку результатов из рабочего потока"""
        if hasattr(self, '_processor_running') and self._processor_running:
            return
        self._processor_running = True
        self._process_results_loop()

    def _process_results_loop(self):
        """Постоянный цикл проверки результатов"""
        try:
            processed = self.browser_worker.process_results()
            if processed:
                self.logger.info(f"Обработано {processed} результатов")
        except Exception as e:
            self.logger.error(f"Ошибка обработки результатов: {e}")
            import traceback
            traceback.print_exc()
        if hasattr(self, '_processor_running') and self._processor_running:
            self.root.after(100, self._process_results_loop)

    def _check_results(self):
        """Периодическая проверка результатов из рабочего потока"""
        try:
            self.browser_worker.process_results()
        except Exception as e:
            self.logger.error(f"Ошибка обработки результатов: {e}")
        if self._pending_command_ids:
            self.root.after(100, self._check_results)

    def _show_browser_path_dialog(self):
        """Показывает диалог для ручного указания пути к браузеру"""
        import tkinter.filedialog as filedialog
        current_path = self.settings.get_browser_path()
        dialog = Toplevel(self.root)
        dialog.title("Укажите путь к браузеру")
        dialog.geometry("600x200")
        dialog.resizable(False, False)
        dialog.configure(bg='#1e1e1e')
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.update_idletasks()
        x = self.root.winfo_x() + (self.root.winfo_width() - 600) // 2
        y = self.root.winfo_y() + (self.root.winfo_height() - 200) // 2
        dialog.geometry(f"+{x}+{y}")
        Label(
            dialog,
            text="Укажите полный путь к исполняемому файлу браузера:",
            bg='#1e1e1e',
            fg='white',
            font=("Arial", 10)
        ).pack(pady=(20, 5))
        Label(
            dialog,
            text="Например: C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            bg='#1e1e1e',
            fg='#888',
            font=("Arial", 9)
        ).pack(pady=(0, 10))
        path_frame = Frame(dialog, bg='#1e1e1e')
        path_frame.pack(fill=X, padx=20, pady=5)
        path_var = StringVar(value=current_path)
        path_entry = Entry(
            path_frame,
            textvariable=path_var,
            font=("Arial", 10),
            bg='#2d2d2d',
            fg='white',
            insertbackground='white',
            relief=FLAT
        )
        path_entry.pack(side=LEFT, fill=X, expand=True, padx=(0, 5))

        def browse():
            file_path = filedialog.askopenfilename(
                title="Выберите браузер",
                filetypes=[("Executable files", "*.exe"), ("All files", "*.*")]
            )
            if file_path:
                path_var.set(file_path)

        browse_btn = Button(
            path_frame,
            text="Обзор...",
            command=browse,
            bg='#3c3c3c',
            fg='white',
            relief=FLAT,
            padx=10,
            pady=5
        )
        browse_btn.pack(side=RIGHT)
        btn_frame = Frame(dialog, bg='#1e1e1e')
        btn_frame.pack(pady=20)

        def save_path():
            new_path = path_var.get().strip()
            if new_path and os.path.exists(new_path):
                self.settings.set_browser_path(new_path)
                dialog.destroy()
                self.root.after(100, self._retry_init)
            elif new_path:
                messagebox.showerror("Ошибка", "Указанный файл не существует!")
            else:
                messagebox.showerror("Ошибка", "Пожалуйста, укажите путь к браузеру!")

        Button(
            btn_frame,
            text="Сохранить и продолжить",
            command=save_path,
            bg='#4CAF50',
            fg='white',
            relief=FLAT,
            padx=20,
            pady=8
        ).pack(side=LEFT, padx=5)
        Button(
            btn_frame,
            text="Отмена",
            command=dialog.destroy,
            bg='#3c3c3c',
            fg='white',
            relief=FLAT,
            padx=20,
            pady=8
        ).pack(side=LEFT, padx=5)

    def _retry_init(self):
        """Повторяет попытку инициализации"""
        self._init_done = False
        self.ready = False
        self.initializing = False
        self._init_translator_step()

    def toggle_browser_visibility(self):
        """Переключает видимость браузера"""
        show = self.show_browser_var.get()
        self.settings.set_show_browser(show)
        self.logger.info(f"Видимость браузера изменена: {'показывать' if show else 'скрывать'}")
        if self._init_done:
            self._restart_translator()

    def _restart_translator(self):
        """Перезапускает переводчик с новыми настройками в фоновом режиме"""
        if self._restarting:
            self.logger.info("Перезапуск уже выполняется, пропускаем")
            return

        if self.initializing:
            self.logger.info("Инициализация уже идет, пропускаем перезапуск")
            return

        self._restarting = True
        self.logger.info("Перезапуск переводчика с новыми настройками...")

        # Блокируем все кнопки как при первом запуске
        self.btn_capture.config(state=DISABLED, bg='#333', fg='#888')
        self.btn_toggle.config(state=DISABLED, bg='#333', fg='#888')
        self.btn_clear_all.config(state=DISABLED, bg='#333', fg='#888')
        self.btn_edit_mode.config(state=DISABLED, bg='#333', fg='#888')

        # Блокируем кнопку настроек (⚙️)
        if hasattr(self, 'settings_btn'):
            self.settings_btn.config(state=DISABLED, bg='#3c3c3c', fg='#666666')
            self.logger.info("Кнопка настроек заблокирована на время перезапуска")

        # === БЛОКИРУЕМ МЕНЮ "НАСТРОЙКИ" ===
        self.set_settings_menu_enabled(False)

        # Показываем статус "Запуск браузера..."
        self.update_status("● " + self.get_string('starting_browser'), '#ff9800')

        # Сбрасываем состояние для перезапуска
        self._init_done = False
        self.ready = False
        self.initializing = False

        self._init_attempts = 0
        self._init_translator_step()

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
        """Переключает язык интерфейса и обновляет URL браузера"""
        current_lang = self.settings.get_language()
        new_lang = "en" if current_lang == "ru" else "ru"
        self.settings.set_language(new_lang)
        self.update_ui_language()
        if hasattr(self, 'lang_btn'):
            self.lang_btn.config(text="EN" if new_lang == "ru" else "RU")
        status_text = self.get_string('ready') if self.ready else self.get_string('starting_browser')
        self.update_status("● " + status_text, '#4CAF50' if self.ready else '#ff9800')
        self.logger.info(f"Язык переключен на: {new_lang}")
        if self._init_done and self.ready and self.browser_worker:
            self.logger.info(f"Обновление URL браузера на язык: {new_lang}")
            self.browser_worker.update_interface_language(new_lang)

    def update_ui_language(self):
        """Обновляет язык интерфейса"""
        self.root.title(self.get_string('app_title'))
        if hasattr(self, 'title_label'):
            self.title_label.config(text=self.get_string('app_title'))
        if hasattr(self, 'btn_capture'):
            # Не обновляем текст напрямую, а вызываем update_hotkey_buttons
            pass
        if hasattr(self, 'btn_toggle'):
            pass
        if hasattr(self, 'hotkeys_label'):
            self.hotkeys_label.config(text=self.get_string('hotkeys_info'))
        if hasattr(self, 'show_browser_check'):
            self.show_browser_check.config(text=self.get_string('show_browser'))
        if hasattr(self, 'target_lang_label'):
            self.target_lang_label.config(text=self.get_string('target_language'))
        self.update_menu_language()
        self.update_hotkey_buttons()  # <-- ДОБАВЛЯЕМ

    def open_app_folder(self):
        """Открывает папку приложения в проводнике"""
        try:
            app_folder = Path.home() / "Documents" / "GoogleScreenTranslate"
            if app_folder.exists():
                os.startfile(str(app_folder))
                self.logger.info(f"Открыта папка приложения: {app_folder}")
            else:
                app_folder.mkdir(parents=True, exist_ok=True)
                os.startfile(str(app_folder))
                self.logger.info(f"Создана и открыта папка приложения: {app_folder}")
        except Exception as e:
            self.logger.error(f"Ошибка открытия папки: {e}")
            messagebox.showerror("Ошибка", f"Не удалось открыть папку:\n{e}")

    def open_settings(self):
        """Открывает окно настроек"""
        from src.settings_window import SettingsWindow
        SettingsWindow(self, self.settings, self.on_settings_changed)

    def on_settings_changed(self):
        """Обработчик изменения настроек"""
        self.update_ui_language()
        self.update_hotkey_buttons()  # <-- ДОБАВЛЯЕМ
        status_text = self.get_string('ready') if self.ready else self.get_string('starting_browser')
        self.update_status("● " + status_text, '#4CAF50' if self.ready else '#ff9800')
        self.logger.info("Настройки применены")

    def reset_settings(self):
        """Сбрасывает настройки к значениям по умолчанию"""
        import tkinter.messagebox as messagebox
        if messagebox.askyesno(self.get_string('settings_title'), self.get_string('settings_reset_confirm')):
            from src.settings import Settings
            for key, value in Settings.DEFAULT_SETTINGS.items():
                self.settings.set(key, value)
            self.settings.save()
            self.update_ui_language()
            self.target_lang_var.set(self.settings.get_target_language())
            current_display = f"{LANGUAGES.get(self.settings.get_target_language(), 'Russian')} ({self.settings.get_target_language()})"
            self.target_lang_combo.set(current_display)
            self.show_indicator_var.set(self.settings.get_show_translation_indicator())
            self.auto_hide_var.set(self.settings.get_auto_hide_overlay())
            messagebox.showinfo(self.get_string('settings_title'), self.get_string('settings_reset_done'))

    def show_shortcuts(self):
        """Показывает окно с горячими клавишами"""
        import tkinter.messagebox as messagebox
        messagebox.showinfo(
            self.get_string('shortcuts_title'),
            self.get_string('shortcuts_text')
        )

    def show_about(self):
        """Показывает окно 'О программе'"""
        import tkinter.messagebox as messagebox
        messagebox.showinfo(
            self.get_string('about_title'),
            self.get_string('about_text')
        )

    def _on_lang_search(self, event):
        """Фильтрует список языков при вводе текста"""
        typed_text = self.target_lang_var.get().lower()
        filtered_items = []
        if typed_text == "":
            filtered_items = self._all_lang_items
        else:
            for item in self._all_lang_items:
                if typed_text in item.lower():
                    filtered_items.append(item)
        self.target_lang_combo['values'] = filtered_items

    def _on_lang_enter(self, event):
        """Обработчик нажатия Enter - выбирает язык"""
        current_text = self.target_lang_var.get().strip()
        current_values = self.target_lang_combo['values']
        if not current_values or len(current_values) == 0:
            return "break"
        if current_text in current_values:
            self.logger.info(f"Пользователь выбрал язык из списка: {current_text}")
            self._apply_language(current_text)
            self.target_lang_combo['values'] = self._all_lang_items
            return "break"
        typed_text = current_text.lower()
        selected = None
        for item in current_values:
            if "(" in item and ")" in item:
                code = item.split("(")[-1].replace(")", "").strip()
                if code.lower() == typed_text:
                    selected = item
                    self.logger.info(f"Найдено совпадение по коду: '{typed_text}' -> '{item}'")
                    break
        if not selected:
            for item in current_values:
                name_part = item.split("(")[0].strip().lower()
                if typed_text == name_part or typed_text in name_part:
                    selected = item
                    self.logger.info(f"Найдено совпадение по названию: '{typed_text}' -> '{item}'")
                    break
        if selected:
            self.target_lang_combo.set(selected)
            self._apply_language(selected)
            self.target_lang_combo['values'] = self._all_lang_items
        else:
            selected = current_values[0]
            self.target_lang_combo.set(selected)
            self._apply_language(selected)
            self.logger.info(f"Не найдено совпадений для '{typed_text}', выбран первый: {selected}")
        return "break"

    def _apply_language(self, selected):
        """Применяет выбранный язык"""
        if "(" in selected and ")" in selected:
            lang_code = selected.split("(")[-1].replace(")", "").strip()
        else:
            lang_code = "ru"
        self.logger.info(f"Выбран целевой язык: {lang_code}")
        self.settings.set_target_language(lang_code)
        if self.ready:
            self.browser_worker.update_language(lang_code)

    def _on_target_lang_changed(self, event):
        """Обработчик изменения целевого языка перевода"""
        selected = self.target_lang_combo.get()
        self._apply_language(selected)

    def _on_resize(self, event):
        """Обработчик изменения размера окна"""
        width = self.root.winfo_width()
        if width < 460:
            self.title_label.config(font=("Arial", 13, "bold"))
            self.lang_btn.config(font=("Arial", 10, "bold"), padx=8, pady=4)
            self.settings_btn.config(font=("Arial", 12), padx=8, pady=4)
            self.btn_capture.config(font=("Arial", 10), padx=15, pady=10)
            self.btn_toggle.config(font=("Arial", 10), padx=15, pady=10)
            self.status.config(font=("Arial", 10))
            self.target_lang_label.config(font=("Arial", 9))
            self.target_lang_combo.config(font=("Arial", 9))
            if hasattr(self, 'hotkeys_label'):
                self.hotkeys_label.config(font=("Arial", 9), wraplength=width - 60)
        else:
            self.title_label.config(font=("Arial", 15, "bold"))
            self.lang_btn.config(font=("Arial", 12, "bold"), padx=12, pady=6)
            self.settings_btn.config(font=("Arial", 14), padx=12, pady=6)
            self.btn_capture.config(font=("Arial", 11), padx=20, pady=12)
            self.btn_toggle.config(font=("Arial", 11), padx=20, pady=12)
            self.status.config(font=("Arial", 11))
            self.target_lang_label.config(font=("Arial", 10))
            self.target_lang_combo.config(font=("Arial", 10))
            if hasattr(self, 'hotkeys_label'):
                self.hotkeys_label.config(font=("Arial", 10), wraplength=min(width - 50, 480))

    def toggle_indicator_visibility(self):
        """Переключает видимость индикатора перевода"""
        show = self.show_indicator_var.get()
        self.settings.set_show_translation_indicator(show)
        self.logger.info(f"Видимость индикатора перевода изменена: {'показывать' if show else 'скрывать'}")

    def update_status(self, text, color='white'):
        """Обновляет статус в интерфейсе"""
        self.root.after(0, lambda: self.status.config(text=text, fg=color))

    def _on_translate_error(self, error_msg):
        """Обработчик ошибки перевода"""
        self.logger.error(f"Ошибка перевода: {error_msg}")
        self._translation_in_progress = False
        self.update_status(self.get_string('error'), '#f44336')
        self.translating = False
        self._hide_translation_overlay()
        self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')

    def _show_translation_overlay(self):
        """Показывает оверлей индикатора перевода"""
        if not self.settings.get_show_translation_indicator():
            return
        try:
            if self.translation_overlay is None:
                from src.translation_overlay import TranslationOverlay
                self.translation_overlay = TranslationOverlay(parent=self.root)
            self.translation_overlay.show(self.get_string('translating'))

            if self.overlay_manager:
                self.overlay_manager._enable_esc_hook()
                self.logger.info("[DEBUG] _show_translation_overlay: глобальный хук ESC включен")

        except Exception as e:
            self.logger.warning(f"Не удалось показать оверлей: {e}")

    def _hide_translation_overlay(self):
        """Скрывает оверлей индикатора перевода"""
        try:
            if self.translation_overlay:
                self.translation_overlay.hide()
                self.translation_overlay = None

            if self.overlay_manager and not self.overlay_manager.overlays:
                self.overlay_manager._disable_esc_hook()
                self.logger.info("[DEBUG] _hide_translation_overlay: глобальный хук ESC отключен")

        except:
            pass

    def run(self):
        """Запускает главный цикл приложения"""
        print(f"{self.get_string('hotkeys_info')}")
        self.root.mainloop()