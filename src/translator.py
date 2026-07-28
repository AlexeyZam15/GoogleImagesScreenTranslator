"""
Модуль для перевода изображений через Google Translate
"""

import os
import time
import logging
import base64
import io
import sys
import winreg
import subprocess
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright
from PIL import Image


class GoogleTranslateDebug:
    def __init__(self, headless: bool = True, target_lang: str = "ru", settings=None):
        self.headless = headless
        self.target_lang = target_lang
        self.settings = settings
        self.base_url = f"https://translate.google.com/details?hl=ru&sl=auto&tl={target_lang}&op=images"
        self._pw = None
        self._context = None
        self._page = None
        self.logger = logging.getLogger(__name__)
        self._cancel_flag = False
        self._worker = None

    def start_browser(self):
        """Запускает браузер с Playwright."""
        import shutil
        import tempfile
        from src.utils import get_safe_temp_dir
        import time

        self.logger.info("Запуск Playwright...")
        self._pw = sync_playwright().start()
        self.logger.info("Поиск браузера...")

        browser_path = None
        if hasattr(self, 'settings'):
            custom_path = self.settings.get_browser_path()
            if custom_path and os.path.exists(custom_path):
                browser_path = custom_path
                self.logger.info(f"✅ Используется пользовательский путь: {browser_path}")

        if not browser_path:
            browser_path = self._find_any_browser()
            if browser_path and hasattr(self, 'settings'):
                self.settings.set_browser_path(browser_path)
                self.logger.info(f"✅ Автоматически найденный путь сохранен: {browser_path}")

        if not browser_path:
            error_msg = (
                "Не найден Яндекс Браузер или Google Chrome.\n"
                "Пожалуйста, установите один из браузеров или укажите путь вручную.\n"
                "Рекомендуется установить Яндекс Браузер для лучшей совместимости."
            )
            self.logger.error(error_msg)
            raise Exception(error_msg)

        self.logger.info(f"Используется браузер: {browser_path}")

        safe_temp_dir = get_safe_temp_dir()
        timestamp = int(time.time() * 1000)
        profile_dir = safe_temp_dir / f"google_translate_profile_{timestamp}"

        if profile_dir.exists():
            try:
                shutil.rmtree(profile_dir)
                self.logger.info("✅ Старый профиль удален")
            except Exception as e:
                self.logger.warning(f"Не удалось удалить профиль: {e}")

        try:
            self.logger.info("Запуск браузера...")
            self._context = self._pw.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
                headless=self.headless,
                locale="ru-RU",
                viewport={"width": 1440, "height": 900},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 "
                    "YaBrowser/24.4.0.0 (1) Yowser/2.5"
                ),
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-gpu",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-setuid-sandbox",
                    "--disable-web-security",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                    "--no-first-run",
                    "--disable-default-apps",
                    "--disable-popup-blocking",
                ],
                ignore_default_args=["--enable-automation"],
                timeout=30000,
                permissions=["clipboard-read", "clipboard-write"],
                executable_path=browser_path,
            )
            self.logger.info("✅ Браузер запущен")
            self.logger.info("Ожидание инициализации браузера (2с)...")
            time.sleep(2)

            # Проверяем, есть ли уже страницы
            pages = self._context.pages
            if pages:
                self.logger.info(f"Найдено {len(pages)} существующих страниц")
                # Используем первую существующую страницу
                self._page = pages[0]
                self.logger.info("Используем существующую страницу")
            else:
                # Создаем новую страницу с обработкой ошибки
                try:
                    self._page = self._context.new_page()
                    self.logger.info("Создана новая страница")
                except Exception as e:
                    self.logger.error(f"Не удалось создать новую страницу: {e}")
                    # Пробуем создать страницу с другими параметрами
                    try:
                        self._page = self._context.new_page(no_viewport=True)
                        self.logger.info("Создана новая страница (no_viewport)")
                    except Exception as e2:
                        self.logger.error(f"Не удалось создать страницу даже с no_viewport: {e2}")
                        raise

            # Закрываем лишние страницы, оставляем только одну
            pages = self._context.pages
            if len(pages) > 1:
                self.logger.info(f"Закрытие {len(pages) - 1} лишних страниц...")
                for i in range(len(pages) - 1, 0, -1):
                    try:
                        if pages[i] != self._page:
                            pages[i].close()
                    except Exception as e:
                        self.logger.warning(f"Не удалось закрыть страницу: {e}")

            self.logger.info("Открытие Google Translate...")
            try:
                self.logger.info(f"Загрузка страницы (таймаут 12с): {self.base_url}")
                self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=12000)
                self.logger.info(f"✅ Google Translate открыт: {self.base_url}")
            except Exception as e:
                self.logger.error(f"Ошибка загрузки страницы: {e}")
                # === ПОЛНОСТЬЮ ЗАКРЫВАЕМ ВСЕ ===
                try:
                    if self._context:
                        self._context.close()
                        self._context = None
                except:
                    pass
                if self._pw:
                    try:
                        self._pw.stop()
                    except:
                        pass
                    self._pw = None
                if profile_dir.exists():
                    try:
                        shutil.rmtree(profile_dir, ignore_errors=True)
                        self.logger.info("🧹 Папка профиля удалена после ошибки")
                    except:
                        pass
                raise Exception(f"Не удалось загрузить Google Translate: {e}")

            self._profile_dir = profile_dir

        except Exception as e:
            self.logger.error(f"Ошибка запуска браузера: {e}")
            # === ПОЛНОСТЬЮ ЗАКРЫВАЕМ ВСЕ ===
            try:
                if hasattr(self, '_context') and self._context:
                    self._context.close()
                    self._context = None
            except:
                pass
            if hasattr(self, '_pw') and self._pw:
                try:
                    self._pw.stop()
                except:
                    pass
                self._pw = None
            try:
                if profile_dir.exists():
                    shutil.rmtree(profile_dir, ignore_errors=True)
                    self.logger.info("🧹 Папка профиля удалена после ошибки")
            except:
                pass
            raise

    def _wait_for_blob_with_cancel(self, timeout: int = 15) -> bool:
        """
        Ожидает появления переведенного изображения (blob) с проверкой отмены.
        """
        self.logger.info(f"Ожидание появления переведенного изображения (таймаут: {timeout}с)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Проверяем флаг отмены
            if self._cancel_flag:
                self.logger.info("[DEBUG] _wait_for_blob_with_cancel: отмена")
                return False

            try:
                all_blobs = self._page.locator('img[src^="blob:"]')
                count = all_blobs.count()
                if count > 0:
                    self.logger.info(f"Найдено {count} blob изображений")
                    blob_img = all_blobs.last
                    alt = blob_img.get_attribute("alt") or ""
                    src = blob_img.get_attribute("src")
                    self.logger.info(f"  blob: src={src[:50] if src else 'None'}..., alt={alt[:30] if alt else 'None'}")
                    if "original" not in alt.lower() and "оригинал" not in alt.lower():
                        if src and len(src) > 20:
                            self.logger.info("✅ Найдено переведенное изображение (blob)")
                            return True
            except Exception as e:
                self.logger.debug(f"Ошибка при поиске blob: {e}")

            time.sleep(0.3)

        self.logger.warning("Переведенное изображение не появилось")
        return False

    def cancel_translation(self):
        """Отменяет текущий перевод"""
        self._cancel_flag = True
        self.logger.info("[DEBUG] GoogleTranslateDebug.cancel_translation() - флаг отмены установлен")

    def reset_page(self):
        """Сбрасывает страницу Google Translate (перезагружает)"""
        self.logger.info("[DEBUG] GoogleTranslateDebug.reset_page() - сброс страницы")

        if not self._page:
            self.logger.warning("[DEBUG] reset_page: страница не инициализирована")
            return

        try:
            # Перезагружаем страницу с переходом на URL загрузки
            self.logger.info(f"[DEBUG] reset_page: переход на {self.base_url}")
            self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=10000)
            self.logger.info("[DEBUG] reset_page: страница сброшена")
        except Exception as e:
            self.logger.error(f"[DEBUG] reset_page: ошибка: {e}")
            try:
                self._page.reload()
                self.logger.info("[DEBUG] reset_page: страница перезагружена (fallback)")
            except Exception as e2:
                self.logger.error(f"[DEBUG] reset_page: не удалось перезагрузить: {e2}")

    def _find_yandex_browser(self) -> Optional[str]:
        """Ищет Яндекс Браузер через реестр Windows"""
        self.logger.info("Поиск Яндекс Браузера через реестр Windows...")
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\browser.exe", 0, winreg.KEY_READ)
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
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Yandex\YandexBrowser", 0,
                                 winreg.KEY_READ)
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
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0,
                                 winreg.KEY_READ)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        if "Яндекс" in display_name or "Yandex" in display_name:
                            install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                            if install_location:
                                browser_path = os.path.join(install_location, "browser.exe")
                                if os.path.exists(browser_path):
                                    self.logger.info(f"✅ Найден Яндекс Браузер (Uninstall): {browser_path}")
                                    return browser_path
                    except:
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                    i += 1
                except WindowsError:
                    break
            winreg.CloseKey(key)
        except WindowsError:
            pass
        self.logger.warning("❌ Яндекс Браузер не найден в реестре")
        return None

    def _find_chrome_browser(self) -> Optional[str]:
        """Ищет Google Chrome через реестр Windows"""
        self.logger.info("Поиск Google Chrome через реестр Windows...")
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\chrome.exe", 0, winreg.KEY_READ)
            try:
                chrome_path = winreg.QueryValueEx(key, "")[0]
                if os.path.exists(chrome_path):
                    self.logger.info(f"✅ Найден Google Chrome (App Paths): {chrome_path}")
                    return chrome_path
            finally:
                winreg.CloseKey(key)
        except WindowsError:
            pass
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", 0,
                                 winreg.KEY_READ)
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    subkey = winreg.OpenKey(key, subkey_name)
                    try:
                        display_name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                        if "Google Chrome" in display_name:
                            install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                            if install_location:
                                chrome_path = os.path.join(install_location, "chrome.exe")
                                if os.path.exists(chrome_path):
                                    self.logger.info(f"✅ Найден Google Chrome (Uninstall): {chrome_path}")
                                    return chrome_path
                    except:
                        pass
                    finally:
                        winreg.CloseKey(subkey)
                    i += 1
                except WindowsError:
                    break
            winreg.CloseKey(key)
        except WindowsError:
            pass
        self.logger.warning("❌ Google Chrome не найден в реестре")
        return None

    def _find_browser_in_path(self) -> Optional[str]:
        """Ищет браузер в системном PATH"""
        self.logger.info("Поиск браузера в системном PATH...")
        try:
            result = subprocess.run(['where', 'yandex'], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                paths = result.stdout.strip().split('\n')
                for path in paths:
                    if path and os.path.exists(path):
                        self.logger.info(f"✅ Найден Яндекс Браузер в PATH: {path}")
                        return path
        except:
            pass
        try:
            result = subprocess.run(['where', 'chrome'], capture_output=True, text=True, shell=True)
            if result.returncode == 0:
                paths = result.stdout.strip().split('\n')
                for path in paths:
                    if path and os.path.exists(path):
                        self.logger.info(f"✅ Найден Google Chrome в PATH: {path}")
                        return path
        except:
            pass
        return None

    def _find_any_browser(self) -> Optional[str]:
        """Ищет любой доступный Chromium-браузер"""
        browser_path = self._find_yandex_browser()
        if browser_path:
            if hasattr(self, 'settings'):
                self.settings.set_browser_path(browser_path)
                self.logger.info(f"✅ Путь к браузеру сохранен в настройки: {browser_path}")
            return browser_path
        browser_path = self._find_chrome_browser()
        if browser_path:
            self.logger.info("⚠️ Яндекс Браузер не найден, будет использован Google Chrome")
            if hasattr(self, 'settings'):
                self.settings.set_browser_path(browser_path)
                self.logger.info(f"✅ Путь к браузеру сохранен в настройки: {browser_path}")
            return browser_path
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
                    self.logger.info(f"✅ Путь к браузеру сохранен в настройки: {path}")
                return path
        self.logger.error("❌ Не найден ни один Chromium-браузер")
        return None

    def update_interface_language(self, lang_code: str):
        """Обновляет язык интерфейса в URL и перезагружает страницу"""
        self.logger.info(f"Обновление языка интерфейса на: {lang_code}")
        hl_param = "ru" if lang_code == "ru" else "en"
        self.base_url = f"https://translate.google.com/details?hl={hl_param}&sl=auto&tl={self.target_lang}&op=images"
        if self._page:
            try:
                self.logger.info(f"Переход на URL: {self.base_url}")
                self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=15000)
                self.logger.info(f"✅ Страница обновлена с языком: {hl_param}")
            except Exception as e:
                self.logger.error(f"Ошибка обновления страницы: {e}")
                raise
        else:
            self.logger.warning("Страница не инициализирована, URL обновлен для следующего запуска")

    def _reset_pages_fast(self):
        """Быстрое обнуление вкладок - используем первую существующую"""
        try:
            if not self._context:
                return
            pages = self._context.pages
            page_count = len(pages)
            if page_count == 0:
                self._page = self._context.new_page()
                self.logger.info("Создана новая вкладка")
                return
            self._page = pages[0]
            self.logger.info(f"Используем существующую вкладку (всего {page_count})")
            if page_count > 1:
                for i in range(page_count - 1, 0, -1):
                    try:
                        pages[i].close()
                    except:
                        pass
                self.logger.info(f"Закрыты лишние вкладки, осталась 1")
        except Exception as e:
            self.logger.warning(f"Ошибка при обнулении вкладок: {e}")
            try:
                self._page = self._context.new_page()
                self.logger.info("Создана новая вкладка (fallback)")
            except:
                pass

    def translate_image(self, image_path: Path, output_dir: Path, worker=None) -> Optional[Path]:
        """
        Переводит изображение через Google Translate.
        Возвращает путь к переведенному изображению или None.
        """
        import time
        total_start = time.time()

        self._worker = worker
        self._cancel_flag = False

        if not self.is_browser_alive():
            self.logger.warning("Браузер закрыт, перезапуск...")
            self.close_browser()
            self.start_browser()
            time.sleep(1)

        self.logger.info("=" * 60)
        self.logger.info("🚀 ЗАПУСК ПЕРЕВОДА ИЗОБРАЖЕНИЯ")
        self.logger.info("=" * 60)

        try:
            # ШАГ 1
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 1: отменено")
                raise Exception("Перевод отменен")

            step_start = time.time()
            self.logger.info("Шаг 1: Проверка готовности страницы")
            try:
                self._page.evaluate("1 + 1")
                self.logger.info(f"  ✓ Страница загружена (+{time.time() - step_start:.3f}с)")
            except Exception as e:
                self.logger.warning(f"Страница недоступна, перезагрузка: {e}")
                try:
                    self._page.reload()
                    self.logger.info(f"  ✓ Страница перезагружена (+{time.time() - step_start:.3f}с)")
                except Exception as e2:
                    self.logger.error(f"Не удалось перезагрузить страницу: {e2}")
                    try:
                        self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=10000)
                        self.logger.info(f"  ✓ Страница открыта заново (+{time.time() - step_start:.3f}с)")
                    except Exception as e3:
                        self.logger.error(f"Не удалось открыть страницу: {e3}")
                        return None
            self.logger.info(f"  ✓ Шаг 1 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 2
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 2: отменено")
                raise Exception("Перевод отменен")

            step_start = time.time()
            self.logger.info("Шаг 2: Ожидание загрузки интерфейса")
            if not self._wait_for_upload_zone(timeout=10000):
                self._page.reload()
                if not self._wait_for_upload_zone(timeout=8000):
                    self.logger.error("Интерфейс не загрузился")
                    return None
            self.logger.info(f"  ✓ Шаг 2 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 3
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 3: отменено")
                raise Exception("Перевод отменен")

            step_start = time.time()
            self.logger.info("Шаг 3: Копирование изображения в буфер обмена")
            if not self._copy_image_to_clipboard(image_path):
                self.logger.error("Не удалось скопировать изображение")
                return None
            self.logger.info(f"  ✓ Шаг 3 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 4
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 4: отменено")
                raise Exception("Перевод отменен")

            step_start = time.time()
            self.logger.info("Шаг 4: Нажатие кнопки 'Вставить из буфера обмена'")
            if not self._find_and_click_paste_button():
                self.logger.error("Не найдена кнопка вставки")
                return None
            self.logger.info(f"  ✓ Шаг 4 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 5 - ОСНОВНОЙ ЦИКЛ ОЖИДАНИЯ С ПРОВЕРКОЙ ОТМЕНЫ
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 5: отменено")
                raise Exception("Перевод отменен")

            step_start = time.time()
            self.logger.info("Шаг 5: Ожидание перевода")

            # Ожидаем перевод с проверкой флага отмены
            if not self._wait_for_blob_with_cancel(timeout=20):
                self.logger.error("Перевод не завершился или был отменен")
                return None
            self.logger.info(f"  ✓ Шаг 5 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 6
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 6: отменено")
                raise Exception("Перевод отменен")

            step_start = time.time()
            self.logger.info("Шаг 6: Скачивание переведенного изображения")
            download_button = self._find_download_button()
            if not download_button:
                self.logger.error("Не найдена видимая кнопка скачивания")
                return None

            # Проверяем отмену перед скачиванием
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 6: отменено перед скачиванием")
                raise Exception("Перевод отменен")

            download_button.scroll_into_view_if_needed()
            if not download_button.is_visible():
                self.logger.error("Кнопка перестала быть видимой")
                return None

            with self._page.expect_download(timeout=20000) as download_info:
                download_button.click()
                self.logger.info("Нажата кнопка скачивания, ожидание загрузки...")

            # Проверяем отмену после скачивания
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 6: отменено после скачивания")
                raise Exception("Перевод отменен")

            download = download_info.value
            self.logger.info(f"Скачивание перехвачено: {download.suggested_filename}")
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / f"translated_{image_path.stem}.png"
            download.save_as(str(output_path))
            self.logger.info(f"  ✓ Шаг 6 выполнен за {time.time() - step_start:.3f}с")

            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 7: отменено")
                raise Exception("Перевод отменен")

            if output_path.exists():
                size = output_path.stat().st_size
                total_elapsed = time.time() - total_start
                self.logger.info(f"✅ Изображение сохранено: {output_path} ({size} байт)")
                self.logger.info(f"⏱️ ОБЩЕЕ ВРЕМЯ ПЕРЕВОДА: {total_elapsed:.3f} секунд")

                self.logger.info("Шаг 7: Переход на страницу загрузки для следующего перевода...")
                try:
                    self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=15000)
                    self.logger.info(f"✅ Переход на страницу загрузки: {self.base_url}")
                    if self._wait_for_upload_zone(timeout=5000):
                        self.logger.info("✅ Интерфейс загружен")
                    else:
                        self.logger.warning("Интерфейс не загрузился после перехода")
                except Exception as e:
                    self.logger.warning(f"Ошибка при переходе на страницу загрузки: {e}")
                    try:
                        self._page.reload()
                        self.logger.info("✅ Страница перезагружена")
                    except Exception as e2:
                        self.logger.warning(f"Не удалось перезагрузить страницу: {e2}")
                return output_path
            else:
                self.logger.error("Файл не был сохранен")
                return None

        except Exception as e:
            if "отменен" in str(e):
                self.logger.info(f"⏹️ ПЕРЕВОД ОТМЕНЕН ПОЛЬЗОВАТЕЛЕМ")
                # Сбрасываем страницу при отмене
                try:
                    self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=10000)
                    self.logger.info("✅ Страница сброшена после отмены")
                except:
                    pass
                raise Exception("Перевод отменен пользователем")
            else:
                total_elapsed = time.time() - total_start
                self.logger.error(f"Критическая ошибка (через {total_elapsed:.3f}с): {e}")
                import traceback
                traceback.print_exc()
                return None

    def close_browser(self):
        """Закрывает браузер и все вкладки, удаляет папку профиля"""
        import shutil

        # Сохраняем путь к папке профиля до закрытия контекста
        profile_dir = getattr(self, '_profile_dir', None)

        try:
            if self._context:
                try:
                    pages = self._context.pages
                    if pages:
                        self.logger.info(f"Закрытие {len(pages)} вкладок...")
                        for page in pages:
                            try:
                                page.close()
                            except:
                                pass
                        self.logger.info("Все вкладки закрыты")
                except Exception as e:
                    self.logger.error(f"Ошибка при закрытии вкладок: {e}")
                try:
                    self._context.close()
                    self.logger.info("Контекст закрыт")
                except Exception as e:
                    self.logger.error(f"Ошибка при закрытии контекста: {e}")
                self._context = None
                self._page = None

            if self._pw:
                try:
                    self._pw.stop()
                    self.logger.info("Playwright остановлен")
                except Exception as e:
                    self.logger.error(f"Ошибка при остановке Playwright: {e}")
                self._pw = None

            # Удаляем папку профиля после закрытия
            if profile_dir and profile_dir.exists():
                try:
                    shutil.rmtree(profile_dir, ignore_errors=True)
                    self.logger.info(f"🧹 Папка профиля удалена: {profile_dir}")
                except Exception as e:
                    self.logger.warning(f"Не удалось удалить папку профиля: {e}")

        except Exception as e:
            self.logger.error(f"Ошибка при закрытии браузера: {e}")

    def update_target_language(self, target_lang: str):
        """Обновляет целевой язык перевода"""
        self.target_lang = target_lang
        self.base_url = f"https://translate.google.com/details?hl=ru&sl=auto&tl={target_lang}&op=images"
        self.logger.info(f"Целевой язык обновлен на: {target_lang}")

    def is_browser_alive(self) -> bool:
        """Проверяет, жив ли браузер и контекст"""
        try:
            if self._context is None or self._page is None:
                return False
            self._page.evaluate("1 + 1")
            return True
        except Exception:
            return False

    def ensure_browser_alive(self):
        """Проверяет, жив ли браузер, и перезапускает если нет"""
        if not self.is_browser_alive():
            self.logger.warning("Браузер не активен, перезапуск...")
            self.close_browser()
            self.start_browser()
            return True
        return False

    def _copy_image_to_clipboard(self, image_path: Path) -> bool:
        """Копирует изображение в буфер обмена через Playwright (быстро)"""
        self.logger.info(f"Копирование изображения в буфер обмена: {image_path}")
        if not image_path.exists():
            self.logger.error(f"Файл не найден: {image_path}")
            return False
        try:
            with open(image_path, 'rb') as f:
                image_data = f.read()
            import base64
            b64_data = base64.b64encode(image_data).decode('utf-8')
            js_code = """
                (b64Data) => {
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
                }
            """
            result = self._page.evaluate(js_code, b64_data)
            if result:
                self.logger.info("✅ Изображение скопировано в буфер обмена")
                return True
            else:
                self.logger.error("❌ Не удалось скопировать изображение в буфер обмена")
                return False
        except Exception as e:
            self.logger.error(f"Ошибка при копировании в буфер: {e}")
            return False

    def _find_and_click_paste_button(self) -> bool:
        """Быстро нажимает кнопку 'Вставить из буфера обмена'"""
        self.logger.info("Вставка изображения из буфера обмена...")
        try:
            self._page.click('body')
            self._page.keyboard.press("Control+V")
            self.logger.info("✅ Вставка через Ctrl+V выполнена")
            return True
        except Exception as e:
            self.logger.warning(f"Ctrl+V не сработал: {e}")
        try:
            button = self._page.locator('button[aria-label="Вставить изображение из буфера обмена"]')
            if button.count() > 0:
                button.first.click(timeout=2000)
                self.logger.info("✅ Кнопка вставки нажата")
                return True
        except Exception as e:
            self.logger.debug(f"Не удалось нажать кнопку: {e}")
        self.logger.warning("Не удалось вставить изображение")
        return False

    def _wait_for_upload_zone(self, timeout: int = 15000) -> bool:
        """Ожидает появления зоны загрузки на вкладке 'Изображения'"""
        self.logger.info("Ожидание загрузки интерфейса...")
        selectors = [
            'button[aria-label="Вставить изображение из буфера обмена"]',
            'button:has-text("Вставить из буфера обмена")',
            'input[type="file"]',
            '.gLXQIf',
            '.T12pLd',
            'div:has-text("Или выберите файл")',
        ]
        start_time = time.time()
        while (time.time() - start_time) * 1000 < timeout:
            for selector in selectors:
                try:
                    locator = self._page.locator(selector).first
                    if locator.count() > 0:
                        if locator.is_visible() or locator.is_attached():
                            self.logger.info(f"Найден элемент: {selector}")
                            return True
                except Exception:
                    pass
            time.sleep(0.5)
        self.logger.warning("Не удалось найти зону загрузки")
        return False

    def _wait_for_blob(self, timeout: int = 15) -> bool:
        """
        Ожидает появления переведенного изображения (blob).
        """
        self.logger.info(f"Ожидание появления переведенного изображения (таймаут: {timeout}с)...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                all_blobs = self._page.locator('img[src^="blob:"]')
                count = all_blobs.count()
                if count > 0:
                    self.logger.info(f"Найдено {count} blob изображений")
                    blob_img = all_blobs.last
                    alt = blob_img.get_attribute("alt") or ""
                    src = blob_img.get_attribute("src")
                    self.logger.info(f"  blob: src={src[:50] if src else 'None'}..., alt={alt[:30] if alt else 'None'}")
                    if "original" not in alt.lower() and "оригинал" not in alt.lower():
                        if src and len(src) > 20:
                            self.logger.info("✅ Найдено переведенное изображение (blob)")
                            return True
            except Exception as e:
                self.logger.debug(f"Ошибка при поиске blob: {e}")
            time.sleep(0.3)
        self.logger.warning("Переведенное изображение не появилось")
        return False

    def _find_download_button(self):
        """
        Находит видимую кнопку скачивания. Возвращает locator или None.
        """
        self.logger.info("Поиск видимой кнопки скачивания...")
        buttons = self._page.locator('button[jsname="hRZeKc"]')
        count = buttons.count()
        self.logger.info(f"Найдено {count} кнопок с jsname='hRZeKc'")
        for i in range(count):
            btn = buttons.nth(i)
            is_visible = btn.is_visible()
            aria = btn.get_attribute("aria-label") or ""
            self.logger.info(f"  Кнопка #{i + 1}: visible={is_visible}, aria='{aria}'")
            if is_visible:
                self.logger.info(f"✅ Найдена видимая кнопка #{i + 1}")
                return btn
        self.logger.info("Пробуем поиск по aria-label...")
        buttons = self._page.locator('button[aria-label="Скачать перевод"]')
        count = buttons.count()
        for i in range(count):
            btn = buttons.nth(i)
            is_visible = btn.is_visible()
            if is_visible:
                self.logger.info(f"✅ Найдена видимая кнопка по aria-label #{i + 1}")
                return btn
        self.logger.warning("Не найдена видимая кнопка скачивания")
        return None