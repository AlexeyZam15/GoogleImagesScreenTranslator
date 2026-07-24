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
        self.temp_dir = Path(tempfile.gettempdir()) / "screenshot_translator"
        self.temp_dir.mkdir(exist_ok=True)
        self.overlay = None
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
        self.create_gui()
        self.update_ui_language()
        self.app_title = self.get_string('app_title')
        self.logger.info(f"Заголовок приложения: {self.app_title}")
        self._setup_app_icon()
        self.setup_hotkeys()
        self.root.after(100, self._init_translator_step)

    def setup_hotkeys(self):
        """Настройка глобальных горячих клавиш"""
        try:
            keyboard.unhook_all()

            def on_key(event):
                if event.name == 'f1' and event.event_type == 'down':
                    self.logger.info("[DEBUG] F1 нажата!")
                    auto_hide_enabled = self.settings.get_auto_hide_overlay()
                    self.logger.info(f"[DEBUG] auto_hide_enabled = {auto_hide_enabled}")
                    if auto_hide_enabled:
                        self.logger.info("[DEBUG] Автоскрытие ВКЛЮЧЕНО, проверяем активное окно")
                        target_hwnd = self.screenshot.get_last_hwnd()
                        try:
                            import win32gui
                            active_hwnd = win32gui.GetForegroundWindow()
                            self.logger.info(f"[DEBUG] active_hwnd={active_hwnd}, target_hwnd={target_hwnd}")
                            class_name = ""
                            window_text = ""
                            try:
                                class_name = win32gui.GetClassName(active_hwnd)
                                window_text = win32gui.GetWindowText(active_hwnd)
                                self.logger.info(f"[DEBUG] active window: class='{class_name}', title='{window_text}'")
                            except:
                                pass
                            is_overlay_active = (class_name == "TkTopLevel" and window_text == "Перевод")
                            overlay_hwnd = None
                            overlay_exists = False
                            if self.overlay and hasattr(self.overlay, 'root') and self.overlay.root.winfo_exists():
                                overlay_exists = True
                                try:
                                    overlay_hwnd = int(self.overlay.root.winfo_id())
                                    self.logger.info(f"[DEBUG] overlay_hwnd={overlay_hwnd}")
                                except Exception as e:
                                    self.logger.info(f"[DEBUG] Ошибка получения HWND оверлея: {e}")
                            if is_overlay_active:
                                self.logger.info("[DEBUG] F1 перехвачена (активно окно оверлея TkTopLevel)")
                                if overlay_exists:
                                    current_time = time.time() * 1000
                                    if current_time - self._key_last_time.get('f1', 0) >= self._debounce_ms:
                                        self._key_last_time['f1'] = current_time
                                        self.root.after(0, self.toggle_overlay)
                                        self.logger.info("[DEBUG] Вызван toggle_overlay")
                                return False
                            if overlay_hwnd is not None and active_hwnd == overlay_hwnd:
                                self.logger.info("[DEBUG] F1 перехвачена (окно оверлея по HWND)")
                                if overlay_exists:
                                    current_time = time.time() * 1000
                                    if current_time - self._key_last_time.get('f1', 0) >= self._debounce_ms:
                                        self._key_last_time['f1'] = current_time
                                        self.root.after(0, self.toggle_overlay)
                                        self.logger.info("[DEBUG] Вызван toggle_overlay")
                                return False
                            if self.overlay and hasattr(self.overlay, '_is_dragging') and self.overlay._is_dragging:
                                self.logger.info("[DEBUG] F1 перехвачена (идет перетаскивание оверлея)")
                                return False
                            if target_hwnd is not None and active_hwnd == target_hwnd:
                                current_time = time.time() * 1000
                                if current_time - self._key_last_time.get('f1', 0) >= self._debounce_ms:
                                    self._key_last_time['f1'] = current_time
                                    self.root.after(0, self.toggle_overlay)
                                    self.logger.info("[DEBUG] F1 перехвачена (целевое окно активно)")
                                return False
                            else:
                                self.logger.info("[DEBUG] F1 пропущена в систему (не оверлей и не целевое окно)")
                                return True
                        except Exception as e:
                            self.logger.warning(f"Ошибка проверки активного окна в хуке: {e}")
                            return True
                    else:
                        self.logger.info("[DEBUG] F1 перехвачена (автоскрытие отключено)")
                        current_time = time.time() * 1000
                        if current_time - self._key_last_time.get('f1', 0) >= self._debounce_ms:
                            self._key_last_time['f1'] = current_time
                            self.root.after(0, self.toggle_overlay)
                        return False
                elif event.name == 'f2' and event.event_type == 'down':
                    self.logger.info("[DEBUG] F2 нажата!")
                    current_time = time.time() * 1000
                    if current_time - self._key_last_time.get('f2', 0) >= self._debounce_ms:
                        self._key_last_time['f2'] = current_time
                        self.root.after(0, self.process)
                        self.logger.info("[DEBUG] F2 перехвачена")
                    return False
                return True

            keyboard.hook(on_key, suppress=True)
            self.logger.info("Горячие клавиши зарегистрированы (F1 - зависит от автоскрытия, F2 - всегда)")
        except Exception as e:
            self.logger.error(f"Ошибка регистрации горячих клавиш: {e}")
            self._setup_tkinter_hotkeys()

    def toggle_overlay(self):
        """Переключает видимость оверлея переведенного скриншота"""
        if not self.overlay:
            self.logger.warning("toggle_overlay: оверлей не существует")
            return
        self.logger.info("[DEBUG] toggle_overlay вызван")
        auto_hide_enabled = self.settings.get_auto_hide_overlay()
        self.logger.info(f"[DEBUG] toggle_overlay: auto_hide_enabled={auto_hide_enabled}")
        target_hwnd = self.screenshot.get_last_hwnd()
        if target_hwnd is None:
            self.logger.debug("toggle_overlay: нет сохраненного HWND целевого окна")
            self.update_status("● Нет активного перевода", '#ff9800')
            return
        if not auto_hide_enabled:
            self.logger.info("[DEBUG] toggle_overlay: автоскрытие отключено, переключаем без проверок")
            self.overlay.toggle()
            status = self.get_string('shown') if self.overlay.is_visible() else self.get_string('hidden')
            self.update_status(f"● {self.get_string('overlay')} {status}", '#2196F3')
            return
        try:
            import win32gui
            active_hwnd = win32gui.GetForegroundWindow()
            self.logger.info(f"[DEBUG] toggle_overlay: active_hwnd={active_hwnd}, target_hwnd={target_hwnd}")
            overlay_hwnd = None
            if self.overlay and hasattr(self.overlay, 'root') and self.overlay.root.winfo_exists():
                try:
                    overlay_hwnd = int(self.overlay.root.winfo_id())
                    self.logger.info(f"[DEBUG] toggle_overlay: overlay_hwnd={overlay_hwnd}")
                except Exception as e:
                    self.logger.info(f"[DEBUG] toggle_overlay: ошибка получения HWND оверлея: {e}")
            is_overlay_active = False
            try:
                class_name = win32gui.GetClassName(active_hwnd)
                window_text = win32gui.GetWindowText(active_hwnd)
                self.logger.info(f"[DEBUG] toggle_overlay: active window: class='{class_name}', title='{window_text}'")
                if class_name == "TkTopLevel" and window_text == "Перевод":
                    is_overlay_active = True
                    self.logger.info("[DEBUG] toggle_overlay: активное окно - это оверлей (TkTopLevel)")
            except Exception as e:
                self.logger.info(f"[DEBUG] toggle_overlay: ошибка получения класса окна: {e}")
            if is_overlay_active or (overlay_hwnd is not None and active_hwnd == overlay_hwnd):
                self.logger.info("[DEBUG] toggle_overlay: активен оверлей, разрешаем переключение")
                self.overlay.toggle()
                status = self.get_string('shown') if self.overlay.is_visible() else self.get_string('hidden')
                self.update_status(f"● {self.get_string('overlay')} {status}", '#2196F3')
                return
            if active_hwnd != target_hwnd:
                self.logger.debug(f"toggle_overlay: активное окно ({active_hwnd}) не является целевым ({target_hwnd})")
                self.update_status("● F1 работает только в целевом окне", '#ff9800')
                return
            self.overlay.toggle()
            status = self.get_string('shown') if self.overlay.is_visible() else self.get_string('hidden')
            self.update_status(f"● {self.get_string('overlay')} {status}", '#2196F3')
        except Exception as e:
            self.logger.warning(f"toggle_overlay: ошибка проверки активного окна: {e}")
            return

    def _setup_tkinter_hotkeys(self):
        """Запасной вариант через Tkinter bind_all"""
        self.logger.warning("Используется запасной метод горячих клавиш (Tkinter)")

        def handle_hotkey(event):
            keysym = event.keysym
            if keysym == "F1" or keysym == "f1":
                self.toggle_overlay()
                return "break"
            if keysym == "F2" or keysym == "f2":
                self.process()
                return "break"
            return None

        self.root.bind_all("<Key-F1>", handle_hotkey)
        self.root.bind_all("<Key-F2>", handle_hotkey)
        self.root.focus_force()
        self.logger.info("Tkinter горячие клавиши зарегистрированы")

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
        if self.overlay:
            self.overlay.close()
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

    def _start_key_block_monitor(self):
        """Устаревший метод - больше не используется"""
        pass

    def _init_translator_step(self):
        """Инициализация переводчика в фоновом режиме"""
        if self._init_done:
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

    def _on_init_complete(self, result, error):
        """Обработчик завершения инициализации"""
        self.logger.info(f"_on_init_complete вызван: result={result}, error={error}")
        if error:
            self.logger.error(f"Ошибка инициализации: {error}")
            self._on_init_error(error)
        else:
            self.logger.info("Инициализация завершена успешно, обновляем UI")
            self.ready = True
            self.initializing = False
            self._init_done = True
            if self.overlay is None:
                self.logger.info("Создание оверлея")
                from src.overlay import OverlayWindow
                auto_hide_enabled = self.settings.get_auto_hide_overlay()
                self.overlay = OverlayWindow(parent=self.root, app_title=self.app_title,
                                             auto_hide_enabled=auto_hide_enabled)
                self.logger.info(f"Оверлей создан: {self.overlay}")
            else:
                self.logger.info(f"Оверлей уже существует: {self.overlay}")
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            self.update_status("● " + self.get_string('ready'), '#4CAF50')
            self.logger.info("UI обновлен: статус 'Готово'")
        self._pending_command_ids = {}

    def _on_init_error(self, error_msg):
        """Обработчик ошибки инициализации"""
        self.initializing = False
        self._init_done = True
        if "Не найден" in error_msg and ("браузер" in error_msg or "Chrome" in error_msg):
            self._handle_browser_not_found(error_msg)
        else:
            self.update_status("● " + self.get_string('error') + ": " + error_msg[:50], '#f44336')
            self.btn_capture.config(state=DISABLED, bg='#333', fg='#888')
            self.logger.error(f"❌ Ошибка инициализации: {error_msg}")

    def _handle_browser_not_found(self, error_msg: str):
        """Обрабатывает ситуацию, когда браузер не найден"""
        self.logger.error(f"Браузер не найден: {error_msg}")
        self.update_status("● Браузер не найден", '#f44336')
        self.btn_capture.config(state=DISABLED, bg='#333', fg='#888')
        result = messagebox.askquestion(
            "Браузер не найден",
            "Не удалось найти Яндекс Браузер или Google Chrome.\n\n"
            "Для работы программы необходим один из этих браузеров.\n\n"
            "Вы можете:\n"
            "1. Установить Яндекс Браузер или Google Chrome\n"
            "2. Указать путь к уже установленному браузеру вручную\n\n"
            "Хотите указать путь к браузеру вручную?",
            icon='warning'
        )
        if result == 'yes':
            self._show_browser_path_dialog()
        else:
            messagebox.showinfo(
                "Информация",
                "Пожалуйста, установите Яндекс Браузер или Google Chrome\n"
                "и перезапустите программу."
            )

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
        self._restarting = True
        self.logger.info("Перезапуск переводчика с новыми настройками...")
        self.update_status("● Перезапуск браузера...", '#ff9800')
        self.btn_capture.config(state=DISABLED, bg='#333')
        show_browser = self.settings.get_show_browser()
        target_lang = self.settings.get_target_language()
        cmd_id = self.browser_worker.restart_browser(
            show_browser,
            target_lang,
            callback=self._on_restart_complete
        )
        self._pending_command_ids[cmd_id] = 'restart'
        self._check_results()

    def _on_restart_complete(self, result, error):
        """Обработчик завершения перезапуска"""
        if error:
            self.logger.error(f"Ошибка перезапуска: {error}")
            self._on_restart_error(error)
        else:
            self.ready = True
            self.btn_capture.config(state=NORMAL, bg='#4CAF50', fg='white')
            self.update_status("● " + self.get_string('ready'), '#4CAF50')
            self.logger.info("✅ Переводчик перезапущен успешно")
        self._restarting = False
        self._pending_command_ids = {}

    def _on_restart_error(self, error_msg):
        """Обработчик ошибки перезапуска"""
        self.update_status("● " + self.get_string('error') + ": " + error_msg[:50], '#f44336')
        self.btn_capture.config(state=DISABLED, bg='#333', fg='#888')
        self.logger.error(f"❌ Ошибка перезапуска: {error_msg}")
        self._restarting = False

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
            self.btn_capture.config(text=self.get_string('btn_capture'))
        if hasattr(self, 'btn_toggle'):
            self.btn_toggle.config(text=self.get_string('btn_toggle'))
        if hasattr(self, 'hotkeys_label'):
            self.hotkeys_label.config(text=self.get_string('hotkeys_info'))
        if hasattr(self, 'show_browser_check'):
            self.show_browser_check.config(text=self.get_string('show_browser'))
        if hasattr(self, 'target_lang_label'):
            self.target_lang_label.config(text=self.get_string('target_language'))
        self.update_menu_language()

    def update_menu_language(self):
        """Обновляет язык главного меню"""
        self.root.config(menu=Menu())
        menubar = Menu(self.root, bg='#1e1e1e', fg='white')
        self.root.config(menu=menubar)
        file_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white')
        menubar.add_cascade(label=self.get_string('menu_file'), menu=file_menu)
        file_menu.add_command(label=self.get_string('menu_open_folder'), command=self.open_app_folder)
        file_menu.add_separator()
        file_menu.add_command(label=self.get_string('menu_exit'), command=self.on_close)
        settings_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white')
        menubar.add_cascade(label=self.get_string('menu_settings'), menu=settings_menu)
        settings_menu.add_command(label=self.get_string('menu_settings_item'), command=self.open_settings)
        settings_menu.add_separator()
        settings_menu.add_command(label=self.get_string('menu_reset_settings'), command=self.reset_settings)
        help_menu = Menu(menubar, tearoff=0, bg='#1e1e1e', fg='white')
        menubar.add_cascade(label=self.get_string('menu_help'), menu=help_menu)
        help_menu.add_command(label=self.get_string('menu_shortcuts'), command=self.show_shortcuts)
        help_menu.add_command(label=self.get_string('menu_about'), command=self.show_about)

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

    def create_gui(self):
        """Создает главное окно приложения с адаптивной версткой"""
        self.root = Tk()
        self.root.title(self.get_string('app_title'))
        self.root.withdraw()
        self.root.geometry("520x520")
        self.root.minsize(520, 520)
        self.root.maxsize(520, 520)
        self.root.resizable(False, False)
        self.root.configure(bg='#1e1e1e')
        self.create_menu()
        self.show_browser_var = BooleanVar(value=self.settings.get_show_browser())
        self.target_lang_var = StringVar(value=self.settings.get_target_language())
        self.show_indicator_var = BooleanVar(value=self.settings.get_show_translation_indicator())
        self.auto_hide_var = BooleanVar(value=self.settings.get_auto_hide_overlay())
        main = Frame(self.root, bg='#1e1e1e')
        main.pack(expand=True, fill=BOTH, padx=25, pady=20)
        header_frame = Frame(main, bg='#1e1e1e', height=60)
        header_frame.pack(fill=X, pady=(0, 15))
        header_frame.pack_propagate(False)
        title_frame = Frame(header_frame, bg='#1e1e1e')
        title_frame.pack(side=LEFT, expand=True, fill=X)
        icon_label = Label(title_frame, text="📸",
                           bg='#1e1e1e', fg='white', font=("Arial", 26))
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
            cursor="hand2"
        )
        self.settings_btn.pack(side=RIGHT, padx=(0, 5))

        def on_enter(e):
            self.lang_btn.config(bg='#4CAF50', fg='white')

        def on_leave(e):
            self.lang_btn.config(bg='#3c3c3c', fg='#4CAF50')

        self.lang_btn.bind('<Enter>', on_enter)
        self.lang_btn.bind('<Leave>', on_leave)

        def on_settings_enter(e):
            self.settings_btn.config(bg='#4CAF50', fg='white')

        def on_settings_leave(e):
            self.settings_btn.config(bg='#3c3c3c', fg='#cccccc')

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
        self.btn_capture = Button(
            btn_frame,
            text=self.get_string('btn_capture'),
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
        self.btn_toggle = Button(
            btn_frame,
            text=self.get_string('btn_toggle'),
            command=self.toggle_overlay,
            font=("Arial", 11),
            bg='#2196F3',
            fg='white',
            relief=FLAT,
            height=1,
            pady=12
        )
        self.btn_toggle.pack(fill=X, ipady=2)
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

    def create_menu(self):
        """Создает главное меню приложения"""
        self.update_menu_language()

    def open_settings(self):
        """Открывает окно настроек"""
        from src.settings_window import SettingsWindow
        SettingsWindow(self, self.settings, self.on_settings_changed)

    def on_settings_changed(self):
        """Обработчик изменения настроек"""
        self.update_ui_language()
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
            if self.overlay:
                self.overlay.set_auto_hide(self.settings.get_auto_hide_overlay())
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

    def process(self):
        """Обработка скриншота"""
        if self.translating or not self.ready or self.initializing:
            return
        self._show_translation_overlay()
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
                self.root.after(0, lambda: self._do_translate(path))
            except Exception as e:
                self.logger.error(f"Ошибка захвата: {e}")
                self.root.after(0, lambda: self._on_translate_error(str(e)))

        threading.Thread(target=capture_task, daemon=True).start()

    def _do_translate(self, image_path: Path):
        """Выполняет перевод в фоновом режиме через BrowserWorker"""
        out = self.temp_dir / "translated"
        cmd_id = self.browser_worker.translate_image(
            image_path,
            out,
            callback=self._on_translate_finished
        )
        self._pending_command_ids[cmd_id] = 'translate'
        self._check_results()

    def _on_translate_finished(self, result, error):
        """Обработчик завершения перевода"""
        self.logger.info(f"_on_translate_finished вызван: result={result}, error={error}")
        try:
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
                    self.logger.info("Завершаем оверлей прогресса")
                    self.translation_overlay.finish()
                    time.sleep(0.3)
                self.logger.info(f"Попытка показать оверлей с результатом")
                self.logger.info(f"self.overlay = {self.overlay}")
                if self.overlay:
                    window_rect = self.screenshot.get_last_window_rect()
                    target_hwnd = self.screenshot.get_last_hwnd()
                    self.logger.info(f"window_rect = {window_rect}, target_hwnd = {target_hwnd}")
                    if window_rect and hasattr(self.overlay, 'show_for_window'):
                        self.logger.info(f"Вызов show_for_window с rect={window_rect}, hwnd={target_hwnd}")
                        self.overlay.show_for_window(result, window_rect, target_hwnd)
                        self.logger.info("show_for_window выполнен")
                    else:
                        self.logger.info("Вызов show_fullscreen")
                        self.overlay.show_fullscreen(result)
                        self.logger.info("show_fullscreen выполнен")
                    self.root.update_idletasks()
                    self.root.update()
                    self.logger.info("Результат перевода показан")
                else:
                    self.logger.error("self.overlay is None! Оверлей не создан.")
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

    def _on_translate_error(self, error_msg):
        """Обработчик ошибки перевода"""
        self.logger.error(f"Ошибка перевода: {error_msg}")
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
        except Exception as e:
            self.logger.warning(f"Не удалось показать оверлей: {e}")

    def _hide_translation_overlay(self):
        """Скрывает оверлей индикатора перевода"""
        try:
            if self.translation_overlay:
                self.translation_overlay.hide()
        except:
            pass

    def run(self):
        """Запускает главный цикл приложения"""
        print(f"{self.get_string('hotkeys_info')}")
        self.root.mainloop()