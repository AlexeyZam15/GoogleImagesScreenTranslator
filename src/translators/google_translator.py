"""
Модуль для перевода изображений через Google Translate.
"""

import os
import time
import logging
import shutil
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright
from PIL import Image

from .base_translator import BaseTranslator
from src.utils import get_safe_temp_dir


class GoogleTranslateDebug(BaseTranslator):
    """Класс для перевода изображений через Google Translate."""

    def __init__(self, headless: bool = True, target_lang: str = "ru", settings=None):
        super().__init__(headless, target_lang, settings)
        self.base_url = f"https://translate.google.com/details?hl=ru&sl=auto&tl={target_lang}&op=images"
        self.logger = logging.getLogger(__name__)

    def create_new_page(self) -> bool:
        """Создаёт новую страницу в существующем контексте браузера."""
        self.logger.info("[BROWSER] Создание новой страницы в существующем контексте...")
        if not self._context:
            self.logger.error("[BROWSER] Контекст не инициализирован")
            return False

        try:
            if self._page:
                try:
                    self._page.close()
                except:
                    pass
                self._page = None

            self._page = self._context.new_page()
            self.logger.info("[BROWSER] Новая страница создана")

            self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=10000)
            self.logger.info(f"[BROWSER] ✅ Страница загружена: {self.base_url}")

            # ============================================================
            # Активируем разрешение на буфер обмена (оно уже сохранено в контексте)
            # ============================================================
            try:
                self._page.evaluate("navigator.clipboard.read().catch(() => {})")
                self.logger.info("[BROWSER] ✅ Разрешение на буфер обмена активировано")
            except Exception as e:
                self.logger.warning(f"[BROWSER] Не удалось активировать разрешение: {e}")

            self._wait_for_interface()
            return True
        except Exception as e:
            self.logger.error(f"[BROWSER] Ошибка создания новой страницы: {e}")
            return False

    def start_browser(self):
        """Запускает браузер с Playwright."""
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
                self.logger.info(f"✅ Автоматически найденный путь сохранён: {browser_path}")

        if not browser_path:
            error_msg = (
                "Не найден Яндекс Браузер или Google Chrome. "
                "Пожалуйста, установите один из браузеров. "
                "Рекомендуется Яндекс Браузер для лучшей совместимости."
            )
            self.logger.error(error_msg)
            raise Exception(error_msg)

        self.logger.info(f"Используется браузер: {browser_path}")

        safe_temp_dir = get_safe_temp_dir()
        timestamp = int(time.time() * 1000)
        # Используем единый префикс с указанием движка
        profile_dir = safe_temp_dir / f"google_translate_profile_{timestamp}"

        # Удаляем старый профиль, если он существует
        if profile_dir.exists():
            try:
                shutil.rmtree(profile_dir)
                self.logger.info("✅ Старый профиль удалён")
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
                timeout=60000,
                permissions=["clipboard-read", "clipboard-write"],
                executable_path=browser_path,
            )
            self.logger.info("✅ Браузер запущен")
            self.logger.info("Ожидание инициализации браузера (3с)...")
            time.sleep(3)

            pages = self._context.pages
            if pages:
                self.logger.info(f"Найдено {len(pages)} существующих страниц")
                self._page = pages[0]
                self.logger.info("Используем существующую страницу")
            else:
                try:
                    self._page = self._context.new_page()
                    self.logger.info("Создана новая страница")
                except Exception as e:
                    self.logger.error(f"Не удалось создать новую страницу: {e}")
                    try:
                        self._page = self._context.new_page(no_viewport=True)
                        self.logger.info("Создана новая страница (no_viewport)")
                    except Exception as e2:
                        self.logger.error(f"Не удалось создать страницу даже с no_viewport: {e2}")
                        raise

            # Закрываем лишние страницы
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
                self.base_url = f"https://translate.google.com/details?hl=ru&sl=auto&tl={self.target_lang}&op=images"
                timeout_ms = 10000
                self.logger.info(f"Загрузка страницы (таймаут {timeout_ms}мс): {self.base_url}")
                self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=timeout_ms)
                self.logger.info(f"✅ Google Translate открыт: {self.base_url}")
            except Exception as e:
                self.logger.error(f"Ошибка загрузки страницы: {e}")
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
            try:
                if profile_dir.exists():
                    shutil.rmtree(profile_dir, ignore_errors=True)
                    self.logger.info("🧹 Папка профиля удалена после ошибки")
            except:
                pass
            raise

    def _wait_for_interface(self, timeout: int = 10000) -> bool:
        """Ожидает появления зоны загрузки на вкладке 'Изображения'."""
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
            time.sleep(0.3)
        self.logger.warning("Не удалось найти зону загрузки")
        return False

    def _wait_for_upload_zone(self, timeout: int = 10000) -> bool:
        """Алиас для _wait_for_interface."""
        return self._wait_for_interface(timeout)

    def _wait_for_blob(self, timeout: int = 15) -> bool:
        """Ожидает появления переведённого изображения (blob)."""
        self.logger.info(f"Ожидание появления переведённого изображения (таймаут: {timeout}с)...")
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
                            self.logger.info("✅ Найдено переведённое изображение (blob)")
                            return True
            except Exception as e:
                self.logger.debug(f"Ошибка при поиске blob: {e}")
            time.sleep(0.3)
        self.logger.warning("Переведённое изображение не появилось")
        return False

    def _wait_for_blob_with_cancel(self, timeout: int = 15) -> bool:
        """Ожидает появления переведённого изображения с проверкой отмены."""
        self.logger.info(f"Ожидание появления переведённого изображения (таймаут: {timeout}с)...")
        start_time = time.time()

        while time.time() - start_time < timeout:
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
                            self.logger.info("✅ Найдено переведённое изображение (blob)")
                            return True
            except Exception as e:
                self.logger.debug(f"Ошибка при поиске blob: {e}")

            time.sleep(0.3)

        self.logger.warning("Переведённое изображение не появилось")
        return False

    def _find_download_button(self):
        """Находит видимую кнопку скачивания."""
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

    def _find_and_click_paste_button(self) -> bool:
        """
        Вставляет изображение из буфера обмена.
        Просто активирует уже существующее разрешение через чтение буфера.
        """
        self.logger.info("Вставка изображения из буфера обмена...")

        # ============================================================
        # ШАГ 1: Активируем разрешение на чтение буфера (оно уже должно быть)
        # ============================================================
        try:
            self.logger.info("Активация разрешения на чтение буфера обмена...")
            js_code = """
            async function activateClipboard() {
                try {
                    // Просто пытаемся прочитать — если разрешение уже есть, это сработает
                    const items = await navigator.clipboard.read();
                    return { success: true };
                } catch (e) {
                    // Если разрешение ещё не получено, браузер покажет диалог
                    return { success: false, error: e.message };
                }
            }
            return await activateClipboard();
            """
            result = self._page.evaluate(js_code)
            self.logger.info(f"Результат активации: {result}")
        except Exception as e:
            self.logger.warning(f"Ошибка при активации: {e}")

        # ============================================================
        # ШАГ 2: Вставляем через Ctrl+V
        # ============================================================
        try:
            self.logger.info("Попытка вставки через Ctrl+V...")
            self._page.click('body')
            time.sleep(0.3)
            self._page.keyboard.press("Control+V")
            self.logger.info("✅ Ctrl+V отправлен")
            time.sleep(1.0)
            return True
        except Exception as e:
            self.logger.warning(f"Ctrl+V не сработал: {e}")

        # ============================================================
        # ШАГ 3: Кнопка "Вставить из буфера обмена"
        # ============================================================
        try:
            self.logger.info("Поиск кнопки 'Вставить изображение из буфера обмена'...")
            button = self._page.locator('button[aria-label="Вставить изображение из буфера обмена"]')
            if button.count() > 0:
                button.first.click(timeout=3000)
                self.logger.info("✅ Кнопка вставки нажата")
                return True
        except Exception as e:
            self.logger.debug(f"Не удалось нажать кнопку: {e}")

        self.logger.warning("Не удалось вставить изображение")
        return False

    def _download_result(self, output_dir: Path, original_name: str) -> Optional[Path]:
        """Скачивает результат перевода."""
        self.logger.info("Скачивание результата...")

        try:
            download_btn = self._find_download_button()
            if not download_btn:
                self.logger.warning("⚠️ Кнопка скачивания не найдена")
                return None

            download_btn.scroll_into_view_if_needed()

            with self._page.expect_download(timeout=30000) as download_info:
                download_btn.click()
                self.logger.info("Нажата кнопка скачивания...")

            download = download_info.value
            self.logger.info(f"Скачивание перехвачено: {download.suggested_filename}")

            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            original_stem = Path(original_name).stem
            ext = Path(download.suggested_filename).suffix or '.png'
            output_path = output_dir / f"{original_stem}_translated{ext}"

            counter = 1
            while output_path.exists():
                output_path = output_dir / f"{original_stem}_translated_{counter}{ext}"
                counter += 1

            download.save_as(str(output_path))
            self.logger.info(f"✅ Результат сохранён: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Ошибка скачивания: {e}")
            return None

    def translate_image(self, image_path: Path, output_dir: Path, worker=None) -> Optional[Path]:
        """Переводит изображение через Google Translate."""
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
        self.logger.info("🚀 ЗАПУСК ПЕРЕВОДА ИЗОБРАЖЕНИЯ (Google Translate)")
        self.logger.info("=" * 60)

        try:
            # ШАГ 1: Проверка готовности страницы
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 1: отменено")
                raise Exception("Перевод отменён")

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
                        timeout_ms = 10000
                        self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=timeout_ms)
                        self.logger.info(f"  ✓ Страница открыта заново (+{time.time() - step_start:.3f}с)")
                    except Exception as e3:
                        self.logger.error(f"Не удалось открыть страницу: {e3}")
                        return None
            self.logger.info(f"  ✓ Шаг 1 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 2: Ожидание загрузки интерфейса
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 2: отменено")
                raise Exception("Перевод отменён")

            step_start = time.time()
            self.logger.info("Шаг 2: Ожидание загрузки интерфейса")
            if not self._wait_for_interface(timeout=10000):
                self._page.reload()
                if not self._wait_for_interface(timeout=10000):
                    self.logger.error("Интерфейс не загрузился")
                    return None
            self.logger.info(f"  ✓ Шаг 2 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 3: Копирование изображения в буфер обмена
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 3: отменено")
                raise Exception("Перевод отменён")

            step_start = time.time()
            self.logger.info("Шаг 3: Копирование изображения в буфер обмена")
            if not self._copy_image_to_clipboard(image_path):
                self.logger.error("Не удалось скопировать изображение")
                return None
            self.logger.info(f"  ✓ Шаг 3 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 4: Вставка изображения
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 4: отменено")
                raise Exception("Перевод отменён")

            step_start = time.time()
            self.logger.info("Шаг 4: Вставка изображения")
            if not self._find_and_click_paste_button():
                self.logger.error("Не удалось вставить изображение")
                return None
            self.logger.info(f"  ✓ Шаг 4 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 5: Ожидание результата
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 5: отменено")
                raise Exception("Перевод отменён")

            step_start = time.time()
            self.logger.info("Шаг 5: Ожидание результата")

            if not self._wait_for_blob_with_cancel(timeout=20):
                self.logger.error("Результат не появился")
                return None
            self.logger.info(f"  ✓ Шаг 5 выполнен за {time.time() - step_start:.3f}с")

            # ШАГ 6: Скачивание результата
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 6: отменено")
                raise Exception("Перевод отменён")

            step_start = time.time()
            self.logger.info("Шаг 6: Скачивание результата")

            output_path = self._download_result(output_dir, image_path.name)
            if not output_path:
                self.logger.error("Не удалось скачать результат")
                return None

            self.logger.info(f"  ✓ Шаг 6 выполнен за {time.time() - step_start:.3f}с")

            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 7: отменено")
                raise Exception("Перевод отменён")

            if output_path.exists():
                size = output_path.stat().st_size
                total_elapsed = time.time() - total_start
                self.logger.info(f"✅ Изображение сохранено: {output_path} ({size} байт)")
                self.logger.info(f"⏱️ ОБЩЕЕ ВРЕМЯ ПЕРЕВОДА: {total_elapsed:.3f} секунд")

                # ============================================================
                # ИСПРАВЛЕНИЕ: Сбрасываем страницу после успешного перевода
                # ============================================================
                self.logger.info("🔄 Сброс страницы Google Translate для следующего перевода...")
                self.reset_page()

                return output_path
            else:
                self.logger.error("Файл не был сохранён")
                return None

        except Exception as e:
            if "отменён" in str(e):
                self.logger.info("⏹️ ПЕРЕВОД ОТМЕНЁН ПОЛЬЗОВАТЕЛЕМ")
                try:
                    self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=10000)
                    self.logger.info("✅ Страница сброшена после отмены")
                except:
                    pass
                raise Exception("Перевод отменён пользователем")
            else:
                total_elapsed = time.time() - total_start
                self.logger.error(f"Критическая ошибка (через {total_elapsed:.3f}с): {e}")
                import traceback
                traceback.print_exc()
                return None

    def reset_page(self):
        """Сбрасывает страницу Google Translate на чистую страницу загрузки изображения."""
        self.logger.info("[DEBUG] GoogleTranslateDebug.reset_page() - сброс страницы")
        if not self._page:
            self.logger.warning("[DEBUG] reset_page: страница не инициализирована")
            return

        try:
            timeout_ms = 10000
            self.logger.info(f"[DEBUG] reset_page: переход на {self.base_url} (таймаут {timeout_ms}мс)")
            self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=timeout_ms)

            # Ждём загрузки интерфейса
            self.logger.info("[DEBUG] reset_page: ожидание загрузки интерфейса...")
            if self._wait_for_interface(timeout=5000):
                self.logger.info("[DEBUG] reset_page: интерфейс загружен, страница сброшена")
            else:
                self.logger.warning("[DEBUG] reset_page: интерфейс не загрузился, но переход выполнен")

            # Дополнительно пробуем активировать разрешение на буфер обмена
            try:
                self._page.evaluate("navigator.clipboard.read().catch(() => {})")
                self.logger.info("[DEBUG] reset_page: разрешение на буфер обмена активировано")
            except Exception as e:
                self.logger.debug(f"[DEBUG] reset_page: не удалось активировать разрешение: {e}")

        except Exception as e:
            self.logger.error(f"[DEBUG] reset_page: ошибка: {e}")
            try:
                self._page.reload()
                self.logger.info("[DEBUG] reset_page: страница перезагружена (fallback)")
                # Ждём загрузку интерфейса после перезагрузки
                self._wait_for_interface(timeout=5000)
            except Exception as e2:
                self.logger.error(f"[DEBUG] reset_page: не удалось перезагрузить: {e2}")

    def update_target_language(self, target_lang: str):
        """Обновляет целевой язык перевода."""
        self.target_lang = target_lang
        self.base_url = f"https://translate.google.com/details?hl=ru&sl=auto&tl={target_lang}&op=images"
        self.logger.info(f"Целевой язык обновлён на: {target_lang}")

    def update_interface_language(self, lang_code: str):
        """Обновляет язык интерфейса."""
        self.logger.info(f"Обновление языка интерфейса на: {lang_code}")
        hl_param = "ru" if lang_code == "ru" else "en"
        self.base_url = f"https://translate.google.com/details?hl={hl_param}&sl=auto&tl={self.target_lang}&op=images"
        if self._page:
            try:
                timeout_ms = 8000
                self.logger.info(f"Переход на URL: {self.base_url} (таймаут {timeout_ms}мс)")
                self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=timeout_ms)
                self.logger.info(f"✅ Страница обновлена с языком: {hl_param}")
            except Exception as e:
                self.logger.error(f"Ошибка обновления страницы: {e}")
                raise
        else:
            self.logger.warning("Страница не инициализирована, URL обновлён для следующего запуска")