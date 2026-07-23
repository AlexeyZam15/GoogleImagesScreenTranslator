"""


Модуль для перевода изображений через Google Translate



"""

import os
import time
import logging
import base64
import io
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright
from PIL import Image


class GoogleTranslateDebug:
    """Класс для перевода изображений в Google Translate (вкладка Images)"""

    def __init__(self, headless: bool = True, target_lang: str = "ru"):
        self.headless = headless
        self.target_lang = target_lang
        self.base_url = f"https://translate.google.com/details?hl=ru&sl=auto&tl={target_lang}&op=images"
        self._pw = None
        self._context = None
        self._page = None
        self.logger = logging.getLogger(__name__)

    def start_browser(self):
        """Запускает Яндекс Браузер с Playwright"""
        self.logger.info("Запуск Playwright...")
        self._pw = sync_playwright().start()

        self.logger.info("Запуск Яндекс Браузера...")

        yandex_path = r"P:\Program Files\Yandex\YandexBrowser\Application\browser.exe"

        if not os.path.exists(yandex_path):
            self.logger.error(f"Яндекс Браузер не найден по пути: {yandex_path}")
            self.logger.error("Пожалуйста, проверьте правильность пути")
            yandex_path = None
        else:
            self.logger.info(f"Яндекс Браузер найден: {yandex_path}")

        self._context = self._pw.chromium.launch_persistent_context(
            user_data_dir="metadata/google_translate_profile",
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
            ],
            ignore_default_args=["--enable-automation"],
            timeout=30000,
            permissions=["clipboard-read", "clipboard-write"],
            executable_path=yandex_path,
        )

        self.logger.info("Яндекс Браузер запущен")

        # Получаем первую вкладку (она пустая)
        pages = self._context.pages
        if pages:
            self._page = pages[0]
            self.logger.info("Используем существующую вкладку")
        else:
            self._page = self._context.new_page()
            self.logger.info("Создана новая вкладка")

        # Закрываем все лишние вкладки, оставляя только текущую
        self._cleanup_pages()

        self.logger.info("Открытие Google Translate на вкладке Изображения...")
        try:
            self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=30000)
            self.logger.info(f"Google Translate открыт: {self.base_url}")
        except Exception as e:
            self.logger.error(f"Ошибка при открытии Google Translate: {e}")
            try:
                self.logger.info("Повторная попытка открытия...")
                self._page.goto(self.base_url, timeout=30000)
                self.logger.info(f"Google Translate открыт (повторно): {self.base_url}")
            except Exception as e2:
                self.logger.error(f"Повторная ошибка при открытии: {e2}")
                raise

    def _cleanup_pages(self):
        """Закрывает все лишние вкладки, оставляя только текущую"""
        try:
            if not self._context:
                return

            pages = self._context.pages
            page_count = len(pages)

            if page_count <= 1:
                self.logger.info(f"Всего {page_count} вкладка, очистка не требуется")
                return

            self.logger.info(f"Найдено {page_count} вкладок, закрываем лишние...")

            # Закрываем все вкладки, кроме текущей (self._page)
            for i, page in enumerate(pages):
                if page != self._page:
                    try:
                        page.close()
                        self.logger.info(f"Закрыта вкладка #{i + 1}")
                    except Exception as e:
                        self.logger.warning(f"Не удалось закрыть вкладку #{i + 1}: {e}")

            self.logger.info(f"Очистка завершена, осталась 1 вкладка")
        except Exception as e:
            self.logger.warning(f"Ошибка при очистке вкладок: {e}")

    def close_browser(self):
        """Закрывает браузер"""
        try:
            if self._context:
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
        """Копирует изображение в буфер обмена через JavaScript"""
        self.logger.info(f"Копирование изображения в буфер обмена: {image_path}")

        if not image_path.exists():
            self.logger.error(f"Файл не найден: {image_path}")
            return False

        try:
            with Image.open(image_path) as img:
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')

                buffer = io.BytesIO()
                img.save(buffer, format='PNG')
                png_data = buffer.getvalue()

            b64_data = base64.b64encode(png_data).decode('utf-8')

            js_code = """
                async (b64Data) => {
                    try {
                        const binaryString = atob(b64Data);
                        const bytes = new Uint8Array(binaryString.length);
                        for (let i = 0; i < binaryString.length; i++) {
                            bytes[i] = binaryString.charCodeAt(i);
                        }

                        const blob = new Blob([bytes], { type: 'image/png' });

                        await navigator.clipboard.write([
                            new ClipboardItem({
                                [blob.type]: blob
                            })
                        ]);

                        return true;
                    } catch (e) {
                        console.error('Clipboard error:', e);
                        return false;
                    }
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
        """Находит и нажимает кнопку 'Вставить из буфера обмена'"""
        self.logger.info("Поиск кнопки 'Вставить из буфера обмена'...")

        button_selectors = [
            'button[aria-label="Вставить изображение из буфера обмена"]',
            'button.VfPpkd-LgbsSe.OLiIxf.PDpWxe',
            'button.Rj2Mlf.OLiIxf.PDpWxe',
            'button.VfPpkd-LgbsSe',
            'button:has-text("Вставить из буфера обмена")',
            'span:has-text("Вставить из буфера обмена")',
            '//button[contains(@aria-label, "Вставить изображение из буфера обмена")]',
            '//button[.//span[text()="Вставить из буфера обмена"]]',
            '//button[contains(., "Вставить из буфера обмена")]',
            'div[jsaction*="wQCqLd"] button',
        ]

        for selector in button_selectors:
            try:
                locator = self._page.locator(selector).first
                if locator.count() > 0 and locator.is_visible():
                    locator.scroll_into_view_if_needed()
                    locator.click(timeout=5000)
                    self.logger.info(f"✅ Нажата кнопка вставки через селектор: {selector}")
                    return True
            except Exception as e:
                self.logger.debug(f"Не удалось использовать селектор {selector}: {e}")
                continue

        self.logger.warning("Не удалось найти кнопку 'Вставить из буфера обмена'")
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

    def translate_image(self, image_path: Path, output_dir: Path) -> Optional[Path]:
        """
        Переводит изображение через Google Translate.
        Возвращает путь к переведенному изображению или None.
        """
        import time
        total_start = time.time()

        if not self.is_browser_alive():
            self.logger.warning("Браузер закрыт, перезапуск...")
            self.close_browser()
            self.start_browser()
            time.sleep(1)

        self.logger.info("=" * 60)
        self.logger.info("🚀 ЗАПУСК ПЕРЕВОДА ИЗОБРАЖЕНИЯ")
        self.logger.info("=" * 60)
        self.logger.info(f"URL: {self.base_url}")

        try:
            step_start = time.time()
            self.logger.info("Шаг 1: Открытие Google Translate")
            try:
                self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=20000)
            except Exception as e:
                self.logger.error(f"Ошибка при открытии страницы: {e}")
                self.logger.info("Попытка перезапуска браузера...")
                self.close_browser()
                self.start_browser()
                time.sleep(1)
                self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=20000)
            self.logger.info(f"  ✓ Шаг 1 выполнен за {time.time() - step_start:.2f}с")

            step_start = time.time()
            self.logger.info("Шаг 2: Ожидание загрузки интерфейса")
            if not self._wait_for_upload_zone(timeout=10000):
                self._page.reload()
                time.sleep(2)
                if not self._wait_for_upload_zone(timeout=8000):
                    self.logger.error("Интерфейс не загрузился")
                    return None
            self.logger.info(f"  ✓ Шаг 2 выполнен за {time.time() - step_start:.2f}с")
            time.sleep(0.5)

            step_start = time.time()
            self.logger.info("Шаг 3: Копирование изображения в буфер обмена")
            if not self._copy_image_to_clipboard(image_path):
                self.logger.error("Не удалось скопировать изображение")
                return None
            self.logger.info(f"  ✓ Шаг 3 выполнен за {time.time() - step_start:.2f}с")
            time.sleep(0.3)

            step_start = time.time()
            self.logger.info("Шаг 4: Нажатие кнопки 'Вставить из буфера обмена'")
            if not self._find_and_click_paste_button():
                self.logger.error("Не найдена кнопка вставки")
                return None
            self.logger.info(f"  ✓ Шаг 4 выполнен за {time.time() - step_start:.2f}с")

            step_start = time.time()
            self.logger.info("Шаг 5: Ожидание перевода")
            if not self._wait_for_blob(timeout=20):
                self.logger.error("Перевод не завершился")
                return None
            self.logger.info(f"  ✓ Шаг 5 выполнен за {time.time() - step_start:.2f}с")
            time.sleep(0.5)

            step_start = time.time()
            self.logger.info("Шаг 6: Скачивание переведенного изображения")
            output_path = output_dir / f"translated_{image_path.stem}.png"

            download_button = self._find_download_button()
            if not download_button:
                self.logger.error("Не найдена видимая кнопка скачивания")
                return None

            download_button.scroll_into_view_if_needed()
            time.sleep(0.3)

            if not download_button.is_visible():
                self.logger.error("Кнопка перестала быть видимой")
                return None

            with self._page.expect_download(timeout=20000) as download_info:
                download_button.click()
                self.logger.info("Нажата кнопка скачивания, ожидание загрузки...")

            download = download_info.value
            self.logger.info(f"Скачивание перехвачено: {download.suggested_filename}")

            output_dir.mkdir(parents=True, exist_ok=True)
            download.save_as(str(output_path))

            self.logger.info(f"  ✓ Шаг 6 выполнен за {time.time() - step_start:.2f}с")

            if output_path.exists():
                size = output_path.stat().st_size
                total_elapsed = time.time() - total_start
                self.logger.info(f"✅ Изображение сохранено: {output_path} ({size} байт)")
                self.logger.info(f"⏱️ ОБЩЕЕ ВРЕМЯ ПЕРЕВОДА: {total_elapsed:.2f} секунд")
                return output_path
            else:
                self.logger.error("Файл не был сохранен")
                return None

        except Exception as e:
            total_elapsed = time.time() - total_start
            self.logger.error(f"Критическая ошибка (через {total_elapsed:.2f}с): {e}")
            import traceback
            traceback.print_exc()
            return None

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
