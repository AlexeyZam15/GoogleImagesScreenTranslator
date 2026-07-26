"""
Утилиты для работы с окнами Windows
"""

import ctypes
import time
import logging
from ctypes import wintypes

# Константы Windows API
WS_OVERLAPPED = 0x00000000
WS_POPUP = 0x80000000
WS_CHILD = 0x40000000
WS_MINIMIZE = 0x20000000
WS_VISIBLE = 0x10000000
WS_DISABLED = 0x08000000
WS_CLIPSIBLINGS = 0x04000000
WS_CLIPCHILDREN = 0x02000000
WS_MAXIMIZE = 0x01000000
WS_CAPTION = 0x00C00000
WS_BORDER = 0x00800000
WS_DLGFRAME = 0x00400000
WS_VSCROLL = 0x00200000
WS_HSCROLL = 0x00100000
WS_SYSMENU = 0x00080000
WS_THICKFRAME = 0x00040000
WS_GROUP = 0x00020000
WS_TABSTOP = 0x00010000
WS_MINIMIZEBOX = 0x00020000
WS_MAXIMIZEBOX = 0x00010000

WS_OVERLAPPEDWINDOW = (WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU |
                       WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)

WS_EX_DLGMODALFRAME = 0x00000001
WS_EX_NOPARENTNOTIFY = 0x00000004
WS_EX_TOPMOST = 0x00000008
WS_EX_ACCEPTFILES = 0x00000010
WS_EX_TRANSPARENT = 0x00000020
WS_EX_MDICHILD = 0x00000040
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_WINDOWEDGE = 0x00000100
WS_EX_CLIENTEDGE = 0x00000200
WS_EX_CONTEXTHELP = 0x00000400
WS_EX_RIGHT = 0x00001000
WS_EX_LEFT = 0x00000000
WS_EX_RTLREADING = 0x00002000
WS_EX_LEFTSCROLLBAR = 0x00004000
WS_EX_CONTROLPARENT = 0x00010000
WS_EX_STATICEDGE = 0x00020000
WS_EX_APPWINDOW = 0x00040000

GWL_STYLE = -16
GWL_EXSTYLE = -20
SWP_NOMOVE = 0x0002
SWP_NOSIZE = 0x0001
SWP_NOZORDER = 0x0004
SWP_FRAMECHANGED = 0x0020
SWP_SHOWWINDOW = 0x0040

RDW_INVALIDATE = 0x0001
RDW_UPDATENOW = 0x0100
RDW_ALLCHILDREN = 0x0080
RDW_FRAME = 0x0400

user32 = ctypes.windll.user32


def get_screen_size():
    """Получает размер экрана"""
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def make_windowed_fullscreen(hwnd):
    """
    Делает окно полноэкранным без рамки (windowed fullscreen)
    Возвращает True в случае успеха, False в случае ошибки
    """
    logger = logging.getLogger(__name__)

    if not hwnd:
        logger.error("Некорректный дескриптор окна")
        return False

    try:
        screen_width, screen_height = get_screen_size()
        logger.info(f"Размер экрана: {screen_width}x{screen_height}")

        current_style = user32.GetWindowLongW(hwnd, GWL_STYLE)
        current_ex_style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)

        new_style = current_style & ~(
                WS_CAPTION | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX | WS_SYSMENU | WS_BORDER | WS_DLGFRAME)
        new_style |= WS_POPUP

        new_ex_style = current_ex_style & ~(
                WS_EX_DLGMODALFRAME | WS_EX_WINDOWEDGE | WS_EX_CLIENTEDGE | WS_EX_STATICEDGE)

        result = user32.SetWindowLongW(hwnd, GWL_STYLE, new_style)
        if result == 0 and ctypes.GetLastError() != 0:
            logger.error(f"Не удалось изменить стиль окна. Ошибка: {ctypes.GetLastError()}")
            return False

        result = user32.SetWindowLongW(hwnd, GWL_EXSTYLE, new_ex_style)
        if result == 0 and ctypes.GetLastError() != 0:
            logger.error(f"Не удалось изменить расширенный стиль окна. Ошибка: {ctypes.GetLastError()}")
            return False

        result = user32.SetWindowPos(
            hwnd,
            None,
            0, 0,
            screen_width, screen_height,
            SWP_NOZORDER | SWP_FRAMECHANGED | SWP_SHOWWINDOW
        )

        if not result:
            logger.error(f"Не удалось изменить размер окна. Ошибка: {ctypes.GetLastError()}")
            return False

        time.sleep(0.1)

        user32.InvalidateRect(hwnd, None, True)
        user32.UpdateWindow(hwnd)

        user32.RedrawWindow(
            hwnd,
            None,
            None,
            RDW_INVALIDATE | RDW_UPDATENOW | RDW_ALLCHILDREN | RDW_FRAME
        )

        logger.info(f"Окно переведено в полноэкранный режим без рамки ({screen_width}x{screen_height})")
        return True

    except Exception as e:
        logger.error(f"Ошибка при переводе в полноэкранный режим: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False


def send_alt_enter_to_window(hwnd):
    """
    Отправляет Alt+Enter активному окну через keyboard
    и делает его оконным полноэкранным.
    ВЫПОЛНЯЕТСЯ ТОЛЬКО ОДИН РАЗ - при первом F3.
    """
    logger = logging.getLogger(__name__)

    if not hwnd:
        logger.error("Некорректный дескриптор окна")
        return False

    try:
        # Активируем целевое окно
        try:
            logger.info(f"Активация целевого окна: {hwnd}")
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.1)
        except Exception as e:
            logger.warning(f"Не удалось активировать окно: {e}")

        # Используем keyboard для отправки Alt+Enter
        try:
            import keyboard
            logger.info("Отправка Alt+Enter через keyboard.press_and_release()")
            keyboard.press_and_release('alt+enter')
            logger.info("Alt+Enter отправлен")
        except Exception as e:
            logger.error(f"Ошибка отправки Alt+Enter через keyboard: {e}")
            return False

        # Ждем переключения режима
        logger.info("Ожидание переключения режима (0.5с)...")
        time.sleep(0.5)

        # Восстанавливаем фокус на целевое окно
        try:
            user32.SetForegroundWindow(hwnd)
            time.sleep(0.1)
        except:
            pass

        # Применяем стили для удаления рамки и растягивания
        logger.info("Перевод окна в режим windowed fullscreen...")
        return make_windowed_fullscreen(hwnd)

    except Exception as e:
        logger.error(f"Ошибка отправки Alt+Enter: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False