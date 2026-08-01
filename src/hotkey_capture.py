"""
Модуль для управления захватом горячих клавиш.
"""

import logging
import time
import tkinter as tk


class HotkeyCaptureManager:
    """Менеджер захвата горячих клавиш."""

    def __init__(self, parent, settings, app=None):
        self.parent = parent
        self.settings = settings
        self.app = app
        self.logger = logging.getLogger(__name__)

        # Состояние захвата
        self.hotkey_buttons = {}
        self.hotkey_vars = {}
        self.hotkey_capturing = {}
        self._first_key = None
        self._main_key = None
        self._first_key_time = 0
        self._capture_action = None

    def _swap_hotkeys_if_conflict(self, action: str, new_combo: str) -> bool:
        """
        Проверяет, занята ли комбинация new_combo другим действием.
        Если занята, меняет местами комбинации.

        Возвращает True, если конфликт был разрешён (или не было конфликта),
        False, если new_combo пустая или невалидная.
        """
        logger = self.logger

        if not new_combo:
            logger.warning("[HOTKEYS] Попытка обмена с пустой комбинацией")
            return False

        # Проверяем, не занята ли комбинация другим действием
        conflicting_action = None
        old_combo = self.hotkey_vars[action].get()

        for a in self.hotkey_vars:
            if a != action and self.hotkey_vars[a].get() == new_combo:
                conflicting_action = a
                break

        logger.info(f"[HOTKEYS] conflicting_action = '{conflicting_action}'")

        if conflicting_action is not None:
            logger.info(f"[HOTKEYS] Комбинация '{new_combo}' уже занята действием '{conflicting_action}'")
            logger.info(f"[HOTKEYS] Меняем местами: {action}={old_combo} <-> {conflicting_action}={new_combo}")

            # 1. Устанавливаем новую комбинацию для action
            self.hotkey_vars[action].set(new_combo)
            self.hotkey_buttons[action].config(text=new_combo.upper(), bg='#4CAF50')
            self.settings.set_hotkey(action, new_combo)
            logger.info(f"[HOTKEYS] Для '{action}' сохранена клавиша '{new_combo}'")

            # 2. Отдаем старую комбинацию конфликтующему действию
            if old_combo:
                self.hotkey_vars[conflicting_action].set(old_combo)
                self.hotkey_buttons[conflicting_action].config(text=old_combo.upper(),
                                                               bg='#2d2d2d')  # <-- ИСПРАВЛЕНО: стандартный цвет
                self.settings.set_hotkey(conflicting_action, old_combo)
                logger.info(f"[HOTKEYS] Для '{conflicting_action}' сохранена клавиша '{old_combo}'")
            else:
                self.hotkey_vars[conflicting_action].set("")
                self.hotkey_buttons[conflicting_action].config(text="—", bg='#2d2d2d')
                self.settings.set_hotkey(conflicting_action, "")
                logger.info(f"[HOTKEYS] Для '{conflicting_action}' клавиша сброшена")

            # Сохраняем настройки
            self.settings.save()
            logger.info(f"[HOTKEYS] ✅ Клавиши поменяны местами и сохранены")
            return True

        else:
            # Конфликта нет, просто назначаем новую комбинацию
            self.hotkey_vars[action].set(new_combo)
            self.hotkey_buttons[action].config(text=new_combo.upper(), bg='#4CAF50')
            self.settings.set_hotkey(action, new_combo)
            self.settings.save()
            logger.info(f"[HOTKEYS] ✅ Назначена комбинация '{new_combo}' для действия '{action}'")
            return True

    def _finish_hotkey_capture(self, action):
        """Завершает захват горячей клавиши."""
        logger = self.logger

        if not self.hotkey_capturing.get(action, False):
            return

        # Проверяем, была ли назначена клавиша
        combo = self.hotkey_vars[action].get()
        logger.info(f"[HOTKEYS] _finish_hotkey_capture: combo='{combo}' для действия '{action}'")

        if not combo or combo == "—" or combo == "":
            old_key = self.settings.get_hotkey(action)
            self.hotkey_vars[action].set(old_key)
            display_text = old_key.upper() if old_key else "—"
            self.hotkey_buttons[action].config(text=display_text, bg='#2d2d2d')
            logger.info(f"[HOTKEYS] Захват отменен, восстановлена клавиша: {old_key}, текст: {display_text}")
        else:
            self.settings.set_hotkey(action, combo)
            display_text = combo.upper()
            self.hotkey_buttons[action].config(text=display_text,
                                               bg='#4CAF50')  # <-- ОСТАВЛЯЕМ ЗЕЛЕНЫЙ ДЛЯ ТЕКУЩЕЙ КНОПКИ
            logger.info(f"[HOTKEYS] Сохранена комбинация '{combo}' для действия '{action}', текст: {display_text}")

        self.hotkey_capturing[action] = False
        self.parent.unbind_all('<Key>')

        if self.app and hasattr(self.app, 'set_actions_blocked'):
            logger.info("[HOTKEYS] Разблокируем действия горячих клавиш")
            self.app.set_actions_blocked(False)

        # Сбрасываем цвет кнопки через 300мс, но сохраняем текст
        def restore_button_color():
            try:
                current_text = self.hotkey_buttons[action].cget('text')
                logger.info(f"[HOTKEYS] restore_button_color: текущий текст='{current_text}'")
                # Если текст пустой или "—", не меняем цвет на зеленый
                if current_text and current_text != "—":
                    self.hotkey_buttons[action].config(bg='#2d2d2d')
                else:
                    self.hotkey_buttons[action].config(bg='#2d2d2d')
            except Exception as e:
                logger.warning(f"[HOTKEYS] Ошибка восстановления цвета: {e}")

        self.parent.after(300, restore_button_color)

        # Сбрасываем состояние
        self._first_key = None
        self._main_key = None
        self._capture_action = None

        logger.info(f"[HOTKEYS] ✅ Захват завершен для действия: {action}")

    def _on_hotkey_key_down(self, event):
        """Обработчик нажатия клавиши для захвата комбинации."""
        logger = self.logger
        action = self._capture_action

        if not self.hotkey_capturing.get(action, False):
            return

        key = event.keysym.lower()
        logger.info(f"[HOTKEYS] Нажата клавиша: {key}")

        # Игнорируем клавиши-модификаторы отдельно
        if key in ['shift', 'control', 'alt', 'win', 'meta', 'super', 'hyper',
                   'alt_l', 'alt_r', 'control_l', 'control_r', 'shift_l', 'shift_r',
                   'caps_lock', 'num_lock', 'scroll_lock']:
            return

        # Игнорируем ESC (используется для отмены)
        if key == 'escape':
            logger.info(f"[HOTKEYS] Нажат ESC - отменяем захват")
            self._cancel_hotkey_capture()
            return

        # Получаем текущие зажатые модификаторы
        import tkinter as tk
        state = event.state
        modifiers = []

        # Проверяем битовые маски модификаторов
        # 0x0001 = Shift, 0x0002 = Caps Lock, 0x0004 = Control, 0x0008 = Alt
        # 0x0010 = Num Lock, 0x0020 = Scroll Lock, 0x0040 = F Lock
        if state & 0x0004:
            modifiers.append('ctrl')
        if state & 0x0001:
            modifiers.append('shift')
        if state & 0x0008:
            modifiers.append('alt')
        if state & 0x0040:
            modifiers.append('win')

        # Собираем комбинацию
        combo_parts = modifiers + [key]
        combo = '+'.join(combo_parts)

        logger.info(f"[HOTKEYS] Сформирована комбинация: {combo}")

        # Вызываем универсальный метод для проверки и обмена
        self._swap_hotkeys_if_conflict(action, combo)

        self._finish_hotkey_capture(action)

    def _finish_single_key(self, action):
        """Завершает захват одиночной клавиши (если пользователь нажал и отпустил)."""
        logger = self.logger

        if self._first_key is None:
            return

        key = self._first_key
        logger.info(f"[HOTKEYS] Назначаем одиночную клавишу: {key}")

        normalized = key

        # Вызываем универсальный метод для проверки и обмена
        self._swap_hotkeys_if_conflict(action, normalized)

        self._finish_hotkey_capture(action)

    def set_hotkey_buttons(self, hotkey_buttons, hotkey_vars):
        """Устанавливает ссылки на кнопки и переменные."""
        self.hotkey_buttons = hotkey_buttons
        self.hotkey_vars = hotkey_vars

    def start_hotkey_capture(self, action):
        """Начинает захват клавиши для переназначения."""
        logger = self.logger
        logger.info("[HOTKEYS] ===== НАЧАЛО ЗАХВАТА КЛАВИШИ =====")
        logger.info(f"[HOTKEYS] Действие: {action}")

        # Принудительно сбрасываем все захваты
        for a in list(self.hotkey_capturing.keys()):
            if self.hotkey_capturing.get(a, False):
                logger.info(f"[HOTKEYS] Принудительно отменяем захват для: {a}")
                self.hotkey_capturing[a] = False
                try:
                    self.hotkey_buttons[a].config(bg='#2d2d2d', text=self.hotkey_vars[a].get().upper() or "—")
                except:
                    pass

        # Отвязываем старые обработчики
        try:
            self.parent.unbind_all('<Key>')
            self.parent.unbind_all('<KeyRelease>')
        except:
            pass

        # Устанавливаем флаг захвата
        self.hotkey_capturing[action] = True

        # Меняем цвет кнопки
        btn = self.hotkey_buttons.get(action)
        if btn:
            btn.config(bg='#FF6B00', text="Нажмите клавишу...")
            btn.update_idletasks()
            logger.info(f"[HOTKEYS] Кнопка для {action} переключена в режим захвата")
        else:
            logger.error(f"[HOTKEYS] Кнопка для {action} не найдена!")
            self.hotkey_capturing[action] = False
            return

        # Блокируем действия горячих клавиш
        if self.app and hasattr(self.app, 'set_actions_blocked'):
            logger.info("[HOTKEYS] Блокируем действия горячих клавиш")
            self.app.set_actions_blocked(True)

        # Устанавливаем фокус
        self.parent.focus_force()
        self.parent.lift()
        self.parent.attributes('-topmost', True)
        self.parent.update_idletasks()

        # Сбрасываем состояние захвата
        self._first_key = None
        self._main_key = None
        self._first_key_time = 0
        self._capture_action = action

        # Привязываем обработчики
        self.parent.bind_all('<Key>', self._on_hotkey_key_down)
        self.parent.bind_all('<KeyRelease>', self._on_hotkey_key_up)
        logger.info(f"[HOTKEYS] Обработчики клавиш привязаны для действия: {action}")
        logger.info("[HOTKEYS] ===== ЗАХВАТ КЛАВИШИ НАЧАТ ======")

    def _on_hotkey_key_up(self, event):
        """Обработчик отпускания клавиши."""
        logger = self.logger
        action = self._capture_action

        if not self.hotkey_capturing.get(action, False):
            return

        key = event.keysym.lower()
        logger.info(f"[HOTKEYS] Отпущена клавиша: {key}")

        if key == self._first_key and self._main_key is None:
            elapsed = time.time() - self._first_key_time
            if elapsed < 0.3:
                logger.info(f"[HOTKEYS] Короткое нажатие ({elapsed:.2f}с) - назначаем одиночную клавишу")
                self._finish_single_key(action)
            else:
                logger.info(f"[HOTKEYS] Долгое нажатие ({elapsed:.2f}с) - ждём вторую клавишу")

        if key == 'escape':
            logger.info(f"[HOTKEYS] Нажат ESC — отменяем захват")
            self._cancel_hotkey_capture()

    def _apply_combo(self, action):
        """Применяет комбинацию клавиш."""
        logger = self.logger

        combo_parts = [self._first_key, self._main_key]

        normalized_parts = []
        for part in combo_parts:
            if 'control' in part or 'ctrl' in part:
                normalized_parts.append('ctrl')
            elif 'shift' in part:
                normalized_parts.append('shift')
            elif 'alt' in part:
                normalized_parts.append('alt')
            elif 'win' in part or 'meta' in part:
                normalized_parts.append('win')
            else:
                normalized_parts.append(part)

        normalized_parts = list(dict.fromkeys(normalized_parts))
        combo = '+'.join(normalized_parts)

        logger.info(f"[HOTKEYS] Сформирована комбинация: {combo}")

        # Проверяем конфликты
        conflicting_action = None
        old_combo = self.hotkey_vars[action].get()
        logger.info(f"[HOTKEYS] old_combo для '{action}' = '{old_combo}'")

        for a in self.hotkey_vars:
            if a != action and self.hotkey_vars[a].get() == combo:
                conflicting_action = a
                break

        logger.info(f"[HOTKEYS] conflicting_action = '{conflicting_action}'")

        if conflicting_action is not None:
            logger.info(f"[HOTKEYS] Комбинация '{combo}' уже занята действием '{conflicting_action}'")
            logger.info(f"[HOTKEYS] Меняем местами: {action}={old_combo} <-> {conflicting_action}={combo}")

            # Устанавливаем новую комбинацию для action
            self.hotkey_vars[action].set(combo)
            self.hotkey_buttons[action].config(text=combo.upper(), bg='#4CAF50')
            self.settings.set_hotkey(action, combo)
            logger.info(f"[HOTKEYS] Для '{action}' сохранена клавиша '{combo}'")

            # Отдаем старую комбинацию конфликтующему действию
            logger.info(f"[HOTKEYS] old_combo = '{old_combo}', проверяем if old_combo:")
            if old_combo:
                logger.info(f"[HOTKEYS] old_combo не пустой, обновляем '{conflicting_action}'")
                self.hotkey_vars[conflicting_action].set(old_combo)
                self.hotkey_buttons[conflicting_action].config(text=old_combo.upper(), bg='#4CAF50')
                self.settings.set_hotkey(conflicting_action, old_combo)
                logger.info(f"[HOTKEYS] Для '{conflicting_action}' сохранена клавиша '{old_combo}'")
            else:
                logger.info(f"[HOTKEYS] old_combo пустой, сбрасываем '{conflicting_action}'")
                self.hotkey_vars[conflicting_action].set("")
                self.hotkey_buttons[conflicting_action].config(text="—", bg='#2d2d2d')
                self.settings.set_hotkey(conflicting_action, "")
                logger.info(f"[HOTKEYS] Для '{conflicting_action}' клавиша сброшена")

            # Сохраняем настройки
            self.settings.save()
            logger.info(f"[HOTKEYS] ✅ Клавиши поменяны местами и сохранены")
        else:
            self.hotkey_vars[action].set(combo)
            self.hotkey_buttons[action].config(text=combo.upper(), bg='#4CAF50')
            self.settings.set_hotkey(action, combo)
            self.settings.save()
            logger.info(f"[HOTKEYS] ✅ Назначена комбинация '{combo}' для действия '{action}'")

        self._finish_hotkey_capture(action)

    def _cancel_hotkey_capture(self):
        """Отменяет текущий захват горячей клавиши."""
        logger = self.logger
        logger.info("[HOTKEYS] ===== ОТМЕНА ЗАХВАТА КЛАВИШИ =====")

        for action in self.hotkey_capturing:
            if self.hotkey_capturing[action]:
                logger.info(f"[HOTKEYS] Отменяем захват для действия: {action}")
                self.hotkey_capturing[action] = False

                old_key = self.settings.get_hotkey(action)
                self.hotkey_vars[action].set(old_key)
                self.hotkey_buttons[action].config(text=old_key.upper() if old_key else "—", bg='#2d2d2d')

                self.parent.unbind_all('<Key>')

                if self.app and hasattr(self.app, 'set_actions_blocked'):
                    logger.info("[HOTKEYS] Разблокируем действия горячих клавиш")
                    self.app.set_actions_blocked(False)

                self._first_key = None
                self._main_key = None
                self._capture_action = None

                logger.info(f"[HOTKEYS] ✅ Захват отменен для действия: {action}")
                break

        logger.info("[HOTKEYS] ===== ОТМЕНА ЗАХВАТА ЗАВЕРШЕНА =====")

    def get_string(self, key):
        """Возвращает локализованную строку."""
        return self.settings.get_string(key)
