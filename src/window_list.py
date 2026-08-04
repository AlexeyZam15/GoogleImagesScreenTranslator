import logging
import win32gui


class WindowListManager:
    """Управляет списком окон и контекстным меню"""

    def __init__(self, app, window_listbox, window_hwnd_map):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.window_listbox = window_listbox
        self._window_hwnd_map = window_hwnd_map

    def refresh(self):
        """Обновляет список окон с оверлеями - показывает все окна из состояния"""
        try:
            self.logger.info("[WINDOW_LIST] Обновление списка окон с оверлеями")

            self.window_listbox.delete(0, 'end')
            self._window_hwnd_map.clear()

            if not self.app.overlay_manager:
                self.logger.info("[WINDOW_LIST] OverlayManager не инициализирован")
                return

            # Получаем состояние оверлеев из файла
            state_file = self.app.overlay_manager._get_overlay_state_file()
            if not state_file.exists():
                self.logger.info("[WINDOW_LIST] Файл состояния не найден")
                return

            import json
            with open(state_file, 'r', encoding='utf-8') as f:
                states = json.load(f)

            if not states:
                self.logger.info("[WINDOW_LIST] Нет сохранённых оверлеев")
                return

            # Группируем оверлеи по HWND с именем приложения
            windows_data = {}  # {hwnd: {'app_name': str, 'overlay_count': int, 'visible_count': int}}

            for key, state in states.items():
                target_hwnd = state.get('target_hwnd')
                app_name = state.get('app_name', 'Неизвестно')
                is_visible = state.get('visible', False)

                if target_hwnd is None:
                    self.logger.warning(f"[WINDOW_LIST] Нет target_hwnd для {key}, пропускаем")
                    continue

                # Проверяем, существует ли окно (для определения видимости)
                is_window_alive = False
                if win32gui.IsWindow(target_hwnd):
                    is_window_alive = True

                if target_hwnd not in windows_data:
                    windows_data[target_hwnd] = {
                        'app_name': app_name,
                        'overlay_count': 0,
                        'visible_count': 0,
                        'is_alive': is_window_alive
                    }

                windows_data[target_hwnd]['overlay_count'] += 1
                if is_visible and is_window_alive:
                    windows_data[target_hwnd]['visible_count'] += 1

            if not windows_data:
                self.logger.info("[WINDOW_LIST] Нет окон с оверлеями")
                return

            # Сортируем по имени приложения
            sorted_windows = sorted(windows_data.items(), key=lambda x: x[1]['app_name'].lower())

            idx = 0
            for hwnd, data in sorted_windows:
                app_name = data['app_name']
                total_count = data['overlay_count']
                visible_count = data['visible_count']
                is_alive = data['is_alive']

                # Формируем отображение
                if is_alive:
                    status_icon = "🟢 "
                else:
                    status_icon = "🔴 "

                if visible_count > 0 and visible_count < total_count:
                    display = f"{status_icon}{app_name[:30] + '...' if len(app_name) > 33 else app_name} ({visible_count}/{total_count})"
                else:
                    display = f"{status_icon}{app_name[:34] + '...' if len(app_name) > 37 else app_name} ({total_count})"

                self.window_listbox.insert('end', display)
                self._window_hwnd_map[idx] = hwnd
                idx += 1

            self.logger.info(
                f"[WINDOW_LIST] Найдено {len(windows_data)} окон с оверлеями (всего оверлеев: {sum(d['overlay_count'] for d in windows_data.values())})")

        except Exception as e:
            self.logger.error(f"[WINDOW_LIST] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self.window_listbox.delete(0, 'end')
            self._window_hwnd_map.clear()

    def _get_app_name_from_state(self, hwnd: int) -> str:
        """Получает сохраненное имя приложения из состояния для указанного HWND."""
        try:
            # Получаем состояние оверлеев из файла
            state_file = self.app.overlay_manager._get_overlay_state_file()
            if not state_file.exists():
                return None

            import json
            with open(state_file, 'r', encoding='utf-8') as f:
                states = json.load(f)

            # Ищем в состоянии оверлей с таким target_hwnd
            for key, state in states.items():
                if state.get('target_hwnd') == hwnd:
                    app_name = state.get('app_name')
                    if app_name:
                        return app_name

            return None
        except Exception as e:
            self.logger.warning(f"[WINDOW_LIST] Ошибка получения имени из состояния: {e}")
            return None

    def get_selected_hwnd(self):
        """Возвращает HWND выбранного окна"""
        selection = self.window_listbox.curselection()
        if not selection:
            return None
        return self._window_hwnd_map.get(selection[0])

    def remove_overlays_for_selected(self):
        """Удаляет оверлеи для выбранного окна (даже если окно закрыто)"""
        self.logger.info("[WINDOW_LIST] === remove_overlays_for_selected НАЧАЛО ===")

        selection = self.window_listbox.curselection()
        self.logger.info(f"[WINDOW_LIST] Выделено: {selection}")

        if not selection:
            self.logger.warning("[WINDOW_LIST] Нет выбранного элемента")
            return

        hwnd = self._window_hwnd_map.get(selection[0])
        self.logger.info(f"[WINDOW_LIST] Получен HWND={hwnd} для индекса {selection[0]}")

        if not hwnd:
            self.logger.warning("[WINDOW_LIST] HWND не найден")
            return

        # Получаем оверлеи для этого HWND из overlay_manager
        overlays = self.app.overlay_manager.get_overlays_for_window(hwnd) if self.app.overlay_manager else []

        # Если в overlay_manager нет оверлеев для этого HWND, пробуем найти их в состоянии
        if not overlays:
            self.logger.info(f"[WINDOW_LIST] Оверлеи для HWND={hwnd} не найдены в overlay_manager, ищем в состоянии...")
            state_file = self.app.overlay_manager._get_overlay_state_file()
            if state_file.exists():
                import json
                with open(state_file, 'r', encoding='utf-8') as f:
                    states = json.load(f)

                # Ищем оверлеи с этим target_hwnd в состоянии
                for key, state in states.items():
                    if state.get('target_hwnd') == hwnd:
                        self.logger.info(f"[WINDOW_LIST] Найден оверлей в состоянии: {key}")
                        # Удаляем из состояния
                        del states[key]
                        break

                # Сохраняем обновлённое состояние
                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(states, f, indent=4, ensure_ascii=False, default=str)

                self.logger.info(f"[WINDOW_LIST] Оверлей для HWND={hwnd} удалён из состояния")

        if not overlays:
            self.logger.info("[WINDOW_LIST] Нет оверлеев для удаления")
            # Обновляем список окон
            self.refresh()
            return

        # Удаляем каждый оверлей
        removed_count = 0
        for overlay in overlays[:]:
            try:
                self.logger.info(f"[WINDOW_LIST] Удаление оверлея: {overlay}")
                self.app.overlay_manager.remove_overlay(overlay)
                removed_count += 1
                self.logger.info(f"[WINDOW_LIST] Оверлей удален (удалено: {removed_count})")
            except Exception as e:
                self.logger.error(f"[WINDOW_LIST] Ошибка удаления оверлея: {e}")
                import traceback
                traceback.print_exc()

        self.logger.info(f"[WINDOW_LIST] Удалено {removed_count} оверлеев")

        # Обновляем список окон
        self.logger.info("[WINDOW_LIST] Обновление списка окон...")
        self.refresh()
        self.logger.info("[WINDOW_LIST] === remove_overlays_for_selected ЗАВЕРШЕН ===")
