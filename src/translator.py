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
        import shutil
        import time

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

        # Удаляем старый профиль для чистого запуска
        profile_path = Path("metadata/google_translate_profile")
        if profile_path.exists():
            try:
                shutil.rmtree(profile_path)
                self.logger.info("✅ Старый профиль удален")
            except Exception as e:
                self.logger.warning(f"Не удалось удалить профиль: {e}")

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

        # Даем браузеру время на инициализацию
        self.logger.info("Ожидание инициализации браузера (3с)...")
        time.sleep(3)

        # Закрываем все существующие вкладки
        pages = self._context.pages
        if pages:
            self.logger.info(f"Закрытие {len(pages)} существующих вкладок...")
            for page in pages:
                try:
                    page.close()
                except Exception as e:
                    self.logger.warning(f"Не удалось закрыть вкладку: {e}")
            self.logger.info("Все вкладки закрыты")

        # Создаем новую чистую вкладку
        self._page = self._context.new_page()
        self.logger.info("Создана новая вкладка")

        # Переходим на Google Translate
        self.logger.info("Открытие Google Translate...")
        try:
            self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=15000)
            self.logger.info(f"✅ Google Translate открыт: {self.base_url}")
        except Exception as e:
            self.logger.error(f"Ошибка при открытии Google Translate: {e}")
            try:
                self.logger.info("Повторная попытка открытия...")
                self._page.goto(self.base_url, timeout=15000)
                self.logger.info(f"✅ Google Translate открыт (повторно): {self.base_url}")
            except Exception as e2:
                self.logger.error(f"Повторная ошибка при открытии: {e2}")
                raise

    def _reset_pages_fast(self):
        """Быстрое обнуление вкладок - используем первую существующую"""
        try:
            if not self._context:
                return

            pages = self._context.pages
            page_count = len(pages)

            if page_count == 0:
                # Нет вкладок - создаем новую
                self._page = self._context.new_page()
                self.logger.info("Создана новая вкладка")
                return

            # Используем первую вкладку
            self._page = pages[0]
            self.logger.info(f"Используем существующую вкладку (всего {page_count})")

            # Закрываем все остальные вкладки быстро (начиная с конца)
            if page_count > 1:
                for i in range(page_count - 1, 0, -1):
                    try:
                        pages[i].close()
                    except:
                        pass
                self.logger.info(f"Закрыты лишние вкладки, осталась 1")

        except Exception as e:
            self.logger.warning(f"Ошибка при обнулении вкладок: {e}")
            # Если что-то пошло не так - создаем новую вкладку
            try:
                self._page = self._context.new_page()
                self.logger.info("Создана новая вкладка (fallback)")
            except:
                pass

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

        try:
            # Шаг 1: Проверка готовности страницы
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

            # Шаг 2: Ожидание загрузки интерфейса
            step_start = time.time()
            self.logger.info("Шаг 2: Ожидание загрузки интерфейса")
            if not self._wait_for_upload_zone(timeout=10000):
                self._page.reload()
                if not self._wait_for_upload_zone(timeout=8000):
                    self.logger.error("Интерфейс не загрузился")
                    return None
            self.logger.info(f"  ✓ Шаг 2 выполнен за {time.time() - step_start:.3f}с")

            # Шаг 3: Копирование изображения в буфер обмена
            step_start = time.time()
            self.logger.info("Шаг 3: Копирование изображения в буфер обмена")
            if not self._copy_image_to_clipboard(image_path):
                self.logger.error("Не удалось скопировать изображение")
                return None
            self.logger.info(f"  ✓ Шаг 3 выполнен за {time.time() - step_start:.3f}с")

            # Шаг 4: Нажатие кнопки 'Вставить из буфера обмена'
            step_start = time.time()
            self.logger.info("Шаг 4: Нажатие кнопки 'Вставить из буфера обмена'")
            if not self._find_and_click_paste_button():
                self.logger.error("Не найдена кнопка вставки")
                return None
            self.logger.info(f"  ✓ Шаг 4 выполнен за {time.time() - step_start:.3f}с")

            # Шаг 5: Ожидание перевода
            step_start = time.time()
            self.logger.info("Шаг 5: Ожидание перевода")
            if not self._wait_for_blob(timeout=20):
                self.logger.error("Перевод не завершился")
                return None
            self.logger.info(f"  ✓ Шаг 5 выполнен за {time.time() - step_start:.3f}с")

            # Шаг 6: Скачивание переведенного изображения
            step_start = time.time()
            self.logger.info("Шаг 6: Скачивание переведенного изображения")
            output_path = output_dir / f"translated_{image_path.stem}.png"

            download_button = self._find_download_button()
            if not download_button:
                self.logger.error("Не найдена видимая кнопка скачивания")
                return None

            download_button.scroll_into_view_if_needed()

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

            self.logger.info(f"  ✓ Шаг 6 выполнен за {time.time() - step_start:.3f}с")

            if output_path.exists():
                size = output_path.stat().st_size
                total_elapsed = time.time() - total_start
                self.logger.info(f"✅ Изображение сохранено: {output_path} ({size} байт)")
                self.logger.info(f"⏱️ ОБЩЕЕ ВРЕМЯ ПЕРЕВОДА: {total_elapsed:.3f} секунд")

                # ВОЗВРАЩАЕМ РЕЗУЛЬТАТ СРАЗУ, БЕЗ ПОДГОТОВКИ СТРАНИЦЫ
                return output_path
            else:
                self.logger.error("Файл не был сохранен")
                return None

        except Exception as e:
            total_elapsed = time.time() - total_start
            self.logger.error(f"Критическая ошибка (через {total_elapsed:.3f}с): {e}")
            import traceback
            traceback.print_exc()
            return None

    def close_browser(self):
        """Закрывает браузер и все вкладки"""
        try:
            if self._context:
                # Закрываем все вкладки
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

                # Закрываем контекст
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
        """Копирует изображение в буфер обмена через Playwright (быстро)"""
        self.logger.info(f"Копирование изображения в буфер обмена: {image_path}")

        if not image_path.exists():
            self.logger.error(f"Файл не найден: {image_path}")
            return False

        try:
            # Используем встроенный метод Playwright для установки буфера обмена
            # Читаем изображение как PNG
            with open(image_path, 'rb') as f:
                image_data = f.read()

            # Кодируем в base64 для передачи в JavaScript
            import base64
            b64_data = base64.b64encode(image_data).decode('utf-8')

            # Минимальный JavaScript для копирования
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

        # Просто нажимаем Ctrl+V - страница уже готова
        try:
            self._page.click('body')
            self._page.keyboard.press("Control+V")
            self.logger.info("✅ Вставка через Ctrl+V выполнена")
            return True
        except Exception as e:
            self.logger.warning(f"Ctrl+V не сработал: {e}")

        # Запасной вариант - ищем кнопку
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
