"""
Главный модуль приложения - объединяет все компоненты
"""

# Стандартные библиотеки
import logging
import tempfile
import time
import threading
import os
import sys
import tkinter as tk
from pathlib import Path
from datetime import datetime

# Сторонние библиотеки
import win32gui

# Локальные импорты
from src.settings import Settings
from src.browser_worker import BrowserWorker
from src.screenshot import ScreenshotCapturer
from src.overlay_manager import OverlayManager
from src.translation_monitor import TranslationMonitor
from src.translator import GoogleTranslateDebug
from src.main_window import MainWindow
from src.hotkeys import HotkeyManager
from src.window_list import WindowListManager
from src.utils import ensure_app_temp_dir
from src.notification_overlay import NotificationOverlay
from typing import Optional
import win32con


def cleanup_old_logs(log_dir, keep_count=5):
    """Очищает старые логи"""
    try:
        if not log_dir.exists():
            return
        log_files = list(log_dir.glob("app_*.log"))
        log_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
        if len(log_files) > keep_count:
            for f in log_files[keep_count:]:
                try:
                    f.unlink()
                except:
                    pass
    except Exception as e:
        print(f"Ошибка очистки логов: {e}")


def setup_logging():
    """Настройка логирования с выводом в консоль и файл"""
    try:
        # Создаем папку для логов
        log_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"app_{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log"

        # Настраиваем корневой логгер
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Удаляем все существующие обработчики (чтобы избежать дублирования)
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Формат для логов
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 1. Обработчик для вывода в терминал (консоль)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        root_logger.addHandler(console_handler)

        # 2. Обработчик для записи в файл
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)

        # Отключаем излишние логи от сторонних библиотек
        logging.getLogger("playwright").setLevel(logging.WARNING)
        logging.getLogger("PIL").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)

        # Принудительная синхронизация вывода (для Windows)
        try:
            sys.stdout.reconfigure(line_buffering=True)
        except:
            pass

        # Тестовое сообщение для проверки
        logger = logging.getLogger(__name__)
        logger.info("=" * 70)
        logger.info(f"Запуск GoogleScreenTranslate")
        logger.info(f"Лог файл: {log_file}")
        logger.info("=" * 70)

        # Очистка старых логов (оставляем последние 5)
        cleanup_old_logs(log_dir, keep_count=5)

        # Дополнительный вывод в консоль (гарантированно)
        print(f"\n✅ Логирование запущено")
        print(f"📁 Лог файл: {log_file}")
        print("=" * 70 + "\n")

        return log_file

    except Exception as e:
        # Если не удалось настроить логирование - выводим ошибку в консоль
        print(f"❌ Ошибка настройки логирования: {e}")
        import traceback
        traceback.print_exc()
        return None


class ScreenshotTranslatorApp:
    """Главный класс приложения"""

    @property
    def root(self):
        """Возвращает корневое окно tkinter для обратной совместимости"""
        return self.ui.root

    def __init__(self):
        # Настройка логирования
        self.log_file = setup_logging()
        self.logger = logging.getLogger(__name__)

        self._force_log_flush()

        self.settings = Settings()
        self.temp_dir = ensure_app_temp_dir()

        # Компоненты
        self.screenshot = ScreenshotCapturer()
        self.browser_worker = BrowserWorker(self.settings)
        self.browser_worker.start()
        self.overlay_manager = None
        self.translation_monitor = None

        # OCR процессор
        self.ocr_processor = None
        self._ocr_initialized = False

        # Состояние
        self.ready = False
        self.initializing = False
        self._init_done = False
        self.translating = False
        self._translation_in_progress = False
        self._capture_mode = False
        self._restarting = False
        self._processor_running = False

        # Очередь задач
        self.translation_queue = []
        self.is_processing_queue = False
        self._pending_command_ids = {}

        # Индикатор
        self._indicator_shown = False
        self._indicator_hidden = True

        # Состояния окон
        self._window_states = {}
        self._current_active_hwnd = None
        self._last_valid_app_name = None

        # ============================================================
        # ДЛЯ F4: запоминаем последний перетащенный F2-оверлей
        # ============================================================
        self._last_dragged_f2_overlay = None

        # Поля для захвата
        self._area_target_hwnd = None
        self._area_is_fullscreen = False
        self._pending_area_rect = None
        self._pending_region_path = None
        self._translated_templates = {}
        self.translation_overlay = None

        # Флаг временного перевода
        self._is_temporary_translation = False

        # Инициализация
        self._init_attempts = 0
        self._max_init_attempts = 3
        self._init_retry_delay = 2000

        # Создаем UI
        self.ui = MainWindow(self)
        self.notification = NotificationOverlay(self.ui.root)
        self.hotkeys = HotkeyManager(self)
        self.window_list = WindowListManager(self, self.ui.window_listbox, self.ui._window_hwnd_map)

        # Настройка
        self.hotkeys.setup()
        self._start_window_monitor()
        self._start_result_processor()

        # Запускаем фоновую инициализацию OCR
        self.ui.root.after(100, self._init_ocr_background)

        # Запуск инициализации
        self.ui.root.after(100, self._init_translator_step)

        self._force_log_flush()
        self.logger.info("✅ Приложение инициализировано успешно")
        self._force_log_flush()

    def _remove_overlay_state_from_file(self, app_name: str, template_id: str = None):
        """
        Удаляет конкретный оверлей из файла состояния.

        Args:
            app_name: Имя приложения
            template_id: ID шаблона (если есть)
        """
        try:
            import json
            from pathlib import Path

            state_file = Path.home() / "Documents" / "GoogleScreenTranslate" / "config" / "overlay_state.json"
            if not state_file.exists():
                return

            with open(state_file, 'r', encoding='utf-8') as f:
                states = json.load(f)

            keys_to_remove = []

            if template_id:
                for key in states.keys():
                    if key.startswith(f"{app_name}_") and template_id in key:
                        keys_to_remove.append(key)
            else:
                keys_to_remove = [key for key in states.keys() if key.startswith(f"{app_name}_")]

            if not keys_to_remove:
                self.logger.info(f"[CLEAR_ALL] Нет записей для удаления для {app_name}")
                return

            for key in keys_to_remove:
                del states[key]
                self.logger.info(f"[CLEAR_ALL] Удалена запись состояния: {key}")

            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(states, f, indent=4, ensure_ascii=False)

            self.logger.info(f"[CLEAR_ALL] Состояние для {app_name} удалено из файла")

        except Exception as e:
            self.logger.warning(f"[CLEAR_ALL] Не удалось обновить файл состояния: {e}")

    def _get_overlay_under_cursor(self):
        """Возвращает оверлей под курсором мыши."""
        try:
            import win32gui
            import win32api

            cursor_pos = win32api.GetCursorPos()
            cursor_x, cursor_y = cursor_pos

            if not self.overlay_manager:
                return None

            for overlay in reversed(self.overlay_manager.overlays):
                try:
                    if overlay is None:
                        continue
                    if not overlay.root or not overlay.root.winfo_exists():
                        continue
                    if not overlay.visible:
                        continue

                    overlay_hwnd = int(overlay.root.winfo_id())
                    rect = win32gui.GetWindowRect(overlay_hwnd)
                    x1, y1, x2, y2 = rect

                    if x1 <= cursor_x <= x2 and y1 <= cursor_y <= y2:
                        self.logger.info(f"[CLEAR_ALL] Найден оверлей под курсором: {overlay._app_name}")
                        return overlay

                except Exception as e:
                    self.logger.warning(f"[CLEAR_ALL] Ошибка проверки оверлея: {e}")
                    continue

        except Exception as e:
            self.logger.warning(f"[CLEAR_ALL] Ошибка получения оверлея под курсором: {e}")

        return None

    def _clear_overlays_list(self, overlays_list):
        """
        Удаляет список оверлеев.

        Args:
            overlays_list: Список оверлеев для удаления
        """
        if not overlays_list:
            return

        app_name = None
        if overlays_list and overlays_list[0]:
            app_name = overlays_list[0]._app_name

        if not app_name:
            app_name = "Неизвестно"

        self.logger.info(f"[CLEAR_ALL] Удаление {len(overlays_list)} оверлеев для {app_name}")

        # Останавливаем монитор
        if self.translation_monitor:
            if self.translation_monitor.is_running():
                self.translation_monitor.stop()
                self.logger.info("[CLEAR_ALL] Монитор остановлен")

            templates_to_remove = []
            for template_data in self.translation_monitor.templates[:]:
                if template_data.get('target_app_name') == app_name:
                    templates_to_remove.append(template_data.get('pair_index'))

            for pair_index in templates_to_remove:
                self.translation_monitor.remove_template(pair_index)
                self.logger.info(f"[CLEAR_ALL] Удален шаблон #{pair_index} для {app_name}")

            self.translation_monitor._frame_cache = None
            self.translation_monitor._frame_cache_hwnd = None
            self.translation_monitor._last_active_hwnd = None
            self.translation_monitor._last_active_app_name = None

        # Удаляем оверлеи
        if hasattr(self.overlay_manager, 'remove_all_overlays_for_app'):
            self.overlay_manager.remove_all_overlays_for_app(app_name, force=True)
        else:
            for overlay in overlays_list[:]:
                try:
                    self.overlay_manager.remove_overlay(overlay, force=True)
                except Exception as e:
                    self.logger.error(f"[CLEAR_ALL] Ошибка удаления оверлея: {e}")

        # Удаляем из файла состояния
        self._remove_app_state_from_file(app_name)

        # Перезапускаем монитор
        if self.translation_monitor:
            remaining_templates = len(self.translation_monitor.templates)
            if remaining_templates > 0 and self.settings.get_auto_replace_translated():
                self.logger.info(f"[CLEAR_ALL] Перезапуск монитора для {remaining_templates} оставшихся шаблонов")
                self.translation_monitor.start()
                self.logger.info("[CLEAR_ALL] Монитор перезапущен")
            elif remaining_templates > 0:
                self.logger.info(
                    f"[CLEAR_ALL] Монитор не перезапущен (автозамена выключена), осталось {remaining_templates} шаблонов"
                )
            else:
                self.logger.info("[CLEAR_ALL] Нет оставшихся шаблонов, монитор не перезапускается")

        self.ui.root.after(100, lambda: self.window_list.refresh(skip_restore=True))

    def _clear_single_overlay(self, overlay):
        """
        Удаляет один оверлей и полностью очищает его состояние.

        Args:
            overlay: Объект оверлея для удаления
        """
        if not overlay:
            return

        self.logger.info(f"[CLEAR_ALL] Удаление одиночного оверлея")

        app_name = overlay._app_name or "Неизвестно"
        template_id = overlay._template_id if hasattr(overlay, '_template_id') else None

        if hasattr(self, '_last_dragged_f2_overlay') and self._last_dragged_f2_overlay == overlay:
            self._last_dragged_f2_overlay = None

        # 1. Удаляем шаблон из монитора
        if self.translation_monitor and template_id:
            for template_data in self.translation_monitor.templates[:]:
                if template_data.get('hash') == template_id:
                    pair_index = template_data.get('pair_index')
                    self.translation_monitor.remove_template(pair_index)
                    self.logger.info(f"[CLEAR_ALL] Шаблон #{pair_index} удален из монитора")
                    break

        # 2. Останавливаем сохранение состояния во время удаления
        if hasattr(self.overlay_manager, '_suppress_save'):
            self.overlay_manager._suppress_save = True

        try:
            # 3. Удаляем оверлей через менеджер (без сохранения состояния)
            #    remove_overlay теперь сам обрабатывает удаление из F1 состояния
            self.overlay_manager.remove_overlay(overlay, force=True)
            self.logger.info("[CLEAR_ALL] Оверлей удалён из менеджера")
        except Exception as e:
            self.logger.error(f"[CLEAR_ALL] Ошибка удаления оверлея: {e}")
        finally:
            # 4. Восстанавливаем сохранение
            if hasattr(self.overlay_manager, '_suppress_save'):
                self.overlay_manager._suppress_save = False

        # 5. Удаляем состояние из файла
        self._remove_overlay_state_from_file(app_name, template_id)

        # 6. Принудительно сохраняем состояние (уже без оверлея)
        self.overlay_manager.save_overlay_state(immediate=True)

        # 7. Обновляем список окон
        self.ui.root.after(100, lambda: self.window_list.refresh(skip_restore=True))

        self.logger.info(f"[CLEAR_ALL] Оверлей полностью удалён и состояние очищено")

    def _remove_app_state_from_file(self, app_name: str):
        """Удаляет состояние для приложения из файла overlay_state.json."""
        try:
            import json
            from pathlib import Path

            state_file = Path.home() / "Documents" / "GoogleScreenTranslate" / "config" / "overlay_state.json"
            if not state_file.exists():
                return

            with open(state_file, 'r', encoding='utf-8') as f:
                states = json.load(f)

            keys_to_remove = [key for key in states.keys() if key.startswith(f"{app_name}_")]
            for key in keys_to_remove:
                del states[key]
                self.logger.info(f"[CLEAR_ALL] Удалена запись состояния: {key}")

            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(states, f, indent=4, ensure_ascii=False)

            self.logger.info(f"[CLEAR_ALL] Состояние для {app_name} удалено из файла")

        except Exception as e:
            self.logger.warning(f"[CLEAR_ALL] Не удалось обновить файл состояния: {e}")

    def _show_f2_overlays_for_app(self, app_name: str):
        """Показывает все F2-оверлеи для указанного приложения."""
        if not self.overlay_manager:
            return

        overlays = self.overlay_manager.get_overlays_by_app_name(app_name)
        for overlay in overlays:
            try:
                # Показываем только F2-оверлеи
                if hasattr(overlay, '_is_f2_overlay') and overlay._is_f2_overlay:
                    # Проверяем, что оверлей не скрыт пользователем (F1)
                    if not overlay._hidden_by_user:
                        if not overlay.visible:
                            overlay.show()
                            self.logger.info(f"[WINDOW] Показан F2-оверлей для {app_name}")
            except Exception as e:
                self.logger.warning(f"[WINDOW] Ошибка показа F2-оверлея: {e}")

    def _force_log_flush(self):
        """Принудительно сбрасывает буферы логов в консоль"""
        try:
            sys.stdout.flush()
            sys.stderr.flush()
            for handler in logging.root.handlers:
                if hasattr(handler, 'flush'):
                    handler.flush()
        except Exception as e:
            # Не используем self.logger здесь, чтобы избежать рекурсии
            print(f"Ошибка при сбросе буферов: {e}")

    def _restart_translator(self):
        """Перезапускает переводчик с сохранением состояния оверлеев"""
        self.logger.info("[APP] === _restart_translator НАЧАЛО ===")
        self.logger.info("[APP] Выполняется сохранение состояния и перезапуск...")

        if not self.browser_worker:
            self.logger.warning("[APP] browser_worker не инициализирован, пропускаем")
            return

        # ============================================================
        # 1. СОХРАНЯЕМ СОСТОЯНИЕ ОВЕРЛЕЕВ ПЕРЕД ОЧИСТКОЙ
        # ============================================================
        if hasattr(self, 'overlay_manager') and self.overlay_manager:
            try:
                # Принудительно сохраняем состояние в файл
                self.overlay_manager.save_overlay_state(immediate=True)
                self.logger.info("[APP] Состояние оверлеев сохранено перед перезапуском")
            except Exception as e:
                self.logger.warning(f"[APP] Ошибка сохранения состояния: {e}")

        # ============================================================
        # 2. ОЧИСТКА КОМПОНЕНТОВ (БЕЗ УДАЛЕНИЯ ФАЙЛА СОСТОЯНИЯ)
        # ============================================================

        # 2.1 Останавливаем и очищаем TranslationMonitor
        if hasattr(self, 'translation_monitor') and self.translation_monitor:
            try:
                self.translation_monitor.stop()
                self.translation_monitor.templates.clear()
                self.logger.info("[APP] TranslationMonitor остановлен и очищен")
            except Exception as e:
                self.logger.warning(f"[APP] Ошибка очистки TranslationMonitor: {e}")
            self.translation_monitor = None

        # 2.2 Закрываем все оверлеи (но не удаляем файл состояния)
        if hasattr(self, 'overlay_manager') and self.overlay_manager:
            try:
                count = len(self.overlay_manager.overlays)
                self.overlay_manager.close_all()
                self.logger.info(f"[APP] Закрыто {count} оверлеев (состояние сохранено)")
            except Exception as e:
                self.logger.warning(f"[APP] Ошибка закрытия оверлеев: {e}")
            self.overlay_manager = None

        # 2.3 Очищаем список окон
        if hasattr(self, 'window_list'):
            try:
                self.window_list.window_listbox.delete(0, 'end')
                self.window_list._window_hwnd_map.clear()
                self.window_list._window_app_map.clear()
                self.logger.info("[APP] Список окон очищен")
            except Exception as e:
                self.logger.warning(f"[APP] Ошибка очистки списка окон: {e}")

        # 2.4 Сбрасываем флаги инициализации
        self.ready = False
        self.initializing = True
        self._init_done = False
        self._init_attempts = 0
        self.logger.info("[APP] Флаги инициализации сброшены")

        # ============================================================
        # 3. ПРОВЕРЯЕМ ДВИЖОК И ПЕРЕЗАПУСКАЕМ БРАУЗЕР
        # ============================================================

        engine = self.settings.get_translator_engine()
        if not hasattr(self, '_last_engine'):
            self._last_engine = engine
        elif self._last_engine != engine:
            self.logger.info(f"[APP] Движок изменен: {self._last_engine} -> {engine}")
            self._last_engine = engine

        show_browser = self.settings.get_show_browser()
        target_lang = self.settings.get_target_language()

        # Статус "starting browser"
        self.ui.update_status("● " + self.ui.get_string('starting_browser'), '#ff9800')

        # Отправляем команду перезапуска
        cmd_id = self.browser_worker.restart_browser(show_browser, target_lang, self._on_init_complete)
        self._pending_command_ids[cmd_id] = 'restart'

        self.logger.info(f"[APP] Команда перезапуска отправлена (id={cmd_id})")
        self.logger.info("[APP] === _restart_translator ЗАВЕРШЕН ===")

    def _create_selection_window(self, screenshot_path):
        """
        Создает окно выбора области и возвращает его вместе с данными.
        """
        from PIL import Image, ImageTk
        import win32gui
        import win32con

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
        display_w, display_h = int(img_width * scale), int(img_height * scale)

        resized = img.resize((display_w, display_h), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        img_x, img_y = (screen_width - display_w) // 2, (screen_height - display_h) // 2

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
            'rect': None,
            'selection_window': selection_window,
            'canvas': canvas,
            'area_count': 0,
            'is_temporary': False,
            'temp_rect': None
        }

        # Добавляем инструкцию
        instruction_text = self.get_string('area_selector_instruction')
        canvas.create_text(
            screen_width // 2, 50,
            text=instruction_text,
            fill="white",
            font=("Arial", 16, "bold")
        )

        counter_text = self.get_string('area_selector_counter').format(0)
        counter_id = canvas.create_text(
            screen_width // 2, 90,
            text=counter_text,
            fill="#4CAF50",
            font=("Arial", 14)
        )
        selection_data['counter_id'] = counter_id

        return selection_window, canvas, selection_data

    def _setup_mouse_handlers(self, canvas, selection_data, screenshot_path, selection_window):
        """Настраивает обработчики мыши для выбора области."""

        # ========== ЛКМ (постоянный оверлей, красная рамка) ==========
        def on_mouse_down(event):
            selection_data['start_x'] = event.x
            selection_data['start_y'] = event.y
            selection_data['is_temporary'] = False
            if selection_data['rect']:
                canvas.delete(selection_data['rect'])
                selection_data['rect'] = None
            if selection_data['temp_rect']:
                canvas.delete(selection_data['temp_rect'])
                selection_data['temp_rect'] = None

        def on_mouse_drag(event):
            if selection_data['start_x'] is not None:
                if selection_data['rect']:
                    canvas.delete(selection_data['rect'])
                selection_data['rect'] = canvas.create_rectangle(
                    selection_data['start_x'], selection_data['start_y'],
                    event.x, event.y,
                    outline='red', width=2,
                    fill='blue', stipple='gray50'
                )

        def on_mouse_up(event):
            if selection_data['start_x'] is not None:
                x1, y1 = min(selection_data['start_x'], event.x), min(selection_data['start_y'], event.y)
                x2, y2 = max(selection_data['start_x'], event.x), max(selection_data['start_y'], event.y)
                if x2 - x1 > 10 and y2 - y1 > 10:
                    self._process_mouse_selection(x1, y1, x2, y2, selection_data, screenshot_path, selection_window,
                                                  is_temporary=False)
                else:
                    if selection_data['rect']:
                        canvas.delete(selection_data['rect'])
                        selection_data['rect'] = None
                    selection_data['start_x'] = None
                    selection_data['start_y'] = None

        # ========== ПКМ (временный оверлей, синяя рамка) ==========
        def on_mouse_down_pkm(event):
            selection_data['start_x'] = event.x
            selection_data['start_y'] = event.y
            selection_data['is_temporary'] = True
            if selection_data['temp_rect']:
                canvas.delete(selection_data['temp_rect'])
                selection_data['temp_rect'] = None
            if selection_data['rect']:
                canvas.delete(selection_data['rect'])
                selection_data['rect'] = None

        def on_mouse_drag_pkm(event):
            if selection_data['start_x'] is not None:
                if selection_data['temp_rect']:
                    canvas.delete(selection_data['temp_rect'])
                selection_data['temp_rect'] = canvas.create_rectangle(
                    selection_data['start_x'], selection_data['start_y'],
                    event.x, event.y,
                    outline='#2196F3', width=2,
                    fill='blue', stipple='gray50'
                )

        def on_mouse_up_pkm(event):
            if selection_data['start_x'] is not None:
                x1, y1 = min(selection_data['start_x'], event.x), min(selection_data['start_y'], event.y)
                x2, y2 = max(selection_data['start_x'], event.x), max(selection_data['start_y'], event.y)
                if x2 - x1 > 10 and y2 - y1 > 10:
                    self._process_mouse_selection(x1, y1, x2, y2, selection_data, screenshot_path, selection_window,
                                                  is_temporary=True)
                else:
                    if selection_data['temp_rect']:
                        canvas.delete(selection_data['temp_rect'])
                        selection_data['temp_rect'] = None
                    selection_data['start_x'] = None
                    selection_data['start_y'] = None

        # Привязываем события
        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)

        canvas.bind("<ButtonPress-3>", on_mouse_down_pkm)
        canvas.bind("<B3-Motion>", on_mouse_drag_pkm)
        canvas.bind("<ButtonRelease-3>", on_mouse_up_pkm)

    def _process_mouse_selection(self, x1, y1, x2, y2, selection_data, screenshot_path, selection_window, is_temporary):
        """Обрабатывает выделение мышью (ЛКМ или ПКМ)."""
        img_x = selection_data['img_x']
        img_y = selection_data['img_y']
        scale_x = selection_data['scale_x']
        scale_y = selection_data['scale_y']
        img_width = selection_data['img'].width
        img_height = selection_data['img'].height
        canvas = selection_data['canvas']
        counter_id = selection_data['counter_id']

        orig_x1 = int((x1 - img_x) * scale_x)
        orig_y1 = int((y1 - img_y) * scale_y)
        orig_x2 = int((x2 - img_x) * scale_x)
        orig_y2 = int((y2 - img_y) * scale_y)

        orig_x1 = max(0, min(orig_x1, img_width))
        orig_y1 = max(0, min(orig_y1, img_height))
        orig_x2 = max(0, min(orig_x2, img_width))
        orig_y2 = max(0, min(orig_y2, img_height))

        selection_data['area_count'] += 1
        counter_text = self.get_string('area_selector_counter').format(selection_data['area_count'])
        canvas.itemconfig(counter_id, text=counter_text)

        if selection_data['rect']:
            canvas.delete(selection_data['rect'])
            selection_data['rect'] = None
        if selection_data['temp_rect']:
            canvas.delete(selection_data['temp_rect'])
            selection_data['temp_rect'] = None
        selection_data['start_x'] = None
        selection_data['start_y'] = None

        self._process_area_selection_continuous(
            orig_x1, orig_y1, orig_x2, orig_y2,
            screenshot_path, selection_window,
            is_temporary=is_temporary
        )

    def _setup_esc_exit_handler(self, canvas, selection_window, exit_area_mode):
        """Настраивает обработчик ESC для выхода из режима выбора области."""

        def on_esc_pressed(e):
            self.logger.info("[F3] ESC нажат в окне выбора области -> выход")
            exit_area_mode()
            return "break"

        # Привязываем к canvas, window и корневому окну
        canvas.bind("<Escape>", on_esc_pressed)
        selection_window.bind("<Escape>", on_esc_pressed)
        self.ui.root.bind("<Escape>", on_esc_pressed)

        canvas.bind("<Return>", lambda e: exit_area_mode())
        selection_window.bind("<Return>", lambda e: exit_area_mode())

    def _force_window_focus(self, selection_window):
        """Принудительно устанавливает фокус на окно выбора области."""
        import win32gui
        import win32con
        import time

        selection_window.update_idletasks()
        time.sleep(0.05)

        try:
            hwnd = int(selection_window.winfo_id())

            # 1. Устанавливаем TOPMOST
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            )

            # 2. Принудительно поднимаем окно
            win32gui.BringWindowToTop(hwnd)
            time.sleep(0.02)

            # 3. Устанавливаем фокус
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.02)

            # 4. Устанавливаем фокус через SetFocus
            win32gui.SetFocus(hwnd)

            # 5. Отправляем сообщение активации
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)

            self.logger.info(f"[F3] Фокус установлен на окно выбора области (HWND: {hwnd})")
        except Exception as e:
            self.logger.warning(f"[F3] Не удалось установить фокус через Win32 API: {e}")

        # Устанавливаем фокус через Tkinter
        selection_window.focus_force()
        selection_window.grab_set()
        selection_window.lift()
        selection_window.update_idletasks()
        time.sleep(0.05)

        # Ещё раз пробуем захватить фокус
        try:
            hwnd = int(selection_window.winfo_id())
            win32gui.SetForegroundWindow(hwnd)
        except:
            pass

        # Таймер для повторной установки фокуса
        def ensure_focus():
            try:
                if selection_window.winfo_exists():
                    hwnd = int(selection_window.winfo_id())
                    win32gui.SetForegroundWindow(hwnd)
                    self.logger.info("[F3] Повторная установка фокуса на окно выбора области")
            except:
                pass

        selection_window.after(100, ensure_focus)

    def _show_continuous_area_selection_window(self, screenshot_path):
        """Показывает окно выделения области"""
        from PIL import Image, ImageTk
        import win32gui
        import win32con
        import time
        import keyboard  # <-- ДОБАВИТЬ

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
        display_w, display_h = int(img_width * scale), int(img_height * scale)

        resized = img.resize((display_w, display_h), Image.Resampling.LANCZOS)
        photo = ImageTk.PhotoImage(resized)
        img_x, img_y = (screen_width - display_w) // 2, (screen_height - display_h) // 2

        canvas.create_image(img_x, img_y, anchor=tk.NW, image=photo)
        canvas.image = photo

        selection_data = {
            'img': img, 'screenshot_path': screenshot_path,
            'scale_x': img_width / display_w, 'scale_y': img_height / display_h,
            'img_x': img_x, 'img_y': img_y,
            'start_x': None, 'start_y': None,
            'rect': None,
            'selection_window': selection_window, 'canvas': canvas,
            'area_count': 0,
            'is_temporary': False,
            'temp_rect': None
        }

        instruction_text = self.get_string('area_selector_instruction')
        canvas.create_text(
            screen_width // 2, 50,
            text=instruction_text,
            fill="white",
            font=("Arial", 16, "bold")
        )

        counter_text = self.get_string('area_selector_counter').format(0)
        counter_id = canvas.create_text(
            screen_width // 2, 90,
            text=counter_text,
            fill="#4CAF50",
            font=("Arial", 14)
        )
        selection_data['counter_id'] = counter_id

        target_hwnd_for_exit = self._area_target_hwnd

        # ========== ПЕРЕМЕННЫЕ ДЛЯ ХУКА ==========
        esc_hook_active = False
        esc_hook_handler = None

        # ========== ЛКМ (постоянный оверлей, красная рамка) ==========
        def on_mouse_down(event):
            selection_data['start_x'] = event.x
            selection_data['start_y'] = event.y
            selection_data['is_temporary'] = False
            if selection_data['rect']:
                canvas.delete(selection_data['rect'])
                selection_data['rect'] = None
            if selection_data['temp_rect']:
                canvas.delete(selection_data['temp_rect'])
                selection_data['temp_rect'] = None

        def on_mouse_drag(event):
            if selection_data['start_x'] is not None:
                if selection_data['rect']:
                    canvas.delete(selection_data['rect'])
                selection_data['rect'] = canvas.create_rectangle(
                    selection_data['start_x'], selection_data['start_y'],
                    event.x, event.y,
                    outline='red', width=2,
                    fill='blue', stipple='gray50'
                )

        def on_mouse_up(event):
            if selection_data['start_x'] is not None:
                x1, y1 = min(selection_data['start_x'], event.x), min(selection_data['start_y'], event.y)
                x2, y2 = max(selection_data['start_x'], event.x), max(selection_data['start_y'], event.y)
                if x2 - x1 > 10 and y2 - y1 > 10:
                    orig_x1 = int((x1 - img_x) * selection_data['scale_x'])
                    orig_y1 = int((y1 - img_y) * selection_data['scale_y'])
                    orig_x2 = int((x2 - img_x) * selection_data['scale_x'])
                    orig_y2 = int((y2 - img_y) * selection_data['scale_y'])
                    orig_x1 = max(0, min(orig_x1, img_width))
                    orig_y1 = max(0, min(orig_y1, img_height))
                    orig_x2 = max(0, min(orig_x2, img_width))
                    orig_y2 = max(0, min(orig_y2, img_height))

                    selection_data['area_count'] += 1
                    counter_text = self.get_string('area_selector_counter').format(selection_data['area_count'])
                    canvas.itemconfig(counter_id, text=counter_text)

                    if selection_data['rect']:
                        canvas.delete(selection_data['rect'])
                        selection_data['rect'] = None
                    selection_data['start_x'] = None
                    selection_data['start_y'] = None

                    self._process_area_selection_continuous(
                        orig_x1, orig_y1, orig_x2, orig_y2,
                        screenshot_path, selection_window,
                        is_temporary=False
                    )
                else:
                    if selection_data['rect']:
                        canvas.delete(selection_data['rect'])
                        selection_data['rect'] = None
                    selection_data['start_x'] = None
                    selection_data['start_y'] = None

        # ========== ПКМ (временный оверлей, синяя рамка) ==========
        def on_mouse_down_pkm(event):
            selection_data['start_x'] = event.x
            selection_data['start_y'] = event.y
            selection_data['is_temporary'] = True
            if selection_data['temp_rect']:
                canvas.delete(selection_data['temp_rect'])
                selection_data['temp_rect'] = None
            if selection_data['rect']:
                canvas.delete(selection_data['rect'])
                selection_data['rect'] = None

        def on_mouse_drag_pkm(event):
            if selection_data['start_x'] is not None:
                if selection_data['temp_rect']:
                    canvas.delete(selection_data['temp_rect'])
                selection_data['temp_rect'] = canvas.create_rectangle(
                    selection_data['start_x'], selection_data['start_y'],
                    event.x, event.y,
                    outline='#2196F3', width=2,
                    fill='blue', stipple='gray50'
                )

        def on_mouse_up_pkm(event):
            if selection_data['start_x'] is not None:
                x1, y1 = min(selection_data['start_x'], event.x), min(selection_data['start_y'], event.y)
                x2, y2 = max(selection_data['start_x'], event.x), max(selection_data['start_y'], event.y)
                if x2 - x1 > 10 and y2 - y1 > 10:
                    orig_x1 = int((x1 - img_x) * selection_data['scale_x'])
                    orig_y1 = int((y1 - img_y) * selection_data['scale_y'])
                    orig_x2 = int((x2 - img_x) * selection_data['scale_x'])
                    orig_y2 = int((y2 - img_y) * selection_data['scale_y'])
                    orig_x1 = max(0, min(orig_x1, img_width))
                    orig_y1 = max(0, min(orig_y1, img_height))
                    orig_x2 = max(0, min(orig_x2, img_width))
                    orig_y2 = max(0, min(orig_y2, img_height))

                    selection_data['area_count'] += 1
                    counter_text = self.get_string('area_selector_counter').format(selection_data['area_count'])
                    canvas.itemconfig(counter_id, text=counter_text)

                    if selection_data['temp_rect']:
                        canvas.delete(selection_data['temp_rect'])
                        selection_data['temp_rect'] = None
                    selection_data['start_x'] = None
                    selection_data['start_y'] = None

                    self._process_area_selection_continuous(
                        orig_x1, orig_y1, orig_x2, orig_y2,
                        screenshot_path, selection_window,
                        is_temporary=True
                    )
                else:
                    if selection_data['temp_rect']:
                        canvas.delete(selection_data['temp_rect'])
                        selection_data['temp_rect'] = None
                    selection_data['start_x'] = None
                    selection_data['start_y'] = None

        # ========== ВЫХОД ==========
        def exit_area_mode():
            self.logger.info("[DEBUG] exit_area_mode() - выход из режима захвата")
            self._capture_mode = False

            # ОТКЛЮЧАЕМ ГЛОБАЛЬНЫЙ ХУК ESC
            nonlocal esc_hook_active, esc_hook_handler
            if esc_hook_active and esc_hook_handler:
                try:
                    keyboard.unhook_key(esc_hook_handler)
                    self.logger.info("[F3] Глобальный хук ESC отключен")
                except Exception as e:
                    self.logger.warning(f"[F3] Ошибка отключения хука ESC: {e}")
                esc_hook_active = False
                esc_hook_handler = None

            # Отключаем глобальную привязку ESC через Tkinter
            self.ui.root.unbind_all("<Escape>")

            self.hotkeys.set_actions_blocked(False)

            if self.translation_queue and not self._indicator_shown:
                self._show_translation_overlay()
                self._indicator_shown = True
                self.logger.info("[DEBUG] Индикатор перевода показан после выхода из F3")

            if target_hwnd_for_exit:
                try:
                    win32gui.SetForegroundWindow(target_hwnd_for_exit)
                    self.logger.info("[F3] Фокус возвращён на целевое окно")
                except Exception as e:
                    self.logger.error(f"[F3] Ошибка возврата фокуса: {e}")
                    self.ui.root.deiconify()
                    self.ui.root.lift()
                    self.ui.root.focus_force()
            else:
                self.ui.root.deiconify()
                self.ui.root.lift()
                self.ui.root.focus_force()

            try:
                selection_window.grab_release()
                selection_window.destroy()
            except:
                pass

        # ========== ПРИВЯЗКА СОБЫТИЙ ==========
        # ЛКМ
        canvas.bind("<ButtonPress-1>", on_mouse_down)
        canvas.bind("<B1-Motion>", on_mouse_drag)
        canvas.bind("<ButtonRelease-1>", on_mouse_up)

        # ПКМ
        canvas.bind("<ButtonPress-3>", on_mouse_down_pkm)
        canvas.bind("<B3-Motion>", on_mouse_drag_pkm)
        canvas.bind("<ButtonRelease-3>", on_mouse_up_pkm)

        # === ВЫХОД ПО ESC ===
        def on_esc_pressed(e):
            self.logger.info("[F3] ESC нажат -> выход из режима захвата")
            exit_area_mode()
            return "break"

        # Привязываем ESC к canvas и window
        canvas.bind("<Escape>", on_esc_pressed)
        selection_window.bind("<Escape>", on_esc_pressed)
        self.ui.root.bind_all("<Escape>", on_esc_pressed)

        # === ГЛОБАЛЬНЫЙ ХУК ЧЕРЕЗ keyboard (перехватывает ESC на системном уровне) ===
        def global_esc_handler(e):
            self.logger.info("[F3] Глобальный хук: ESC нажат -> выход из режима захвата")
            exit_area_mode()
            return False  # Блокируем дальнейшую обработку

        try:
            esc_hook_handler = keyboard.on_press_key('esc', global_esc_handler, suppress=True)
            esc_hook_active = True
            self.logger.info("[F3] Глобальный хук ESC установлен через keyboard")
        except Exception as e:
            self.logger.warning(f"[F3] Не удалось установить глобальный хук ESC: {e}")

        # Enter для выхода
        canvas.bind("<Return>", lambda e: exit_area_mode())
        selection_window.bind("<Return>", lambda e: exit_area_mode())

        # === УСИЛЕННЫЙ ЗАХВАТ ФОКУСА ===
        selection_window.update_idletasks()
        time.sleep(0.05)

        try:
            hwnd = int(selection_window.winfo_id())

            # 1. Устанавливаем TOPMOST
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            )

            # 2. Принудительно поднимаем окно
            win32gui.BringWindowToTop(hwnd)
            time.sleep(0.02)

            # 3. Устанавливаем фокус
            win32gui.SetForegroundWindow(hwnd)
            time.sleep(0.02)

            # 4. Устанавливаем фокус через SetFocus
            win32gui.SetFocus(hwnd)

            # 5. Отправляем сообщение активации
            win32gui.SendMessage(hwnd, win32con.WM_ACTIVATE, win32con.WA_ACTIVE, 0)

            self.logger.info(f"[F3] Фокус установлен на окно выбора области (HWND: {hwnd})")
        except Exception as e:
            self.logger.warning(f"[F3] Не удалось установить фокус через Win32 API: {e}")

        # Устанавливаем фокус через Tkinter
        canvas.focus_set()
        selection_window.focus_force()
        selection_window.grab_set()
        selection_window.lift()

        # Дополнительная задержка для стабилизации
        selection_window.update_idletasks()
        time.sleep(0.05)

        # Ещё раз пробуем захватить фокус
        try:
            hwnd = int(selection_window.winfo_id())
            win32gui.SetForegroundWindow(hwnd)
        except:
            pass

        # === ТАЙМЕР ДЛЯ ПОВТОРНОЙ УСТАНОВКИ ФОКУСА ===
        def ensure_focus():
            try:
                if selection_window.winfo_exists():
                    hwnd = int(selection_window.winfo_id())
                    win32gui.SetForegroundWindow(hwnd)
                    self.logger.info("[F3] Повторная установка фокуса на окно выбора области")
            except:
                pass

        selection_window.after(100, ensure_focus)

        self.hotkeys.set_actions_blocked(True)

    def _auto_switch_fullscreen_window(self, hwnd: int, app_name: str):
        """
        Автоматически переключает полноэкранное окно в оконный режим,
        если для этого приложения есть оверлеи и включена соответствующая настройка.
        """
        # Проверяем, включена ли настройка
        if not self.settings.get_auto_windowed_fullscreen():
            return

        # Проверяем, есть ли оверлеи для этого приложения
        if not self.overlay_manager:
            return

        overlays_for_app = self.overlay_manager.get_overlays_by_app_name(app_name)
        if not overlays_for_app:
            return

        # Проверяем, находится ли окно в полноэкранном режиме
        if not self.screenshot.is_window_fullscreen(hwnd):
            return

        self.logger.info(f"[AUTO_SWITCH] Обнаружен полноэкранный режим для {app_name} с оверлеями, переключаем...")

        try:
            import keyboard
            from src.window_utils import make_windowed_fullscreen

            # Отправляем Alt+Enter
            keyboard.press_and_release('alt+enter')
            self.logger.info("[AUTO_SWITCH] Alt+Enter отправлен")
            time.sleep(0.5)

            # Применяем оконный полноэкранный режим
            make_windowed_fullscreen(hwnd)
            time.sleep(0.3)
            self.logger.info("[AUTO_SWITCH] Окно переключено в оконный полноэкранный режим")

            # Возвращаем фокус на окно
            try:
                import win32gui
                win32gui.SetForegroundWindow(hwnd)
            except Exception as e:
                self.logger.warning(f"[AUTO_SWITCH] Не удалось вернуть фокус: {e}")

        except Exception as e:
            self.logger.warning(f"[AUTO_SWITCH] Ошибка переключения: {e}")

    def _init_ocr_background(self):
        """Фоновая инициализация EasyOCR при старте приложения"""
        try:
            from src.ocr_processor import OCRProcessor

            self.logger.info("🔄 Запуск фоновой инициализации EasyOCR...")

            def init_task():
                try:
                    self.ocr_processor = OCRProcessor()
                    self.ocr_processor.initialize()
                    self._ocr_initialized = True
                    self.logger.info("✅ EasyOCR готов к использованию")
                    # Удаляем уведомление
                    # if hasattr(self, 'show_notification'):
                    #     self.ui.root.after(0, lambda: self.show_notification("✅ OCR готов", 1500))
                except ImportError as e:
                    self.logger.warning(f"EasyOCR не установлен: {e}")
                    self._ocr_initialized = False
                    self.ocr_processor = None
                    # Удаляем уведомление
                    # if hasattr(self, 'show_notification'):
                    #     self.ui.root.after(0, lambda: self.show_notification("❌ EasyOCR не установлен", 2000))
                except Exception as e:
                    self.logger.error(f"❌ Ошибка инициализации EasyOCR: {e}")
                    self._ocr_initialized = False
                    self.ocr_processor = None

            import threading
            threading.Thread(target=init_task, daemon=True).start()

        except ImportError as e:
            self.logger.warning(f"Модуль OCR не найден: {e}")
            self._ocr_initialized = False
            self.ocr_processor = None

    def process_fullscreen_with_ocr(self):
        """
        Длительное зажатие F3 - скриншот всего окна + OCR + оверлеи по зонам
        """
        if self.translating or not self.ready:
            return

        # Проверяем, готов ли OCR
        if not self._ocr_initialized or self.ocr_processor is None:
            self.logger.warning("[F3_HOLD] OCR не инициализирован, запускаем...")
            self.show_notification("⏳ Инициализация OCR...")
            self._init_ocr_background()
            self.ui.root.after(3000, self.process_fullscreen_with_ocr)
            return

        self.logger.info("[F3_HOLD] Начало обработки с OCR (OCR готов)")

        self.set_actions_blocked(True)

        current_hwnd = win32gui.GetForegroundWindow()
        if current_hwnd:
            self.screenshot._last_hwnd = current_hwnd
            self.screenshot._is_fullscreen = self.screenshot.is_window_fullscreen(current_hwnd)

        # Переключение полноэкранного режима
        if self.screenshot._is_fullscreen and self.settings.get_auto_windowed_fullscreen():
            self.logger.info("[F3_HOLD] Обнаружен полноэкранный режим, переключаем в оконный...")
            try:
                import keyboard
                from src.window_utils import make_windowed_fullscreen

                keyboard.press_and_release('alt+enter')
                self.logger.info("[F3_HOLD] Alt+Enter отправлен")
                time.sleep(0.5)

                make_windowed_fullscreen(current_hwnd)
                time.sleep(0.3)
                self.logger.info("[F3_HOLD] Окно переключено в оконный полноэкранный режим")
            except Exception as e:
                self.logger.warning(f"[F3_HOLD] Ошибка переключения полноэкранного режима: {e}")

        self.translating = True
        # Статус "translating" — УБИРАЕМ
        self.logger.info("[F3_HOLD] Запуск перевода с OCR...")

        # Показываем индикатор
        self._show_translation_overlay()

        def capture_and_translate_task():
            import time
            from PIL import Image

            try:
                img = self.screenshot.capture_active_window()
                if not img:
                    # Ошибка захвата — только лог
                    self.logger.error("[F3_HOLD] Ошибка захвата окна")
                    self.translating = False
                    self.set_actions_blocked(False)
                    self._hide_translation_overlay()
                    return

                screenshot_path = self.temp_dir / f"fullscreen_{int(time.time())}.png"
                img.save(screenshot_path)

                window_rect = self.screenshot.get_last_window_rect() or self.screenshot.get_active_window_rect()
                if not window_rect:
                    window_rect = (0, 0, img.width, img.height)

                out_dir = self.temp_dir / "translated_ocr"
                out_dir.mkdir(parents=True, exist_ok=True)

                self._pending_area_rect = None
                self._pending_region_path = None
                self._is_temporary_translation = False

                cmd_id = self.browser_worker.translate_image(
                    screenshot_path,
                    out_dir,
                    lambda result, error: self._on_ocr_translate_finished(
                        result, error,
                        screenshot_path,
                        window_rect,
                        current_hwnd
                    )
                )
                self._pending_command_ids[cmd_id] = 'translate_ocr'

            except Exception as e:
                self.logger.error(f"[F3_HOLD] Ошибка: {e}")
                self.translating = False
                self.set_actions_blocked(False)
                self._hide_translation_overlay()

        threading.Thread(target=capture_and_translate_task, daemon=True).start()

    def _on_ocr_translate_finished(self, result, error, screenshot_path, window_rect, target_hwnd):
        """Обработчик завершения перевода для OCR режима."""
        import time
        total_start = time.time()
        self.logger.info(f"[F3_HOLD] ===== НАЧАЛО ОБРАБОТКИ OCR РЕЗУЛЬТАТА =====")

        self.logger.info(f"[F3_HOLD] Перевод завершён, error={error}")

        self._translation_in_progress = False
        self.translating = False

        try:
            if error:
                self._handle_ocr_error(error)
                return

            if not result or not Path(result).exists():
                self._handle_ocr_no_result()
                return

            self.logger.info(f"[F3_HOLD] Результат перевода получен: {result}")
            self.show_notification("🔄 OCR анализ...")

            # Проверяем OCR
            if self.ocr_processor is None or not self._ocr_initialized:
                self._handle_ocr_not_ready()
                return

            translated_image_path = Path(result)

            # Загружаем изображения
            original_img, translated_img = self._load_ocr_images(screenshot_path, translated_image_path)
            if original_img is None or translated_img is None:
                return

            # === ПОЛУЧАЕМ РАЗМЕРЫ ИЗОБРАЖЕНИЙ ===
            orig_w, orig_h = original_img.size
            trans_w, trans_h = translated_img.size
            self.logger.info(f"[F3_HOLD] Размеры: оригинал={orig_w}x{orig_h}, перевод={trans_w}x{trans_h}")

            # Подготавливаем дебаг
            debug_dir, timestamp = self._prepare_ocr_debug_dir()

            # Получаем регионы через OCR с параметрами для движка
            regions = self._get_ocr_regions(translated_image_path, debug_dir, timestamp)

            # Сохраняем дебаг-картинку
            self._save_ocr_debug_image(translated_img, regions, debug_dir, timestamp)

            overlay_created_count = 0

            if not regions:
                self._handle_ocr_no_text()
                return

            self.show_notification(f"📝 Создание {len(regions)} оверлеев...")

            # Получаем существующие оверлеи
            app_name, existing_overlays = self._get_existing_overlays(target_hwnd)

            wx1, wy1, wx2, wy2 = window_rect
            win_width = wx2 - wx1
            win_height = wy2 - wy1

            scale_x = win_width / trans_w if trans_w > 0 else 1.0
            scale_y = win_height / trans_h if trans_h > 0 else 1.0

            created_count, skipped_count, updated_count = self._process_ocr_regions(
                regions, original_img, translated_img, window_rect, target_hwnd,
                app_name, existing_overlays, scale_x, scale_y, wx1, wy1,
                orig_w, orig_h
            )

            self._finalize_ocr_processing(created_count, skipped_count, updated_count)

        except Exception as e:
            self._handle_ocr_exception(e)

        finally:
            total_time = time.time() - total_start
            self.logger.info(f"[TIMING] ===== ИТОГО: {total_time:.3f}с =====")
            self.logger.info("[F3_HOLD] ===== ЗАВЕРШЕНИЕ ОБРАБОТКИ OCR РЕЗУЛЬТАТА =====")
            self.set_actions_blocked(False)
            self._pending_command_ids = {}
            self.is_processing_queue = False

    def _handle_ocr_error(self, error):
        """Обрабатывает ошибку OCR."""
        self.logger.error(f"[F3_HOLD] Ошибка перевода: {error}")
        # Статус ошибки убран
        self.set_actions_blocked(False)
        self._hide_translation_overlay()

    def _handle_ocr_no_result(self):
        """Обрабатывает случай отсутствия результата."""
        self.logger.error("[F3_HOLD] Результат перевода не найден")
        # Статус ошибки убран
        self.set_actions_blocked(False)
        self._hide_translation_overlay()

    def _handle_ocr_not_ready(self):
        """Обрабатывает случай, когда OCR не готов."""
        self.logger.error("[F3_HOLD] OCR не инициализирован")
        self.show_notification("❌ OCR не готов")
        # Статус ошибки убран
        self.set_actions_blocked(False)
        self._hide_translation_overlay()

    def _load_ocr_images(self, screenshot_path: Path, translated_image_path: Path):
        """Загружает оригинальное и переведенное изображения."""
        from PIL import Image
        try:
            original_img = Image.open(screenshot_path)
            translated_img = Image.open(translated_image_path)
            return original_img, translated_img
        except Exception as e:
            self.logger.error(f"[F3_HOLD] Ошибка загрузки изображений: {e}")
            self._hide_translation_overlay()
            return None, None

    def _prepare_ocr_debug_dir(self):
        """Подготавливает директорию для дебага OCR."""
        from pathlib import Path
        debug_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        return debug_dir, timestamp

    def _get_ocr_regions(self, translated_image_path: Path, debug_dir: Path, timestamp: str):
        """Получает регионы через OCR с параметрами для движка."""
        import time
        step_start = time.time()
        self.logger.info("[TIMING] Этап 4: OCR-обработка (get_regions_from_image)...")

        engine = self.settings.get_translator_engine()
        if engine == "yandex":
            # Для Яндекс - объединяем только зоны с минимальным gap (0-1px)
            regions = self.ocr_processor.get_regions_from_image(
                translated_image_path,
                save_debug=True,
                debug_dir=debug_dir,
                debug_prefix=timestamp,
                gap_coefficient=0.05,  # очень маленький коэффициент
                max_gap=2  # максимум 2px
            )
        else:
            # Для Google - стандартные параметры
            regions = self.ocr_processor.get_regions_from_image(
                translated_image_path,
                save_debug=True,
                debug_dir=debug_dir,
                debug_prefix=timestamp
            )

        ocr_time = time.time() - step_start
        self.logger.info(f"[TIMING] Этап 4: {ocr_time:.3f}с (найдено {len(regions)} областей, движок: {engine})")
        return regions

    def _save_ocr_debug_image(self, translated_img, regions, debug_dir, timestamp):
        """Сохраняет отладочное изображение с зонами."""
        from PIL import ImageDraw
        try:
            debug_img = translated_img.copy()
            draw = ImageDraw.Draw(debug_img)
            for i, (x1, y1, x2, y2) in enumerate(regions):
                draw.rectangle([x1, y1, x2, y2], outline='red', width=3)
                draw.text((x1, y1 - 20), f"#{i}", fill='red')
            debug_path = debug_dir / f"debug_translated_zones_{timestamp}.png"
            debug_img.save(debug_path)
            self.logger.info(f"[DEBUG] Отладочный скриншот сохранен: {debug_path}")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось сохранить отладочный скриншот: {e}")

    def _handle_ocr_no_text(self):
        """Обрабатывает случай, когда текст не обнаружен."""
        self.logger.info("[F3_HOLD] Текст не обнаружен")
        self.show_notification("ℹ️ Текст не обнаружен")
        # Статус убран
        self.set_actions_blocked(False)
        self._hide_translation_overlay()

    def _get_existing_overlays(self, target_hwnd):
        """Получает существующие оверлеи для приложения."""
        from src.window_utils import get_process_name_by_hwnd
        app_name = get_process_name_by_hwnd(target_hwnd) if target_hwnd else None
        existing_overlays = []
        if self.overlay_manager and app_name:
            existing_overlays = self.overlay_manager.get_overlays_by_app_name(app_name)
            self.logger.info(f"[F3_HOLD] Найдено {len(existing_overlays)} существующих оверлеев для {app_name}")
        return app_name, existing_overlays

    def _process_ocr_regions(self, regions, original_img, translated_img, window_rect, target_hwnd,
                             app_name, existing_overlays, scale_x, scale_y, wx1, wy1,
                             orig_w, orig_h):
        """Обрабатывает все OCR регионы — ТОЛЬКО ДОБАВЛЯЕТ ШАБЛОНЫ В МОНИТОР, без создания оверлеев."""

        import time
        from pathlib import Path

        loop_start = time.time()
        self.logger.info(f"[TIMING] Этап 7: Обработка {len(regions)} зон...")

        created_count = 0
        skipped_count = 0

        # Временно отключаем сохранение состояния, чтобы не создавать лишних записей
        if hasattr(self.overlay_manager, '_suppress_save'):
            self.overlay_manager._suppress_save = True

        for i, (x1, y1, x2, y2) in enumerate(regions):
            zone_start = time.time()
            try:
                screen_x1 = wx1 + int(x1 * scale_x)
                screen_y1 = wy1 + int(y1 * scale_y)
                screen_x2 = wx1 + int(x2 * scale_x)
                screen_y2 = wy1 + int(y2 * scale_y)

                if screen_x2 <= screen_x1 or screen_y2 <= screen_y1:
                    continue

                region_window_rect = (screen_x1, screen_y1, screen_x2, screen_y2)
                region_area = (screen_x2 - screen_x1) * (screen_y2 - screen_y1)

                # Проверяем пересечение с существующими оверлеями
                existing_overlay = self._find_overlapping_overlay(existing_overlays, region_window_rect, region_area)

                if existing_overlay:
                    skipped_count += 1
                    self.logger.info(f"[F3_HOLD] Зона #{i} пропущена (уже занята)")
                    continue

                # === ИЗМЕНЕНИЕ: НЕ создаем оверлей, только добавляем шаблон в монитор ===
                # Сохраняем регион изображения как шаблон
                region_img = translated_img.crop((x1, y1, x2, y2))
                region_path = self.temp_dir / f"ocr_region_{i}_{int(time.time())}.png"
                region_img.save(region_path)

                # Сохраняем соответствующий участок оригинального изображения для шаблона
                orig_x1 = max(0, min(screen_x1 - wx1, orig_w))
                orig_y1 = max(0, min(screen_y1 - wy1, orig_h))
                orig_x2 = max(0, min(screen_x2 - wx1, orig_w))
                orig_y2 = max(0, min(screen_y2 - wy1, orig_h))

                if orig_x2 > orig_x1 and orig_y2 > orig_y1:
                    template_path = self.temp_dir / f"template_{i}_{int(time.time())}.png"
                    template_img = original_img.crop((orig_x1, orig_y1, orig_x2, orig_y2))
                    template_img.save(template_path)

                    # Добавляем шаблон в монитор — оверлей будет создан автоматически при нахождении
                    if self.translation_monitor:
                        pair_index, file_hash = self.translation_monitor.add_template(
                            region_image=template_path,
                            translated_image=region_path,
                            target_app_name=app_name,
                            is_temporary=False,
                            lifetime_seconds=180
                        )

                        if pair_index >= 0 and file_hash:
                            created_count += 1
                            self.logger.info(
                                f"[F3_HOLD] Шаблон #{pair_index} добавлен в монитор (оверлей будет создан при нахождении)")
                        else:
                            self.logger.warning(f"[F3_HOLD] Не удалось добавить шаблон #{i} в монитор")
                    else:
                        self.logger.warning("[F3_HOLD] TranslationMonitor не инициализирован, шаблон не добавлен")

            except Exception as e:
                self.logger.error(f"[F3_HOLD] Ошибка обработки зоны {i}: {e}")

            zone_time = time.time() - zone_start
            if zone_time > 0.1:
                self.logger.info(f"[TIMING] Зона #{i} обработана за {zone_time:.3f}с")

        loop_time = time.time() - loop_start
        self.logger.info(
            f"[TIMING] Этап 7: {loop_time:.3f}с (добавлено шаблонов: {created_count}, пропущено: {skipped_count})"
        )

        if hasattr(self.overlay_manager, '_suppress_save'):
            self.overlay_manager._suppress_save = False

        return created_count, skipped_count, 0

    def _find_overlapping_overlay(self, existing_overlays, region_window_rect, region_area):
        """Находит существующий оверлей, перекрывающий регион."""
        for overlay in existing_overlays:
            if overlay._last_window_rect:
                ox1, oy1, ox2, oy2 = overlay._last_window_rect
                overlap_x1 = max(region_window_rect[0], ox1)
                overlap_y1 = max(region_window_rect[1], oy1)
                overlap_x2 = min(region_window_rect[2], ox2)
                overlap_y2 = min(region_window_rect[3], oy2)
                if overlap_x2 > overlap_x1 and overlap_y2 > overlap_y1:
                    overlap_area = (overlap_x2 - overlap_x1) * (overlap_y2 - overlap_y1)
                    if overlap_area > region_area * 0.3:
                        return overlay
        return None

    def _create_overlay_for_region(self, i, x1, y1, x2, y2, translated_img, region_window_rect,
                                   target_hwnd, app_name, existing_overlays, original_img,
                                   orig_w, orig_h, wx1, wy1):
        """Создает оверлей для одного региона."""
        import time
        from pathlib import Path

        try:
            region_img = translated_img.crop((x1, y1, x2, y2))
            region_path = self.temp_dir / f"ocr_region_{i}_{int(time.time())}.png"
            region_img.save(region_path)

            overlay = self.overlay_manager._create_overlay_from_data(
                image_path=region_path,
                window_rect=region_window_rect,
                target_hwnd=target_hwnd,
                is_auto_replace=True,
                is_window_screenshot=True,
                template_id=None,
                show_immediately=True,
                is_temporary=False,
                lifetime_seconds=180,
                app_name=app_name
            )

            if overlay:
                overlay._is_visible_by_user = True
                overlay._hidden_by_user = False
                if not overlay.visible:
                    overlay.show()
                existing_overlays.append(overlay)

                # Добавляем шаблон в монитор
                self._add_template_to_monitor(
                    overlay, region_window_rect, original_img, orig_w, orig_h,
                    wx1, wy1, app_name, i
                )
                return True
        except Exception as e:
            self.logger.error(f"[F3_HOLD] Ошибка создания оверлея {i}: {e}")
        return False

    def _add_template_to_monitor(self, overlay, region_window_rect, original_img,
                                 orig_w, orig_h, wx1, wy1, app_name, i):
        """Добавляет шаблон в монитор для автозамены."""
        import time
        from pathlib import Path

        if not self.translation_monitor or not self.settings.get_auto_replace_translated():
            return

        try:
            screen_x1, screen_y1, screen_x2, screen_y2 = region_window_rect

            orig_x1 = max(0, min(screen_x1 - wx1, orig_w))
            orig_y1 = max(0, min(screen_y1 - wy1, orig_h))
            orig_x2 = max(0, min(screen_x2 - wx1, orig_w))
            orig_y2 = max(0, min(screen_y2 - wy1, orig_h))

            if orig_x2 > orig_x1 and orig_y2 > orig_y1:
                template_path = self.temp_dir / f"template_{i}_{int(time.time())}.png"
                template_img = original_img.crop((orig_x1, orig_y1, orig_x2, orig_y2))
                template_img.save(template_path)

                # Используем translated_path из оверлея
                translated_path = overlay._last_image_path

                pair_index, file_hash = self.translation_monitor.add_template(
                    region_image=template_path,
                    translated_image=translated_path,
                    target_app_name=app_name,
                    is_temporary=False,
                    lifetime_seconds=180
                )

                if pair_index >= 0 and file_hash:
                    overlay._template_id = file_hash
                    for template_data in self.translation_monitor.templates:
                        if template_data.get('hash') == file_hash:
                            template_data['overlay'] = overlay
                            template_data['found'] = False
                            template_data['offset_x'] = 0
                            template_data['offset_y'] = 0
                            template_data['offset_initialized'] = True
                            template_data['overlay_width'] = screen_x2 - screen_x1
                            template_data['overlay_height'] = screen_y2 - screen_y1
                            self.logger.info(f"[F3_HOLD] Шаблон #{pair_index} добавлен в монитор")
                            break
        except Exception as e:
            self.logger.warning(f"[F3_HOLD] Не удалось создать шаблон: {e}")

    def _finalize_ocr_processing(self, created_count, skipped_count, updated_count):
        """Завершает обработку OCR."""
        total_count = created_count + updated_count
        self.logger.info(
            f"[F3_HOLD] Создано {created_count} новых оверлеев, пропущено {skipped_count} занятых зон"
        )
        self.ui.root.after(500, self.window_list.refresh)

        if created_count > 0 or skipped_count > 0:
            self.logger.info("[F3_HOLD] Обработка завершена, скрываем индикатор")
            self._hide_translation_overlay()
        else:
            self.logger.info("[F3_HOLD] Не создано ни одного оверлея, скрываем индикатор")
            self._hide_translation_overlay()

        if created_count > 0:
            self.show_notification(f"✅ {created_count} оверлеев создано ({skipped_count} пропущено)")
            # Статус убран
        else:
            if skipped_count > 0:
                self.show_notification(f"ℹ️ Все {skipped_count} зон уже заняты оверлеями")
                # Статус убран
            else:
                self.show_notification("⚠️ Не удалось создать оверлеи")
                # Статус убран

    def _handle_ocr_exception(self, e):
        """Обрабатывает исключение в OCR."""
        self.logger.error(f"[F3_HOLD] Ошибка OCR: {e}")
        import traceback
        traceback.print_exc()
        self.show_notification(f"❌ Ошибка OCR: {str(e)[:30]}")
        self.ui.update_status("● " + self.ui.get_string('error'), '#f44336')
        self._hide_translation_overlay()

    def _get_app_name_by_hwnd(self, hwnd: int) -> str:
        """Возвращает имя приложения по HWND."""
        try:
            from src.window_utils import get_process_name_by_hwnd
            return get_process_name_by_hwnd(hwnd, default_name="Неизвестно")
        except Exception as e:
            self.logger.warning(f"[WINDOW] Ошибка получения имени по HWND: {e}")
            return "Неизвестно"

    def clear_all_overlays(self):
        """
        Удаляет последний перетащенный F2-оверлей.
        Если такого нет - удаляет оверлеи для текущего приложения.
        """
        self.logger.info("[CLEAR_ALL] Начинаем удаление оверлеев")

        if not self.overlay_manager:
            self.logger.warning("[CLEAR_ALL] OverlayManager не инициализирован")
            self.show_notification(self.get_string('notification_remove_no_app'))
            return

        # ============================================================
        # 1. ПРОВЕРЯЕМ: ЕСТЬ ЛИ ПОСЛЕДНИЙ ПЕРЕТАЩЕННЫЙ F2-ОВЕРЛЕЙ
        # ============================================================
        if hasattr(self, '_last_dragged_f2_overlay') and self._last_dragged_f2_overlay:
            overlay = self._last_dragged_f2_overlay

            try:
                if overlay and overlay.root and overlay.root.winfo_exists():
                    app_name = overlay._app_name or "Неизвестно"
                    self.logger.info(f"[CLEAR_ALL] Удаляем последний перетащенный F2-оверлей для {app_name}")
                    self._clear_single_overlay(overlay)
                    self._last_dragged_f2_overlay = None
                    self.show_notification(f"🗑️ Удалён перетащенный оверлей для {app_name}")
                    return
                else:
                    self._last_dragged_f2_overlay = None
                    self.logger.info("[CLEAR_ALL] Последний перетащенный оверлей уже удалён")
            except Exception as e:
                self.logger.warning(f"[CLEAR_ALL] Ошибка проверки перетащенного оверлея: {e}")
                self._last_dragged_f2_overlay = None

        # ============================================================
        # 2. ПРОВЕРЯЕМ ОВЕРЛЕЙ ПОД КУРСОРОМ
        # ============================================================
        overlay_under_cursor = self._get_overlay_under_cursor()

        if overlay_under_cursor:
            self.logger.info(f"[CLEAR_ALL] Найден оверлей под курсором, удаляем")
            app_name = overlay_under_cursor._app_name or "Неизвестно"
            self._clear_single_overlay(overlay_under_cursor)
            self.show_notification(f"🗑️ Удалён оверлей для {app_name}")
            return

        # ============================================================
        # 3. УДАЛЯЕМ ПО ИМЕНИ ПРИЛОЖЕНИЯ
        # ============================================================
        current_app = self._get_current_app_name()
        self.logger.info(f"[CLEAR_ALL] Текущее приложение: {current_app}")

        if not current_app:
            self.logger.warning("[CLEAR_ALL] Не удалось определить текущее приложение")
            self.show_notification(self.get_string('notification_remove_no_app'))
            return

        overlays_for_app = self.overlay_manager.get_overlays_by_app_name(current_app)

        if not overlays_for_app:
            self.logger.info(f"[CLEAR_ALL] Нет оверлеев для приложения {current_app}")

            # Проверяем, есть ли вообще оверлеи
            total_overlays = len(self.overlay_manager.overlays)
            if total_overlays > 0:
                self.show_notification(f"ℹ️ Нет оверлеев для {current_app} (есть для других приложений)")
            else:
                self.show_notification(f"ℹ️ Нет оверлеев для удаления")
            return

        overlays_count = len(overlays_for_app)
        self.logger.info(f"[CLEAR_ALL] Найдено {overlays_count} оверлеев для приложения {current_app}")

        # Останавливаем сохранение состояния во время массового удаления
        if hasattr(self.overlay_manager, '_suppress_save'):
            self.overlay_manager._suppress_save = True

        try:
            if hasattr(self.overlay_manager, 'remove_all_overlays_for_app'):
                self.overlay_manager.remove_all_overlays_for_app(current_app, force=True)
            else:
                for overlay in overlays_for_app[:]:
                    try:
                        self.overlay_manager.remove_overlay(overlay, force=True)
                    except Exception as e:
                        self.logger.error(f"[CLEAR_ALL] Ошибка удаления оверлея: {e}")
        finally:
            if hasattr(self.overlay_manager, '_suppress_save'):
                self.overlay_manager._suppress_save = False

        # Удаляем состояние из файла
        self._remove_app_state_from_file(current_app)

        # Принудительно сохраняем состояние
        self.overlay_manager.save_overlay_state(immediate=True)

        # Обновляем список окон
        self.ui.root.after(100, lambda: self.window_list.refresh(skip_restore=True))

        self.show_notification(
            self.get_string('clear_all_completed').format(app_name=current_app, count=overlays_count)
        )
        self.logger.info(f"[CLEAR_ALL] Очистка завершена для {current_app}")

    def get_string(self, key: str) -> str:
        """Возвращает локализованную строку"""
        if hasattr(self, 'settings'):
            return self.settings.get_string(key)
        return key

    def _get_current_app_name(self) -> Optional[str]:
        """
        Возвращает имя текущего активного приложения.
        Игнорирует python.exe (главное окно программы) и возвращает предыдущее активное приложение.
        """
        try:
            import win32gui
            from src.window_utils import get_process_name_by_hwnd

            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                self.logger.warning("[WINDOW] Не удалось получить активное окно")
                return self._last_valid_app_name if hasattr(self, '_last_valid_app_name') else None

            app_name = get_process_name_by_hwnd(hwnd)
            self.logger.info(f"[WINDOW] Текущее активное приложение: {app_name}")

            if app_name and app_name.lower() == "python.exe":
                self.logger.info("[WINDOW] Активное окно - python.exe (игнорируем), возвращаем предыдущее")
                return self._last_valid_app_name if hasattr(self, '_last_valid_app_name') else None

            self._last_valid_app_name = app_name
            return app_name

        except Exception as e:
            self.logger.warning(f"[WINDOW] Ошибка получения имени текущего окна: {e}")
            return self._last_valid_app_name if hasattr(self, '_last_valid_app_name') else None

    def toggle_overlay(self):
        """Переключает видимость оверлеев (F1) с запоминанием состояния"""
        self.logger.info("[DEBUG] toggle_overlay вызван")

        if not self.overlay_manager:
            self.logger.warning("toggle_overlay: менеджер оверлеев не инициализирован")
            return

        if not self.overlay_manager.overlays:
            self.logger.info("toggle_overlay: нет активных оверлеев")
            self.show_notification(self.get_string('overlay_toggle_no_overlays'))
            return

        # ============================================================
        # Проверяем, есть ли сохранённое состояние F1
        # ============================================================
        if self.overlay_manager._f1_state:
            # Есть сохранённое состояние - восстанавливаем его
            self.logger.info("[F1] Восстанавливаем сохранённое состояние")
            self.overlay_manager.restore_f1_state()

            # Очищаем состояние после восстановления
            self.overlay_manager._f1_state.clear()
            self.show_notification("👁️ Восстановлено предыдущее состояние оверлеев")
            return

        # ============================================================
        # Нет сохранённого состояния - сохраняем текущее и переключаем
        # ============================================================

        # Сохраняем текущее состояние всех оверлеев
        self.overlay_manager.save_f1_state()

        # Переключаем все оверлеи (инвертируем видимость)
        all_visible = all(ov.visible for ov in self.overlay_manager.overlays if ov is not None)
        new_state = not all_visible

        self.logger.info(
            f"[F1] Переключаем все {len(self.overlay_manager.overlays)} оверлеев в состояние: {'показаны' if new_state else 'скрыты'}")

        for overlay in self.overlay_manager.overlays:
            try:
                if overlay is None or not overlay.root or not overlay.root.winfo_exists():
                    continue

                if new_state:
                    # Показываем оверлей
                    overlay._hidden_by_user = False
                    overlay._is_visible_by_user = True
                    if not overlay.visible:
                        overlay.show()
                else:
                    # Скрываем оверлей
                    overlay._hidden_by_user = True
                    overlay._is_visible_by_user = False
                    if overlay.visible:
                        overlay.hide(by_user=True)
            except Exception as e:
                self.logger.error(f"Ошибка при переключении оверлея: {e}")

        self.overlay_manager.save_overlay_state()

        status_text = "показаны" if new_state else "скрыты"
        self.show_notification(f"👁️ Все оверлеи {status_text}")
        self.logger.info(f"F1: все оверлеи {status_text}")

    def _clear_window_state(self, app_name: str):
        """Очищает состояние для указанного приложения."""
        if app_name in self._window_states:
            del self._window_states[app_name]
            self.logger.info(f"[STATE] Состояние очищено для {app_name}")

    def _on_init_complete(self, result, error):
        """Завершение инициализации (восстанавливает оверлеи из сохранённого состояния)"""
        if error:
            self.logger.error(f"Ошибка инициализации: {error}")
            self.initializing = False
            # Статус ошибки убран — только лог
            self.ui.root.after(self._init_retry_delay, self._init_translator_step)
            return

        self.logger.info("Инициализация завершена")
        self.ready = True
        self.initializing = False
        self._init_done = True
        self._init_attempts = 0

        # Сохраняем используемый движок
        self._last_engine = self.settings.get_translator_engine()
        engine_name = "Google Translate" if self._last_engine == "google" else "Яндекс.Переводчик (OCR)"
        self.logger.info(f"[APP] Используется движок: {engine_name}")

        # ============================================================
        # Переустанавливаем горячие клавиши после инициализации
        # ============================================================
        if hasattr(self, 'hotkeys'):
            self.hotkeys.setup()
            self.logger.info("[APP] Горячие клавиши переустановлены после инициализации браузера")

        # ============================================================
        # Создаём компоненты заново (как при первом запуске)
        # ============================================================

        # Создаём OverlayManager, если его нет
        if not self.overlay_manager:
            self.overlay_manager = OverlayManager(self)
            self.logger.info("[APP] OverlayManager создан")

        # Создаём TranslationMonitor, если его нет
        if not self.translation_monitor:
            self.translation_monitor = TranslationMonitor(self, self.overlay_manager, self.settings)
            self.logger.info("[APP] TranslationMonitor создан")

        # ============================================================
        # ВОССТАНАВЛИВАЕМ ОВЕРЛЕИ ИЗ СОХРАНЁННОГО СОСТОЯНИЯ
        # ============================================================
        restored_count = 0
        if self.overlay_manager:
            try:
                restored_count = self.overlay_manager.restore_overlays_from_state(self)
                if restored_count > 0:
                    self.logger.info(f"[STATE] Восстановлено {restored_count} оверлеев из сохранённого состояния")
                    self.ui.root.after(500, self.window_list.refresh)
                else:
                    self.logger.info("[STATE] Нет сохранённых оверлеев для восстановления")
            except Exception as e:
                self.logger.error(f"[STATE] Ошибка восстановления оверлеев: {e}")

        # Разблокируем меню настроек
        if hasattr(self.ui, 'settings_btn'):
            self.ui.settings_btn.config(state=tk.NORMAL, bg='#3c3c3c', fg='#cccccc')

        self.ui.set_settings_menu_enabled(True)

        # Обновляем статус на "Готов"
        ready_text = self.ui.get_string('ready')
        self.logger.info(f"[STATUS] Обновление статуса на: {ready_text}")
        self.ui.update_status(f"● {ready_text} ({engine_name})", '#4CAF50')
        self.logger.info("[STATUS] Статус обновлён на Готов")

        self.window_list.refresh()
        self.logger.info("Инициализация полностью завершена, статус: Готов")

        # Показываем уведомление о готовности
        self.show_notification(f"✅ {self.ui.get_string('ready_notification')} ({engine_name})", 2000)

    def _on_window_switch(self, new_hwnd):
        """Обработчик переключения окон - показывает/скрывает оверлеи при переключении"""

        if new_hwnd == self._current_active_hwnd:
            return

        try:
            import win32gui
            class_name = win32gui.GetClassName(new_hwnd)
            window_text = win32gui.GetWindowText(new_hwnd)
            if class_name == "TkTopLevel" and window_text == "Перевод":
                return
        except:
            pass

        old_hwnd = self._current_active_hwnd
        self._current_active_hwnd = new_hwnd

        if new_hwnd:
            try:
                from src.window_utils import get_process_name_by_hwnd
                app_name = get_process_name_by_hwnd(new_hwnd, default_name="Неизвестно")
                self._auto_switch_fullscreen_window(new_hwnd, app_name)
            except Exception as e:
                self.logger.warning(f"[WINDOW] Ошибка авто-переключения: {e}")

        if not self.overlay_manager:
            return

        if self.overlay_manager.is_dragging():
            return

        try:
            from src.window_utils import get_process_name_by_hwnd
            active_app_name = get_process_name_by_hwnd(new_hwnd, default_name="Неизвестно") if new_hwnd else None

            if active_app_name and active_app_name.lower() != "python.exe":
                self._last_valid_app_name = active_app_name
                self.logger.info(f"[WINDOW] Запомнено валидное приложение: {active_app_name}")

        except:
            active_app_name = None

        auto_hide_enabled = self.settings.get_auto_hide_overlay() if hasattr(self, 'settings') else True

        if active_app_name:
            f2_overlays = []
            for overlay in self.overlay_manager.get_overlays_by_app_name(active_app_name):
                if hasattr(overlay, '_is_f2_overlay') and overlay._is_f2_overlay:
                    f2_overlays.append(overlay)

            if f2_overlays:
                self.logger.info(f"[WINDOW] Найдено {len(f2_overlays)} F2-оверлеев для {active_app_name}")

                if not auto_hide_enabled:
                    self.logger.info(f"[WINDOW] Auto-hide выключен, показываем ВСЕ F2-оверлеи для {active_app_name}")
                    for overlay in f2_overlays:
                        try:
                            if not overlay._hidden_by_user:
                                overlay._is_visible_by_user = True
                                if not overlay.visible:
                                    overlay.show()
                                    self.logger.info(
                                        f"[WINDOW] Показан F2-оверлей для {active_app_name} (auto-hide OFF)")
                        except Exception as e:
                            self.logger.warning(f"[WINDOW] Ошибка показа F2-оверлея: {e}")
                else:
                    self.logger.info(f"[WINDOW] Auto-hide включен, показываем F2-оверлеи для активного окна")
                    for overlay in f2_overlays:
                        try:
                            if not overlay._hidden_by_user:
                                overlay._is_visible_by_user = True
                                if not overlay.visible:
                                    overlay.show()
                                    self.logger.info(
                                        f"[WINDOW] Показан F2-оверлей для {active_app_name} (auto-hide ON)")
                        except Exception as e:
                            self.logger.warning(f"[WINDOW] Ошибка показа F2-оверлея: {e}")

        if auto_hide_enabled:
            for app_name, overlays in list(self.overlay_manager.overlays_by_app_name.items()):
                if app_name != active_app_name:
                    for overlay in overlays:
                        try:
                            if overlay.visible:
                                is_f2 = hasattr(overlay, '_is_f2_overlay') and overlay._is_f2_overlay
                                if is_f2:
                                    overlay.hide(by_user=False)
                                    self.logger.info(
                                        f"[WINDOW] Скрыт F2-оверлей для {app_name} (не активно, auto-hide ON)")
                                else:
                                    overlay.hide(by_user=False)
                                    self.logger.info(f"[WINDOW] Скрыт оверлей для {app_name} (не активно)")
                        except Exception as e:
                            self.logger.warning(f"[WINDOW] Ошибка скрытия оверлея: {e}")
        else:
            self.logger.info("[WINDOW] Auto-hide выключен, F2-оверлеи не скрываются при переключении окон")

        if hasattr(self, 'translation_monitor') and self.translation_monitor and auto_hide_enabled:
            monitor = self.translation_monitor
            for template_data in monitor.templates:
                target_app = template_data.get('target_app_name')
                overlay = template_data.get('overlay')
                if overlay and overlay.visible:
                    if target_app and target_app != "Неизвестно" and target_app != active_app_name:
                        try:
                            overlay.hide(by_user=False)
                            self.logger.info(
                                f"[WINDOW] Скрыт оверлей для {target_app} (не соответствует активному {active_app_name})"
                            )
                        except Exception as e:
                            self.logger.warning(f"[WINDOW] Ошибка скрытия оверлея: {e}")

        self.logger.info(
            f"[WINDOW] Переключение на {active_app_name}, оверлеи будут показаны монитором при нахождении шаблонов"
        )

    def toggle_edit_mode(self):
        """Переключает режим редактирования"""
        if not self.overlay_manager:
            return

        self._edit_mode_enabled = not getattr(self, '_edit_mode_enabled', False)
        self.settings.set_edit_mode_enabled(self._edit_mode_enabled)

        # Обновляем все оверлеи (только режим редактирования, без принудительного показа)
        self.overlay_manager.update_edit_mode_for_all(self._edit_mode_enabled)

        status_text = "включён" if self._edit_mode_enabled else "выключен"
        status_color = '#4CAF50' if self._edit_mode_enabled else '#ff9800'

        self.ui.update_status(f"● Режим редактирования {status_text}", status_color)
        self.show_notification(f"✏️ Режим редактирования {status_text}")

        if self._edit_mode_enabled:
            # Включаем режим: отключаем автоскрытие и монитор видимости
            for overlay in self.overlay_manager.overlays:
                try:
                    overlay.auto_hide_enabled = False
                    overlay._stop_visibility_monitor()
                    # НЕ ПОКАЗЫВАЕМ ОВЕРЛЕЙ ПРИНУДИТЕЛЬНО!
                    # Оверлеи показываются только когда монитор находит шаблон
                except Exception as e:
                    self.logger.warning(f"[EDIT_MODE] Ошибка настройки оверлея: {e}")
        else:
            # Выключаем режим: включаем автоскрытие
            for overlay in self.overlay_manager.overlays:
                try:
                    overlay.auto_hide_enabled = True
                    if overlay.visible:
                        overlay._start_visibility_monitor()
                except Exception as e:
                    self.logger.warning(f"[EDIT_MODE] Ошибка настройки оверлея: {e}")

    def process(self):
        """Скриншот окна (F2)"""
        if self.translating or not self.ready:
            return

        self.set_actions_blocked(True)
        current_hwnd = win32gui.GetForegroundWindow()
        if current_hwnd:
            self.screenshot._last_hwnd = current_hwnd
            self.screenshot._is_fullscreen = self.screenshot.is_window_fullscreen(current_hwnd)

        self.translating = True
        # Убираем статус "translating" — только лог
        self.logger.info("[F2] Захват скриншота...")
        self.show_notification(self.get_string('notification_capturing'))

        def capture_task():
            try:
                from PIL import Image
                img = self.screenshot.capture_active_window()
                if not img:
                    # Ошибка захвата — только лог
                    self.logger.error("[F2] Ошибка захвата окна")
                    self.translating = False
                    self.set_actions_blocked(False)
                    return

                self.ui.root.after(0, self._show_translation_overlay)
                path = self.temp_dir / f"scr_{int(time.time())}.png"
                img.save(path)

                task = {'type': 'screenshot', 'image_path': path, 'area_rect': None}
                self.translation_queue.append(task)
                self.translating = False

                if not self.is_processing_queue:
                    self._process_next_in_queue()
            except Exception as e:
                self.logger.error(f"Ошибка захвата: {e}")
                self.translating = False
                self.set_actions_blocked(False)

        threading.Thread(target=capture_task, daemon=True).start()

    def _on_translate_finished(self, result, error):
        self.logger.info(f"[DEBUG] === _on_translate_finished НАЧАЛО ===")
        self.logger.info(f"[DEBUG] result={result}, error={error}")

        self._translation_in_progress = False
        self._total_tasks_processed = getattr(self, '_total_tasks_processed', 0) + 1

        try:
            if error and "отменен" in str(error):
                self.logger.info("[DEBUG] перевод был отменен")
                self.translating = False
                self._pending_command_ids = {}
                self._pending_area_rect = None
                self.is_processing_queue = False
                self.set_actions_blocked(False)
                self._hide_translation_overlay()
                self._process_next_in_queue()
                return

            if error:
                self.logger.error(f"Ошибка перевода: {error}")
                self._hide_translation_overlay()
                return

            is_temporary = getattr(self, '_is_temporary_translation', False)
            self._is_temporary_translation = False

            overlay_created = False

            if result and self.overlay_manager:
                self.logger.info(f"Результат перевода получен: {result}")
                self.show_notification(self.get_string('notification_translation_ready'))

                region_path = getattr(self, '_pending_region_path', None)
                auto_replace_enabled = self.settings.get_auto_replace_translated()

                lifetime_seconds = self.settings.get_temporary_lifetime() if is_temporary else 180

                if region_path and region_path.exists() and self.translation_monitor and auto_replace_enabled:
                    target_hwnd = self.screenshot.get_last_hwnd()
                    from src.window_utils import get_process_name_by_hwnd
                    target_app_name = get_process_name_by_hwnd(target_hwnd) if target_hwnd else None

                    add_result = self.translation_monitor.add_template(
                        region_path, result,
                        target_app_name,
                        is_temporary=is_temporary,
                        lifetime_seconds=lifetime_seconds
                    )
                    if add_result and len(add_result) == 2:
                        pair_index, file_hash = add_result
                        self.logger.info(
                            f"[DEBUG] {'Временный' if is_temporary else 'Постоянный'} шаблон #{pair_index} добавлен в монитор, время жизни: {lifetime_seconds}с"
                        )
                        overlay_created = True
                    else:
                        self.logger.warning("[DEBUG] Не удалось добавить шаблон в монитор")
                else:
                    target_hwnd = self.screenshot.get_last_hwnd()
                    window_rect = getattr(self, '_pending_area_rect', None) or self.screenshot.get_last_window_rect()

                    if target_hwnd and window_rect:
                        self.logger.info(f"[DEBUG] Создаем оверлей сразу (автозамена выключена или нет region_path)")

                        from src.window_utils import get_process_name_by_hwnd
                        app_name = get_process_name_by_hwnd(target_hwnd) if target_hwnd else None

                        overlay = self.overlay_manager._create_overlay_from_data(
                            image_path=result,
                            window_rect=window_rect,
                            target_hwnd=target_hwnd,
                            is_auto_replace=False,
                            is_window_screenshot=(region_path is None),
                            template_id=None,
                            show_immediately=True,
                            is_temporary=is_temporary,
                            lifetime_seconds=lifetime_seconds,
                            app_name=app_name,
                            force_edit_mode=True  # <-- ВСЕГДА ВКЛЮЧАЕМ РЕЖИМ РЕДАКТИРОВАНИЯ ДЛЯ F2
                        )

                        if overlay:
                            overlay._is_visible_by_user = True
                            overlay._hidden_by_user = False
                            if not overlay.visible:
                                overlay.show()
                            self.ui.root.after(100, self.window_list.refresh)
                            overlay_created = True

                    self._pending_region_path = None

            else:
                self.logger.warning("Результат перевода пустой")
                self.show_notification("Ошибка перевода")

            if overlay_created:
                self.logger.info("[DEBUG] Оверлей создан, скрываем индикатор")
                self._hide_translation_overlay()
            else:
                self.logger.info("[DEBUG] Оверлей НЕ создан, скрываем индикатор (fallback)")
                self._hide_translation_overlay()

        except Exception as e:
            self.logger.error(f"Ошибка показа результата: {e}")
            import traceback
            traceback.print_exc()
            self.show_notification("Ошибка при обработке перевода")
            self._hide_translation_overlay()

        finally:
            self.translating = False
            self._pending_command_ids = {}
            self._pending_area_rect = None
            self.is_processing_queue = False
            self.set_actions_blocked(False)

            if self.translation_queue:
                self._process_next_in_queue()
            else:
                self.logger.info("[DEBUG] Очередь пуста")

    def toggle_auto_replace_mode(self):
        if not self.translation_monitor:
            return
        current = self.settings.get_auto_replace_translated()
        new_state = not current
        self.settings.set_auto_replace_translated(new_state)
        if new_state and self.translation_monitor.templates:
            self.translation_monitor.start()
        else:
            self.translation_monitor.stop()
        status_text = "включена" if new_state else "выключена"
        self.show_notification(f"Автозамена {status_text}")

    def capture_area(self):
        if not self.ready or self.initializing or self._capture_mode:
            return

        # Убеждаемся, что ESC не заблокирован перед открытием окна выбора области
        try:
            import keyboard
            keyboard.unblock_key('esc')
            self.logger.info("[F3] ESC разблокирован перед открытием окна выбора области")
        except Exception as e:
            self.logger.warning(f"[F3] Не удалось разблокировать ESC: {e}")

        self.set_actions_blocked(True)
        self._capture_mode = True
        try:
            self.ui.root.iconify()
        except:
            pass
        self.ui.root.after(300, self._capture_window_for_area)

        # === ПРИНУДИТЕЛЬНЫЙ ЗАХВАТ ФОКУСА ДЛЯ ESC ===
        def ensure_esc_capture():
            try:
                if hasattr(self, '_area_selector') and self._area_selector:
                    if self._area_selector.root and self._area_selector.root.winfo_exists():
                        self._area_selector.root.focus_force()
                        self._area_selector.root.grab_set()
                        self.logger.info("[F3] Принудительный захват фокуса для ESC")
            except:
                pass

        self.ui.root.after(500, ensure_esc_capture)

    def _on_translate_error(self, error_msg):
        self.logger.error(f"Ошибка перевода: {error_msg}")
        self._translation_in_progress = False
        # Статус ошибки убран
        self.translating = False
        self.set_actions_blocked(False)
        self._hide_translation_overlay()
        self.show_notification(f"Ошибка: {error_msg[:30]}")

    def show_notification(self, text, duration_ms=1500):
        if hasattr(self, 'notification'):
            self.notification.show(text, duration_ms)

    def _cancel_translation(self):
        """Отменяет текущий перевод"""
        if not self._translation_in_progress:
            return
        self.logger.info("[DEBUG] _cancel_translation: отменяем перевод")
        if self.browser_worker:
            self.browser_worker.cancel_translation()
        self._translation_in_progress = False
        self._hide_translation_overlay()
        self.translating = False
        self.set_actions_blocked(False)

    def _capture_window_for_area(self):
        """Захват окна для области"""
        try:
            from PIL import ImageGrab
            from src.window_utils import make_windowed_fullscreen
            import time

            current_hwnd = win32gui.GetForegroundWindow()
            if not current_hwnd:
                # Ошибка захвата — только лог
                self.logger.error("[F3] Не удалось получить активное окно")
                self._capture_mode = False
                self.set_actions_blocked(False)
                self.ui.root.deiconify()
                return

            self.screenshot._last_hwnd = current_hwnd
            self._area_target_hwnd = current_hwnd
            self.screenshot._is_fullscreen = self.screenshot.is_window_fullscreen(current_hwnd)
            self._area_is_fullscreen = self.screenshot._is_fullscreen

            if self._area_is_fullscreen:
                self.logger.info("[F3] Переключение окна в оконный полноэкранный режим")

                try:
                    import keyboard
                    keyboard.press_and_release('alt+enter')
                    self.logger.info("[F3] Alt+Enter отправлен")
                    time.sleep(0.5)
                except Exception as e:
                    self.logger.warning(f"[F3] Не удалось отправить Alt+Enter: {e}")

                make_windowed_fullscreen(current_hwnd)
                time.sleep(0.3)
                self.logger.info("[F3] Окно переключено в оконный полноэкранный режим")

            img = ImageGrab.grab()
            if not img:
                # Ошибка захвата — только лог
                self.logger.error("[F3] Ошибка захвата экрана")
                self._capture_mode = False
                self.set_actions_blocked(False)
                self.ui.root.deiconify()
                return

            screenshot_path = self.temp_dir / f"area_screenshot_{int(time.time())}.png"
            img.save(screenshot_path)

            self._show_continuous_area_selection_window(screenshot_path)
        except Exception as e:
            self.logger.error(f"Ошибка захвата области: {e}")
            # Ошибка — только лог
            self._capture_mode = False
            self.set_actions_blocked(False)
            self.ui.root.deiconify()

    def set_actions_blocked(self, blocked):
        """Блокирует/разблокирует горячие клавиши на системном уровне"""
        if hasattr(self, 'hotkeys'):
            self.hotkeys.set_actions_blocked(blocked)
            if blocked:
                self.logger.info("[HOTKEYS] Горячие клавиши заблокированы на системном уровне")
                # Дополнительная блокировка через keyboard
                try:
                    import keyboard
                    keyboard.block_key('f4')
                    keyboard.block_key('f1')
                    keyboard.block_key('f2')
                    keyboard.block_key('f3')
                    keyboard.block_key('f5')
                    keyboard.block_key('f6')
                    # НЕ БЛОКИРУЕМ ESC, чтобы он работал в окне выбора области
                    # keyboard.block_key('esc')  # <-- УДАЛЕНО
                    self.logger.info("[HOTKEYS] Дополнительная блокировка клавиш через block_key (ESC не блокируется)")
                except Exception as e:
                    self.logger.warning(f"[HOTKEYS] Не удалось заблокировать клавиши: {e}")
            else:
                self.logger.info("[HOTKEYS] Горячие клавиши разблокированы")
                try:
                    import keyboard
                    keyboard.unblock_key('f4')
                    keyboard.unblock_key('f1')
                    keyboard.unblock_key('f2')
                    keyboard.unblock_key('f3')
                    keyboard.unblock_key('f5')
                    keyboard.unblock_key('f6')
                    # keyboard.unblock_key('esc')  # <-- УДАЛЕНО
                except:
                    pass
        else:
            self.logger.warning("[HOTKEYS] HotkeyManager не инициализирован")

    def setup_hotkeys(self):
        """
        Настройка глобальных горячих клавиш.
        Использует HotkeyManager для единообразной регистрации всех хоткеев.
        """
        self.logger.info("[HOTKEYS] Настройка горячих клавиш через HotkeyManager")
        if hasattr(self, 'hotkeys'):
            self.hotkeys.setup()
        else:
            self.logger.warning("[HOTKEYS] HotkeyManager не инициализирован, создаём...")
            self.hotkeys = HotkeyManager(self)
            self.hotkeys.setup()

    def _on_overlay_removed(self, target_hwnd):
        """Вызывается при удалении оверлея"""
        self.logger.info(f"[OVERLAY] Удалён оверлей для HWND={target_hwnd}")
        # Обновляем список окон
        self.window_list.refresh()

    def _on_overlay_created(self, target_hwnd):
        """Вызывается при создании нового оверлея"""
        self.logger.info(f"[OVERLAY] Создан оверлей для HWND={target_hwnd}")
        # Обновляем список окон
        self.window_list.refresh()

    def _process_next_in_queue(self):
        """Обрабатывает следующую задачу в очереди"""
        if self.is_processing_queue or not self.translation_queue:
            self.is_processing_queue = False
            return

        self.is_processing_queue = True

        task = self.translation_queue.pop(0)

        if task.get('type') == 'screenshot':
            self._pending_area_rect = None
            self._pending_region_path = None
            self._do_translate(task['image_path'])
        else:
            self._pending_area_rect = task.get('area_rect')
            self._pending_region_path = task.get('region_path')
            is_temporary = task.get('is_temporary', False)  # <-- ИЗВЛЕКАЕМ
            self._do_translate(
                task['image_path'],
                task.get('area_rect'),
                task.get('region_path'),
                is_temporary=is_temporary  # <-- ПЕРЕДАЁМ
            )

    def run(self):
        """Запускает главный цикл"""
        self.ui.root.mainloop()

    def _start_window_monitor(self):
        """Мониторинг переключения окон"""

        def check_window():
            try:
                current_hwnd = win32gui.GetForegroundWindow()
                if current_hwnd != self._current_active_hwnd:
                    self._on_window_switch(current_hwnd)
            except:
                pass
            self.ui.root.after(500, check_window)

        self.ui.root.after(500, check_window)

    def _start_result_processor(self):
        """Запускает постоянную проверку результатов из рабочего потока (как в оригинале)"""
        if self._processor_running:
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
        if self._processor_running:
            self.ui.root.after(100, self._process_results_loop)

    def _init_translator_step(self):
        """Инициализация переводчика с учетом выбранного движка"""
        if self._init_done or self.initializing:
            return

        self._init_attempts += 1
        if self._init_attempts > self._max_init_attempts:
            # Ошибка инициализации — убираем из статуса, только лог
            self.logger.error("[APP] Превышено количество попыток инициализации")
            self._init_attempts = 0
            self.ui.root.after(5000, self._init_translator_step)
            return

        self.initializing = True
        # Статус "starting browser" — ОСТАВЛЯЕМ
        self.ui.update_status("● " + self.ui.get_string('starting_browser'), '#ff9800')

        show_browser = self.settings.get_show_browser()
        target_lang = self.settings.get_target_language()
        engine = self.settings.get_translator_engine()
        self._last_engine = engine

        self.logger.info(f"[APP] Инициализация с движком: {engine}")

        cmd_id = self.browser_worker.init_browser(show_browser, target_lang, self._on_init_complete)
        self._pending_command_ids[cmd_id] = 'init'

    # === ОСНОВНЫЕ ДЕЙСТВИЯ ===

    def _process_area_selection_continuous(self, x1, y1, x2, y2, screenshot_path, selection_window, is_temporary=False):
        """Обработка выделенной области"""
        from PIL import Image

        full_img = Image.open(screenshot_path)
        cropped = full_img.crop((x1, y1, x2, y2))
        if not cropped:
            return

        region_path = self.temp_dir / f"region_{int(time.time())}.png"
        cropped.save(region_path)

        path = self.temp_dir / f"area_{int(time.time())}.png"
        cropped.save(path)

        target_hwnd = self._area_target_hwnd or self.screenshot.get_last_hwnd()
        is_fullscreen = self._area_is_fullscreen if self._area_is_fullscreen else self.screenshot.is_last_window_fullscreen()

        task = {
            'type': 'area',
            'image_path': path,
            'area_rect': (x1, y1, x2, y2),
            'target_hwnd': target_hwnd,
            'is_fullscreen': is_fullscreen,
            'region_path': region_path,
            'is_temporary': is_temporary  # <-- НОВЫЙ ФЛАГ
        }
        self.translation_queue.append(task)
        if not self.is_processing_queue:
            self._process_next_in_queue()

    def _do_translate(self, image_path, area_rect=None, region_path=None, is_temporary=False):
        """Выполняет перевод"""
        if self._translation_in_progress:
            return

        self._translation_in_progress = True
        self.translating = True

        # <-- ПОКАЗЫВАЕМ ИНДИКАТОР ПЕРЕВОДА
        self._show_translation_overlay()

        self._pending_area_rect = area_rect
        self._pending_region_path = region_path
        self._is_temporary_translation = is_temporary

        out = self.temp_dir / "translated"
        cmd_id = self.browser_worker.translate_image(image_path, out, self._on_translate_finished)
        self._pending_command_ids[cmd_id] = 'translate'

    def _show_translation_overlay(self):
        """Показывает индикатор перевода - использует один экземпляр"""
        if not self.settings.get_show_translation_indicator():
            return

        # <-- ЗАЩИТА ОТ ПОВТОРНЫХ ВЫЗЫВОВ
        if self._indicator_shown:
            self.logger.debug("[DEBUG] Индикатор уже показан, пропускаем")
            return

        try:
            from src.translation_overlay import TranslationOverlay

            if not self.translation_overlay:
                self.logger.info("[DEBUG] Создаем новый индикатор перевода")
                self.translation_overlay = TranslationOverlay(
                    parent=self.ui.root,
                    settings=self.settings
                )
                self.translation_overlay.set_app(self)

            self.translation_overlay.show(self.get_string('translation_status_translating'))
            self._indicator_shown = True
            self._indicator_hidden = False
            self.logger.info("[DEBUG] Индикатор перевода показан")

        except Exception as e:
            self.logger.warning(f"Не удалось показать индикатор: {e}")

    def _hide_translation_overlay(self):
        """Скрывает индикатор перевода"""
        # <-- ЗАЩИТА ОТ ПОВТОРНЫХ ВЫЗЫВОВ
        if self._indicator_hidden:
            self.logger.debug("[DEBUG] Индикатор уже скрыт, пропускаем")
            return

        try:
            if self.translation_overlay:
                self.logger.info("[DEBUG] Скрываем индикатор перевода")
                self.translation_overlay.finish()
                self._indicator_shown = False
                self._indicator_hidden = True
                self.logger.info("[DEBUG] Индикатор перевода скрыт")
        except Exception as e:
            self.logger.warning(f"Не удалось скрыть индикатор: {e}")

    # === КОНТЕКСТНОЕ МЕНЮ ===

    def _context_remove_overlays(self):
        """Удалить оверлеи для выбранного окна"""
        self.logger.info("[CONTEXT] === _context_remove_overlays НАЧАЛО ===")

        if not self.window_list:
            self.logger.warning("[CONTEXT] window_list не инициализирован")
            return

        self.logger.info("[CONTEXT] Вызов window_list.remove_overlays_for_selected()")
        self.window_list.remove_overlays_for_selected()

        self.logger.info("[CONTEXT] === _context_remove_overlays ЗАВЕРШЕН ===")

    # === НАСТРОЙКИ И ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ ===

    def open_settings(self):
        """Открывает окно настроек"""
        from src.settings_window import SettingsWindow
        # Сохраняем текущий движок для отслеживания изменений
        self._last_engine = self.settings.get_translator_engine()
        SettingsWindow(self, self.settings, self.on_settings_changed)

    def on_settings_changed(self):
        """Обработчик изменения настроек"""
        self.ui.update_ui_language()
        self.hotkeys.setup()

        # Проверяем, изменился ли движок перевода
        if not hasattr(self, '_last_engine'):
            self._last_engine = self.settings.get_translator_engine()
        else:
            new_engine = self.settings.get_translator_engine()
            if self._last_engine != new_engine:
                self._last_engine = new_engine
                self.logger.info(
                    f"[SETTINGS] Движок изменен: {self._last_engine} -> {new_engine}, перезапускаем браузер"
                )
                if self.ready:
                    self._restart_translator()
                else:
                    self.logger.info("[SETTINGS] Браузер не готов, перезапуск отложен")

        # Обновляем статус, если приложение готово — ТОЛЬКО ДЛЯ БРАУЗЕРА
        if self.ready:
            engine = self.settings.get_translator_engine()
            engine_name = "Google Translate" if engine == "google" else "Яндекс.Переводчик (OCR)"
            self.ui.update_status(
                f"● {self.ui.get_string('ready')} ({engine_name})",
                '#4CAF50'
            )
        elif hasattr(self, 'initializing') and self.initializing:
            self.ui.update_status(
                "● " + self.ui.get_string('starting_browser'),
                '#ff9800'
            )

    def reset_settings(self):
        import tkinter.messagebox as messagebox
        if messagebox.askyesno(self.ui.get_string('settings_title'), self.ui.get_string('settings_reset_confirm')):
            for key, value in Settings.DEFAULT_SETTINGS.items():
                self.settings.set(key, value)
            self.settings.save()
            self.ui.update_ui_language()
            messagebox.showinfo(self.ui.get_string('settings_title'), self.ui.get_string('settings_reset_done'))

    def toggle_language(self):
        current = self.settings.get_language()
        new = "en" if current == "ru" else "ru"
        self.settings.set_language(new)
        self.ui.update_ui_language()
        if hasattr(self.ui, 'lang_btn'):
            self.ui.lang_btn.config(text="EN" if new == "ru" else "RU")

    def open_app_folder(self):
        try:
            app_folder = Path.home() / "Documents" / "GoogleScreenTranslate"
            if not app_folder.exists():
                app_folder.mkdir(parents=True, exist_ok=True)
            os.startfile(str(app_folder))
        except Exception as e:
            self.logger.error(f"Ошибка открытия папки: {e}")

    def show_help(self):
        import webbrowser

        help_window = tk.Toplevel(self.ui.root)
        help_window.withdraw()
        help_window.title(self.ui.get_string('help_title'))
        help_window.configure(bg='#1e1e1e')
        help_window.transient(self.ui.root)
        help_window.grab_set()

        main_frame = tk.Frame(help_window, bg='#1e1e1e')
        main_frame.pack(fill=tk.BOTH, expand=True, padx=30, pady=25)

        tk.Label(main_frame, text="📸 Google Screen Translate",
                 bg='#1e1e1e', fg='#4CAF50', font=("Segoe UI", 16, "bold")).pack(pady=(0, 5))
        tk.Label(main_frame, text=self.ui.get_string('help_subtitle'),
                 bg='#1e1e1e', fg='#888888', font=("Segoe UI", 10)).pack(pady=(0, 20))

        tk.Frame(main_frame, bg='#3c3c3c', height=1).pack(fill=tk.X, pady=5)

        tk.Label(main_frame, text=self.ui.get_string('help_info'),
                 bg='#1e1e1e', fg='#aaaaaa', font=("Segoe UI", 10)).pack(pady=(15, 8))

        def open_link(url):
            webbrowser.open(url)

        link_style = {'bg': '#1e1e1e', 'font': ("Segoe UI", 10, "underline"),
                      'relief': tk.FLAT, 'cursor': "hand2", 'pady': 5}

        tk.Button(main_frame, text="🐙 GitHub: AlexeyZam15/GoogleImagesScreenTranslator",
                  command=lambda: open_link("https://github.com/AlexeyZam15/GoogleImagesScreenTranslator"),
                  fg='#4CAF50', **link_style).pack(pady=3)
        tk.Button(main_frame, text="💬 Discord: discord.gg/TSRFfRUwn",
                  command=lambda: open_link("https://discord.gg/TSRFfRUwn"),
                  fg='#5865F2', **link_style).pack(pady=3)

        tk.Button(main_frame, text=self.ui.get_string('help_close'),
                  command=help_window.destroy,
                  bg='#4CAF50', fg='white', font=("Segoe UI", 10, "bold"),
                  relief=tk.FLAT, padx=30, pady=8, cursor="hand2").pack(pady=(20, 0))

        help_window.update_idletasks()
        w, h = 600, 320
        x = (help_window.winfo_screenwidth() - w) // 2
        y = (help_window.winfo_screenheight() - h) // 2
        help_window.geometry(f"{w}x{h}+{x}+{y}")
        help_window.resizable(False, False)
        help_window.deiconify()
        help_window.lift()
        help_window.focus_force()

    def on_close(self):
        """Закрытие приложения с таймаутами и принудительным завершением"""
        import time
        import threading
        import os
        from pathlib import Path

        self.logger.info("=" * 60)
        self.logger.info("🛑 НАЧАЛО ЗАКРЫТИЯ ПРИЛОЖЕНИЯ")
        self.logger.info("=" * 60)

        # 1. Устанавливаем глобальный флаг закрытия
        self._closing = True

        # 2. Сохраняем состояние оверлеев перед закрытием
        if hasattr(self, 'overlay_manager') and self.overlay_manager:
            try:
                self.overlay_manager.save_overlay_state(immediate=True)
                self.logger.info("[CLOSE] Состояние оверлеев сохранено")
            except Exception as e:
                self.logger.warning(f"[CLOSE] Ошибка сохранения состояния: {e}")

        # 3. Скрываем индикатор
        try:
            self._hide_translation_overlay()
        except:
            pass

        # 4. Отключаем горячие клавиши
        try:
            import keyboard
            keyboard.unhook_all()
            self.logger.info("[CLOSE] Горячие клавиши отключены")
        except Exception as e:
            self.logger.warning(f"[CLOSE] Ошибка отключения клавиш: {e}")

        # 5. Сохраняем настройки
        try:
            if hasattr(self, 'settings'):
                self.settings.save()
                self.logger.info("[CLOSE] Настройки сохранены")
        except Exception as e:
            self.logger.warning(f"[CLOSE] Ошибка сохранения настроек: {e}")

        # 6. Останавливаем TranslationMonitor
        if hasattr(self, 'translation_monitor') and self.translation_monitor:
            try:
                self.logger.info("[CLOSE] Остановка TranslationMonitor...")
                self.translation_monitor.stop()
                self.logger.info("[CLOSE] TranslationMonitor остановлен")
            except Exception as e:
                self.logger.warning(f"[CLOSE] Ошибка остановки TranslationMonitor: {e}")

        # 7. Останавливаем BrowserWorker
        if hasattr(self, 'browser_worker') and self.browser_worker:
            try:
                self.logger.info("[CLOSE] Остановка BrowserWorker...")
                self.browser_worker.stop()
                self.logger.info("[CLOSE] BrowserWorker остановлен")
            except Exception as e:
                self.logger.warning(f"[CLOSE] Ошибка остановки BrowserWorker: {e}")

        # 8. Закрываем оверлеи
        if hasattr(self, 'overlay_manager') and self.overlay_manager:
            try:
                self.logger.info("[CLOSE] Закрытие оверлеев...")
                self.overlay_manager.close_all()
                self.logger.info("[CLOSE] Оверлеи закрыты")
            except Exception as e:
                self.logger.warning(f"[CLOSE] Ошибка закрытия оверлеев: {e}")

        # 9. Освобождаем DXcam
        if hasattr(self, 'screenshot') and self.screenshot:
            try:
                self.logger.info("[CLOSE] Освобождение DXcam...")
                self.screenshot.release_camera()
                self.logger.info("[CLOSE] DXcam освобожден")
            except Exception as e:
                self.logger.warning(f"[CLOSE] Ошибка освобождения DXcam: {e}")

        # 10. Ждем завершения всех потоков
        self.logger.info("[CLOSE] Ожидание завершения потоков...")
        time.sleep(0.5)

        # 11. Закрываем главное окно
        try:
            self.logger.info("[CLOSE] Закрытие главного окна...")
            if self.ui and self.ui.root:
                self.ui.root.destroy()
            self.logger.info("[CLOSE] Главное окно закрыто")
        except Exception as e:
            self.logger.error(f"[CLOSE] Ошибка закрытия главного окна: {e}")

        self.logger.info("=" * 60)
        self.logger.info("✅ ЗАКРЫТИЕ ЗАВЕРШЕНО")
        self.logger.info("=" * 60)

        # 12. Принудительное завершение
        def force_exit():
            time.sleep(2.0)
            self.logger.warning("[CLOSE] Принудительное завершение процесса...")
            try:
                os._exit(0)
            except:
                pass

        force_thread = threading.Thread(target=force_exit, daemon=True)
        force_thread.start()
