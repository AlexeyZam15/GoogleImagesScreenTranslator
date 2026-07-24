"""
Модуль для работы с браузером в отдельном потоке
"""

import threading
import queue
import time
import logging
from typing import Optional, Callable, Any
from pathlib import Path

from src.translator import GoogleTranslateDebug
from src.settings import Settings


class BrowserWorker:
    """
    Управляет браузером в отдельном потоке с очередью команд
    """

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

    def start(self):
        """Запускает рабочий поток"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()
        self.logger.info("BrowserWorker запущен")

    def stop(self):
        """Останавливает рабочий поток"""
        self._running = False
        if self._command_queue:
            try:
                self._command_queue.put_nowait(None)
            except:
                pass
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=2.0)
        self.logger.info("BrowserWorker остановлен")

    def _worker_loop(self):
        """Главный цикл рабочего потока"""
        self.logger.info("Рабочий цикл BrowserWorker запущен")
        while self._running:
            try:
                try:
                    command = self._command_queue.get(timeout=0.5)
                except queue.Empty:
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
                    self._result_queue.put({
                        'id': cmd_id,
                        'success': True,
                        'result': result,
                        'error': None,
                        'callback': callback
                    })
                    self.logger.info(f"Команда {cmd_type} выполнена успешно, результат в очереди")
                except Exception as e:
                    self.logger.error(f"Ошибка выполнения команды {cmd_type}: {e}")
                    self._result_queue.put({
                        'id': cmd_id,
                        'success': False,
                        'result': None,
                        'error': str(e),
                        'callback': callback
                    })
            except Exception as e:
                self.logger.error(f"Ошибка в рабочем цикле: {e}")
                time.sleep(0.1)
        if self.translator:
            try:
                self.translator.close_browser()
            except:
                pass
            self.translator = None
        self.logger.info("Рабочий цикл BrowserWorker завершен")

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
            elif cmd_type == 'close':
                return self._close_browser()
            else:
                raise ValueError(f"Неизвестная команда: {cmd_type}")
        except Exception as e:
            self.logger.error(f"Ошибка выполнения команды {cmd_type}: {e}")
            raise

    def _init_browser(self, show_browser: bool, target_lang: str):
        """Инициализация браузера"""
        self.logger.info("Инициализация браузера...")
        self._initializing = True
        try:
            if self.translator:
                self.translator.close_browser()
                self.translator = None
            self.translator = GoogleTranslateDebug(
                headless=not show_browser,
                target_lang=target_lang,
                settings=self.settings
            )
            self.translator.start_browser()
            self._ready = True
            self._initializing = False
            self.logger.info("Браузер инициализирован успешно")
            return {'ready': True}
        except Exception as e:
            self._initializing = False
            self._ready = False
            self.logger.error(f"Ошибка инициализации браузера: {e}")
            raise

    def _restart_browser(self, show_browser: bool, target_lang: str):
        """Перезапуск браузера"""
        self.logger.info("Перезапуск браузера...")
        if self.translator:
            self.translator.close_browser()
            self.translator = None
        self._ready = False
        return self._init_browser(show_browser, target_lang)

    def _translate_image(self, image_path: Path, output_dir: Path):
        """Перевод изображения"""
        if not self._ready or not self.translator:
            raise RuntimeError("Браузер не готов")
        self.logger.info(f"Перевод изображения: {image_path}")
        return self.translator.translate_image(image_path, output_dir)

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

    def process_results(self):
        """Обрабатывает полученные результаты (вызывать из основного потока)"""
        processed = 0
        try:
            while True:
                result = self._result_queue.get_nowait()
                processed += 1
                self.logger.info(f"Обработка результата: id={result.get('id')}, success={result.get('success')}")
                callback = result.get('callback')
                if callback:
                    self.logger.info(f"Вызов колбэка для id={result.get('id')}")
                    if result['success']:
                        callback(result['result'], None)
                    else:
                        callback(None, result['error'])
                else:
                    self.logger.warning(f"Нет колбэка для результата id={result.get('id')}")
        except queue.Empty:
            pass
        return processed

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