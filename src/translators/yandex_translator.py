"""
Модуль для перевода изображений через Яндекс.Переводчик (OCR).
"""

import os
import time
import logging
import shutil
import base64
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright

from .base_translator import BaseTranslator
from src.utils import get_safe_temp_dir


class YandexOcrTranslator(BaseTranslator):
    """Класс для перевода изображений через Яндекс.Переводчик (OCR)."""

    def __init__(self, headless: bool = True, target_lang: str = "ru", settings=None):
        super().__init__(headless, target_lang, settings)
        self.base_url = "https://translate.yandex.ru/ocr"
        self.logger = logging.getLogger(__name__)

    def create_new_page(self) -> bool:
        """Создаёт новую страницу в существующем контексте браузера."""
        self.logger.info("[BROWSER] Создание новой страницы в существующем контексте (Yandex)...")
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
            self.logger.info("[BROWSER] Новая страница создана (Yandex)")

            self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=10000)
            self.logger.info(f"[BROWSER] ✅ Страница загружена: {self.base_url}")

            self._wait_for_interface()
            return True
        except Exception as e:
            self.logger.error(f"[BROWSER] Ошибка создания новой страницы (Yandex): {e}")
            return False

    def start_browser(self):
        """Запускает браузер с Playwright для Яндекс.Переводчика."""
        import time

        self.logger.info("Запуск Yandex OCR браузера...")
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
                "Пожалуйста, установите один из браузеров."
            )
            self.logger.error(error_msg)
            raise Exception(error_msg)

        self.logger.info(f"Используется браузер: {browser_path}")

        safe_temp_dir = get_safe_temp_dir()
        timestamp = int(time.time() * 1000)
        profile_dir = safe_temp_dir / f"yandex_ocr_profile_{timestamp}"

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
                viewport={"width": 1280, "height": 800},
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
                ],
                ignore_default_args=["--enable-automation"],
                timeout=60000,
                executable_path=browser_path,
            )
            self.logger.info("✅ Браузер запущен")

            time.sleep(3)

            pages = self._context.pages
            if pages:
                self._page = pages[0]
                self.logger.info("Используем существующую страницу")
            else:
                self._page = self._context.new_page()
                self.logger.info("Создана новая страница")

            # Закрываем лишние страницы
            pages = self._context.pages
            if len(pages) > 1:
                for i in range(len(pages) - 1, 0, -1):
                    try:
                        if pages[i] != self._page:
                            pages[i].close()
                    except:
                        pass

            self.logger.info("Открытие Яндекс.Переводчика (OCR)...")
            self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=8000)
            self.logger.info(f"✅ Яндекс.Переводчик открыт: {self.base_url}")

            # Применяем целевой язык, если он был указан и не русский
            if self.target_lang and self.target_lang != "ru":
                self.logger.info(f"[YANDEX] Применение начального языка: {self.target_lang}")
                time.sleep(1)
                self.update_target_language(self.target_lang)

            self._profile_dir = profile_dir

            # Ожидаем загрузки интерфейса
            self._wait_for_interface()

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
            raise

    def _wait_for_interface(self, timeout: int = 10000) -> bool:
        """Ожидает загрузки интерфейса Яндекс.Переводчика."""
        self.logger.info("Ожидание загрузки интерфейса...")

        selectors = [
            '.dropBlock',
            '.dropMessage',
            '#ocrUrlInput',
            '.fileContainer-content',
            'button[aria-label="Вставить"]',
            '[data-testid="upload-area"]',
            '.upload-container',
            '[data-testid="dropzone"]'
        ]

        for selector in selectors:
            try:
                self._page.wait_for_selector(selector, timeout=timeout)
                self.logger.info(f"✅ Найден элемент: {selector}")
                return True
            except:
                pass

        self.logger.warning("⚠️ Не удалось найти элементы интерфейса")
        return False

    def _wait_for_upload_zone(self, timeout: int = 10000) -> bool:
        """
        Ожидает появления зоны загрузки на странице Яндекс.Переводчика.
        Это алиас для _wait_for_interface для совместимости с GoogleTranslateDebug.
        """
        return self._wait_for_interface(timeout)

    def _find_and_click_paste_button(self) -> bool:
        """Находит и нажимает кнопку вставки изображения."""
        self.logger.info("Вставка изображения...")

        # Пробуем через Ctrl+V
        try:
            self._page.click('body')
            time.sleep(0.3)
            self._page.keyboard.press("Control+V")
            self.logger.info("✅ Ctrl+V отправлен")
            time.sleep(1.5)
            return True
        except Exception as e:
            self.logger.warning(f"Ctrl+V не сработал: {e}")

        # Пробуем найти кнопку вставки по aria-label
        try:
            paste_button = self._page.locator('button[aria-label="Вставить"]').first
            if paste_button.count() > 0 and paste_button.is_visible():
                paste_button.click()
                self.logger.info("✅ Кнопка 'Вставить' нажата")
                return True
        except:
            pass

        # Пробуем другие селекторы
        try:
            paste_button = self._page.locator('[data-testid="paste-button"]').first
            if paste_button.count() > 0 and paste_button.is_visible():
                paste_button.click()
                self.logger.info("✅ Кнопка вставки (data-testid) нажата")
                return True
        except:
            pass

        # Пробуем найти любую кнопку с текстом "Вставить"
        try:
            paste_button = self._page.locator('button:has-text("Вставить")').first
            if paste_button.count() > 0 and paste_button.is_visible():
                paste_button.click()
                self.logger.info("✅ Кнопка с текстом 'Вставить' нажата")
                return True
        except:
            pass

        self.logger.error("❌ Не удалось вставить изображение")
        return False

    def _wait_for_result(self, timeout: int = 60000) -> bool:
        """Ожидает появления результата OCR/перевода."""
        self.logger.info(f"Ожидание результата OCR (таймаут: {timeout // 1000}с)...")
        start_time = time.time()

        while (time.time() - start_time) * 1000 < timeout:
            if self._cancel_flag:
                self.logger.info("[DEBUG] _wait_for_result: отмена")
                return False

            try:
                # Проверяем кнопку скачивания
                download_btn = self._page.locator('#downloadButton').first
                if download_btn.count() > 0 and download_btn.is_visible():
                    self.logger.info("✅ Найдена кнопка 'Скачать'")
                    return True
            except:
                pass

            # Проверяем наличие результата
            try:
                result_selectors = [
                    '.ocr-result',
                    '.translation-result',
                    '.result-content',
                    'img[src^="blob:"]',
                    '[data-testid="result"]',
                    '.image-container img',
                    '.result-image',
                    '#resultImage'
                ]
                for selector in result_selectors:
                    try:
                        elem = self._page.locator(selector).first
                        if elem.count() > 0 and elem.is_visible():
                            self.logger.info(f"✅ Найден результат: {selector}")
                            return True
                    except:
                        pass
            except:
                pass

            time.sleep(0.5)

        self.logger.warning("⚠️ Таймаут ожидания результата")
        return False

    def _download_result(self, output_dir: Path, original_name: str) -> Optional[Path]:
        """Скачивает результат OCR."""
        self.logger.info("Скачивание результата...")

        try:
            # Ищем кнопку скачивания
            download_btn = self._page.locator('#downloadButton').first

            if download_btn.count() == 0:
                self.logger.warning("⚠️ Кнопка 'Скачать' не найдена")
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
            output_path = output_dir / f"{original_stem}_yandex_translated{ext}"

            counter = 1
            while output_path.exists():
                output_path = output_dir / f"{original_stem}_yandex_translated_{counter}{ext}"
                counter += 1

            download.save_as(str(output_path))
            self.logger.info(f"✅ Результат сохранён: {output_path}")
            return output_path

        except Exception as e:
            self.logger.error(f"Ошибка скачивания: {e}")
            return None

    def translate_image(self, image_path: Path, output_dir: Path, worker=None) -> Optional[Path]:
        """Переводит изображение через Яндекс.Переводчик (OCR)."""
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
        self.logger.info("🚀 ЗАПУСК ПЕРЕВОДА ИЗОБРАЖЕНИЯ (Yandex OCR)")
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
            if not self._wait_for_upload_zone(timeout=10000):
                self._page.reload()
                if not self._wait_for_upload_zone(timeout=10000):
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

            if not self._wait_for_result(timeout=60000):
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

            # ШАГ 7: Возврат на главную страницу
            if self._cancel_flag:
                self.logger.info("[DEBUG] Шаг 7: отменено")
                raise Exception("Перевод отменён")

            self.logger.info("Шаг 7: Переход на страницу загрузки для следующего перевода...")
            try:
                timeout_ms = 10000
                self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=timeout_ms)
                self.logger.info(f"✅ Переход на страницу загрузки: {self.base_url}")
                if self._wait_for_upload_zone(timeout=10000):
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

            if output_path.exists():
                size = output_path.stat().st_size
                total_elapsed = time.time() - total_start
                self.logger.info(f"✅ Изображение сохранено: {output_path} ({size} байт)")
                self.logger.info(f"⏱️ ОБЩЕЕ ВРЕМЯ ПЕРЕВОДА: {total_elapsed:.3f} секунд")
                return output_path
            else:
                self.logger.error("Файл не был сохранён")
                return None

        except Exception as e:
            if "отменён" in str(e):
                self.logger.info("⏹️ ПЕРЕВОД ОТМЕНЁН ПОЛЬЗОВАТЕЛЕМ")
                try:
                    timeout_ms = 10000
                    self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=timeout_ms)
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
        """Сбрасывает страницу Яндекс.Переводчика."""
        self.logger.info("[DEBUG] YandexOcrTranslator.reset_page() - сброс страницы")
        try:
            self._page.goto(self.base_url, wait_until="domcontentloaded", timeout=8000)
            self._wait_for_interface()
            self.logger.info("[DEBUG] Страница сброшена")
        except Exception as e:
            self.logger.error(f"Ошибка сброса страницы: {e}")

    def update_target_language(self, target_lang: str):
        """Обновляет целевой язык перевода для Яндекс.Переводчика через интерфейс."""
        import time

        self.logger.info(f"[YANDEX] Обновление целевого языка на: {target_lang}")
        self.target_lang = target_lang

        if not self._page:
            self.logger.warning("[YANDEX] Страница не инициализирована, язык не может быть обновлён")
            return

        try:
            # 1. Кликаем по кнопке выбора целевого языка
            self.logger.info("[YANDEX] Поиск кнопки выбора языка...")
            dst_button = self._page.locator('button#dstLangButton')

            if dst_button.count() == 0:
                self.logger.warning("[YANDEX] Кнопка выбора языка не найдена")
                return

            dst_button.click()
            self.logger.info("[YANDEX] Кнопка выбора языка нажата")
            time.sleep(0.5)

            # 2. Находим и кликаем по нужному языку в списке
            self.logger.info(f"[YANDEX] Поиск языка '{target_lang}' в списке...")
            lang_item = self._page.locator(f'.langs-item[data-value="{target_lang}"]')

            if lang_item.count() == 0:
                self.logger.warning(f"[YANDEX] Язык '{target_lang}' не найден в списке")
                self._page.click('body')
                return

            lang_item.scroll_into_view_if_needed()
            lang_item.click()
            self.logger.info(f"[YANDEX] Выбран язык: {target_lang}")

            time.sleep(0.5)
            self._page.click('body')
            self.logger.info("[YANDEX] Список языков закрыт")

        except Exception as e:
            self.logger.error(f"[YANDEX] Ошибка при обновлении языка: {e}")

    def update_interface_language(self, lang_code: str):
        """Обновляет язык интерфейса."""
        self.logger.info(f"Обновление языка интерфейса на: {lang_code}")
        # Яндекс.Переводчик автоматически определяет язык