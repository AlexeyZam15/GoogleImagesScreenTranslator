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
    """Настройка логирования"""
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
    """Главный класс приложения"""

    @property
    def root(self):
        """Возвращает корневое окно tkinter для обратной совместимости"""
        return self.ui.root

    def __init__(self):
        setup_logging()
        self.logger = logging.getLogger(__name__)
        self.settings = Settings()
        self.temp_dir = ensure_app_temp_dir()

        # Компоненты
        self.screenshot = ScreenshotCapturer()
        self.browser_worker = BrowserWorker(self.settings)
        self.browser_worker.start()
        self.overlay_manager = None
        self.translation_monitor = None

        # === OCR процессор (инициализируется при старте в фоне) ===
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

        # === НОВЫЙ АТРИБУТ ДЛЯ ИНДИКАТОРА ===
        self._indicator_shown = False
        self._indicator_hidden = False

        # Состояния окон
        self._window_states = {}
        self._current_active_hwnd = None

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

        # Запускаем обработчик результатов (как в оригинале)
        self._start_result_processor()

        # === ЗАПУСКАЕМ ФОНОВУЮ ИНИЦИАЛИЗАЦИЮ OCR ===
        self.ui.root.after(100, self._init_ocr_background)

        # Запуск инициализации
        self.ui.root.after(100, self._init_translator_step)

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
        self.ui.update_status("● " + self.ui.get_string('translating'), '#ff9800')

        # Показываем индикатор
        self._show_translation_overlay()

        def capture_and_translate_task():
            import time
            from PIL import Image

            try:
                img = self.screenshot.capture_active_window()
                if not img:
                    self.ui.update_status("● " + self.ui.get_string('capture_error'), '#f44336')
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

                # Передаем screenshot_path и window_rect в колбэк
                cmd_id = self.browser_worker.translate_image(
                    screenshot_path,
                    out_dir,
                    lambda result, error: self._on_ocr_translate_finished(
                        result, error,
                        screenshot_path,  # <-- передаем путь к скриншоту
                        window_rect,  # <-- передаем rect окна
                        current_hwnd  # <-- передаем HWND
                    )
                )
                self._pending_command_ids[cmd_id] = 'translate_ocr'

            except Exception as e:
                self.logger.error(f"[F3_HOLD] Ошибка: {e}")
                self.translating = False
                self.set_actions_blocked(False)
                self._hide_translation_overlay()
                self.ui.update_status("● " + self.ui.get_string('error'), '#f44336')

        threading.Thread(target=capture_and_translate_task, daemon=True).start()

    def _on_ocr_translate_finished(self, result, error, screenshot_path, window_rect, target_hwnd):
        """Обработчик завершения перевода для OCR режима."""
        self.logger.info(f"[F3_HOLD] Перевод завершён, error={error}")

        self._translation_in_progress = False
        self.translating = False

        try:
            if error:
                self.logger.error(f"[F3_HOLD] Ошибка перевода: {error}")
                self.ui.update_status("● " + self.ui.get_string('translate_error'), '#f44336')
                self.set_actions_blocked(False)
                self._hide_translation_overlay()
                return

            if not result or not Path(result).exists():
                self.logger.error("[F3_HOLD] Результат перевода не найден")
                self.ui.update_status("● " + self.ui.get_string('translate_error'), '#f44336')
                self.set_actions_blocked(False)
                self._hide_translation_overlay()
                return

            self.logger.info(f"[F3_HOLD] Результат перевода получен: {result}")
            self._hide_translation_overlay()
            self.show_notification("🔄 OCR анализ...")

            try:
                from PIL import Image, ImageDraw
                from src.window_utils import get_process_name_by_hwnd
                import os
                import shutil

                if self.ocr_processor is None or not self._ocr_initialized:
                    self.logger.error("[F3_HOLD] OCR не инициализирован")
                    self.show_notification("❌ OCR не готов")
                    self.ui.update_status("● OCR не готов", '#f44336')
                    self.set_actions_blocked(False)
                    return

                translated_image_path = Path(result)

                # Загружаем изображения
                original_img = Image.open(screenshot_path)
                translated_img = Image.open(translated_image_path)

                orig_w, orig_h = original_img.size
                trans_w, trans_h = translated_img.size

                # === ОДНА ПОСТОЯННАЯ ПАПКА ДЛЯ ДЕБАГА ===
                debug_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "debug"
                debug_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"[DEBUG] Папка для дебага: {debug_dir}")

                # Получаем timestamp для имён файлов
                timestamp = time.strftime("%Y%m%d_%H%M%S")

                # === ПОЛУЧАЕМ ЗОНЫ (С СОХРАНЕНИЕМ ДЕБАГА) ===
                regions = self.ocr_processor.get_regions_from_image(
                    translated_image_path,
                    save_debug=True,
                    debug_dir=debug_dir,  # <-- ПЕРЕДАЁМ ПОСТОЯННУЮ ПАПКУ
                    debug_prefix=timestamp  # <-- ПЕРЕДАЁМ ПРЕФИКС ДЛЯ ИМЁН ФАЙЛОВ
                )
                self.logger.info(f"[F3_HOLD] Найдено {len(regions)} областей (после объединения)")

                # === СОХРАНЯЕМ ДЕБАГ-КАРТИНКУ С ОБЪЕДИНЁННЫМИ ЗОНАМИ ===
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

                if not regions:
                    self.logger.info("[F3_HOLD] Текст не обнаружен")
                    self.show_notification("ℹ️ Текст не обнаружен")
                    self.ui.update_status("● " + self.ui.get_string('ready'), '#4CAF50')
                    self.set_actions_blocked(False)
                    return

                self.show_notification(f"📝 Создание {len(regions)} оверлеев...")

                app_name = get_process_name_by_hwnd(target_hwnd) if target_hwnd else None

                wx1, wy1, wx2, wy2 = window_rect
                win_width = wx2 - wx1
                win_height = wy2 - wy1

                # Коэффициенты масштабирования
                scale_x = win_width / trans_w if trans_w > 0 else 1.0
                scale_y = win_height / trans_h if trans_h > 0 else 1.0

                created_count = 0

                if hasattr(self.overlay_manager, '_suppress_save'):
                    self.overlay_manager._suppress_save = True

                for i, (x1, y1, x2, y2) in enumerate(regions):
                    try:
                        screen_x1 = wx1 + int(x1 * scale_x)
                        screen_y1 = wy1 + int(y1 * scale_y)
                        screen_x2 = wx1 + int(x2 * scale_x)
                        screen_y2 = wy1 + int(y2 * scale_y)

                        if screen_x2 <= screen_x1 or screen_y2 <= screen_y1:
                            continue

                        region_window_rect = (screen_x1, screen_y1, screen_x2, screen_y2)

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
                            created_count += 1

                            if self.translation_monitor and self.settings.get_auto_replace_translated():
                                try:
                                    orig_x1 = screen_x1 - wx1
                                    orig_y1 = screen_y1 - wy1
                                    orig_x2 = screen_x2 - wx1
                                    orig_y2 = screen_y2 - wy1

                                    orig_x1 = max(0, min(orig_x1, orig_w))
                                    orig_y1 = max(0, min(orig_y1, orig_h))
                                    orig_x2 = max(0, min(orig_x2, orig_w))
                                    orig_y2 = max(0, min(orig_y2, orig_h))

                                    if orig_x2 > orig_x1 and orig_y2 > orig_y1:
                                        template_path = self.temp_dir / f"template_{i}_{int(time.time())}.png"
                                        template_img = original_img.crop((orig_x1, orig_y1, orig_x2, orig_y2))
                                        template_img.save(template_path)

                                        pair_index, file_hash = self.translation_monitor.add_template(
                                            region_image=template_path,
                                            translated_image=region_path,
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
                                                    self.logger.info(
                                                        f"[F3_HOLD] Шаблон #{pair_index} добавлен в монитор"
                                                    )
                                                    break
                                except Exception as e:
                                    self.logger.warning(f"[F3_HOLD] Не удалось создать шаблон: {e}")

                    except Exception as e:
                        self.logger.error(f"[F3_HOLD] Ошибка создания оверлея {i}: {e}")

                if hasattr(self.overlay_manager, '_suppress_save'):
                    self.overlay_manager._suppress_save = False
                    self.overlay_manager.save_overlay_state(immediate=True)

                self.logger.info(f"[F3_HOLD] Создано оверлеев: {created_count} из {len(regions)}")
                self.ui.root.after(500, self.window_list.refresh)

                if created_count > 0:
                    self.show_notification(f"✅ Создано {created_count} оверлеев")
                    self.ui.update_status(f"● {created_count} оверлеев создано", '#4CAF50')
                else:
                    self.show_notification("⚠️ Не удалось создать оверлеи")
                    self.ui.update_status("● " + self.ui.get_string('error'), '#f44336')

            except Exception as e:
                self.logger.error(f"[F3_HOLD] Ошибка OCR: {e}")
                import traceback
                traceback.print_exc()
                self.show_notification(f"❌ Ошибка OCR: {str(e)[:30]}")
                self.ui.update_status("● " + self.ui.get_string('error'), '#f44336')

        finally:
            self.set_actions_blocked(False)
            self._pending_command_ids = {}
            self.is_processing_queue = False

    def _get_app_name_by_hwnd(self, hwnd: int) -> str:
        """Возвращает имя приложения по HWND."""
        try:
            from src.window_utils import get_process_name_by_hwnd
            return get_process_name_by_hwnd(hwnd, default_name="Неизвестно")
        except Exception as e:
            self.logger.warning(f"[WINDOW] Ошибка получения имени по HWND: {e}")
            return "Неизвестно"

    def clear_all_overlays(self):
        """Удаляет все оверлеи для текущего активного приложения (F4)"""
        self.logger.info("[CLEAR_ALL] Начинаем удаление оверлеев для текущего приложения")

        if not self.overlay_manager:
            self.logger.warning("[CLEAR_ALL] OverlayManager не инициализирован")
            self.show_notification(self.get_string('notification_remove_no_app'))
            return

        current_app = self._get_current_app_name()
        if not current_app:
            self.logger.warning("[CLEAR_ALL] Не удалось определить текущее приложение")
            self.show_notification(self.get_string('notification_remove_no_app'))
            return

        overlays_for_app = self.overlay_manager.get_overlays_by_app_name(current_app)

        if not overlays_for_app:
            self.logger.info(f"[CLEAR_ALL] Нет оверлеев для приложения {current_app}")
            self.show_notification(self.get_string('clear_all_no_overlays').format(app_name=current_app))
            return

        overlays_count = len(overlays_for_app)
        self.logger.info(f"[CLEAR_ALL] Найдено {overlays_count} оверлеев для приложения {current_app}")

        # === ОСТАНАВЛИВАЕМ МОНИТОР ===
        monitor_was_running = False
        if self.translation_monitor:
            if self.translation_monitor.is_running():
                monitor_was_running = True
                self.translation_monitor.stop()
                self.logger.info("[CLEAR_ALL] Монитор остановлен")

            # Очищаем шаблоны для этого приложения из монитора
            templates_to_remove = []
            for template_data in self.translation_monitor.templates[:]:
                if template_data.get('target_app_name') == current_app:
                    templates_to_remove.append(template_data.get('pair_index'))

            for pair_index in templates_to_remove:
                self.translation_monitor.remove_template(pair_index)
                self.logger.info(f"[CLEAR_ALL] Удален шаблон #{pair_index} для {current_app}")

            # Очищаем кэш монитора
            self.translation_monitor._frame_cache = None
            self.translation_monitor._frame_cache_hwnd = None
            self.translation_monitor._last_active_hwnd = None
            self.translation_monitor._last_active_app_name = None

        # === ИСПОЛЬЗУЕМ МАССОВОЕ УДАЛЕНИЕ ===
        if hasattr(self.overlay_manager, 'remove_all_overlays_for_app'):
            # Быстрое массовое удаление
            self.overlay_manager.remove_all_overlays_for_app(current_app, force=True)
            removed_count = overlays_count
        else:
            # Fallback на поштучное удаление
            removed_count = 0
            for overlay in overlays_for_app[:]:
                try:
                    self.overlay_manager.remove_overlay(overlay, force=True)
                    removed_count += 1
                except Exception as e:
                    self.logger.error(f"[CLEAR_ALL] Ошибка удаления оверлея: {e}")

        # === УДАЛЯЕМ ИЗ ФАЙЛА СОСТОЯНИЯ ===
        try:
            import json
            state_file = Path.home() / "Documents" / "GoogleScreenTranslate" / "config" / "overlay_state.json"
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    states = json.load(f)

                keys_to_remove = [key for key in states.keys() if key.startswith(f"{current_app}_")]
                for key in keys_to_remove:
                    del states[key]
                    self.logger.info(f"[CLEAR_ALL] Удалена запись состояния: {key}")

                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(states, f, indent=4, ensure_ascii=False)
                self.logger.info(f"[CLEAR_ALL] Состояние для {current_app} удалено из файла")
        except Exception as e:
            self.logger.warning(f"[CLEAR_ALL] Не удалось обновить файл состояния: {e}")

        # === ПЕРЕЗАПУСКАЕМ МОНИТОР, ЕСЛИ ЕСТЬ ШАБЛОНЫ ДЛЯ ДРУГИХ ПРИЛОЖЕНИЙ ===
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

        # === ОБНОВЛЯЕМ СПИСОК ОКОН ===
        self.ui.root.after(100, lambda: self.window_list.refresh(skip_restore=True))

        self.logger.info(f"[CLEAR_ALL] Очистка завершена для {current_app}")
        self.show_notification(
            self.get_string('clear_all_completed').format(app_name=current_app, count=removed_count)
        )

    def get_string(self, key: str) -> str:
        """Возвращает локализованную строку"""
        if hasattr(self, 'settings'):
            return self.settings.get_string(key)
        return key

    def _get_current_app_name(self) -> Optional[str]:
        """Возвращает имя текущего активного приложения."""
        try:
            import win32gui
            from src.window_utils import get_process_name_by_hwnd
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return get_process_name_by_hwnd(hwnd)
        except Exception as e:
            self.logger.warning(f"[WINDOW] Ошибка получения имени текущего окна: {e}")
        return None

    def toggle_overlay(self):
        """Переключает видимость оверлеев ТОЛЬКО для текущего активного приложения (F1)"""
        self.logger.info("[DEBUG] toggle_overlay вызван")

        if not self.overlay_manager:
            self.logger.warning("toggle_overlay: менеджер оверлеев не инициализирован")
            return

        if not self.overlay_manager.overlays:
            self.logger.info("toggle_overlay: нет активных оверлеев")
            self.show_notification(self.get_string('overlay_toggle_no_overlays'))
            return

        # Получаем имя текущего активного приложения
        current_app = self._get_current_app_name()
        if not current_app:
            self.logger.warning("toggle_overlay: не удалось определить текущее приложение")
            self.show_notification(self.get_string('overlay_toggle_unknown_app'))
            return

        # Получаем оверлеи для текущего приложения
        overlays_for_app = self.overlay_manager.get_overlays_by_app_name(current_app)

        if not overlays_for_app:
            self.logger.info(f"toggle_overlay: нет оверлеев для приложения {current_app}")
            self.show_notification(self.get_string('overlay_toggle_no_overlays_for_app').format(app_name=current_app))
            return

        # Проверяем, включена ли автозамена
        auto_replace_enabled = self.settings.get_auto_replace_translated()

        # Если автозамена включена, фильтруем оверлеи по наличию найденных шаблонов
        if auto_replace_enabled and self.translation_monitor:
            # Собираем хеши найденных шаблонов
            found_template_hashes = set()
            for template_data in self.translation_monitor.templates:
                if template_data.get('found', False):
                    template_hash = template_data.get('hash')
                    if template_hash:
                        found_template_hashes.add(template_hash)

            self.logger.info(f"[F1] Найдено шаблонов на экране: {len(found_template_hashes)}")

            # Фильтруем оверлеи: показываем только те, чьи шаблоны найдены
            overlays_to_toggle = []
            for overlay in overlays_for_app:
                template_id = overlay._template_id
                if template_id and template_id in found_template_hashes:
                    overlays_to_toggle.append(overlay)

            # Если нет ни одного найденного шаблона — показываем уведомление и выходим
            if not overlays_to_toggle:
                self.logger.info(f"[F1] Нет найденных шаблонов для приложения {current_app}")
                self.show_notification(self.get_string('overlay_toggle_no_templates_found'))
                return

            # Используем отфильтрованный список
            overlays_for_app = overlays_to_toggle
            self.logger.info(f"[F1] Отфильтровано оверлеев с найденными шаблонами: {len(overlays_for_app)}")

        # Проверяем, все ли оверлеи для этого приложения скрыты или видны
        all_visible = all(ov.visible for ov in overlays_for_app)
        new_state = not all_visible

        self.logger.info(
            f"toggle_overlay: переключение {len(overlays_for_app)} оверлеев для {current_app} в состояние: {'показаны' if new_state else 'скрыты'}")

        for overlay in overlays_for_app:
            try:
                if new_state:
                    # Показываем оверлей
                    overlay._hidden_by_user = False
                    overlay._is_visible_by_user = True
                    overlay.show()
                else:
                    # Скрываем оверлей
                    overlay._hidden_by_user = True
                    overlay._is_visible_by_user = False
                    overlay.hide(by_user=True)
            except Exception as e:
                self.logger.error(f"Ошибка при переключении оверлея: {e}")

        # Сохраняем состояние
        self.overlay_manager.save_overlay_state()

        # Уведомление с локализацией
        status_text = self.get_string('overlay_toggle_status_shown') if new_state else self.get_string(
            'overlay_toggle_status_hidden')
        self.show_notification(
            self.get_string('overlay_toggle_notification').format(app_name=current_app, status=status_text))
        self.logger.info(f"F1: оверлеи для {current_app} {status_text}")

    def _clear_window_state(self, app_name: str):
        """Очищает состояние для указанного приложения."""
        if app_name in self._window_states:
            del self._window_states[app_name]
            self.logger.info(f"[STATE] Состояние очищено для {app_name}")

    def _on_init_complete(self, result, error):
        """Завершение инициализации"""
        if error:
            self.logger.error(f"Ошибка инициализации: {error}")
            self.initializing = False
            self.ui.update_status("● Ошибка: " + str(error)[:50], '#f44336')
            self.ui.root.after(self._init_retry_delay, self._init_translator_step)
            return

        self.logger.info("Инициализация завершена")
        self.ready = True
        self.initializing = False
        self._init_done = True
        self._init_attempts = 0

        # === ПОКАЗЫВАЕМ УВЕДОМЛЕНИЕ О ГОТОВНОСТИ ===
        self.show_notification("✅ " + self.ui.get_string('ready_notification'), 2000)

        if not self.overlay_manager:
            self.overlay_manager = OverlayManager(self)

        if not self.translation_monitor:
            self.translation_monitor = TranslationMonitor(self, self.overlay_manager, self.settings)
            self.logger.info("TranslationMonitor создан")

            if self.settings.get_auto_replace_translated():
                self.logger.info("Автозамена включена, монитор будет запущен при добавлении шаблонов")

        restored_count = 0
        if self.overlay_manager:
            restored_count = self.overlay_manager.restore_overlays_from_state(self)
            if restored_count > 0:
                self.logger.info(f"[STATE] Восстановлено {restored_count} оверлеев")
                self.ui.root.after(500, self.window_list.refresh)
            else:
                self.logger.info("[STATE] Нет сохранённых оверлеев для восстановления")

        if hasattr(self.ui, 'settings_btn'):
            self.ui.settings_btn.config(state=tk.NORMAL, bg='#3c3c3c', fg='#cccccc')

        self.ui.set_settings_menu_enabled(True)
        self.ui.update_status("● " + self.ui.get_string('ready'), '#4CAF50')

        self.window_list.refresh()

    def _on_window_switch(self, new_hwnd):
        """Обработчик переключения окон - скрывает все оверлеи при переключении и выполняет авто-переключение фулскрина"""

        if new_hwnd == self._current_active_hwnd:
            return

        # Игнорируем оверлей
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

        # === НОВАЯ ЛОГИКА: автоматическое переключение полноэкранного режима ===
        if new_hwnd:
            try:
                from src.window_utils import get_process_name_by_hwnd
                app_name = get_process_name_by_hwnd(new_hwnd, default_name="Неизвестно")
                self._auto_switch_fullscreen_window(new_hwnd, app_name)
            except Exception as e:
                self.logger.warning(f"[WINDOW] Ошибка авто-переключения: {e}")

        # Существующая логика скрытия оверлеев
        if self.overlay_manager and not self.overlay_manager.is_dragging():
            for overlay in self.overlay_manager.overlays[:]:
                try:
                    if overlay.visible:
                        overlay.hide(by_user=False)
                        self.logger.info(f"[WINDOW] Скрыт оверлей при переключении окон")
                except Exception as e:
                    self.logger.warning(f"[WINDOW] Ошибка скрытия оверлея: {e}")

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
        self.ui.update_status("● " + self.ui.get_string('translating'), '#ff9800')
        self.show_notification(self.get_string('notification_capturing'))  # <-- ЛОКАЛИЗОВАНО

        def capture_task():
            try:
                from PIL import Image
                img = self.screenshot.capture_active_window()
                if not img:
                    self.ui.update_status("● " + self.ui.get_string('capture_error'), '#f44336')
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
        """Завершение перевода"""
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
                self._process_next_in_queue()
                return

            if error:
                self.logger.error(f"Ошибка перевода: {error}")
                self._on_translate_error(error)
                return

            is_temporary = getattr(self, '_is_temporary_translation', False)
            self._is_temporary_translation = False

            if result and self.overlay_manager:
                self.logger.info(f"Результат перевода получен: {result}")
                self.show_notification(self.get_string('notification_translation_ready'))

                region_path = getattr(self, '_pending_region_path', None)
                auto_replace_enabled = self.settings.get_auto_replace_translated()

                # Получаем время жизни из настроек для временного оверлея
                lifetime_seconds = self.settings.get_temporary_lifetime() if is_temporary else 180

                if region_path and region_path.exists() and self.translation_monitor and auto_replace_enabled:
                    target_hwnd = self.screenshot.get_last_hwnd()
                    from src.window_utils import get_process_name_by_hwnd
                    target_app_name = get_process_name_by_hwnd(target_hwnd) if target_hwnd else None

                    add_result = self.translation_monitor.add_template(
                        region_path, result,
                        target_app_name,
                        is_temporary=is_temporary,
                        lifetime_seconds=lifetime_seconds  # <-- ПЕРЕДАЁМ ВРЕМЯ ЖИЗНИ
                    )
                    if add_result and len(add_result) == 2:
                        pair_index, file_hash = add_result
                        self.logger.info(
                            f"[DEBUG] {'Временный' if is_temporary else 'Постоянный'} шаблон #{pair_index} добавлен в монитор, время жизни: {lifetime_seconds}с"
                        )
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
                            app_name=app_name
                        )

                        if overlay:
                            overlay._is_visible_by_user = True
                            overlay._hidden_by_user = False
                            if not overlay.visible:
                                overlay.show()
                            self.ui.root.after(100, self.window_list.refresh)

                    self._pending_region_path = None

            else:
                self.logger.warning("Результат перевода пустой")
                self.ui.update_status("● " + self.ui.get_string('translate_error'), '#f44336')
                self.show_notification("Ошибка перевода")

        except Exception as e:
            self.logger.error(f"Ошибка показа результата: {e}")
            import traceback
            traceback.print_exc()
            self.ui.update_status("● " + self.ui.get_string('error'), '#f44336')
            self.show_notification("Ошибка при обработке перевода")
        finally:
            self.translating = False
            self._pending_command_ids = {}
            self._pending_area_rect = None
            self.is_processing_queue = False
            self.set_actions_blocked(False)

            if self.translation_queue:
                self._process_next_in_queue()
            else:
                if self._indicator_shown:
                    self._hide_translation_overlay()
                    self._indicator_shown = False
                    self.logger.info("[DEBUG] Индикатор перевода скрыт (очередь пуста)")

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
        self.set_actions_blocked(True)
        self._capture_mode = True
        # Удалено: self.show_notification(self.get_string('notification_select_area'))
        try:
            self.ui.root.iconify()
        except:
            pass
        self.ui.root.after(300, self._capture_window_for_area)

    def _on_translate_error(self, error_msg):
        self.logger.error(f"Ошибка перевода: {error_msg}")
        self._translation_in_progress = False
        self.ui.update_status("● " + self.ui.get_string('error'), '#f44336')
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
                self.ui.update_status("● " + self.ui.get_string('capture_error'), '#f44336')
                self._capture_mode = False
                self.set_actions_blocked(False)
                self.ui.root.deiconify()
                return

            self.screenshot._last_hwnd = current_hwnd
            self._area_target_hwnd = current_hwnd
            self.screenshot._is_fullscreen = self.screenshot.is_window_fullscreen(current_hwnd)
            self._area_is_fullscreen = self.screenshot._is_fullscreen

            # === ПЕРЕКЛЮЧАЕМ ОКНО В ОКОННЫЙ ПОЛНОЭКРАННЫЙ РЕЖИМ ===
            if self._area_is_fullscreen:
                self.logger.info("[F3] Переключение окна в оконный полноэкранный режим")

                # Сначала отправляем Alt+Enter, чтобы игра переключилась в оконный режим
                try:
                    import keyboard
                    keyboard.press_and_release('alt+enter')
                    self.logger.info("[F3] Alt+Enter отправлен")
                    time.sleep(0.5)  # Даём игре время переключиться
                except Exception as e:
                    self.logger.warning(f"[F3] Не удалось отправить Alt+Enter: {e}")

                # Теперь применяем стили для удаления рамки
                make_windowed_fullscreen(current_hwnd)
                time.sleep(0.3)
                self.logger.info("[F3] Окно переключено в оконный полноэкранный режим")

            img = ImageGrab.grab()
            if not img:
                self.ui.update_status("● " + self.ui.get_string('capture_error'), '#f44336')
                self._capture_mode = False
                self.set_actions_blocked(False)
                self.ui.root.deiconify()
                return

            screenshot_path = self.temp_dir / f"area_screenshot_{int(time.time())}.png"
            img.save(screenshot_path)

            self._show_continuous_area_selection_window(screenshot_path)
        except Exception as e:
            self.logger.error(f"Ошибка захвата области: {e}")
            self.ui.update_status("● " + self.ui.get_string('capture_error'), '#f44336')
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
                    keyboard.block_key('esc')
                    self.logger.info("[HOTKEYS] Дополнительная блокировка клавиш через block_key")
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
                    keyboard.unblock_key('esc')
                except:
                    pass
        else:
            self.logger.warning("[HOTKEYS] HotkeyManager не инициализирован")

    def setup_hotkeys(self):
        """Настройка глобальных горячих клавиш"""
        self.logger.info("[HOTKEYS] Настройка горячих клавиш (упрощенная версия)")
        try:
            import keyboard
            keyboard.unhook_all()
            self.logger.info("[HOTKEYS] Старые хуки отключены")

            hotkeys = self.settings.get_all_hotkeys()
            self.logger.info(f"[HOTKEYS] Загружены настройки: {hotkeys}")

            # Обработчики для одиночных клавиш
            def make_handler(action):
                def handler(e):
                    self.logger.info(f"[HOTKEYS] Нажата клавиша: {action}")
                    if action == 'toggle_overlay':
                        self.toggle_overlay()
                    elif action == 'screenshot':
                        self.process()
                    elif action == 'area':
                        self.capture_area()
                    elif action == 'area_temporary':
                        self.capture_area_temporary()
                    elif action == 'clear_all':
                        self.clear_all_overlays()
                    elif action == 'edit_mode':
                        self.toggle_edit_mode()
                    elif action == 'auto_replace':
                        self.toggle_auto_replace_mode()
                    return True

                return handler

            for action, hotkey in hotkeys.items():
                keyboard.on_press_key(hotkey, make_handler(action), suppress=True)
                self.logger.info(f"[HOTKEYS] Зарегистрирована клавиша {hotkey} -> {action}")

        except Exception as e:
            self.logger.error(f"[HOTKEYS] Ошибка регистрации горячих клавиш: {e}")

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

    def _show_continuous_area_selection_window(self, screenshot_path):
        """Показывает окно выделения области"""
        from PIL import Image, ImageTk
        import win32gui
        import win32con
        import time

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

        # ПКМ - полностью переопределяем
        canvas.bind("<ButtonPress-3>", on_mouse_down_pkm)
        canvas.bind("<B3-Motion>", on_mouse_drag_pkm)
        canvas.bind("<ButtonRelease-3>", on_mouse_up_pkm)

        # Выход по ESC и Enter
        canvas.bind("<Escape>", lambda e: exit_area_mode())
        selection_window.bind("<Escape>", lambda e: exit_area_mode())
        canvas.bind("<Return>", lambda e: exit_area_mode())

        # === ПРИНУДИТЕЛЬНЫЙ ФОКУС НА ОКНО ВЫБОРА ОБЛАСТИ ===
        selection_window.update_idletasks()
        time.sleep(0.05)

        try:
            hwnd = int(selection_window.winfo_id())
            win32gui.SetForegroundWindow(hwnd)
            win32gui.SetFocus(hwnd)
            win32gui.BringWindowToTop(hwnd)
            self.logger.info(f"[F3] Фокус установлен на окно выбора области (HWND: {hwnd})")
        except Exception as e:
            self.logger.warning(f"[F3] Не удалось установить фокус через Win32 API: {e}")

        canvas.focus_set()
        selection_window.focus_force()
        selection_window.grab_set()
        selection_window.lift()

        self.hotkeys.set_actions_blocked(True)

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
        """Инициализация переводчика"""
        if self._init_done or self.initializing:
            return

        self._init_attempts += 1
        if self._init_attempts > self._max_init_attempts:
            self.ui.update_status("● Ошибка инициализации", '#f44336')
            self._init_attempts = 0
            self.ui.root.after(5000, self._init_translator_step)
            return

        self.initializing = True
        self.ui.update_status("● " + self.ui.get_string('starting_browser'), '#ff9800')

        show_browser = self.settings.get_show_browser()
        target_lang = self.settings.get_target_language()

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

        self._pending_area_rect = area_rect
        self._pending_region_path = region_path
        self._is_temporary_translation = is_temporary  # <-- СОХРАНЯЕМ ФЛАГ

        out = self.temp_dir / "translated"
        cmd_id = self.browser_worker.translate_image(image_path, out, self._on_translate_finished)
        self._pending_command_ids[cmd_id] = 'translate'

    def _show_translation_overlay(self):
        """Показывает индикатор перевода - использует один экземпляр"""
        if not self.settings.get_show_translation_indicator():
            return

        try:
            from src.translation_overlay import TranslationOverlay

            # Если индикатор еще не создан - создаем с передачей настроек
            if not self.translation_overlay:
                self.logger.info("[DEBUG] Создаем новый индикатор перевода")
                self.translation_overlay = TranslationOverlay(
                    parent=self.ui.root,
                    settings=self.settings  # <-- ПЕРЕДАЕМ НАСТРОЙКИ
                )

            # Показываем индикатор (локализованная строка)
            self.translation_overlay.show(self.get_string('translation_status_translating'))
            self.logger.info("[DEBUG] Индикатор перевода показан")

        except Exception as e:
            self.logger.warning(f"Не удалось показать индикатор: {e}")

    def _hide_translation_overlay(self):
        """Скрывает индикатор перевода"""
        try:
            if self.translation_overlay:
                self.logger.info("[DEBUG] Скрываем индикатор перевода")
                self.translation_overlay.finish()
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
        from src.settings_window import SettingsWindow
        SettingsWindow(self, self.settings, self.on_settings_changed)

    def on_settings_changed(self):
        self.ui.update_ui_language()
        self.hotkeys.setup()
        self.ui.update_status("● " + self.ui.get_string('ready'), '#4CAF50')

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
        """Закрытие приложения"""
        self._hide_translation_overlay()
        try:
            import keyboard
            keyboard.unhook_all()
        except:
            pass
        if hasattr(self, 'settings'):
            self.settings.save()
        if hasattr(self, 'browser_worker'):
            self.browser_worker.stop()
        if self.overlay_manager:
            self.overlay_manager.close_all()
        self.ui.root.destroy()
