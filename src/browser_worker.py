"""
Модуль для работы с браузером в отдельном потоке
"""

import threading
import queue
import time
import logging
from typing import Optional, Callable, Any
from pathlib import Path

# Локальные импорты
from src.translator import GoogleTranslateDebug
from src.settings import Settings


class BrowserWorker:
    """
    Управляет браузером в отдельном потоке с очередью команд
    """

    __slots__ = (
        'logger', 'settings', 'translator', '_command_queue', '_result_queue',
        '_running', '_thread', '_ready', '_initializing', '_cancel_flag',
        '_last_result_time', '_result_batch', '_batch_max_size'
    )

    def __init__(self, settings: Settings):
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.translator: Optional[GoogleTranslateDebug] = None
        self._command_queue = queue.Queue()
        self._result_queue = queue.Queue()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._ready = False
        self._initializing = False
        self._cancel_flag = False

        # Оптимизация обработки результатов
        self._last_result_time = 0
        self._result_batch = []
        self._batch_max_size = 10

    def _worker_loop(self):
        """Главный цикл рабочего потока (оптимизированная версия)"""
        self.logger.info("Рабочий цикл BrowserWorker запущен")

        while self._running:
            try:
                # Уменьшаем таймаут для более быстрой реакции
                try:
                    command = self._command_queue.get(timeout=0.1)
                except queue.Empty:
                    # Обрабатываем накопленные результаты
                    self._flush_results()
                    continue

                if command is None:
                    break

                cmd_type = command.get('type')
                cmd_id = command.get('id')
                args = command.get('args', [])
                kwargs = command.get('kwargs', {})
                callback = command.get('callback')

                self.logger.info(f"Выполнение команды: {cmd_type} (id={cmd_id})")

                try:
                    result = self._execute_command(cmd_type, *args, **kwargs)
                    # Добавляем результат в пакет для оптимизации
                    self._result_batch.append({
                        'id': cmd_id,
                        'success': True,
                        'result': result,
                        'error': None,
                        'callback': callback
                    })

                    # Если набралось достаточно результатов - отправляем пакет
                    if len(self._result_batch) >= self._batch_max_size:
                        self._flush_results()

                except Exception as e:
                    self.logger.error(f"Ошибка выполнения команды {cmd_type}: {e}")
                    self._result_batch.append({
                        'id': cmd_id,
                        'success': False,
                        'result': None,
                        'error': str(e),
                        'callback': callback
                    })

            except Exception as e:
                self.logger.error(f"Ошибка в рабочем цикле: {e}")
                time.sleep(0.05)

        # Очищаем оставшиеся результаты при завершении
        self._flush_results()

        if self.translator:
            try:
                self.translator.close_browser()
            except:
                pass
            self.translator = None

        self.logger.info("Рабочий цикл BrowserWorker завершен")

    def _flush_results(self):
        """Отправляет накопленные результаты одним пакетом"""
        if not self._result_batch:
            return

        # Отправляем все результаты в очередь
        for result in self._result_batch:
            self._result_queue.put(result)

        self.logger.debug(f"Отправлено {len(self._result_batch)} результатов")
        self._result_batch.clear()

    def process_results(self):
        """Обрабатывает полученные результаты (оптимизированная версия)"""
        processed = 0

        try:
            # Обрабатываем все накопленные результаты за один раз
            results = []
            while True:
                try:
                    result = self._result_queue.get_nowait()
                    results.append(result)
                    processed += 1
                except queue.Empty:
                    break

            if not results:
                return 0

            self.logger.info(f"Обработка {len(results)} результатов...")

            for result in results:
                callback = result.get('callback')
                if callback:
                    if result['success']:
                        callback(result['result'], None)
                    else:
                        callback(None, result['error'])

        except Exception as e:
            self.logger.error(f"Ошибка обработки результатов: {e}")

        return processed

    def _init_browser(self, show_browser: bool, target_lang: str):
        """Инициализация браузера с выбором движка"""
        self.logger.info("Инициализация браузера...")
        self._initializing = True
        try:
            if self.translator:
                self.logger.info("Закрываем существующий экземпляр переводчика...")
                try:
                    self.translator.close_browser()
                except Exception as e:
                    self.logger.warning(f"Ошибка при закрытии старого браузера: {e}")
                self.translator = None

            import time
            time.sleep(2.0)  # УВЕЛИЧЕНО: 0.5 -> 2.0

            engine = self.settings.get_translator_engine()
            self.logger.info(f"Используемый движок перевода: {engine}")

            if engine == "yandex":
                from src.translator import YandexOcrTranslator
                self.translator = YandexOcrTranslator(
                    headless=not show_browser,
                    target_lang=target_lang,
                    settings=self.settings
                )
            else:
                from src.translator import GoogleTranslateDebug
                self.translator = GoogleTranslateDebug(
                    headless=not show_browser,
                    target_lang=target_lang,
                    settings=self.settings
                )

            self.logger.info("Запускаем браузер...")
            self.translator.start_browser()

            self._ready = True
            self._initializing = False
            self.logger.info(f"Браузер инициализирован успешно (движок: {engine})")
            return {'ready': True}

        except Exception as e:
            self._initializing = False
            self._ready = False
            self.logger.error(f"Ошибка инициализации браузера: {e}")
            if self.translator:
                try:
                    self.translator.close_browser()
                except Exception as e2:
                    self.logger.warning(f"Ошибка при закрытии браузера после ошибки: {e2}")
                self.translator = None
            import time
            time.sleep(0.5)
            raise

    def _restart_browser(self, show_browser: bool, target_lang: str):
        """Перезапуск браузера."""
        self.logger.info("Перезапуск браузера...")
        if self.translator:
            self.logger.info("Закрываем существующий браузер...")
            try:
                self.translator.close_browser()
            except Exception as e:
                self.logger.warning(f"Ошибка при закрытии браузера: {e}")
            self.translator = None
        self._ready = False

        import time
        time.sleep(2.0)  # УВЕЛИЧЕНО: 1.0 -> 2.0

        return self._init_browser(show_browser, target_lang)

    def _reset_page(self):
        """Сбрасывает страницу Google Translate"""
        if not self.translator:
            self.logger.warning("[DEBUG] _reset_page: translator не инициализирован")
            return {'success': False, 'error': 'translator not initialized'}

        self.logger.info("[DEBUG] _reset_page: сброс страницы Google Translate")
        self.translator.reset_page()
        return {'success': True}

    def cancel_translation(self):
        """Отменяет текущий перевод"""
        self._cancel_flag = True
        self.logger.info("[DEBUG] BrowserWorker.cancel_translation() - флаг отмены установлен")
        if self.translator:
            self.translator.cancel_translation()

    def start(self):
        """Запускает рабочий поток"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        self.logger.info("BrowserWorker запущен")

    def stop(self):
        """Останавливает рабочий поток с таймаутом и принудительным завершением"""
        import time
        import threading

        self.logger.info("[BROWSER_WORKER] Остановка...")

        # 1. Устанавливаем флаг остановки
        self._running = False

        # 2. Отправляем сигнал в очередь
        if self._command_queue:
            try:
                self._command_queue.put_nowait(None)
                self.logger.info("[BROWSER_WORKER] Сигнал остановки отправлен в очередь")
            except Exception as e:
                self.logger.warning(f"[BROWSER_WORKER] Ошибка отправки сигнала: {e}")

        # 3. Отменяем текущий перевод
        if hasattr(self, 'translator') and self.translator:
            try:
                self.translator.cancel_translation()
            except:
                pass

        # 4. Закрываем браузер (это может занять время)
        if hasattr(self, 'translator') and self.translator:
            try:
                self.logger.info("[BROWSER_WORKER] Закрытие браузера...")
                close_start = time.time()
                self.translator.close_browser()
                close_elapsed = time.time() - close_start
                self.logger.info(f"[BROWSER_WORKER] Браузер закрыт за {close_elapsed:.2f}с")
            except Exception as e:
                self.logger.warning(f"[BROWSER_WORKER] Ошибка закрытия браузера: {e}")
            self.translator = None

        # 5. Ждем завершения потока с таймаутом (уменьшено до 0.5 секунды)
        if self._thread and self._thread.is_alive():
            self.logger.info("[BROWSER_WORKER] Ожидание завершения потока...")
            self._thread.join(timeout=0.5)  # УМЕНЬШЕНО: 3.0 -> 0.5

            if self._thread.is_alive():
                self.logger.warning("[BROWSER_WORKER] Поток не завершился за 0.5 секунды, продолжаем закрытие.")
                # Не пытаемся сделать поток демоном - просто продолжаем
                # Поток будет завершен при выходе из процесса

        self.logger.info("[BROWSER_WORKER] Остановлен")

    def _execute_command(self, cmd_type: str, *args, **kwargs):
        """Выполняет команду в рабочем потоке"""
        self.logger.info(f"Выполнение команды: {cmd_type} с аргументами: args={args}, kwargs={kwargs}")
        try:
            if cmd_type == 'init':
                return self._init_browser(*args, **kwargs)
            elif cmd_type == 'translate':
                return self._translate_image(*args, **kwargs)
            elif cmd_type == 'restart':
                return self._restart_browser(*args, **kwargs)
            elif cmd_type == 'update_language':
                return self._update_language(*args, **kwargs)
            elif cmd_type == 'update_interface_language':
                return self._update_interface_language(*args, **kwargs)
            elif cmd_type == 'reset_page':
                return self._reset_page()
            elif cmd_type == 'close':
                return self._close_browser()
            else:
                raise ValueError(f"Неизвестная команда: {cmd_type}")
        except Exception as e:
            self.logger.error(f"Ошибка выполнения команды {cmd_type}: {e}")
            raise

    def _translate_image(self, image_path: Path, output_dir: Path):
        """Перевод изображения"""
        if not self._ready or not self.translator:
            raise RuntimeError("Браузер не готов")

        self._cancel_flag = False
        self.logger.info(f"Перевод изображения: {image_path}")
        return self.translator.translate_image(image_path, output_dir, self)

    def _update_language(self, target_lang: str):
        """Обновление целевого языка"""
        if self.translator:
            self.translator.update_target_language(target_lang)
            self.logger.info(f"Язык обновлен на: {target_lang}")
        return {'success': True}

    def _update_interface_language(self, lang_code: str):
        """Обновляет язык интерфейса браузера"""
        if not self.translator:
            raise RuntimeError("Браузер не инициализирован")
        self.logger.info(f"Обновление языка интерфейса на: {lang_code}")
        self.translator.update_interface_language(lang_code)
        return {'success': True}

    def _close_browser(self):
        """Закрытие браузера"""
        if self.translator:
            self.translator.close_browser()
            self.translator = None
        self._ready = False
        return {'success': True}

    def init_browser(self, show_browser: bool, target_lang: str,
                     callback: Optional[Callable] = None) -> int:
        """Отправляет команду инициализации браузера"""
        cmd_id = id(self) + len(self._command_queue.queue)
        self._command_queue.put({
            'type': 'init',
            'id': cmd_id,
            'args': [show_browser, target_lang],
            'kwargs': {},
            'callback': callback
        })
        self.logger.info(f"Команда init отправлена в очередь (id={cmd_id})")
        return cmd_id

    def translate_image(self, image_path: Path, output_dir: Path,
                        callback: Optional[Callable] = None) -> int:
        """Отправляет команду перевода изображения"""
        cmd_id = id(self) + len(self._command_queue.queue)
        self._command_queue.put({
            'type': 'translate',
            'id': cmd_id,
            'args': [image_path, output_dir],
            'kwargs': {},
            'callback': callback
        })
        return cmd_id

    def restart_browser(self, show_browser: bool, target_lang: str,
                        callback: Optional[Callable] = None) -> int:
        """Отправляет команду перезапуска браузера"""
        cmd_id = id(self) + len(self._command_queue.queue)
        self._command_queue.put({
            'type': 'restart',
            'id': cmd_id,
            'args': [show_browser, target_lang],
            'kwargs': {},
            'callback': callback
        })
        return cmd_id

    def update_language(self, target_lang: str,
                        callback: Optional[Callable] = None) -> int:
        """Отправляет команду обновления языка"""
        cmd_id = id(self) + len(self._command_queue.queue)
        self._command_queue.put({
            'type': 'update_language',
            'id': cmd_id,
            'args': [target_lang],
            'kwargs': {},
            'callback': callback
        })
        return cmd_id

    def update_interface_language(self, lang_code: str,
                                  callback: Optional[Callable] = None) -> int:
        """Отправляет команду обновления языка интерфейса"""
        cmd_id = id(self) + len(self._command_queue.queue)
        self._command_queue.put({
            'type': 'update_interface_language',
            'id': cmd_id,
            'args': [lang_code],
            'kwargs': {},
            'callback': callback
        })
        return cmd_id

    def close_browser(self, callback: Optional[Callable] = None) -> int:
        """Отправляет команду закрытия браузера"""
        cmd_id = id(self) + len(self._command_queue.queue)
        self._command_queue.put({
            'type': 'close',
            'id': cmd_id,
            'args': [],
            'kwargs': {},
            'callback': callback
        })
        return cmd_id

    @property
    def is_ready(self) -> bool:
        """Готов ли браузер"""
        return self._ready and self.translator is not None

    @property
    def is_initializing(self) -> bool:
        """Идет ли инициализация"""
        return self._initializing

    def get_translator(self) -> Optional[GoogleTranslateDebug]:
        """Возвращает переводчика (только для чтения)"""
        return self.translator
