import ctypes
import time
import logging
import os
from ctypes import wintypes

# Windows API
import win32api
import win32con
import win32process
import win32gui
import win32file
from typing import Optional

# Psutil (опционально)
try:
    import psutil
except ImportError:
    psutil = None

# Windows API константы
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
kernel32 = ctypes.windll.kernel32


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


def get_process_name_by_hwnd(hwnd: int, default_name: str = None) -> str:
    """
    Получает имя процесса (исполняемого файла) по HWND окна.
    Возвращает имя процесса или default_name (или "Неизвестно") в случае ошибки.

    Args:
        hwnd: Дескриптор окна
        default_name: Имя по умолчанию, если не удалось получить (если None - возвращается "Неизвестно")
    """
    logger = logging.getLogger(__name__)

    # Проверяем, что HWND валидный
    if not hwnd or not win32gui.IsWindow(hwnd):
        # Если HWND невалидный, пробуем получить имя через последний известный процесс
        # Но если default_name передан - используем его
        if default_name and default_name != "Неизвестно":
            logger.debug(f"get_process_name_by_hwnd: HWND {hwnd} невалидный, используем default_name={default_name}")
            return default_name

        logger.warning(f"get_process_name_by_hwnd: некорректный HWND: {hwnd}")
        return default_name if default_name else "Неизвестно"

    try:
        # Получаем PID процесса, которому принадлежит окно
        _, pid = win32process.GetWindowThreadProcessId(hwnd)

        # Проверяем, что PID корректный (положительное число)
        if not pid or pid <= 0:
            logger.warning(f"get_process_name_by_hwnd: получен некорректный PID={pid} для HWND={hwnd}")
            return default_name if default_name else "Неизвестно"

        # === СПОСОБ 1: Через psutil (наиболее надёжный) ===
        if psutil is not None:
            try:
                proc = psutil.Process(pid)
                return proc.name()
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                logger.debug(f"psutil не смог получить имя для PID {pid}: {e}")

        # === СПОСОБ 2: Через OpenProcess + GetModuleFileNameEx ===
        try:
            process_handle = win32api.OpenProcess(
                win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                False,
                pid
            )
            try:
                exe_path = win32process.GetModuleFileNameEx(process_handle, 0)
                if exe_path:
                    return os.path.splitext(os.path.basename(exe_path))[0]
            finally:
                win32api.CloseHandle(process_handle)
        except Exception as e:
            logger.debug(f"GetModuleFileNameEx не сработал для PID {pid}: {e}")

        # === СПОСОБ 3: Через EnumProcessModules ===
        try:
            PROCESS_QUERY_INFORMATION = 0x0400
            PROCESS_VM_READ = 0x0010

            process_handle = win32api.OpenProcess(
                PROCESS_QUERY_INFORMATION | PROCESS_VM_READ,
                False,
                pid
            )
            if process_handle:
                try:
                    modules = ctypes.create_string_buffer(1024)
                    cb_needed = ctypes.c_uint32()
                    result = ctypes.windll.psapi.EnumProcessModules(
                        process_handle,
                        ctypes.byref(modules),
                        ctypes.sizeof(modules),
                        ctypes.byref(cb_needed)
                    )
                    if result:
                        module_handle = ctypes.c_void_p()
                        ctypes.memmove(ctypes.byref(module_handle), modules, ctypes.sizeof(ctypes.c_void_p))

                        module_path = ctypes.create_string_buffer(1024)
                        ctypes.windll.psapi.GetModuleFileNameExA(
                            process_handle,
                            module_handle,
                            module_path,
                            ctypes.sizeof(module_path)
                        )
                        if module_path.value:
                            return \
                                os.path.splitext(os.path.basename(module_path.value.decode('utf-8', errors='ignore')))[
                                    0]
                finally:
                    win32api.CloseHandle(process_handle)
        except Exception as e:
            logger.debug(f"EnumProcessModules не сработал для PID {pid}: {e}")

        # === СПОСОБ 4: QueryFullProcessImageName ===
        try:
            PROCESS_QUERY_INFORMATION = 0x0400
            process_handle = win32api.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
            if process_handle:
                try:
                    exe_path = ctypes.create_unicode_buffer(1024)
                    size = ctypes.c_uint32(ctypes.sizeof(exe_path))
                    if kernel32.QueryFullProcessImageNameW(process_handle, 0, exe_path, ctypes.byref(size)):
                        if exe_path.value:
                            return os.path.splitext(os.path.basename(exe_path.value))[0]
                finally:
                    win32api.CloseHandle(process_handle)
        except Exception as e:
            logger.debug(f"QueryFullProcessImageName не сработал для PID {pid}: {e}")

        # === СПОСОБ 5: Через Toolhelp32Snapshot ===
        try:
            snapshot = win32api.CreateToolhelp32Snapshot(win32con.TH32CS_SNAPPROCESS, 0)
            try:
                process_entry = win32process.Process32First(snapshot)
                while process_entry:
                    if process_entry.th32ProcessID == pid:
                        return os.path.splitext(process_entry.szExeFile)[0]
                    process_entry = win32process.Process32Next(snapshot)
            finally:
                win32api.CloseHandle(snapshot)
        except Exception as e:
            logger.debug(f"Toolhelp32Snapshot не сработал для PID {pid}: {e}")

        # === ПОСЛЕДНИЙ FALLBACK ===
        logger.warning(f"Не удалось получить имя процесса для PID {pid}, возвращаем default_name")
        return default_name if default_name else f"PID {pid}"

    except Exception as e:
        logger.error(f"Ошибка в get_process_name_by_hwnd для HWND {hwnd}: {e}")
        return default_name if default_name else "Неизвестно"


def find_window_by_app_name(app_name: str) -> Optional[int]:
    """
    Находит HWND окна по имени приложения (процесса).

    Args:
        app_name: Имя исполняемого файла (например, "LIBM.exe")

    Returns:
        HWND окна или None, если окно не найдено
    """
    logger = logging.getLogger(__name__)

    if not app_name or app_name == "Неизвестно":
        return None

    try:
        import win32gui

        def enum_callback(hwnd, hwnds):
            if win32gui.IsWindowVisible(hwnd):
                try:
                    if get_process_name_by_hwnd(hwnd) == app_name:
                        hwnds.append(hwnd)
                        return False  # Останавливаем поиск
                except Exception:
                    pass
            return True

        hwnds = []
        win32gui.EnumWindows(enum_callback, hwnds)
        return hwnds[0] if hwnds else None

    except Exception as e:
        logger.warning(f"Ошибка поиска окна по имени {app_name}: {e}")
        return None
