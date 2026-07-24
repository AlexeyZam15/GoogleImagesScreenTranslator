"""
Модуль для захвата скриншотов активного окна
Использует DXcam для полноэкранных приложений
"""

import logging
from typing import Optional, Tuple
from PIL import Image
import win32gui
import win32con
import win32ui
import win32api
import dxcam
import cv2
import numpy as np


class ScreenshotCapturer:
    """Класс для захвата скриншотов активного окна"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._last_window_rect = None
        self._last_hwnd = None
        self._is_fullscreen = False
        self.camera = None

    def is_window_fullscreen(self, hwnd: int) -> bool:
        """Проверяет, находится ли окно в полноэкранном режиме"""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect
            win_width = x2 - x1
            win_height = y2 - y1

            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

            is_fullscreen = (win_width >= screen_width - 10 and
                             win_height >= screen_height - 10)

            if is_fullscreen:
                self.logger.info(f"Окно {hwnd} определено как полноэкранное")

            return is_fullscreen
        except Exception as e:
            self.logger.warning(f"Ошибка проверки полноэкранного режима: {e}")
            return False

    def get_active_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Возвращает координаты активного окна"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return None
            rect = win32gui.GetWindowRect(hwnd)
            return rect
        except Exception as e:
            self.logger.error(f"Ошибка получения размеров окна: {e}")
            return None

    def capture_active_window(self) -> Optional[Image.Image]:
        """Захватывает скриншот активного окна"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                self.logger.error("Не удалось получить активное окно")
                return None

            self._last_hwnd = hwnd
            self._is_fullscreen = self.is_window_fullscreen(hwnd)

            if self._is_fullscreen:
                self.logger.info("Обнаружено полноэкранное приложение, используем DXcam")
                return self._capture_with_dxcam(hwnd)
            else:
                self.logger.info("Обычное окно, используем BitBlt")
                return self._capture_standard_window(hwnd)

        except Exception as e:
            self.logger.error(f"Ошибка захвата скриншота: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _capture_standard_window(self, hwnd: int) -> Optional[Image.Image]:
        """Стандартный метод захвата через BitBlt (для обычных окон)"""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect
            width = x2 - x1
            height = y2 - y1

            if width <= 0 or height <= 0:
                self.logger.error(f"Некорректные размеры окна: {width}x{height}")
                return None

            self._last_window_rect = rect

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

            self.logger.info(f"Скриншот через BitBlt: {width}x{height}, HWND={hwnd}")
            return img

        except Exception as e:
            self.logger.error(f"Ошибка стандартного захвата: {e}")
            return None

    def _capture_with_dxcam(self, hwnd: int) -> Optional[Image.Image]:
        """
        Захват через DXcam (Desktop Duplication API)
        Работает с полноэкранными играми, захватывает ТОЛЬКО окно
        """
        self.logger.info("Захват через DXcam...")

        try:
            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect
            width = x2 - x1
            height = y2 - y1

            if width <= 0 or height <= 0:
                self.logger.error(f"Некорректные размеры окна: {width}x{height}")
                return None

            self._last_window_rect = rect

            # Создаем камеру для региона окна
            if self.camera is None:
                self.camera = dxcam.create(region=(x1, y1, x2, y2))
            else:
                # Обновляем регион
                self.camera.region = (x1, y1, x2, y2)

            # Захватываем кадр
            frame = self.camera.grab()

            if frame is None:
                self.logger.warning("DXcam не вернул кадр, пробуем fallback")
                return self._capture_fullscreen_fallback(hwnd)

            # Конвертируем BGR в RGB и создаем PIL Image
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            img = Image.fromarray(frame_rgb)

            self.logger.info(f"Скриншот через DXcam: {img.width}x{img.height}")
            return img

        except ImportError:
            self.logger.warning("DXcam не установлен, используем fallback")
            return self._capture_fullscreen_fallback(hwnd)
        except Exception as e:
            self.logger.error(f"Ошибка DXcam: {e}")
            return self._capture_fullscreen_fallback(hwnd)

    def _capture_fullscreen_fallback(self, hwnd: int) -> Optional[Image.Image]:
        """
        Fallback метод через Desktop DC (захват всего экрана с обрезанием)
        Используется если DXcam не работает
        """
        self.logger.info("Использование fallback метода через Desktop DC...")

        try:
            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect

            screen_dc = win32gui.GetDC(0)
            dc = win32ui.CreateDCFromHandle(screen_dc)
            mem_dc = dc.CreateCompatibleDC()

            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

            bitmap = win32ui.CreateBitmap()
            bitmap.CreateCompatibleBitmap(dc, screen_width, screen_height)
            mem_dc.SelectObject(bitmap)

            mem_dc.BitBlt((0, 0), (screen_width, screen_height), dc, (0, 0), win32con.SRCCOPY)

            bmpinfo = bitmap.GetInfo()
            bmpstr = bitmap.GetBitmapBits(True)

            full_img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            crop_x1 = max(0, x1)
            crop_y1 = max(0, y1)
            crop_x2 = min(screen_width, x2)
            crop_y2 = min(screen_height, y2)

            img = full_img.crop((crop_x1, crop_y1, crop_x2, crop_y2))

            dc.DeleteDC()
            mem_dc.DeleteDC()
            win32gui.ReleaseDC(0, screen_dc)
            win32gui.DeleteObject(bitmap.GetHandle())

            self.logger.info(f"Fallback скриншот: {img.width}x{img.height}")
            return img

        except Exception as e:
            self.logger.error(f"Ошибка fallback захвата: {e}")
            return None

    def get_last_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Возвращает размеры последнего захваченного окна"""
        return getattr(self, '_last_window_rect', None)

    def get_last_hwnd(self) -> Optional[int]:
        """Возвращает HWND последнего захваченного окна"""
        return getattr(self, '_last_hwnd', None)

    def release_camera(self):
        """Освобождает DXcam камеру"""
        if self.camera is not None:
            try:
                self.camera.release()
                self.camera = None
                self.logger.info("DXcam камера освобождена")
            except Exception as e:
                self.logger.warning(f"Ошибка освобождения камеры: {e}")