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

import cv2
import numpy as np
import win32gui
import win32ui
import win32con
import ctypes
from PIL import Image, ImageGrab
import ctypes

class TranslationMonitor:
    """Мониторит экран, ищет сохраненные области (шаблоны) и показывает их переводы."""

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
        self.delay_sec = 0.3
        self._template_counter = 0

        if settings:
            self.confidence_threshold = settings.get_confidence_threshold()
            self.delay_sec = settings.get_monitor_delay()

        self.logger.info("TranslationMonitor инициализирован")

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

        # === УБИРАЕМ ПРИНУДИТЕЛЬНЫЙ ПОКАЗ ОВЕРЛЕЕВ ПРИ ЗАПУСКЕ ===
        # Оверлеи будут показаны только когда шаблоны будут найдены при сканировании
        # Это устраняет "мигание" при восстановлении

    def add_template(self, region_image: Path, translated_image: Path, target_hwnd: int = None):
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

            # Проверяем, существует ли уже шаблон с таким хешем
            for template_data in self.templates:
                if template_data.get('hash') == file_hash:
                    self.logger.info(f"Шаблон с хешем {file_hash[:8]} уже существует, обновляем перевод")
                    template_data['translated_path'] = translated_image
                    template_data['target_hwnd'] = target_hwnd
                    return template_data['pair_index'], file_hash

            pair_index = self._template_counter
            self._template_counter += 1

            template_data = {
                'pair_index': pair_index,
                'template_path': region_image,
                'translated_path': translated_image,
                'template': template,
                'hash': file_hash,
                'found': False,
                'last_position': None,
                'overlay': None,
                'enabled': True,
                'target_hwnd': target_hwnd
            }

            self.templates.append(template_data)
            self.logger.info(f"Добавлен шаблон #{pair_index} (хеш: {file_hash[:8]}) для окна HWND={target_hwnd}")

            if self.settings and self.settings.get_auto_replace_translated():
                if not self.monitoring:
                    self.start()

            return pair_index, file_hash

        except Exception as e:
            self.logger.error(f"Ошибка добавления шаблона: {e}")
            return -1, None

    def _update_overlay(self, template_data: Dict, x: int, y: int, w: int, h: int):
        """Обновляет или создает оверлей для шаблона."""
        translated_path = template_data.get('translated_path')
        if not translated_path or not translated_path.exists():
            return

        pair_index = template_data['pair_index']
        template_id = f"pair_{pair_index}"

        saved_position = None
        if self.overlay_manager:
            saved_position = self.overlay_manager.get_saved_position(template_id)

        if template_data.get('overlay'):
            try:
                overlay = template_data['overlay']
                if overlay.root and overlay.root.winfo_exists():
                    if saved_position:
                        saved_x, saved_y = saved_position
                        current_x = overlay.root.winfo_x()
                        current_y = overlay.root.winfo_y()
                        if abs(current_x - saved_x) > 5 or abs(current_y - saved_y) > 5:
                            overlay.root.geometry(f"+{saved_x}+{saved_y}")
                            self.logger.info(
                                f"[MONITOR] Оверлей #{pair_index} перемещен в сохраненную позицию ({saved_x}, {saved_y})")
                    else:
                        current_x = overlay.root.winfo_x()
                        current_y = overlay.root.winfo_y()
                        if abs(current_x - x) > 5 or abs(current_y - y) > 5:
                            overlay.root.geometry(f"+{x}+{y}")
                            self.logger.info(f"[MONITOR] Оверлей #{pair_index} перемещен в позицию шаблона ({x}, {y})")

                    if not overlay.visible and not overlay._hidden_by_user:
                        overlay._is_visible_by_user = True
                        overlay.root.after(0,
                                           lambda: overlay.show() if overlay.root and overlay.root.winfo_exists() else None)
                        self.logger.info(f"[MONITOR] Оверлей #{pair_index} показан (найден шаблон)")
                    elif not overlay.visible and overlay._hidden_by_user:
                        self.logger.info(f"[MONITOR] Оверлей #{pair_index} найден, но скрыт пользователем (F1)")
                    return
                else:
                    template_data['overlay'] = None
            except:
                template_data['overlay'] = None

        if self.overlay_manager:
            window_rect = (x, y, x + w, y + h)
            if saved_position:
                saved_x, saved_y = saved_position
                window_rect = (saved_x, saved_y, saved_x + w, saved_y + h)
                self.logger.info(
                    f"[MONITOR] Используем сохраненную позицию для оверлея #{pair_index}: ({saved_x}, {saved_y})")

            overlay = self.overlay_manager.create_overlay(
                image_path=translated_path,
                window_rect=window_rect,
                target_hwnd=template_data.get('target_hwnd'),
                is_fullscreen=False,
                show_immediately=True,
                is_window_screenshot=False,
                is_auto_replace=True,
                template_id=template_id
            )
            if overlay:
                template_data['overlay'] = overlay
                overlay._is_visible_by_user = True
                overlay._is_auto_replace = True
                overlay._creation_time = time.time()
                overlay._monitor_stable_time = time.time() + 3.0
                if not overlay._hidden_by_user:
                    overlay.show()
                self.logger.info(f"[MONITOR] Создан новый оверлей для шаблона #{pair_index}")

    def _capture_window(self, hwnd: int) -> Optional[np.ndarray]:
        """Захватывает скриншот окна через PrintWindow (для браузеров)."""
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

            # Сначала пробуем PrintWindow (работает с браузерами)
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
                img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

                self.logger.debug(f"Окно {hwnd} захвачено через PrintWindow: {width}x{height}")
                return img_bgr

            dc.DeleteDC()
            mem_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)
            win32gui.DeleteObject(bitmap.GetHandle())

            # Если PrintWindow не сработал - пробуем BitBlt
            self.logger.debug(f"PrintWindow не сработал для {hwnd}, пробуем BitBlt")
            return self._capture_window_bitblt(hwnd)

        except Exception as e:
            self.logger.warning(f"Ошибка захвата окна {hwnd}: {e}")
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
                if template_data.get('overlay'):
                    try:
                        overlay = template_data['overlay']
                        if overlay.visible:
                            overlay.hide(by_user=False)  # <-- by_user=False
                    except:
                        pass
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
                    if template_data.get('overlay'):
                        try:
                            overlay = template_data['overlay']
                            if overlay.visible:
                                overlay.hide(by_user=False)  # <-- by_user=False
                                self.logger.info(f"Шаблон #{idx} НЕ НАЙДЕН, скрываем оверлей")
                        except:
                            pass

        except Exception as e:
            self.logger.warning(f"Ошибка поиска шаблона #{idx}: {e}")

    def remove_template(self, pair_index: int):
        """Удаляет шаблон по индексу."""
        for i, template_data in enumerate(self.templates):
            if template_data['pair_index'] == pair_index:
                if template_data['overlay']:
                    try:
                        template_data['overlay'].close()
                    except:
                        pass
                del self.templates[i]
                self.logger.info(f"Удален шаблон #{pair_index}")
                return

    def clear_all_templates(self):
        """Удаляет все шаблоны."""
        for template_data in self.templates:
            if template_data['overlay']:
                try:
                    template_data['overlay'].close()
                except:
                    pass
        self.templates.clear()
        self.logger.info("Все шаблоны удалены")

    def stop(self):
        """Останавливает мониторинг."""
        self.monitoring = False
        for template_data in self.templates:
            template_data['found'] = False
            if template_data.get('overlay'):
                try:
                    overlay = template_data['overlay']
                    if overlay.visible:
                        overlay.hide()
                except:
                    pass
        self.logger.info("Мониторинг остановлен")

    def is_running(self) -> bool:
        return self.monitoring

    def set_confidence(self, confidence: float):
        self.confidence_threshold = max(0.5, min(1.0, confidence))

    def set_delay(self, delay: float):
        self.delay_sec = max(0.1, delay)

    def _monitor_loop(self):
        """Основной цикл мониторинга — проверяет ТОЛЬКО шаблоны активного окна."""
        last_time = time.time()
        self.logger.info("[MONITOR] Цикл мониторинга запущен")

        iteration_count = 0

        while self.monitoring:
            try:
                current_time = time.time()
                if current_time - last_time >= self.delay_sec:
                    last_time = current_time
                    iteration_count += 1

                    if iteration_count % 10 == 0:
                        self.logger.info(f"[MONITOR] Итерация #{iteration_count}, шаблонов: {len(self.templates)}")

                    if not self.monitoring:
                        break

                    if not self.templates:
                        time.sleep(0.1)
                        continue

                    # === ПОЛУЧАЕМ АКТИВНОЕ ОКНО ===
                    try:
                        import win32gui
                        active_hwnd = win32gui.GetForegroundWindow()
                        if not active_hwnd:
                            time.sleep(0.05)
                            continue
                    except:
                        time.sleep(0.05)
                        continue

                    # === ПРОВЕРКА: ЯВЛЯЕТСЯ ЛИ АКТИВНОЕ ОКНО ОКНОМ ВЫДЕЛЕНИЯ ===
                    is_selection_window = False
                    try:
                        if hasattr(self, 'parent') and self.parent:
                            parent = self.parent
                            if hasattr(parent, '_capture_mode') and parent._capture_mode:
                                is_selection_window = True
                    except:
                        pass

                    if is_selection_window:
                        time.sleep(0.05)
                        continue

                    # === ПРОВЕРЯЕМ ТОЛЬКО ШАБЛОНЫ ДЛЯ АКТИВНОГО ОКНА ===
                    for template_data in self.templates:
                        if not template_data.get('enabled', True):
                            continue

                        target_hwnd = template_data.get('target_hwnd')
                        if not target_hwnd:
                            continue

                        # === ЕСЛИ ОКНО НЕ АКТИВНО — СКРЫВАЕМ ОВЕРЛЕЙ, НО НЕ УДАЛЯЕМ ===
                        if target_hwnd != active_hwnd:
                            if template_data.get('overlay'):
                                try:
                                    overlay = template_data['overlay']
                                    if overlay.visible:
                                        overlay.hide(by_user=False)
                                        self.logger.info(f"[MONITOR] Оверлей скрыт - окно {target_hwnd} не активно")
                                except:
                                    pass
                            continue

                        # === ПРОВЕРЯЕМ СУЩЕСТВОВАНИЕ ОКНА ===
                        try:
                            if not win32gui.IsWindow(target_hwnd) or not win32gui.IsWindowVisible(target_hwnd):
                                if template_data.get('found', False):
                                    template_data['found'] = False
                                    if template_data.get('overlay'):
                                        try:
                                            overlay = template_data['overlay']
                                            if overlay.visible:
                                                overlay.hide(by_user=False)
                                                self.logger.info(
                                                    f"[MONITOR] Окно {target_hwnd} недоступно, скрываем оверлей")
                                        except:
                                            pass
                                continue
                        except:
                            continue

                        # === ЗАХВАТЫВАЕМ СКРИНШОТ АКТИВНОГО ОКНА ===
                        image = self._capture_window(target_hwnd)
                        if image is None:
                            continue

                        # === ИЩЕМ ШАБЛОН В ЭТОМ ОКНЕ ===
                        self._find_in_window(image, template_data)

                    time.sleep(0.05)

            except Exception as e:
                self.logger.error(f"[MONITOR] Ошибка: {e}")
                time.sleep(0.5)

        self.logger.info("[MONITOR] Цикл мониторинга завершен")
