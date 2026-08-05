"""
Управление горячими клавишами
"""

import logging
import time
import keyboard


class HotkeyManager:
    """Управляет глобальными горячими клавишами (оптимизированная версия)"""

    __slots__ = (
        'app', 'logger', 'settings', '_key_last_time', '_debounce_ms',
        '_hotkey_hook_active', '_hotkeys_blocked', '_pressed_keys',
        '_hotkey_actions', '_single_keys', '_combinations', '_action_queue',
        '_processing_queue', '_block_callback', '_block_hook_active',
        '_blocked_keys', '_permanently_blocked'
    )

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.settings = app.settings

        self._key_last_time = {}
        self._debounce_ms = 300  # Уменьшено с 500 до 300
        self._hotkey_hook_active = False
        self._hotkeys_blocked = False
        self._pressed_keys = set()
        self._hotkey_actions = {}
        self._single_keys = []
        self._combinations = {}
        self._action_queue = []
        self._processing_queue = False
        self._block_callback = None
        self._block_hook_active = False
        self._blocked_keys = []
        self._permanently_blocked = ['f1', 'f2', 'f3', 'f4', 'f5', 'f6']

    def setup(self):
        """Настраивает горячие клавиши через низкоуровневый хук (оптимизированная версия)"""
        self.logger.info("=" * 60)
        self.logger.info("[HOTKEYS] НАСТРОЙКА ГОРЯЧИХ КЛАВИШ (оптимизированная)")
        self.logger.info("=" * 60)

        try:
            import keyboard

            keyboard.unhook_all()
            self.logger.info("[HOTKEYS] Старые хуки отключены")

            self._hotkey_actions = self.settings.get_all_hotkeys()
            self._single_keys = []
            self._combinations = {}

            for action, hotkey in self._hotkey_actions.items():
                if hotkey and '+' in hotkey:
                    self._combinations[action] = hotkey
                elif hotkey:
                    self._single_keys.append(hotkey)

            # Создаем множество для быстрой проверки одиночных клавиш
            single_keys_set = set(self._single_keys)

            # Низкоуровневый хук с оптимизированной обработкой
            def low_level_handler(event):
                if event.event_type not in ('down', 'up'):
                    return True

                key = event.name.lower()
                event_type = event.event_type

                # Блокируем только если не в режиме захвата
                if self._hotkeys_blocked:
                    return True

                # Оптимизация: быстрая проверка одиночных клавиш через set
                if key in single_keys_set:
                    # Находим действие для этой клавиши (кэшируем в словаре)
                    action = None
                    for act, hk in self._hotkey_actions.items():
                        if hk == key:
                            action = act
                            break

                    if action:
                        self._queue_action(action)
                        return False

                # Проверка комбинаций (только для нажатий)
                if event_type == 'down':
                    self._pressed_keys.add(key)

                    # Оптимизация: используем локальные переменные
                    pressed = self._pressed_keys
                    current_pressed = set(pressed)

                    for action, hotkey in self._combinations.items():
                        hotkey_parts = [p.lower().strip() for p in hotkey.split('+') if p.strip()]
                        if not hotkey_parts:
                            continue

                        # Быстрая проверка
                        all_pressed = True
                        for part in hotkey_parts:
                            found = False
                            for pressed_key in current_pressed:
                                if part in pressed_key or pressed_key in part:
                                    found = True
                                    break
                            if not found:
                                all_pressed = False
                                break

                        if all_pressed:
                            self._queue_action(action)
                            self._pressed_keys.clear()
                            return False
                else:
                    self._pressed_keys.discard(key)

                return True

            keyboard.hook(low_level_handler, suppress=True)
            self._hotkey_hook_active = True
            self.logger.info("[HOTKEYS] Низкоуровневый хук установлен")

            self.logger.info(f"[HOTKEYS] Горячие клавиши зарегистрированы: {self._hotkey_actions}")

        except Exception as e:
            self.logger.error(f"[HOTKEYS] Ошибка регистрации: {e}")

    def _queue_action(self, action):
        """Ставит действие в очередь для выполнения в главном потоке (оптимизированная версия)"""
        if self._hotkeys_blocked:
            return

        current_time = time.time() * 1000
        if current_time - self._key_last_time.get(action, 0) < self._debounce_ms:
            return
        self._key_last_time[action] = current_time

        # Добавляем в очередь
        self._action_queue.append(action)

        # Запускаем обработку очереди в главном потоке
        if not self._processing_queue:
            self._process_queue()

    def _process_queue(self):
        """Обрабатывает очередь действий в главном потоке (оптимизированная версия)"""
        if self._processing_queue:
            return

        self._processing_queue = True

        def process():
            try:
                # Обрабатываем все действия в очереди за один раз
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

    def set_actions_blocked(self, blocked):
        """Блокирует/разблокирует выполнение действий горячих клавиш"""
        self._hotkeys_blocked = blocked
        if blocked:
            self.logger.info("[HOTKEYS] Выполнение действий горячих клавиш заблокировано")
        else:
            self.logger.info("[HOTKEYS] Выполнение действий горячих клавиш разблокировано")

    def _setup_block_hook(self, keys_to_block):
        """Устанавливает дополнительный хук для подавления клавиш"""
        try:
            import keyboard

            if self._block_hook_active:
                keyboard.unhook(self._block_callback)
                self._block_hook_active = False

            def block_callback(event):
                if event.event_type in ('down', 'up'):
                    key = event.name.lower()
                    if key in keys_to_block:
                        self.logger.debug(f"[HOTKEYS] Подавление клавиши: {key}")
                        return False
                return True

            keyboard.hook(block_callback, suppress=True)
            self._block_callback = block_callback
            self._block_hook_active = True
            self.logger.info(f"[HOTKEYS] Дополнительный хук подавления установлен для {len(keys_to_block)} клавиш")

        except Exception as e:
            self.logger.warning(f"[HOTKEYS] Не удалось установить дополнительный хук: {e}")

    def _unblock_keys(self):
        """Разблокирует дополнительные клавиши (постоянно заблокированные остаются)"""
        try:
            import keyboard
            for key in self._blocked_keys:
                try:
                    keyboard.unblock_key(key)
                    self.logger.info(f"[HOTKEYS] Разблокировка клавиши: {key}")
                except Exception as e:
                    self.logger.warning(f"[HOTKEYS] Не удалось разблокировать {key}: {e}")
            self._blocked_keys = []

            self.logger.info(f"[HOTKEYS] Постоянно заблокированы: {self._permanently_blocked}")
        except Exception as e:
            self.logger.error(f"[HOTKEYS] Ошибка разблокировки клавиш: {e}")

    def _block_keys(self):
        """Блокирует дополнительные клавиши (кроме постоянно заблокированных)"""
        try:
            import keyboard
            self._blocked_keys = []
            all_keys = set()

            for action, hotkey in self._hotkey_actions.items():
                if hotkey:
                    parts = hotkey.split('+')
                    for part in parts:
                        key = part.strip().lower()
                        if key in self._permanently_blocked:
                            continue
                        if key and key not in all_keys:
                            all_keys.add(key)
                            try:
                                keyboard.block_key(key)
                                self._blocked_keys.append(key)
                                self.logger.info(f"[HOTKEYS] Блокировка клавиши: {key}")
                            except Exception as e:
                                self.logger.warning(f"[HOTKEYS] Не удалось заблокировать {key}: {e}")

            self.logger.info(f"[HOTKEYS] Заблокировано дополнительно {len(self._blocked_keys)} клавиш")
        except Exception as e:
            self.logger.error(f"[HOTKEYS] Ошибка блокировки клавиш: {e}")

    def cleanup(self):
        """Очищает все хуки"""
        try:
            import keyboard
            keyboard.unhook_all()
            self._hotkey_hook_active = False
            self._action_queue.clear()
            self._processing_queue = False
            self.logger.info("[HOTKEYS] Все хуки очищены")
        except Exception as e:
            self.logger.error(f"[HOTKEYS] Ошибка очистки: {e}")

    def _execute_action(self, action):
        """Выполняет действие по горячей клавише"""
        self.logger.info(f"[HOTKEYS] ВЫПОЛНЕНИЕ: {action}")
        if action == 'toggle_overlay':
            self.app.toggle_overlay()
        elif action == 'screenshot':
            self.app.process()
        elif action == 'area':
            self.app.capture_area()
        elif action == 'clear_all':
            self.app.clear_all_overlays()
        elif action == 'edit_mode':
            self.app.toggle_edit_mode()
        elif action == 'auto_replace':
            self.app.toggle_auto_replace_mode()
        else:
            self.logger.warning(f"[HOTKEYS] Неизвестное действие: {action}")
