"""
Утилиты для работы с файловой системой
"""

import os
import tempfile
from pathlib import Path


def get_safe_temp_dir() -> Path:
    """
    Возвращает безопасный путь к временной папке.
    Если стандартная временная папка недоступна - использует папку в Documents.
    """
    # Пробуем получить стандартную временную папку
    try:
        temp_dir = Path(tempfile.gettempdir())
        # Проверяем, существует ли папка и можно ли в нее писать
        if temp_dir.exists() and os.access(str(temp_dir), os.W_OK):
            return temp_dir
    except Exception:
        pass

    # Fallback: используем папку в Documents
    try:
        fallback_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "temp"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir
    except Exception:
        pass

    # Второй fallback: используем текущую папку
    try:
        fallback_dir = Path(os.getcwd()) / "temp"
        fallback_dir.mkdir(parents=True, exist_ok=True)
        return fallback_dir
    except Exception:
        pass

    # Последний fallback: используем системную temp, даже если она не существует
    # Попытка создать ее
    try:
        temp_dir = Path(tempfile.gettempdir())
        temp_dir.mkdir(parents=True, exist_ok=True)
        return temp_dir
    except Exception:
        raise RuntimeError("Не удалось найти или создать временную папку")


def get_app_temp_dir() -> Path:
    """
    Возвращает папку для временных файлов приложения
    """
    return get_safe_temp_dir() / "screenshot_translator"


def ensure_app_temp_dir() -> Path:
    """
    Создает и возвращает папку для временных файлов приложения
    """
    temp_dir = get_app_temp_dir()
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir