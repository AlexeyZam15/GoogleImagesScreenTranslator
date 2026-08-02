"""

Управление горячими клавишами

"""

import logging
import time
import keyboard


class HotkeyManager:
    """Управляет глобальными горячими клавишами"""

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.settings = app.settings

        self._key_last_time = {}
        self._debounce_ms = 500
        self._hotkey_hook_active = True
        self._actions_blocked = False
        self._pressed_keys = set()
        self._hotkey_actions = {}

    def setup(self):
        """Настраивает горячие клавиши"""
        self.logger.info("=" * 60)
        self.logger.info("[HOTKEYS] НАСТРОЙКА ГОРЯЧИХ КЛАВИШ")
        self.logger.info("=" * 60)

        try:
            keyboard.unhook_all()
            self.logger.info("[HOTKEYS] Старые хуки отключены")

            self._hotkey_actions = self.settings.get_all_hotkeys()
            self.logger.info(f"[HOTKEYS] Назначенные действия: {self._hotkey_actions}")

            single_keys = ['f1', 'f2', 'f3', 'f4', 'f5', 'f6']

            def make_single_handler(action):
                def handler(e):
                    # Проверяем, заблокированы ли действия
                    if self._actions_blocked:
                        self.logger.debug(f"[HOTKEYS] Действие {action} заблокировано")
                        return True

                    current_time = time.time() * 1000
                    if current_time - self._key_last_time.get(action, 0) >= self._debounce_ms:
                        self._key_last_time[action] = current_time
                        self.logger.info(f"[HOTKEYS] ДЕЙСТВИЕ: {action}")
                        self._execute_action(action)
                    return True

                return handler

            for action, hotkey in self._hotkey_actions.items():
                if hotkey in single_keys:
                    keyboard.on_press_key(hotkey, make_single_handler(action), suppress=True)
                    self.logger.info(f"[HOTKEYS] Зарегистрирована клавиша {hotkey} -> {action}")

            # Комбинации клавиш
            combinations = {a: h for a, h in self._hotkey_actions.items() if h not in single_keys}
            if combinations:
                self.logger.info(f"[HOTKEYS] Обнаружены комбинации: {combinations}")
                self._pressed_keys = set()

                def on_combination_key(event):
                    if self._actions_blocked:
                        return True

                    if event.event_type == 'down':
                        self._pressed_keys.add(event.name)
                    elif event.event_type == 'up':
                        self._pressed_keys.discard(event.name)
                        return True

                    if event.event_type == 'down':
                        current_pressed = set(self._pressed_keys)
                        for action, hotkey in combinations.items():
                            hotkey_parts = [p.lower().strip() for p in hotkey.split('+') if p.strip()]
                            if not hotkey_parts:
                                continue

                            # Проверяем, что все части комбинации нажаты
                            all_pressed = True
                            pressed_lower = [p.lower() for p in current_pressed]
                            for part in hotkey_parts:
                                found = False
                                for pressed in pressed_lower:
                                    if part in pressed or pressed in part:
                                        found = True
                                        break
                                if not found:
                                    all_pressed = False
                                    break

                            if all_pressed:
                                current_time = time.time() * 1000
                                combo_key = f"{action}_{hotkey}"
                                if current_time - self._key_last_time.get(combo_key, 0) >= self._debounce_ms:
                                    self._key_last_time[combo_key] = current_time
                                    self.logger.info(f"[HOTKEYS] Комбинация сработала: {action} ({hotkey})")
                                    self._execute_action(action)
                                    self._pressed_keys.clear()
                                    return False
                    return True

                keyboard.hook(on_combination_key, suppress=True)
                self.logger.info("[HOTKEYS] Хук для комбинаций установлен")

            self._hotkey_hook_active = True
            self.logger.info("=" * 60)
            self.logger.info(f"[HOTKEYS] Горячие клавиши зарегистрированы: {self._hotkey_actions}")
            self.logger.info("=" * 60)

        except Exception as e:
            self.logger.error(f"[HOTKEYS] Ошибка регистрации: {e}")

    def _execute_action(self, action):
        """Выполняет действие по горячей клавише"""
        if self._actions_blocked:
            self.logger.info(f"[HOTKEYS] Действие {action} заблокировано")
            return

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

    def set_actions_blocked(self, blocked):
        """Блокирует/разблокирует действия горячих клавиш"""
        self._actions_blocked = blocked
        if blocked:
            self.logger.info("[HOTKEYS] Действия горячих клавиш заблокированы")
        else:
            self.logger.info("[HOTKEYS] Действия горячих клавиш разблокированы")
        # Не пересоздаем хуки, просто меняем флаг

    def cleanup(self):
        """Очищает хуки"""
        try:
            keyboard.unhook_all()
            self._hotkey_hook_active = False
            self.logger.info("[HOTKEYS] Хуки очищены")
        except:
            pass
