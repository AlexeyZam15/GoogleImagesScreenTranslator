"""
Модуль для захвата скриншотов активного окна
Использует DXcam для полноэкранных приложений
"""

import logging
import time
from typing import Optional, Tuple
from pathlib import Path

# PIL
from PIL import Image

# Windows API
import win32gui
import win32ui
import win32con
import win32api

# DXcam
import dxcam

# OpenCV и NumPy
import cv2
import numpy as np

# Windows API для низкоуровневых операций
import ctypes

# Локальные переменные для user32
user32 = ctypes.windll.user32


class ScreenshotCapturer:
    """Класс для захвата скриншотов активного окна"""

    __slots__ = (
        'logger', '_last_window_rect', '_last_hwnd', '_is_fullscreen',
        'camera', '_cache', '_cache_hwnd', '_cache_time', '_cache_ttl'
    )

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self._last_window_rect = None
        self._last_hwnd = None
        self._is_fullscreen = False
        self.camera = None

        # Кэш для повторных захватов
        self._cache = None
        self._cache_hwnd = None
        self._cache_time = 0
        self._cache_ttl = 0.05  # 50ms кэш

    def _capture_standard_window(self, hwnd: int) -> Optional[Image.Image]:
        """Стандартный метод захвата через BitBlt"""
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
            try:
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

                self._cache = img
                self._cache_hwnd = hwnd
                self._cache_time = time.time()

                return img
            finally:
                try:
                    dc.DeleteDC()
                    mem_dc.DeleteDC()
                    win32gui.ReleaseDC(hwnd, hwnd_dc)
                    win32gui.DeleteObject(bitmap.GetHandle())
                except:
                    pass

        except Exception as e:
            self.logger.error(f"Ошибка стандартного захвата: {e}")
            return None

    def _capture_with_printwindow(self, hwnd: int) -> Optional[Image.Image]:
        """Захват через PrintWindow (для браузеров и DX-приложений)"""
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

            PW_RENDERFULLCONTENT = 0x00000002
            user32 = ctypes.windll.user32

            result = user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), PW_RENDERFULLCONTENT)

            if not result:
                result = user32.PrintWindow(hwnd, mem_dc.GetSafeHdc(), 0)

            if not result:
                dc.DeleteDC()
                mem_dc.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwnd_dc)
                self.logger.warning(f"PrintWindow не сработал для окна {hwnd}")
                return None

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

            self.logger.info(f"Скриншот через PrintWindow: {width}x{height}, HWND={hwnd}")
            return img

        except Exception as e:
            self.logger.error(f"Ошибка PrintWindow захвата: {e}")
            return None

    def capture_active_window(self) -> Optional[Image.Image]:
        """Захватывает скриншот активного окна"""
        try:
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                self.logger.error("Не удалось получить активное окно")
                return None

            current_time = time.time()
            if (self._cache is not None and
                    self._cache_hwnd == hwnd and
                    current_time - self._cache_time < self._cache_ttl):
                self.logger.debug("Используем кэшированный скриншот")
                return self._cache

            try:
                class_name = win32gui.GetClassName(hwnd)
                window_text = win32gui.GetWindowText(hwnd)
                if class_name == "TkTopLevel" and window_text == "Перевод":
                    if self._last_hwnd is not None:
                        self.logger.info(f"Активное окно - оверлей, используем сохраненный HWND: {self._last_hwnd}")
                        hwnd = self._last_hwnd
                    else:
                        target_hwnd = self._find_target_window()
                        if target_hwnd:
                            hwnd = target_hwnd
                            self.logger.info(f"Найдено целевое окно через EnumWindows: {hwnd}")
                        else:
                            return None
            except Exception as e:
                self.logger.warning(f"Ошибка проверки активного окна: {e}")

            self._last_hwnd = hwnd
            self._is_fullscreen = self.is_window_fullscreen(hwnd)

            if self._is_fullscreen:
                self.logger.info("Обнаружено полноэкранное приложение, используем DXcam")
                return self._capture_with_dxcam(hwnd)
            else:
                img = self._capture_with_printwindow(hwnd)
                if img:
                    self._cache = img
                    self._cache_hwnd = hwnd
                    self._cache_time = time.time()
                    return img

                return self._capture_standard_window(hwnd)

        except Exception as e:
            self.logger.error(f"Ошибка захвата скриншота: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _find_target_window(self) -> Optional[int]:
        """Находит целевое окно (не оверлей) через EnumWindows"""
        import win32gui
        import win32con

        overlay_hwnd = None
        if self._last_hwnd:
            overlay_hwnd = self._last_hwnd

        target_hwnd = None

        def enum_callback(hwnd, lparam):
            nonlocal target_hwnd
            try:
                if not win32gui.IsWindowVisible(hwnd):
                    return True
                if overlay_hwnd and hwnd == overlay_hwnd:
                    return True
                try:
                    class_name = win32gui.GetClassName(hwnd)
                    window_text = win32gui.GetWindowText(hwnd)
                    if class_name == "TkTopLevel" and window_text == "Перевод":
                        return True
                except:
                    pass
                try:
                    window_text = win32gui.GetWindowText(hwnd)
                    if not window_text or len(window_text) == 0:
                        return True
                except:
                    return True
                try:
                    class_name = win32gui.GetClassName(hwnd)
                    if class_name in ["Progman", "WorkerW", "Shell_TrayWnd", "SysListView32"]:
                        return True
                except:
                    pass
                target_hwnd = hwnd
                return False
            except:
                return True

        try:
            win32gui.EnumWindows(enum_callback, None)
        except:
            pass

        return target_hwnd

    def is_window_fullscreen(self, hwnd: int) -> bool:
        """Проверяет, находится ли окно в полноэкранном режиме"""
        try:
            rect = win32gui.GetWindowRect(hwnd)
            x1, y1, x2, y2 = rect
            win_width = x2 - x1
            win_height = y2 - y1

            screen_width = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
            screen_height = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)

            style = win32gui.GetWindowLong(hwnd, win32con.GWL_STYLE)

            has_caption = (style & win32con.WS_CAPTION) == win32con.WS_CAPTION
            has_sysmenu = (style & win32con.WS_SYSMENU) == win32con.WS_SYSMENU
            has_border = (style & win32con.WS_BORDER) == win32con.WS_BORDER
            has_thickframe = (style & win32con.WS_THICKFRAME) == win32con.WS_THICKFRAME
            has_popup = (style & win32con.WS_POPUP) == win32con.WS_POPUP
            has_minimizebox = (style & win32con.WS_MINIMIZEBOX) == win32con.WS_MINIMIZEBOX
            has_maximizebox = (style & win32con.WS_MAXIMIZEBOX) == win32con.WS_MAXIMIZEBOX

            if not (win_width >= screen_width - 10 and win_height >= screen_height - 10):
                return False

            if not (abs(x1) <= 10 and abs(y1) <= 10):
                return False

            has_window_elements = has_caption or has_sysmenu or has_border or has_thickframe
            if has_window_elements:
                return False

            if has_popup:
                return False

            return True

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

    def is_last_window_fullscreen(self) -> bool:
        """Возвращает, было ли последнее захваченное окно полноэкранным"""
        return getattr(self, '_is_fullscreen', False)

    def get_last_hwnd(self) -> Optional[int]:
        """Возвращает HWND последнего захваченного окна"""
        return getattr(self, '_last_hwnd', None)

    def _capture_with_dxcam(self, hwnd: int) -> Optional[Image.Image]:
        """Захват через DXcam"""
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

            if self.camera is None:
                self.camera = dxcam.create(
                    region=(x1, y1, x2, y2),
                    output_color="RGB"
                )
            else:
                self.camera.region = (x1, y1, x2, y2)
                if hasattr(self.camera, 'output_color'):
                    self.camera.output_color = "RGB"

            frame = self.camera.grab()

            if frame is None:
                self.logger.warning("DXcam не вернул кадр, пробуем fallback")
                return self._capture_fullscreen_fallback(hwnd)

            self.logger.info(f"DXcam кадр: shape={frame.shape}, dtype={frame.dtype}")
            img = Image.fromarray(frame, 'RGB')
            self.logger.info(f"Скриншот через DXcam: {img.width}x{img.height}")
            return img

        except ImportError:
            self.logger.warning("DXcam не установлен, используем fallback")
            return self._capture_fullscreen_fallback(hwnd)
        except Exception as e:
            self.logger.error(f"Ошибка DXcam: {e}")
            return self._capture_fullscreen_fallback(hwnd)

    def _capture_fullscreen_fallback(self, hwnd: int) -> Optional[Image.Image]:
        """Fallback метод через Desktop DC"""
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

    def release_camera(self):
        """Освобождает DXcam камеру"""
        if self.camera is not None:
            try:
                self.camera.release()
                self.camera = None
                self.logger.info("DXcam камера освобождена")
            except Exception as e:
                self.logger.warning(f"Ошибка освобождения камеры: {e}")
