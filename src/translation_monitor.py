"""
Модуль для автоматического мониторинга экрана и замены областей на их переводы.
Адаптирован из AutoArtReplacer ScreenMonitor.
"""

import logging
import threading
import time
import traceback
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from functools import lru_cache

# Третьи стороны (сначала тяжелые библиотеки)
import cv2
import numpy as np

# Windows API - ИСПРАВЛЕННЫЕ ИМПОРТЫ
import win32gui
import win32ui
import win32con
import ctypes
from ctypes import wintypes

# PIL
from PIL import Image, ImageGrab


class TranslationMonitor:
    """Мониторит экран, ищет сохраненные области (шаблоны) и показывает их переводы."""

    __slots__ = (
        'parent', 'overlay_manager', 'settings', 'logger', 'debug_mode',
        'templates', 'monitoring', 'monitor_thread', 'confidence_threshold',
        'delay_sec', '_template_counter', '_app_name_cache', '_cache_max_size',
        '_last_active_hwnd', '_last_active_app_name', '_skip_count',
        '_last_capture_time', '_last_captured_image', '_last_captured_hwnd',
        '_updating_overlay', '_idle_counter', '_last_check_time',
        '_frame_cache', '_frame_cache_hwnd', '_frame_cache_time',
        '_frame_cache_ttl',
        '_frame_cache_original_size', '_frame_cache_scale',
        '_capture_debug_counter',
        '_size_debug_counter',
        '_match_debug_counter',
        '_first_scan_after_switch',
        '_our_app_name'  # <-- ДОБАВЛЯЕМ
    )

    def __init__(self, parent, overlay_manager, settings, debug_mode=False):
        self.parent = parent
        self.overlay_manager = overlay_manager
        self.settings = settings
        self.logger = logging.getLogger(__name__)
        self.debug_mode = debug_mode

        self.templates: List[Dict] = []
        self.monitoring = False
        self.monitor_thread = None
        self.confidence_threshold = 0.8
        self.delay_sec = 0.15
        self._template_counter = 0

        # Кэш для имён приложений
        self._app_name_cache = {}
        self._cache_max_size = 100

        # Флаг активного окна для оптимизации
        self._last_active_hwnd = None
        self._last_active_app_name = None
        self._skip_count = 0
        self._idle_counter = 0
        self._last_check_time = 0

        # Кэш для скриншотов
        self._frame_cache = None
        self._frame_cache_hwnd = None
        self._frame_cache_time = 0
        self._frame_cache_ttl = 0.05

        # Атрибуты для уменьшенного изображения
        self._frame_cache_original_size = None
        self._frame_cache_scale = 1.0

        # Отладочные счётчики
        self._capture_debug_counter = 0
        self._size_debug_counter = {}
        self._match_debug_counter = {}

        # Первый скан после переключения окна
        self._first_scan_after_switch = True

        # Дополнительные атрибуты
        self._updating_overlay = False
        self._last_capture_time = 0
        self._last_captured_image = None
        self._last_captured_hwnd = None

        # ============================================================
        # ОПРЕДЕЛЯЕМ ИМЯ НАШЕГО ПРИЛОЖЕНИЯ ОДИН РАЗ
        # ============================================================
        self._our_app_name = self._get_our_app_name()

        if settings:
            self.confidence_threshold = settings.get_confidence_threshold()
            self.delay_sec = settings.get_monitor_delay()

        self.logger.info(f"TranslationMonitor инициализирован, имя приложения: {self._our_app_name}")

    def _monitor_loop(self):
        """Основной цикл мониторинга — оптимизированная версия."""
        import win32gui
        from src.window_utils import get_process_name_by_hwnd

        self.logger.info("[MONITOR] Цикл мониторинга запущен (оптимизированный)")

        # Определяем имя нашего приложения
        our_app_name = self._get_our_app_name()

        last_time = time.time()
        iteration_count = 0
        last_found_time = {}
        debug_counter = 0

        SEARCH_SCALE = 0.5

        while self.monitoring:
            try:
                if not self.monitoring:
                    break

                current_time = time.time()
                elapsed = current_time - last_time

                if elapsed < self.delay_sec:
                    time.sleep(0.02)
                    continue

                last_time = current_time
                iteration_count += 1

                if iteration_count % 100 == 0:
                    self.logger.info(f"[MONITOR] Итерация #{iteration_count}, шаблонов: {len(self.templates)}")

                if not self.monitoring or not self.templates:
                    time.sleep(0.05)
                    continue

                if self.overlay_manager and self.overlay_manager.is_dragging():
                    time.sleep(0.02)
                    continue

                # ============================================================
                # ПОЛУЧАЕМ АКТИВНОЕ ОКНО (С УЧЁТОМ НАШЕГО ПРИЛОЖЕНИЯ)
                # ============================================================
                active_hwnd, active_app_name = self._get_active_window_for_scan(our_app_name)
                if active_hwnd is None:
                    time.sleep(0.02)
                    continue

                debug_counter += 1
                if debug_counter % 100 == 0:
                    self.logger.info(
                        f"[MONITOR_DEBUG] Активное окно: HWND={active_hwnd}, App='{active_app_name}', "
                        f"шаблонов: {len([t for t in self.templates if t.get('target_app_name') == active_app_name])}"
                    )

                self._last_active_app_name = active_app_name

                if hasattr(self, 'parent') and self.parent:
                    if hasattr(self.parent, '_capture_mode') and self.parent._capture_mode:
                        time.sleep(0.02)
                        continue

                # ============================================================
                # ПОЛУЧАЕМ АКТИВНЫЕ ШАБЛОНЫ
                # ============================================================
                active_templates, inactive_templates = self._get_active_templates(active_app_name)

                if self._first_scan_after_switch:
                    self._handle_first_scan(active_templates, active_app_name)

                if not active_templates:
                    if debug_counter % 50 == 0:
                        self.logger.info(
                            f"[MONITOR_DEBUG] Нет активных шаблонов для {active_app_name}. "
                            f"Всего шаблонов: {len(self.templates)}"
                        )
                    time.sleep(0.02)
                    continue

                # ============================================================
                # ЗАХВАТ И УМЕНЬШЕНИЕ ИЗОБРАЖЕНИЯ
                # ============================================================
                resized = self._get_scaled_frame(active_hwnd, current_time, SEARCH_SCALE, debug_counter)
                if resized is None:
                    time.sleep(0.02)
                    continue

                # ============================================================
                # ПОИСК ШАБЛОНОВ И ОБНОВЛЕНИЕ ОВЕРЛЕЕВ
                # ============================================================
                self._search_templates_and_update_overlays(
                    resized, active_templates, active_app_name,
                    SEARCH_SCALE, current_time, last_found_time, debug_counter
                )

                # ============================================================
                # ЗАВЕРШЕНИЕ ПЕРВОГО СКАНИРОВАНИЯ
                # ============================================================
                if self._first_scan_after_switch:
                    self._finish_first_scan(active_templates)

            except Exception as e:
                self.logger.error(f"[MONITOR] Ошибка: {e}")
                time.sleep(0.1)

        self.logger.info("[MONITOR] Цикл мониторинга завершен")

    def _get_our_app_name(self) -> str:
        """Определяет имя текущего приложения."""
        try:
            import os
            import psutil
            current_pid = os.getpid()
            current_process = psutil.Process(current_pid)
            return current_process.name().lower()
        except Exception as e:
            self.logger.warning(f"Не удалось определить имя приложения: {e}")
            return "python.exe"

    def _get_active_window_for_scan(self, our_app_name: str) -> tuple:
        """
        Возвращает (HWND, app_name) для сканирования.
        Если активное окно принадлежит нашему приложению, использует сохранённое окно.
        """
        import win32gui
        from src.window_utils import get_process_name_by_hwnd

        try:
            active_hwnd = win32gui.GetForegroundWindow()
            if not active_hwnd:
                return None, None
        except:
            return None, None

        active_app_name = self._get_cached_app_name(active_hwnd)

        # Проверяем, является ли активное окно нашим приложением
        if active_app_name and active_app_name.lower() == our_app_name:
            if hasattr(self, 'parent') and self.parent:
                if hasattr(self.parent, '_last_real_active_hwnd') and self.parent._last_real_active_hwnd:
                    last_hwnd = self.parent._last_real_active_hwnd
                    if win32gui.IsWindow(last_hwnd) and win32gui.IsWindowVisible(last_hwnd):
                        last_app_name = get_process_name_by_hwnd(last_hwnd)
                        # Логируем только при первом сканировании
                        if self._first_scan_after_switch:
                            self.logger.info(
                                f"[MONITOR] Активно наше приложение, сканируем сохранённое окно: {last_app_name}")
                        return last_hwnd, last_app_name
                    else:
                        self.parent._last_real_active_hwnd = None
            return None, None

        return active_hwnd, active_app_name

    def _get_active_templates(self, active_app_name: str) -> tuple:
        """Возвращает (active_templates, inactive_templates)."""
        active_templates = []
        inactive_templates = []

        for template_data in self.templates:
            if not template_data.get('enabled', True):
                continue
            target_app_name = template_data.get('target_app_name')

            if target_app_name and target_app_name != "Неизвестно":
                if target_app_name == active_app_name:
                    active_templates.append(template_data)
                else:
                    inactive_templates.append(template_data)
            else:
                active_templates.append(template_data)

        return active_templates, inactive_templates

    def _handle_first_scan(self, active_templates: List, active_app_name: str):
        """Обрабатывает первый скан после переключения окна."""
        total_templates = len(self.templates)
        active_count = len(active_templates)

        if not active_templates:
            self._first_scan_after_switch = False
            return

        self.logger.info(
            f"[MONITOR] Сканирование для {active_app_name} (активных: {active_count}/{total_templates})"
        )

    def _get_scaled_frame(self, active_hwnd: int, current_time: float, scale: float, debug_counter: int):
        """Захватывает и уменьшает изображение окна."""
        import cv2

        if (self._frame_cache_hwnd != active_hwnd or
                current_time - self._frame_cache_time > self._frame_cache_ttl):
            image = self._capture_window(active_hwnd)
            if image is not None:
                h, w = image.shape[:2]
                new_w = int(w * scale)
                new_h = int(h * scale)
                resized = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

                self._frame_cache = resized
                self._frame_cache_original_size = (w, h)
                self._frame_cache_scale = scale
                self._frame_cache_hwnd = active_hwnd
                self._frame_cache_time = current_time

                if debug_counter % 100 == 0:
                    self.logger.info(
                        f"[MONITOR_DEBUG] Захвачено окно: {w}x{h} -> уменьшено до {new_w}x{new_h}, HWND={active_hwnd}"
                    )
                return resized
            else:
                if debug_counter % 100 == 0:
                    self.logger.warning(f"[MONITOR_DEBUG] НЕ удалось захватить окно HWND={active_hwnd}")
                return self._frame_cache

        return self._frame_cache

    def _search_templates_and_update_overlays(self, resized, active_templates: List, active_app_name: str,
                                              search_scale: float, current_time: float,
                                              last_found_time: Dict, debug_counter: int):
        """
        Ищет шаблоны в изображении и обновляет оверлеи.
        """
        import cv2

        if resized is None:
            return

        img_h, img_w = resized.shape[:2]

        for template_data in active_templates:
            if not self.monitoring:
                break

            if not template_data.get('enabled', True):
                continue

            pair_index = template_data.get('pair_index', 0)
            overlay = template_data.get('overlay')

            # Пропускаем часто найденные шаблоны
            if pair_index in last_found_time:
                time_since_found = current_time - last_found_time[pair_index]
                if template_data.get('found', False) and overlay and overlay.visible and time_since_found < 1.0:
                    continue

            template = template_data.get('template')
            if template is None:
                continue

            t_h, t_w = template.shape[:2]
            scaled_t_w = int(t_w * search_scale)
            scaled_t_h = int(t_h * search_scale)

            if scaled_t_h > img_h or scaled_t_w > img_w:
                continue

            # Кэшируем уменьшенный шаблон
            if 'template_scaled' not in template_data or template_data.get('template_scale') != search_scale:
                template_data['template_scaled'] = cv2.resize(template, (scaled_t_w, scaled_t_h),
                                                              interpolation=cv2.INTER_AREA)
                template_data['template_scale'] = search_scale

            scaled_template = template_data['template_scaled']

            try:
                result = cv2.matchTemplate(resized, scaled_template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
            except Exception as e:
                self.logger.warning(f"[MONITOR] Ошибка matchTemplate для шаблона #{pair_index}: {e}")
                continue

            scaled_x = max_loc[0]
            scaled_y = max_loc[1]
            original_x = int(scaled_x / search_scale)
            original_y = int(scaled_y / search_scale)
            original_w = int(scaled_t_w / search_scale)
            original_h = int(scaled_t_h / search_scale)

            # Логирование для первого сканирования
            if self._first_scan_after_switch:
                if max_val >= self.confidence_threshold:
                    self.logger.info(f"[MONITOR] ✅ Шаблон #{pair_index} найден (точность {max_val:.3f})")

            if max_val >= self.confidence_threshold:
                if not template_data.get('found', False):
                    template_data['found'] = True
                    if debug_counter % 20 == 0:
                        self.logger.info(f"✅ Шаблон #{pair_index} найден с точностью {max_val:.3f}")

                template_data['last_position'] = (original_x, original_y, original_w, original_h)
                self._update_overlay(template_data, original_x, original_y, original_w, original_h)
                last_found_time[pair_index] = current_time
            else:
                if template_data.get('found', False):
                    template_data['found'] = False
                    overlay = template_data.get('overlay')
                    if overlay and overlay.visible and not self.overlay_manager.is_dragging():
                        self._hide_overlay_in_main_thread(overlay, pair_index)

            time.sleep(0.01)

    def _finish_first_scan(self, active_templates: List):
        """Завершает первый скан после переключения окна."""
        found_count = sum(1 for t in active_templates if t.get('found', False))
        total_count = len(active_templates)
        self.logger.info(
            f"[MONITOR] Сканирование завершено: найдено {found_count}/{total_count}"
        )
        self._first_scan_after_switch = False

    def _get_cached_app_name(self, hwnd: int) -> str:
        """Получает имя приложения с кэшированием."""
        if hwnd in self._app_name_cache:
            return self._app_name_cache[hwnd]

        from src.window_utils import get_process_name_by_hwnd
        app_name = get_process_name_by_hwnd(hwnd, default_name="Неизвестно")

        if len(self._app_name_cache) > self._cache_max_size:
            keys = list(self._app_name_cache.keys())
            for key in keys[:len(keys) // 2]:
                del self._app_name_cache[key]

        self._app_name_cache[hwnd] = app_name
        return app_name

    def add_template(self, region_image: Path, translated_image: Path, target_app_name: str = None,
                     is_temporary: bool = False, lifetime_seconds: int = 180):
        """Добавляет новый шаблон для мониторинга. Возвращает (pair_index, file_hash)."""

        if not region_image.exists():
            self.logger.error(f"Шаблон не найден: {region_image}")
            return -1, None

        if not translated_image.exists():
            self.logger.error(f"Перевод не найден: {translated_image}")
            return -1, None

        try:
            template = cv2.imread(str(region_image))
            if template is None:
                self.logger.error(f"Не удалось загрузить шаблон: {region_image}")
                return -1, None

            import hashlib
            with open(region_image, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()

            # Проверяем, существует ли уже такой шаблон
            for template_data in self.templates:
                if template_data.get('hash') == file_hash:
                    self.logger.info(f"Шаблон с хешем {file_hash[:8]} уже существует, обновляем перевод")
                    template_data['translated_path'] = translated_image
                    template_data['template'] = template
                    template_data['found'] = False
                    template_data['last_position'] = None
                    template_data['last_template_position'] = None
                    template_data['is_temporary'] = is_temporary
                    template_data['lifetime_seconds'] = lifetime_seconds
                    if target_app_name:
                        template_data['target_app_name'] = target_app_name
                    if template_data.get('overlay'):
                        try:
                            template_data['overlay'].close()
                        except:
                            pass
                        template_data['overlay'] = None
                    return template_data['pair_index'], file_hash

            pair_index = self._template_counter
            self._template_counter += 1

            template_text = "Шаблон"
            try:
                template_text = region_image.stem
                if template_text.startswith("ocr_region_"):
                    template_text = f"Область {template_text.replace('ocr_region_', '')}"
            except:
                pass

            template_data = {
                'pair_index': pair_index,
                'template_path': region_image,
                'translated_path': translated_image,
                'template': template,
                'hash': file_hash,
                'found': False,
                'last_position': None,
                'last_template_position': None,
                'overlay': None,
                'enabled': True,
                'target_app_name': target_app_name,
                'offset_x': 0,
                'offset_y': 0,
                'offset_initialized': False,
                'overlay_width': 0,
                'overlay_height': 0,
                'is_temporary': is_temporary,
                'lifetime_seconds': lifetime_seconds,
                'template_text': template_text
            }

            self.templates.append(template_data)

            # Локализованное сообщение о добавлении шаблона
            if is_temporary:
                self.logger.info(
                    f"Добавлен временный шаблон #{pair_index} (хеш: {file_hash[:8]}) для приложения {target_app_name}, время жизни: {lifetime_seconds}с"
                )
            else:
                self.logger.info(
                    f"Добавлен шаблон #{pair_index} (хеш: {file_hash[:8]}) для приложения {target_app_name}"
                )

            self._frame_cache = None
            self._frame_cache_hwnd = None
            self._frame_cache_time = 0
            self._last_active_hwnd = None
            self._last_active_app_name = None
            self._idle_counter = 0

            if self.settings and self.settings.get_auto_replace_translated():
                if not self.monitoring:
                    self.start()
                    self.logger.info("Монитор запущен после добавления шаблона")
                else:
                    self.logger.info("Монитор уже запущен, сбрасываем кэш для немедленного сканирования")
                    self._last_check_time = 0

            return pair_index, file_hash

        except Exception as e:
            self.logger.error(f"Ошибка добавления шаблона: {e}")
            return -1, None

    def _capture_window(self, hwnd: int) -> Optional[np.ndarray]:
        """Оптимизированный захват окна с проверкой"""
        if not hwnd:
            return None

        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return None

            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect
            width = x2 - x1
            height = y2 - y1

            if width <= 0 or height <= 0:
                return None

            # ОТЛАДКА: размер окна
            self._capture_debug_counter += 1
            if self._capture_debug_counter % 20 == 0:
                self.logger.info(f"[MONITOR_DEBUG] Захват окна: {width}x{height}, HWND={hwnd}")

            # Пытаемся захватить через PrintWindow
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            dc = win32ui.CreateDCFromHandle(hwnd_dc)
            mem_dc = dc.CreateCompatibleDC()

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(dc, width, height)
            mem_dc.SelectObject(bitmap)

            PW_RENDERFULLCONTENT = 0x00000002
            user32 = ctypes.windll.user32

            result = user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)

            if not result:
                result = user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), 0)

            if result:
                bmpinfo = bitmap.GetInfo()
                bmpstr = bitmap.GetBitmapBits(True)

                img = Image.frombuffer(
                    'RGB',
                    (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                    bmpstr, 'raw', 'BGRX', 0, 1
                )

                dc.DeleteDC()
                mem_dc.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwnd_dc)
                win32gui.DeleteObject(bitmap.GetHandle())

                img_array = np.array(img)
                return cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

            dc.DeleteDC()
            mem_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            win32gui.DeleteObject(bitmap.GetHandle())

            # ОТЛАДКА: PrintWindow не сработал
            if self._capture_debug_counter % 20 == 0:
                self.logger.warning(f"[MONITOR_DEBUG] PrintWindow не сработал для HWND={hwnd}, пробуем BitBlt")

            return self._capture_window_bitblt(hwnd)

        except Exception as e:
            if self._capture_debug_counter % 20 == 0:
                self.logger.warning(f"[MONITOR_DEBUG] Ошибка захвата окна {hwnd}: {e}")
            return self._capture_window_bitblt(hwnd)

    def _capture_window_bitblt(self, hwnd: int) -> Optional[np.ndarray]:
        """Захват окна через BitBlt (fallback)."""
        try:
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return None

            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect
            width = x2 - x1
            height = y2 - y1

            if width <= 0 or height <= 0:
                return None

            hwnd_dc = win32gui.GetWindowDC(hwnd)
            dc = win32ui.CreateDCFromHandle(hwnd_dc)
            mem_dc = dc.CreateCompatibleDC()

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(dc, width, height)
            mem_dc.SelectObject(bitmap)

            mem_dc.BitBlt((0, 0), (width, height), dc, (0, 0), win32con.SRCCOPY)

            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)

            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            dc.DeleteDC()
            mem_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            win32gui.DeleteObject(bitmap.GetHandle())

            img_array = np.array(img)
            img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

            self.logger.debug(f"Окно {hwnd} захвачено через BitBlt: {width}x{height}")
            return img_bgr

        except Exception as e:
            self.logger.warning(f"Ошибка BitBlt захвата окна {hwnd}: {e}")
            return None

    def remove_template(self, pair_index: int):
        """Удаляет шаблон по индексу."""
        self.logger.info(f"[MONITOR] Удаление шаблона #{pair_index}")
        for i, template_data in enumerate(self.templates):
            if template_data['pair_index'] == pair_index:
                # Закрываем оверлей, если он есть
                if template_data.get('overlay'):
                    try:
                        overlay = template_data['overlay']
                        if overlay.root and overlay.root.winfo_exists():
                            overlay.close()
                        self.logger.info(f"[MONITOR] Оверлей закрыт для шаблона #{pair_index}")
                    except Exception as e:
                        self.logger.warning(f"[MONITOR] Ошибка закрытия оверлея при удалении: {e}")
                    template_data['overlay'] = None

                # Удаляем шаблон из списка
                del self.templates[i]
                self.logger.info(f"[MONITOR] ✅ Шаблон #{pair_index} удален. Осталось {len(self.templates)} шаблонов")

                # ИСПРАВЛЕНИЕ: сбрасываем кэш, чтобы монитор не пытался восстановить удалённый шаблон
                self._frame_cache = None
                self._frame_cache_hwnd = None
                self._frame_cache_time = 0
                self._last_active_hwnd = None
                self._last_active_app_name = None

                return

        self.logger.warning(f"[MONITOR] ❌ Шаблон #{pair_index} не найден в списке")

    def start(self):
        """Запускает мониторинг."""
        if self.monitoring:
            return

        if not self.templates:
            self.logger.info("Нет шаблонов для мониторинга")
            return

        self.monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        self.logger.info(f"Мониторинг запущен для {len(self.templates)} шаблонов")

    def stop(self):
        """Останавливает мониторинг."""
        self.logger.info("[MONITOR] Остановка мониторинга...")
        self.monitoring = False

        # Даем потоку время на завершение
        import time
        time.sleep(0.1)

        # Сбрасываем кэш, чтобы освободить память
        self._frame_cache = None
        self._frame_cache_hwnd = None
        self._frame_cache_time = 0

        # Очищаем ссылки на оверлеи
        for template_data in self.templates:
            template_data['overlay'] = None

        self.logger.info("[MONITOR] Мониторинг остановлен")

    def is_running(self) -> bool:
        return self.monitoring

    def set_confidence(self, confidence: float):
        self.confidence_threshold = max(0.5, min(1.0, confidence))

    def set_delay(self, delay: float):
        self.delay_sec = max(0.1, delay)

    def clear_all_templates(self):
        """Удаляет все шаблоны и связанные с ними оверлеи."""
        self.logger.info("[MONITOR] Очистка всех шаблонов...")

        self.monitoring = False

        for template_data in self.templates:
            if template_data.get('overlay'):
                try:
                    overlay = template_data['overlay']
                    if overlay.root and overlay.root.winfo_exists():
                        overlay.close()
                    else:
                        overlay.close()
                except Exception as e:
                    self.logger.warning(f"[MONITOR] Ошибка закрытия оверлея: {e}")

        self.templates.clear()
        self._template_counter = 0
        self._app_name_cache.clear()

        self.logger.info("[MONITOR] Все шаблоны удалены")

    def _update_overlay(self, template_data: Dict, x: int, y: int, w: int, h: int):
        """Обновляет или создает оверлей для шаблона. (Вызывается из фонового потока)"""
        if hasattr(self, '_updating_overlay') and self._updating_overlay:
            return

        # === НОВАЯ ПРОВЕРКА: если монитор остановлен, не создаем оверлей ===
        if not self.monitoring:
            self.logger.debug(
                f"[MONITOR] Монитор остановлен, пропускаем создание оверлея для шаблона #{template_data.get('pair_index')}")
            return

        self._updating_overlay = True

        try:
            translated_path = template_data.get('translated_path')
            if not translated_path or not translated_path.exists():
                return

            pair_index = template_data['pair_index']
            template_id = template_data.get('hash')
            overlay = template_data.get('overlay')
            target_app_name = template_data.get('target_app_name')

            # === УБРАНА ПРОВЕРКА overlay._is_visible_by_user ===
            # Оверлей может быть скрыт, но это не должно блокировать показ

            if self.overlay_manager and self.overlay_manager.is_dragging():
                self.logger.debug(f"[MONITOR] Перетаскивание активно, пропускаем обновление шаблона #{pair_index}")
                return

            # === УБРАНА ПРОВЕРКА АКТИВНОГО ПРИЛОЖЕНИЯ ===
            # Проверка будет выполняться в _update_overlay_gui в главном потоке

            if self.parent and hasattr(self.parent, 'root'):
                root = self.parent.root
                if root and root.winfo_exists():
                    # === ВСЕГДА ВЫЗЫВАЕМ _update_overlay_gui, КОГДА ШАБЛОН НАЙДЕН ===
                    self.logger.info(
                        f"[MONITOR] Отправка _update_overlay_gui в главный поток для шаблона #{pair_index}")
                    root.after(0, lambda: self._update_overlay_gui(template_data, x, y, w, h, translated_path,
                                                                   template_id))
                else:
                    self.logger.warning("[DEBUG] root не существует, пропускаем")
            else:
                self.logger.warning("[DEBUG] parent.root не найден, пропускаем")

        finally:
            self._updating_overlay = False

    def _update_overlay_gui(self, template_data: Dict, x: int, y: int, w: int, h: int, translated_path: Path,
                            template_id: str):
        """Обновляет или создает оверлей в главном потоке с проверкой активного окна."""

        try:
            if not self.monitoring:
                return

            pair_index = template_data['pair_index']
            overlay = template_data.get('overlay')
            target_app_name = template_data.get('target_app_name')
            is_found = template_data.get('found', False)
            is_temporary = template_data.get('is_temporary', False)
            lifetime_seconds = template_data.get('lifetime_seconds', 180)

            # ============================================================
            # ПРОВЕРКА АКТИВНОГО ОКНА
            # ============================================================
            try:
                import win32gui
                from src.window_utils import get_process_name_by_hwnd

                active_hwnd = win32gui.GetForegroundWindow()
                if active_hwnd:
                    active_app_name = get_process_name_by_hwnd(active_hwnd)

                    if active_app_name and active_app_name.lower() == self._our_app_name:
                        self.logger.debug(f"[MONITOR] Активное окно {active_app_name} (наше приложение), не скрываем")
                    elif target_app_name and target_app_name != "Неизвестно":
                        if active_app_name != target_app_name:
                            self.logger.info(
                                f"[MONITOR] Шаблон #{pair_index} для {target_app_name}, "
                                f"но активное окно {active_app_name} — скрываем оверлей"
                            )
                            if overlay and overlay.visible:
                                self._hide_overlay_in_main_thread(overlay, pair_index)
                            return
            except Exception as e:
                self.logger.warning(f"[MONITOR] Ошибка проверки активного окна: {e}")

            if not template_id:
                template_id = template_data.get('hash')

            if not is_found:
                if overlay and overlay.visible:
                    self._hide_overlay_in_main_thread(overlay, pair_index)
                return

            # ШАБЛОН НАЙДЕН
            template_x = x
            template_y = y
            template_w = w
            template_h = h

            offset_x = template_data.get('offset_x', 0)
            offset_y = template_data.get('offset_y', 0)

            overlay_w = template_data.get('overlay_width', template_w)
            overlay_h = template_data.get('overlay_height', template_h)

            if overlay_w == 0 or overlay_h == 0:
                overlay_w = template_w
                overlay_h = template_h
                template_data['overlay_width'] = overlay_w
                template_data['overlay_height'] = overlay_h

            final_x = template_x + offset_x
            final_y = template_y + offset_y
            final_w = overlay_w
            final_h = overlay_h

            current_template_pos = (template_x, template_y)
            last_template_pos = template_data.get('last_template_position')

            # ЕСЛИ ОВЕРЛЕЙ УЖЕ СУЩЕСТВУЕТ
            if overlay:
                try:
                    if overlay.root and overlay.root.winfo_exists():
                        if not overlay.can_be_shown_by_monitor():
                            self.logger.info(
                                f"[MONITOR] Шаблон #{pair_index} найден, но оверлей скрыт мышью/пользователем, не показываем"
                            )
                            return

                        if hasattr(overlay, '_closing') and overlay._closing:
                            return

                        position_changed = (last_template_pos is None or last_template_pos != current_template_pos)

                        if position_changed:
                            overlay.root.geometry(f"{final_w}x{final_h}+{final_x}+{final_y}")
                            overlay.root.update_idletasks()
                            overlay._last_window_rect = (final_x, final_y, final_x + final_w, final_y + final_h)
                            overlay._saved_position = (final_x, final_y)
                            template_data['last_template_position'] = current_template_pos
                            self.logger.info(f"[MONITOR] Обновлена позиция оверлея #{pair_index}")

                        overlay._hidden_by_user = False
                        overlay._hidden_by_mouse = False

                        if not overlay.visible:
                            overlay.show()
                            # ============================================================
                            # ДОБАВЛЯЕМ ОВЕРЛЕЙ В СПИСОК НЕДАВНО АКТИВНЫХ
                            # ============================================================
                            if self.parent and hasattr(self.parent, '_add_recent_overlay'):
                                self.parent._add_recent_overlay(overlay)
                            self.logger.info(f"[MONITOR] Показан оверлей #{pair_index}")
                        else:
                            if position_changed:
                                overlay.root.lift()

                        return
                    else:
                        template_data['overlay'] = None
                except Exception as e:
                    self.logger.warning(f"[MONITOR] Ошибка обновления оверлея #{pair_index}: {e}")
                    template_data['overlay'] = None

            # СОЗДАЁМ НОВЫЙ ОВЕРЛЕЙ
            if not self.monitoring:
                return

            if self.overlay_manager:
                try:
                    if not template_data.get('offset_initialized', False):
                        template_data['offset_x'] = 0
                        template_data['offset_y'] = 0
                        template_data['offset_initialized'] = True
                        template_data['overlay_width'] = template_w
                        template_data['overlay_height'] = template_h

                    window_rect = (final_x, final_y, final_x + final_w, final_y + final_h)

                    target_hwnd = None
                    if target_app_name and target_app_name != "Неизвестно":
                        target_hwnd = self._find_window_by_app_name(target_app_name)

                    new_overlay = self.overlay_manager._create_overlay_from_data(
                        image_path=translated_path,
                        window_rect=window_rect,
                        target_hwnd=target_hwnd,
                        is_auto_replace=True,
                        is_window_screenshot=False,
                        template_id=template_id,
                        show_immediately=True,
                        saved_x=final_x,
                        saved_y=final_y,
                        saved_w=final_w,
                        saved_h=final_h,
                        app_name=target_app_name,
                        is_temporary=is_temporary,
                        lifetime_seconds=lifetime_seconds
                    )

                    if new_overlay:
                        template_data['overlay'] = new_overlay
                        template_data['last_template_position'] = current_template_pos

                        new_overlay._is_visible_by_user = True
                        new_overlay._hidden_by_user = False
                        new_overlay._hidden_by_mouse = False
                        new_overlay._is_auto_replace = True
                        new_overlay._creation_time = time.time()
                        new_overlay._monitor_stable_time = time.time() + 3.0
                        new_overlay.auto_hide_enabled = False
                        new_overlay._stop_visibility_monitor()

                        if not new_overlay.visible:
                            new_overlay.show()
                            # ============================================================
                            # ДОБАВЛЯЕМ ОВЕРЛЕЙ В СПИСОК НЕДАВНО АКТИВНЫХ
                            # ============================================================
                            if self.parent and hasattr(self.parent, '_add_recent_overlay'):
                                self.parent._add_recent_overlay(new_overlay)

                        template_data['overlay_width'] = final_w
                        template_data['overlay_height'] = final_h

                        self.logger.info(f"[MONITOR] Создан оверлей для шаблона #{pair_index}")

                except Exception as e:
                    self.logger.error(f"[MONITOR] Ошибка создания оверлея #{pair_index}: {e}")

        except Exception as e:
            self.logger.error(f"[MONITOR] Ошибка в _update_overlay_gui: {e}")

    def _find_window_by_app_name(self, app_name: str) -> Optional[int]:
        """Находит HWND окна по имени приложения."""
        try:
            import win32gui

            def enum_callback(hwnd, hwnds):
                if win32gui.IsWindowVisible(hwnd):
                    try:
                        from src.window_utils import get_process_name_by_hwnd
                        if get_process_name_by_hwnd(hwnd) == app_name:
                            hwnds.append(hwnd)
                            return False
                    except:
                        pass
                return True

            hwnds = []
            win32gui.EnumWindows(enum_callback, hwnds)
            return hwnds[0] if hwnds else None
        except Exception as e:
            self.logger.warning(f"[MONITOR] Ошибка поиска окна по имени {app_name}: {e}")
            return None

    def _hide_overlay_in_main_thread(self, overlay, pair_index):
        """Скрывает оверлей в главном потоке."""
        # --- ИСПРАВЛЕНИЕ: проверяем перетаскивание перед отправкой в главный поток ---
        if self.overlay_manager and self.overlay_manager.is_dragging():
            self.logger.info(f"[MONITOR] Перетаскивание активно, оверлей #{pair_index} не скрываем")
            return

        if self.parent and hasattr(self.parent, 'root'):
            root = self.parent.root
            if root and root.winfo_exists():
                root.after(0, lambda: self._hide_overlay_gui(overlay, pair_index))

    def _hide_overlay_gui(self, overlay, pair_index):
        """Скрывает оверлей в главном потоке."""
        try:
            # --- ИСПРАВЛЕНИЕ: не скрываем во время перетаскивания ---
            if self.overlay_manager and self.overlay_manager.is_dragging():
                self.logger.info(f"[MONITOR] Перетаскивание активно, оверлей #{pair_index} не скрываем")
                return

            if overlay and overlay.visible:
                overlay._stop_visibility_monitor()
                overlay.visible = False
                overlay.root.withdraw()
                overlay._hidden_by_user = False
                overlay._hidden_by_mouse = False
                overlay._mouse_over = False
                self.logger.info(f"[MONITOR] Оверлей #{pair_index} скрыт в главном потоке")
        except Exception as e:
            self.logger.warning(f"[MONITOR] Ошибка скрытия оверлея #{pair_index}: {e}")

    def _find_in_window(self, image: np.ndarray, template_data: Dict):
        """Ищет шаблон в изображении окна."""
        if image is None:
            return

        idx = template_data.get('pair_index')
        img_h, img_w = image.shape[:2]

        template = template_data.get('template')
        if template is None:
            self.logger.warning(f"Шаблон #{idx} пустой")
            return

        t_h, t_w = template.shape[:2]

        if t_h > img_h or t_w > img_w:
            if template_data.get('found', False):
                template_data['found'] = False
                overlay = template_data.get('overlay')
                if overlay and overlay.visible:
                    self._hide_overlay_in_main_thread(overlay, idx)
            return

        try:
            result = cv2.matchTemplate(image, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if max_val >= self.confidence_threshold:
                template_x = max_loc[0]
                template_y = max_loc[1]

                if not template_data.get('found', False):
                    template_data['found'] = True
                    self.logger.info(f"Шаблон #{idx} найден с точностью {max_val:.3f}")

                template_data['last_position'] = (template_x, template_y, t_w, t_h)
                self._update_overlay(template_data, template_x, template_y, t_w, t_h)
            else:
                if template_data.get('found', False):
                    template_data['found'] = False
                    overlay = template_data.get('overlay')
                    if overlay and overlay.visible:
                        self._hide_overlay_in_main_thread(overlay, idx)

        except Exception as e:
            self.logger.warning(f"Ошибка поиска шаблона #{idx}: {e}")
