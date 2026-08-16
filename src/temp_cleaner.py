"""
Модуль для очистки временных файлов и профилей браузеров.
Использует несколько методов для быстрого и тихого удаления.
"""

import os
import shutil
import logging
import time
import threading
import subprocess
from pathlib import Path
from typing import List, Optional, Callable

# Windows API для быстрого удаления (тихого)
try:
    import ctypes
    from ctypes import wintypes

    # Константы для SHFileOperation
    FO_DELETE = 0x0003
    FOF_SILENT = 0x0004
    FOF_NOCONFIRMATION = 0x0010
    FOF_NOERRORUI = 0x0400


    class SHFILEOPSTRUCTW(ctypes.Structure):
        _fields_ = [
            ('hwnd', wintypes.HWND),
            ('wFunc', wintypes.UINT),
            ('pFrom', wintypes.LPCWSTR),
            ('pTo', wintypes.LPCWSTR),
            ('fFlags', wintypes.WORD),
            ('fAnyOperationsAborted', wintypes.BOOL),
            ('hNameMappings', wintypes.LPVOID),
            ('lpszProgressTitle', wintypes.LPCWSTR),
        ]


    shell32 = ctypes.windll.shell32
    shell32.SHFileOperationW.argtypes = [ctypes.POINTER(SHFILEOPSTRUCTW)]
    shell32.SHFileOperationW.restype = ctypes.c_int

    HAS_WINAPI = True
except ImportError:
    HAS_WINAPI = False

# Префиксы папок профилей
PROFILE_PREFIXES = [
    "google_translate_profile_",
    "yandex_ocr_profile_",
    "translator_profile_",
    "debug_profile_",
    "playwright-artifacts-",
    "playwright_chromiumdev_profile_",
]

APP_TEMP_PREFIXES = [
    "screenshot_translator",
]


def get_temp_dir() -> Path:
    import tempfile
    return Path(tempfile.gettempdir())


def delete_folder_winapi(folder_path: Path) -> bool:
    """Тихое удаление через Windows API SHFileOperation."""
    if not folder_path.exists():
        return True

    if not HAS_WINAPI:
        return False

    try:
        path_str = str(folder_path) + '\0\0'

        op = SHFILEOPSTRUCTW()
        op.hwnd = None
        op.wFunc = FO_DELETE
        op.pFrom = path_str
        op.pTo = None
        op.fFlags = FOF_SILENT | FOF_NOCONFIRMATION | FOF_NOERRORUI
        op.fAnyOperationsAborted = False
        op.hNameMappings = None
        op.lpszProgressTitle = None

        result = shell32.SHFileOperationW(ctypes.byref(op))
        return result == 0
    except Exception:
        return False


def delete_folder_cmd(folder_path: Path) -> bool:
    """Удаление через командную строку (rd /s /q)."""
    if not folder_path.exists():
        return True

    try:
        result = subprocess.run(
            ['cmd', '/c', 'rd', '/s', '/q', str(folder_path)],
            capture_output=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, 'CREATE_NO_WINDOW') else 0
        )
        return result.returncode == 0 or not folder_path.exists()
    except Exception:
        return False


def delete_folder_fast(folder_path: Path) -> bool:
    """Быстрое и тихое удаление папки."""
    if not folder_path.exists():
        return True

    if HAS_WINAPI:
        try:
            if delete_folder_winapi(folder_path):
                return True
        except:
            pass

    try:
        if delete_folder_cmd(folder_path):
            return True
    except:
        pass

    try:
        shutil.rmtree(folder_path, ignore_errors=True)
        return True
    except:
        pass

    return False


def find_app_temp_dirs(temp_dir: Optional[Path] = None) -> List[Path]:
    if temp_dir is None:
        temp_dir = get_temp_dir()

    found_dirs = []
    if not temp_dir.exists():
        return found_dirs

    for item in temp_dir.iterdir():
        if not item.is_dir():
            continue
        name = item.name

        for prefix in PROFILE_PREFIXES:
            if name.startswith(prefix):
                found_dirs.append(item)
                break

        for prefix in APP_TEMP_PREFIXES:
            if name == prefix or name.startswith(prefix):
                found_dirs.append(item)
                break

    return found_dirs


def cleanup_all_profiles_sync(temp_dir: Optional[Path] = None,
                              logger: Optional[logging.Logger] = None) -> int:
    """Синхронное удаление всех временных папок."""
    if logger is None:
        logger = logging.getLogger(__name__)

    dirs = find_app_temp_dirs(temp_dir)

    if not dirs:
        logger.info("[TEMP_CLEANER] Временные папки не найдены")
        return 0

    logger.info(f"[TEMP_CLEANER] Удаление {len(dirs)} папок...")

    deleted_count = 0
    total = len(dirs)

    for i, dir_path in enumerate(dirs):
        try:
            if delete_folder_fast(dir_path):
                deleted_count += 1
                if deleted_count % 10 == 0 or deleted_count == total:
                    logger.info(f"[TEMP_CLEANER] 🗑️ Удалено {deleted_count}/{total} папок")
            else:
                logger.debug(f"[TEMP_CLEANER] ⚠️ Не удалось: {dir_path.name}")
        except Exception as e:
            logger.debug(f"[TEMP_CLEANER] Ошибка: {dir_path.name} - {e}")

    if deleted_count > 0:
        logger.info(f"[TEMP_CLEANER] ✅ Удалено {deleted_count} из {total} папок")
    else:
        logger.info(f"[TEMP_CLEANER] Не удалось удалить ни одной папки")

    return deleted_count


def cleanup_all_profiles(temp_dir: Optional[Path] = None,
                         logger: Optional[logging.Logger] = None,
                         wait: bool = False,
                         timeout: float = 5.0) -> int:
    """
    Удаление всех временных папок.

    Args:
        temp_dir: Путь к временной директории
        logger: Логгер
        wait: Если True - дожидаться завершения
        timeout: Таймаут ожидания в секундах

    Returns:
        Количество удалённых папок или -1 если таймаут
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    dirs = find_app_temp_dirs(temp_dir)

    if not dirs:
        logger.info("[TEMP_CLEANER] Временные папки не найдены")
        return 0

    logger.info(f"[TEMP_CLEANER] Найдено {len(dirs)} папок для удаления")

    if not wait:
        # Асинхронное удаление с НЕ-daemon потоком
        def cleanup_thread():
            try:
                cleanup_all_profiles_sync(temp_dir, logger)
            except Exception as e:
                logger.error(f"[TEMP_CLEANER] Ошибка в потоке: {e}")

        thread = threading.Thread(target=cleanup_thread, daemon=False)
        thread.start()
        return len(dirs)
    else:
        # Синхронное удаление с ожиданием
        return cleanup_all_profiles_sync(temp_dir, logger)


def cleanup_old_profiles(max_age_days: int = 7, temp_dir: Optional[Path] = None,
                         logger: Optional[logging.Logger] = None,
                         wait: bool = False) -> int:
    """Удаляет временные папки старше указанного количества дней."""
    if logger is None:
        logger = logging.getLogger(__name__)

    dirs = find_app_temp_dirs(temp_dir)
    if not dirs:
        return 0

    cutoff_time = time.time() - (max_age_days * 24 * 60 * 60)
    old_dirs = []

    for dir_path in dirs:
        try:
            mtime = dir_path.stat().st_mtime
            if mtime < cutoff_time:
                old_dirs.append(dir_path)
        except Exception:
            pass

    if not old_dirs:
        logger.info(f"[TEMP_CLEANER] Старые папки (старше {max_age_days} дней) не найдены")
        return 0

    logger.info(f"[TEMP_CLEANER] Найдено {len(old_dirs)} старых папок")

    if not wait:
        # Асинхронное удаление с НЕ-daemon потоком
        def cleanup_old():
            deleted = 0
            for dir_path in old_dirs:
                if delete_folder_fast(dir_path):
                    deleted += 1
            if deleted > 0:
                logger.info(f"[TEMP_CLEANER] ✅ Удалено {deleted} старых папок")

        thread = threading.Thread(target=cleanup_old, daemon=False)
        thread.start()
        return len(old_dirs)
    else:
        # Синхронное удаление
        deleted = 0
        for dir_path in old_dirs:
            if delete_folder_fast(dir_path):
                deleted += 1
        if deleted > 0:
            logger.info(f"[TEMP_CLEANER] ✅ Удалено {deleted} старых папок")
        return deleted
