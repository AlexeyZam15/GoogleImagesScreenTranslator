# src/version_checker.py

import shutil
import logging
from pathlib import Path

# === ТЕКУЩАЯ ВЕРСИЯ ПРИЛОЖЕНИЯ (увеличивать при каждом релизе) ===
APP_VERSION = "0.5"


def check_and_clean_version(app_docs_path: Path) -> bool:
    """
    Проверяет версию приложения и очищает папку при несоответствии.

    Args:
        app_docs_path: Путь к папке приложения в документах (Documents/GoogleScreenTranslate)

    Returns:
        bool: True если версия совпадает или была успешно обновлена, False в случае ошибки
    """
    # Создаём папку, если её нет
    app_docs_path.mkdir(parents=True, exist_ok=True)

    version_file = app_docs_path / "version.txt"
    current_version = APP_VERSION.strip()

    # Читаем сохранённую версию
    saved_version = None
    if version_file.exists():
        try:
            saved_version = version_file.read_text(encoding='utf-8').strip()
        except Exception:
            saved_version = None

    # Если версии совпадают — ничего не делаем
    if saved_version == current_version:
        return True

    # Версии не совпадают или файла нет — очищаем папку
    logging.info(
        f"[VERSION] Несоответствие версий: сохранено '{saved_version}', текущая '{current_version}'. Очистка папки...")

    # Удаляем всё, кроме самого файла версии (которого ещё нет)
    for item in app_docs_path.iterdir():
        if item.name == "version.txt":
            continue
        try:
            if item.is_dir():
                shutil.rmtree(item)
            else:
                item.unlink()
        except Exception as e:
            logging.warning(f"[VERSION] Не удалось удалить {item}: {e}")

    # Записываем новую версию
    try:
        version_file.write_text(current_version, encoding='utf-8')
        logging.info(f"[VERSION] Записана новая версия: {current_version}")
        return True
    except Exception as e:
        logging.error(f"[VERSION] Не удалось записать файл версии: {e}")
        return False