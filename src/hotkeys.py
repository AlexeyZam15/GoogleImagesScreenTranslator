"""
Управление горячими клавишами - с поддержкой длительного зажатия F3
"""

import logging
import time
import keyboard
import win32con


class HotkeyManager:
    """Управляет глобальными горячими клавишами"""

    # Время зажатия для определения длительного нажатия (мс)
    HOLD_THRESHOLD_MS = 500

    __slots__ = (
        'app', 'logger', 'settings', '_key_last_time', '_debounce_ms',
        '_hotkey_hook_active', '_hotkeys_blocked', '_hotkey_actions',
        '_action_queue', '_processing_queue',
        '_f3_down_time', '_f3_timer', '_f3_hold_triggered',
        '_f5_down_time', '_f5_timer', '_f5_hold_triggered'
    )

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.settings = app.settings

        self._key_last_time = {}
        self._debounce_ms = 300
        self._hotkey_hook_active = False
        self._hotkeys_blocked = False
        self._hotkey_actions = {}
        self._action_queue = []
        self._processing_queue = False

        # Для отслеживания длительного зажатия F3
        self._f3_down_time = 0
        self._f3_timer = None
        self._f3_hold_triggered = False

        self._f5_down_time = 0
        self._f5_timer = None
        self._f5_hold_triggered = False

    def _on_f5_down(self, event):
        """Обработчик нажатия F5"""
        if self._hotkeys_blocked:
            return
        self.logger.info("[HOTKEYS] F5 нажата (down)")
        self._f5_down_time = time.time()
        self._f5_hold_triggered = False

    def _on_f5_up(self, event):
        """Обработчик отпускания F5"""
        if self._hotkeys_blocked:
            return
        self.logger.info("[HOTKEYS] F5 отпущена (up)")
        if not self._f5_hold_triggered and self._f5_down_time > 0:
            elapsed_ms = (time.time() - self._f5_down_time) * 1000
            if elapsed_ms > 50:
                self.logger.info("[HOTKEYS] Короткое нажатие F5 -> edit_mode")
                self._queue_action('edit_mode')
            self._f5_down_time = 0

    def setup(self):
        """Настраивает горячие клавиши"""
        self.logger.info("=" * 60)
        self.logger.info("[HOTKEYS] НАСТРОЙКА ГОРЯЧИХ КЛАВИШ")
        self.logger.info("=" * 60)

        try:
            # ============================================================
            # Полностью очищаем все старые хуки
            # ============================================================
            keyboard.unhook_all()
            self.logger.info("[HOTKEYS] Все старые хуки отключены")

            self._hotkey_actions = self.settings.get_all_hotkeys()

            # Список действий, которые обрабатываются отдельно (сложные/длительное зажатие)
            special_actions = ['area', 'fullscreen_ocr', 'edit_mode']

            # Регистрируем обычные клавиши
            for action, hotkey in self._hotkey_actions.items():
                if action in special_actions:
                    continue  # Эти обрабатываются отдельно
                if hotkey:
                    try:
                        keyboard.on_press_key(hotkey, lambda e, a=action: self._queue_action(a), suppress=True)
                        self.logger.info(f"[HOTKEYS] Зарегистрировано (блокировка): {hotkey} -> {action}")
                    except Exception as e:
                        self.logger.warning(f"[HOTKEYS] Не удалось зарегистрировать {hotkey}: {e}")

            # ============================================================
            # Регистрируем F3 отдельно для обработки длительного зажатия
            # ============================================================
            try:
                # НЕ вызываем keyboard.unhook_key('f3') — это вызывает ошибку!
                keyboard.on_press_key('f3', self._on_f3_down, suppress=True)
                keyboard.on_release_key('f3', self._on_f3_up, suppress=True)
                self.logger.info("[HOTKEYS] Зарегистрировано: F3 (с поддержкой длительного зажатия, блокировка)")
            except Exception as e:
                self.logger.warning(f"[HOTKEYS] Не удалось зарегистрировать F3: {e}")

            # ============================================================
            # Регистрируем F5 отдельно (аналогично F3)
            # ============================================================
            try:
                # НЕ вызываем keyboard.unhook_key('f5') — это вызывает ошибку!
                keyboard.on_press_key('f5', self._on_f5_down, suppress=True)
                keyboard.on_release_key('f5', self._on_f5_up, suppress=True)
                self.logger.info("[HOTKEYS] Зарегистрировано: F5 (блокировка)")
            except Exception as e:
                self.logger.warning(f"[HOTKEYS] Не удалось зарегистрировать F5: {e}")

            self._hotkey_hook_active = True
            self.logger.info("[HOTKEYS] Горячие клавиши зарегистрированы (все с блокировкой)")

        except Exception as e:
            self.logger.error(f"[HOTKEYS] Ошибка регистрации: {e}")

    def _on_f3_down(self, event):
        """Обработчик нажатия F3"""
        if self._hotkeys_blocked:
            return

        self.logger.info("[HOTKEYS] F3 нажата (down)")
        self._f3_down_time = time.time()
        self._f3_hold_triggered = False

        # Отменяем старый таймер
        if self._f3_timer:
            try:
                if hasattr(self.app, 'root') and self.app.root:
                    self.app.root.after_cancel(self._f3_timer)
                    self.logger.info("[HOTKEYS] Старый таймер F3 отменён")
            except Exception as e:
                self.logger.warning(f"[HOTKEYS] Ошибка отмены таймера: {e}")
            self._f3_timer = None

        # Запускаем новый таймер
        if hasattr(self.app, 'root') and self.app.root:
            self._f3_timer = self.app.root.after(
                self.HOLD_THRESHOLD_MS,
                self._on_f3_hold
            )
            self.logger.info(f"[HOTKEYS] Таймер F3 запущен на {self.HOLD_THRESHOLD_MS}мс")

    def _on_f3_up(self, event):
        """Обработчик отпускания F3"""
        if self._hotkeys_blocked:
            return

        self.logger.info("[HOTKEYS] F3 отпущена (up)")

        # Отменяем таймер
        if self._f3_timer:
            try:
                if hasattr(self.app, 'root') and self.app.root:
                    self.app.root.after_cancel(self._f3_timer)
                    self.logger.info("[HOTKEYS] Таймер F3 отменён (клавиша отпущена)")
            except Exception as e:
                self.logger.warning(f"[HOTKEYS] Ошибка отмены таймера: {e}")
            self._f3_timer = None

        # Если длительное зажатие НЕ сработало - выполняем обычное F3
        if not self._f3_hold_triggered:
            if self._f3_down_time > 0:
                elapsed_ms = (time.time() - self._f3_down_time) * 1000
                self.logger.info(f"[HOTKEYS] Время удержания F3: {elapsed_ms:.0f}мс")
                if elapsed_ms > 50 and elapsed_ms < self.HOLD_THRESHOLD_MS:
                    self.logger.info("[HOTKEYS] Короткое нажатие F3 -> area")
                    self._queue_action('area')
                elif elapsed_ms >= self.HOLD_THRESHOLD_MS:
                    # Если таймер не сработал, но время удержания больше порога
                    self.logger.info("[HOTKEYS] Длительное удержание F3 (таймер не сработал) -> fullscreen_ocr")
                    self._queue_action('fullscreen_ocr')
                self._f3_down_time = 0
        else:
            self.logger.info("[HOTKEYS] Длительное зажатие уже сработало, пропускаем")
            self._f3_down_time = 0

    def _on_f3_hold(self):
        """Обработчик длительного зажатия F3"""
        self.logger.info("[HOTKEYS] ⏰ Длительное зажатие F3 (500мс) -> fullscreen_ocr")
        self._f3_hold_triggered = True
        self._f3_timer = None
        self._f3_down_time = 0
        self._queue_action('fullscreen_ocr')

    def _queue_action(self, action):
        """Ставит действие в очередь для выполнения в главном потоке"""
        if self._hotkeys_blocked:
            self.logger.info(f"[HOTKEYS] Действие {action} заблокировано (hotkeys_blocked=True)")
            return

        current_time = time.time() * 1000
        if current_time - self._key_last_time.get(action, 0) < self._debounce_ms:
            return
        self._key_last_time[action] = current_time

        self._action_queue.append(action)

        if not self._processing_queue:
            self._process_queue()

    def _process_queue(self):
        """Обрабатывает очередь действий в главном потоке"""
        if self._processing_queue:
            return

        self._processing_queue = True

        def process():
            try:
                actions_to_process = []
                while self._action_queue:
                    actions_to_process.append(self._action_queue.pop(0))

                if not actions_to_process:
                    return

                for action in actions_to_process:
                    self.logger.info(f"[HOTKEYS] ВЫПОЛНЕНИЕ: {action}")
                    self._execute_action(action)

            finally:
                self._processing_queue = False

        if hasattr(self.app, 'root') and self.app.root:
            self.app.root.after(0, process)
        else:
            import threading
            threading.Thread(target=process, daemon=True).start()

    def _execute_action(self, action):
        """Выполняет действие по горячей клавише"""
        self.logger.info(f"[HOTKEYS] ВЫПОЛНЕНИЕ: {action}")
        if action == 'toggle_overlay':
            self.app.toggle_overlay()
        elif action == 'screenshot':
            self.app.process()
        elif action == 'area':
            self.app.capture_area()
        elif action == 'fullscreen_ocr':
            self.app.process_fullscreen_with_ocr()
        elif action == 'clear_all':
            self.app.clear_all_overlays()
        elif action == 'edit_mode':
            self.app.toggle_edit_mode()
        elif action == 'auto_replace':
            self.app.toggle_auto_replace_mode()
        else:
            self.logger.warning(f"[HOTKEYS] Неизвестное действие: {action}")

    def set_actions_blocked(self, blocked):
        """Блокирует/разблокирует выполнение действий горячих клавиш"""
        self._hotkeys_blocked = blocked
        if blocked:
            self.logger.info("[HOTKEYS] Горячие клавиши заблокированы")
            # Дополнительная блокировка через keyboard
            try:
                import keyboard
                keyboard.block_key('f4')
                keyboard.block_key('f1')
                keyboard.block_key('f2')
                keyboard.block_key('f3')
                keyboard.block_key('f5')
                keyboard.block_key('f6')
                # НЕ БЛОКИРУЕМ ESC
                # keyboard.block_key('esc')
            except Exception as e:
                self.logger.warning(f"[HOTKEYS] Не удалось заблокировать клавиши: {e}")
        else:
            self.logger.info("[HOTKEYS] Горячие клавиши разблокированы")
            try:
                import keyboard
                keyboard.unblock_key('f4')
                keyboard.unblock_key('f1')
                keyboard.unblock_key('f2')
                keyboard.unblock_key('f3')
                keyboard.unblock_key('f5')
                keyboard.unblock_key('f6')
                # keyboard.unblock_key('esc')
            except:
                pass

    def cleanup(self):
        """Очищает все хуки"""
        try:
            keyboard.unhook_all()
            self._hotkey_hook_active = False
            self._action_queue.clear()
            self._processing_queue = False
            self.logger.info("[HOTKEYS] Все хуки очищены")
        except Exception as e:
            self.logger.error(f"[HOTKEYS] Ошибка очистки: {e}")
