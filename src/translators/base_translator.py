"""
Базовый класс для всех переводчиков.
Содержит общие методы для работы с браузером.
"""

import os
import time
import logging
import shutil
import subprocess
import winreg
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

from src.utils import get_safe_temp_dir


class BaseTranslator:
    """Базовый класс для переводчиков изображений."""

    def __init__(self, headless: bool = True, target_lang: str = "ru", settings=None):
        self.headless = headless
        self.target_lang = target_lang
        self.settings = settings
        self.base_url = ""
        self._pw = None
        self._context = None
        self._page = None
        self.logger = logging.getLogger(__name__)
        self._cancel_flag = False
        self._worker = None
        self._profile_dir = None
        self._profile_prefix = "translator_profile"  # <-- ДОБАВЛЕНО

    def _get_profile_prefix(self) -> str:
        """
        Возвращает префикс для папки профиля.
        Может быть переопределён в наследниках.
        """
        return "translator_profile"

    def _grant_clipboard_permission(self) -> bool:
        """
        Запрашивает разрешение на доступ к буферу обмена для текущей страницы.
        Возвращает True, если разрешение получено.
        """
        if not self._page:
            self.logger.warning("Нет активной страницы для запроса разрешения")
            return False

        try:
            self.logger.info("Запрос разрешения на доступ к буферу обмена...")

            js_code = """
            async function requestClipboardPermission() {
                try {
                    const result = await navigator.permissions.query({ name: 'clipboard-read' });
                    if (result.state === 'granted' || result.state === 'prompt') {
                        // Пытаемся прочитать буфер для активации разрешения
                        try {
                            await navigator.clipboard.read();
                            return { success: true, state: result.state };
                        } catch (e) {
                            // Если не удалось прочитать, но разрешение запрошено
                            return { success: true, state: result.state, note: 'read_failed' };
                        }
                    }
                    return { success: false, state: result.state };
                } catch (e) {
                    return { success: false, error: e.message };
                }
            }
            return await requestClipboardPermission();
            """

            result = self._page.evaluate(js_code)
            self.logger.info(f"Результат запроса разрешения: {result}")

            if result and result.get('success'):
                self.logger.info("✅ Разрешение на буфер обмена получено")
                return True
            else:
                self.logger.warning(f"⚠️ Не удалось получить разрешение: {result}")
                return False

        except Exception as e:
            self.logger.warning(f"Ошибка при запросе разрешения: {e}")
            return False

    def create_new_page(self) -> bool:
        """Создаёт новую страницу в существующем контексте браузера.
        Должен быть переопределён в наследниках."""
        raise NotImplementedError

    def start_browser(self):
        """Запускает браузер с Playwright.
        Должен быть переопределён в наследниках."""
        raise NotImplementedError

    def _find_yandex_browser(self) -> Optional[str]:
        """Ищет Яндекс Браузер через реестр Windows."""
        self.logger.info("Поиск Яндекс Браузера через реестр Windows...")

        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\browser.exe",
                0, winreg.KEY_READ
            )
            try:
                browser_path = winreg.QueryValueEx(key, "")[0]
                if os.path.exists(browser_path):
                    self.logger.info(f"✅ Найден Яндекс Браузер (App Paths): {browser_path}")
                    return browser_path
            finally:
                winreg.CloseKey(key)
        except WindowsError:
            pass

        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Yandex\YandexBrowser", 0, winreg.KEY_READ)
            try:
                install_dir = winreg.QueryValueEx(key, "InstallDir")[0]
                browser_path = os.path.join(install_dir, "browser.exe")
                if os.path.exists(browser_path):
                    self.logger.info(f"✅ Найден Яндекс Браузер (HKCU): {browser_path}")
                    return browser_path
            finally:
                winreg.CloseKey(key)
        except WindowsError:
            pass

        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Yandex\YandexBrowser",
                0, winreg.KEY_READ
            )
            try:
                install_dir = winreg.QueryValueEx(key, "InstallDir")[0]
                browser_path = os.path.join(install_dir, "browser.exe")
                if os.path.exists(browser_path):
                    self.logger.info(f"✅ Найден Яндекс Браузер (HKLM 64-bit): {browser_path}")
                    return browser_path
            finally:
                winreg.CloseKey(key)
        except WindowsError:
            pass

        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Yandex\YandexBrowser", 0, winreg.KEY_READ)
            try:
                install_dir = winreg.QueryValueEx(key, "InstallDir")[0]
                browser_path = os.path.join(install_dir, "browser.exe")
                if os.path.exists(browser_path):
                    self.logger.info(f"✅ Найден Яндекс Браузер (HKLM 32-bit): {browser_path}")
                    return browser_path
            finally:
                winreg.CloseKey(key)
        except WindowsError:
            pass

        # Поиск в стандартных путях
        paths = [
            r"C:\Program Files\Yandex\YandexBrowser\Application\browser.exe",
            r"C:\Program Files (x86)\Yandex\YandexBrowser\Application\browser.exe",
        ]
        for path in paths:
            if os.path.exists(path):
                self.logger.info(f"✅ Найден Яндекс Браузер (стандартный путь): {path}")
                return path

        self.logger.warning("❌ Яндекс Браузер не найден")
        return None

    def _find_chrome_browser(self) -> Optional[str]:
        """Ищет Google Chrome через реестр Windows."""
        self.logger.info("Поиск Google Chrome через реестр Windows...")

        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe",
                0, winreg.KEY_READ
            )
            try:
                chrome_path = winreg.QueryValueEx(key, "")[0]
                if os.path.exists(chrome_path):
                    self.logger.info(f"✅ Найден Google Chrome (App Paths): {chrome_path}")
                    return chrome_path
            finally:
                winreg.CloseKey(key)
        except WindowsError:
            pass

        # Поиск в стандартных путях
        paths = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        ]
        for path in paths:
            if os.path.exists(path):
                self.logger.info(f"✅ Найден Google Chrome (стандартный путь): {path}")
                return path

        self.logger.warning("❌ Google Chrome не найден")
        return None

    def _find_any_browser(self) -> Optional[str]:
        """Ищет любой доступный Chromium-браузер."""
        browser_path = self._find_yandex_browser()
        if browser_path:
            if hasattr(self, 'settings'):
                self.settings.set_browser_path(browser_path)
                self.logger.info(f"✅ Путь к браузеру сохранён в настройки: {browser_path}")
            return browser_path

        browser_path = self._find_chrome_browser()
        if browser_path:
            self.logger.info("⚠️ Яндекс Браузер не найден, будет использован Google Chrome")
            if hasattr(self, 'settings'):
                self.settings.set_browser_path(browser_path)
                self.logger.info(f"✅ Путь к браузеру сохранён в настройки: {browser_path}")
            return browser_path

        # Поиск других Chromium-браузеров
        chromium_paths = [
            r"C:\Program Files\Chromium\Application\chrome.exe",
            r"C:\Program Files (x86)\Chromium\Application\chrome.exe",
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files\Vivaldi\Application\vivaldi.exe",
            r"C:\Program Files (x86)\Vivaldi\Application\vivaldi.exe",
        ]
        for path in chromium_paths:
            if os.path.exists(path):
                self.logger.info(f"✅ Найден Chromium-браузер: {path}")
                if hasattr(self, 'settings'):
                    self.settings.set_browser_path(path)
                    self.logger.info(f"✅ Путь к браузеру сохранён в настройки: {path}")
                return path

        self.logger.error("❌ Не найден ни один Chromium-браузер")
        return None

    def _copy_image_to_clipboard(self, image_path: Path) -> bool:
        """Копирует изображение в буфер обмена через JavaScript."""
        self.logger.info(f"Копирование изображения в буфер обмена: {image_path}")
        if not image_path.exists():
            self.logger.error(f"Файл не найден: {image_path}")
            return False

        try:
            import base64
            with open(image_path, 'rb') as f:
                image_data = f.read()
            b64_data = base64.b64encode(image_data).decode('utf-8')

            js_code = """
                (b64Data) => {
                    try {
                        const byteCharacters = atob(b64Data);
                        const byteNumbers = new Array(byteCharacters.length);
                        for (let i = 0; i < byteCharacters.length; i++) {
                            byteNumbers[i] = byteCharacters.charCodeAt(i);
                        }
                        const byteArray = new Uint8Array(byteNumbers);
                        const blob = new Blob([byteArray], { type: 'image/png' });
                        return navigator.clipboard.write([
                            new ClipboardItem({
                                [blob.type]: blob
                            })
                        ]).then(() => true).catch(() => false);
                    } catch(e) {
                        return false;
                    }
                }
            """
            result = self._page.evaluate(js_code, b64_data)
            if result:
                self.logger.info("✅ Изображение скопировано в буфер обмена")
                return True
            else:
                self.logger.error("❌ Не удалось скопировать изображение")
                return False
        except Exception as e:
            self.logger.error(f"Ошибка копирования: {e}")
            return False

    def cancel_translation(self):
        """Отменяет текущий перевод."""
        self._cancel_flag = True
        self.logger.info("[DEBUG] cancel_translation() - флаг отмены установлен")

    def reset_page(self):
        """Сбрасывает страницу. Должен быть переопределён в наследниках."""
        raise NotImplementedError

    def update_target_language(self, target_lang: str):
        """Обновляет целевой язык. Должен быть переопределён в наследниках."""
        raise NotImplementedError

    def update_interface_language(self, lang_code: str):
        """Обновляет язык интерфейса. Должен быть переопределён в наследниках."""
        raise NotImplementedError

    def is_browser_alive(self) -> bool:
        """Проверяет, жив ли браузер."""
        try:
            if self._context is None or self._page is None:
                return False
            self._page.evaluate("1 + 1")
            return True
        except Exception:
            return False

    def close_browser(self):
        """Закрывает браузер и удаляет папку профиля."""
        self._cancel_flag = True
        self.logger.info("[BROWSER] Закрытие браузера...")

        try:
            if self._context:
                try:
                    pages = self._context.pages
                    for page in pages:
                        try:
                            page.close()
                        except:
                            pass
                except:
                    pass
                try:
                    self._context.close()
                except:
                    pass
                self._context = None
                self._page = None

            if self._pw:
                try:
                    self._pw.stop()
                except:
                    pass
                self._pw = None

            # Удаляем папку профиля
            if self._profile_dir and self._profile_dir.exists():
                try:
                    shutil.rmtree(self._profile_dir, ignore_errors=True)
                    self.logger.info(f"[BROWSER] 🧹 Папка профиля удалена: {self._profile_dir}")
                except Exception as e:
                    self.logger.warning(f"[BROWSER] Не удалось удалить профиль: {e}")
                self._profile_dir = None

            self.logger.info("[BROWSER] Браузер закрыт")
        except Exception as e:
            self.logger.error(f"[BROWSER] Ошибка при закрытии браузера: {e}")

    def translate_image(self, image_path: Path, output_dir: Path, worker=None) -> Optional[Path]:
        """Переводит изображение. Должен быть переопределён в наследниках."""
        raise NotImplementedError
