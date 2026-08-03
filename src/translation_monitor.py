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

            # Запускаем монитор если автозамена включена
            if self.settings and self.settings.get_auto_replace_translated():
                if not self.monitoring:
                    self.start()
                    self.logger.info("Монитор запущен после добавления шаблона")

            return pair_index, file_hash

        except Exception as e:
            self.logger.error(f"Ошибка добавления шаблона: {e}")
            return -1, None

    def clear_all_templates(self):
        """Удаляет все шаблоны и связанные с ними оверлеи."""
        self.logger.info("[MONITOR] Очистка всех шаблонов...")

        # Сначала останавливаем монитор
        self.monitoring = False

        # Закрываем все оверлеи, связанные с шаблонами
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

        # Очищаем список шаблонов
        self.templates.clear()
        self._template_counter = 0

        self.logger.info("[MONITOR] Все шаблоны удалены")

    def _update_overlay_gui(self, template_data: Dict, x: int, y: int, w: int, h: int, translated_path: Path,
                            template_id: str):
        """Обновляет или создает оверлей в главном потоке. Позиция вычисляется ДО создания."""
        try:
            self.logger.info(
                f"[DEBUG] === _update_overlay_gui НАЧАЛО для шаблона #{template_data.get('pair_index')} ===")

            pair_index = template_data['pair_index']
            overlay = template_data.get('overlay')
            target_hwnd = template_data.get('target_hwnd')

            if not template_id:
                template_id = template_data.get('hash')

            if template_data.get('found', False) is False:
                self.logger.info(f"[DEBUG] Шаблон #{pair_index} больше не найден, пропускаем показ")
                return

            # === ВЫЧИСЛЯЕМ ФИНАЛЬНУЮ ПОЗИЦИЮ ===
            final_x = x
            final_y = y
            final_w = w
            final_h = h

            # Если оверлей уже существует - проверяем сохраненную позицию
            if overlay:
                try:
                    if overlay.root and overlay.root.winfo_exists():
                        # === ВСЕГДА ПРОВЕРЯЕМ СОХРАНЕННУЮ ПОЗИЦИЮ ===
                        saved_position = None
                        if self.overlay_manager:
                            saved_position = self.overlay_manager.get_saved_position(template_id)

                        if saved_position:
                            saved_x, saved_y = saved_position
                            final_x = saved_x
                            final_y = saved_y
                            self.logger.info(f"[DEBUG] Используем сохраненную позицию оверлея: ({saved_x}, {saved_y})")

                            # Если оверлей виден и позиция изменилась - обновляем
                            if overlay.visible:
                                current_x = overlay.root.winfo_x()
                                current_y = overlay.root.winfo_y()
                                if abs(current_x - saved_x) > 5 or abs(current_y - saved_y) > 5:
                                    overlay.root.geometry(f"+{saved_x}+{saved_y}")
                                    self.logger.info(
                                        f"[DEBUG] Обновлена позиция оверлея на сохраненную: ({saved_x}, {saved_y})")
                                # Если оверлей скрыт, но должен быть виден - показываем
                                if not overlay.visible and overlay._is_visible_by_user and not overlay._hidden_by_user:
                                    overlay._saved_position = (saved_x, saved_y)
                                    overlay._user_moved = True
                                    overlay.show()
                                return
                        else:
                            # Нет сохраненной позиции - используем позицию шаблона
                            self.logger.info(f"[DEBUG] Нет сохраненной позиции, используем позицию шаблона: ({x}, {y})")
                            current_x = overlay.root.winfo_x()
                            current_y = overlay.root.winfo_y()
                            if abs(current_x - x) > 5 or abs(current_y - y) > 5:
                                overlay.root.geometry(f"+{x}+{y}")
                                self.logger.info(f"[DEBUG] Обновлена позиция оверлея на позицию шаблона: ({x}, {y})")

                            if not overlay.visible and overlay._is_visible_by_user and not overlay._hidden_by_user:
                                overlay.show()
                            elif overlay.visible:
                                overlay.root.lift()
                            return
                    else:
                        template_data['overlay'] = None
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Ошибка при обновлении существующего оверлея: {e}")
                    template_data['overlay'] = None

            # === СОЗДАЁМ НОВЫЙ ОВЕРЛЕЙ ===
            self.logger.info(f"[DEBUG] Создаем новый оверлей для шаблона #{pair_index}")

            if self.overlay_manager:
                try:
                    # Проверяем сохраненную позицию перед созданием
                    saved_position = self.overlay_manager.get_saved_position(template_id)
                    if saved_position:
                        saved_x, saved_y = saved_position
                        final_x = saved_x
                        final_y = saved_y
                        self.logger.info(f"[DEBUG] Создаем оверлей с сохраненной позицией: ({saved_x}, {saved_y})")

                    window_rect = (final_x, final_y, final_x + final_w, final_y + final_h)

                    # Используем общий метод из overlay_manager с финальной позицией
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
                        saved_h=final_h
                    )

                    if new_overlay:
                        template_data['overlay'] = new_overlay
                        new_overlay._is_visible_by_user = True
                        new_overlay._is_auto_replace = True
                        new_overlay._creation_time = time.time()
                        new_overlay._monitor_stable_time = time.time() + 3.0
                        new_overlay._user_moved = True  # Важно: помечаем как перемещенный, чтобы сохранялась позиция
                        new_overlay.auto_hide_enabled = False
                        new_overlay._stop_visibility_monitor()

                        self.logger.info(
                            f"[MONITOR] Создан и показан новый оверлей для шаблона #{pair_index} в позиции ({final_x}, {final_y})")
                    else:
                        self.logger.warning(f"[MONITOR] Не удалось создать оверлей для шаблона #{pair_index}")
                except Exception as e:
                    self.logger.error(f"[MONITOR] Ошибка создания оверлея для шаблона #{pair_index}: {e}")
            else:
                self.logger.warning("[MONITOR] overlay_manager отсутствует")

            self.logger.info(f"[DEBUG] === _update_overlay_gui ЗАВЕРШЕН для шаблона #{pair_index} ===")

        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка в _update_overlay_gui: {e}")
            import traceback
            traceback.print_exc()

    def _monitor_loop(self):
        """Основной цикл мониторинга — проверяет ТОЛЬКО шаблоны активного окна."""
        last_time = time.time()
        self.logger.info("[MONITOR] Цикл мониторинга запущен")

        iteration_count = 0
        last_found_time = {}

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

                    # === ПРОВЕРКА: ИДЕТ ЛИ ПЕРЕТАСКИВАНИЕ ОВЕРЛЕЯ ===
                    if self.overlay_manager and self.overlay_manager.is_dragging():
                        time.sleep(0.05)
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

                        overlay = template_data.get('overlay')
                        is_overlay_visible_by_user = overlay._is_visible_by_user if overlay else False

                        # === ЕСЛИ ОКНО НЕ АКТИВНО — ПРИНУДИТЕЛЬНО СКРЫВАЕМ ОВЕРЛЕЙ ===
                        # НО НЕ СКРЫВАЕМ, ЕСЛИ ИДЕТ ПЕРЕТАСКИВАНИЕ (уже проверили выше)
                        if target_hwnd != active_hwnd:
                            # Проверяем режим редактирования: если оверлей в режиме редактирования, НЕ СКРЫВАЕМ
                            if overlay and hasattr(overlay, '_edit_mode_enabled') and overlay._edit_mode_enabled:
                                self.logger.debug(
                                    f"[MONITOR] Шаблон #{template_data.get('pair_index')} в режиме редактирования, не скрываем при смене окна")
                                continue
                            if overlay and overlay.visible:
                                # Скрываем в главном потоке
                                self._hide_overlay_in_main_thread(overlay, template_data.get('pair_index', 0))
                            continue

                        # === ПРОВЕРЯЕМ СУЩЕСТВОВАНИЕ ОКНА ===
                        try:
                            if not win32gui.IsWindow(target_hwnd) or not win32gui.IsWindowVisible(target_hwnd):
                                if template_data.get('found', False):
                                    template_data['found'] = False
                                    if overlay and overlay.visible:
                                        self._hide_overlay_in_main_thread(overlay, template_data.get('pair_index', 0))
                                continue
                        except:
                            continue

                        # === ЕСЛИ ПОЛЬЗОВАТЕЛЬ СКРЫЛ ОВЕРЛЕЙ (F1) — НЕ ПОКАЗЫВАЕМ ЕГО ===
                        if overlay and not is_overlay_visible_by_user:
                            continue

                        # === ПРОВЕРКА: НЕ НАХОДИЛИ ЛИ ШАБЛОН СЛИШКОМ НЕДАВНО ===
                        pair_index = template_data.get('pair_index', 0)
                        if pair_index in last_found_time:
                            time_since_found = time.time() - last_found_time[pair_index]
                            if template_data.get('found',
                                                 False) and overlay and overlay.visible and time_since_found < 2.0:
                                continue

                        # === ЗАХВАТЫВАЕМ СКРИНШОТ АКТИВНОГО ОКНА ===
                        image = self._capture_window(target_hwnd)
                        if image is None:
                            continue

                        # === ИЩЕМ ШАБЛОН В ЭТОМ ОКНЕ ===
                        self._find_in_window(image, template_data)

                        # Обновляем время последнего поиска для этого шаблона
                        if template_data.get('found', False):
                            last_found_time[pair_index] = time.time()

                    time.sleep(0.05)

            except Exception as e:
                self.logger.error(f"[MONITOR] Ошибка: {e}")
                time.sleep(0.5)

        self.logger.info("[MONITOR] Цикл мониторинга завершен")

    def _update_overlay(self, template_data: Dict, x: int, y: int, w: int, h: int):
        """Обновляет или создает оверлей для шаблона. (Вызывается из фонового потока)"""
        # Защита от рекурсивных вызовов
        if hasattr(self, '_updating_overlay') and self._updating_overlay:
            return
        self._updating_overlay = True

        try:
            self.logger.info(f"[DEBUG] === _update_overlay НАЧАЛО для шаблона #{template_data.get('pair_index')} ===")

            translated_path = template_data.get('translated_path')
            if not translated_path or not translated_path.exists():
                self.logger.info("[DEBUG] translated_path не существует, пропускаем")
                return

            pair_index = template_data['pair_index']
            template_id = template_data.get('hash')
            overlay = template_data.get('overlay')
            target_hwnd = template_data.get('target_hwnd')

            # === ПРОВЕРКА: СКРЫТ ЛИ ОВЕРЛЕЙ ПОЛЬЗОВАТЕЛЕМ ===
            if overlay and not overlay._is_visible_by_user:
                self.logger.info(f"[DEBUG] Оверлей #{pair_index} скрыт пользователем, не показываем")
                return

            # === ПРОВЕРКА: АКТИВНО ЛИ ЦЕЛЕВОЕ ОКНО ===
            if target_hwnd:
                try:
                    import win32gui
                    if not win32gui.IsWindow(target_hwnd):
                        self.logger.info(f"[DEBUG] Целевое окно HWND={target_hwnd} не существует, пропускаем")
                        return
                    active_hwnd = win32gui.GetForegroundWindow()
                    if active_hwnd != target_hwnd:
                        self.logger.info(f"[DEBUG] Целевое окно HWND={target_hwnd} не активно, оверлей не создаем")
                        if overlay and overlay.visible:
                            self._hide_overlay_in_main_thread(overlay, pair_index)
                        return
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Ошибка проверки активного окна: {e}")

            # === ВЫПОЛНЯЕМ GUI-ОПЕРАЦИИ В ГЛАВНОМ ПОТОКЕ ===
            if self.parent and hasattr(self.parent, 'root'):
                root = self.parent.root
                if root and root.winfo_exists():
                    root.after(0, lambda: self._update_overlay_gui(template_data, x, y, w, h, translated_path,
                                                                   template_id))
                else:
                    self.logger.warning("[DEBUG] root не существует, пропускаем")
            else:
                self.logger.warning("[DEBUG] parent.root не найден, пропускаем")

            self.logger.info(f"[DEBUG] === _update_overlay ЗАВЕРШЕН для шаблона #{pair_index} ===")

        finally:
            self._updating_overlay = False

    def _hide_overlay_in_main_thread(self, overlay, pair_index):
        """Скрывает оверлей в главном потоке."""
        if self.parent and hasattr(self.parent, 'root'):
            root = self.parent.root
            if root and root.winfo_exists():
                root.after(0, lambda: self._hide_overlay_gui(overlay, pair_index))

    def _hide_overlay_gui(self, overlay, pair_index):
        """Скрывает оверлей в главном потоке."""
        try:
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

        # Оверлеи будут показаны только когда шаблоны будут найдены при сканировании
        # Это устраняет "мигание" при восстановлении

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
                    except Exception as e:
                        self.logger.warning(f"[MONITOR] Ошибка закрытия оверлея при удалении: {e}")
                del self.templates[i]
                self.logger.info(f"[MONITOR] ✅ Шаблон #{pair_index} удален. Осталось {len(self.templates)} шаблонов")
                return
        self.logger.warning(f"[MONITOR] ❌ Шаблон #{pair_index} не найден в списке")

    def stop(self):
        """Останавливает мониторинг и скрывает все оверлеи."""
        self.monitoring = False
        self.logger.info("[MONITOR] Мониторинг остановлен")

    def is_running(self) -> bool:
        return self.monitoring

    def set_confidence(self, confidence: float):
        self.confidence_threshold = max(0.5, min(1.0, confidence))

    def set_delay(self, delay: float):
        self.delay_sec = max(0.1, delay)
