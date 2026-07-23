"""
Модуль для захвата скриншотов активного окна
"""

import logging
from typing import Optional, Tuple
from PIL import Image
import win32gui
import win32con
import win32ui


class ScreenshotCapturer:
    """Класс для захвата скриншотов активного окна"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def get_active_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Возвращает координаты активного окна (x1, y1, x2, y2)"""
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

            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect
            width = x2 - x1
            height = y2 - y1

            if width <= 0 or height <= 0:
                self.logger.error(f"Некорректные размеры окна: {width}x{height}")
                return None

            # Сохраняем размеры для использования в оверлее
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

            self.logger.info(f"Скриншот сделан: {width}x{height}")
            return img

        except Exception as e:
            self.logger.error(f"Ошибка захвата скриншота: {e}")
            import traceback
            traceback.print_exc()
            return None

    def get_last_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        """Возвращает размеры последнего захваченного окна"""
        return getattr(self, '_last_window_rect', None)