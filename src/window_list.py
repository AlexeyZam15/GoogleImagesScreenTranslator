import logging
import win32gui
from src.window_utils import get_process_name_by_hwnd


class WindowListManager:
    """Управляет списком окон и контекстным меню"""

    def __init__(self, app, window_listbox, window_hwnd_map):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self.window_listbox = window_listbox
        self._window_hwnd_map = window_hwnd_map
        # Новый словарь для хранения соответствия индекс -> имя приложения
        self._window_app_map = {}

    def refresh(self):
        """Обновляет список окон с оверлеями - группирует по имени приложения"""
        try:
            self.logger.info("[WINDOW_LIST] Обновление списка окон с оверлеями (группировка по имени приложения)")

            self.window_listbox.delete(0, 'end')
            self._window_hwnd_map.clear()
            self._window_app_map.clear()

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

            # Группируем оверлеи по ИМЕНИ ПРИЛОЖЕНИЯ (а не по HWND)
            apps_data = {}  # {app_name: {'hwnds': [hwnd1, hwnd2], 'overlay_count': int, 'visible_count': int}}

            for key, state in states.items():
                target_hwnd = state.get('target_hwnd')
                app_name = state.get('app_name', 'Неизвестно')
                is_visible = state.get('visible', False)

                if target_hwnd is None:
                    self.logger.warning(f"[WINDOW_LIST] Нет target_hwnd для {key}, пропускаем")
                    continue

                # Проверяем, существует ли окно
                is_window_alive = win32gui.IsWindow(target_hwnd) if target_hwnd else False

                # Если имя приложения = "Неизвестно" или окно закрыто - пробуем получить имя заново
                if app_name == 'Неизвестно' or not is_window_alive:
                    try:
                        # Передаём сохранённое имя как default, чтобы не терять его
                        saved_name = app_name if app_name != 'Неизвестно' else None
                        new_app_name = get_process_name_by_hwnd(target_hwnd, default_name=saved_name)
                        if new_app_name and new_app_name != 'Неизвестно':
                            app_name = new_app_name
                            # Обновляем состояние для будущих запусков
                            state['app_name'] = app_name
                    except Exception as e:
                        self.logger.warning(f"[WINDOW_LIST] Ошибка получения имени для HWND {target_hwnd}: {e}")

                if app_name not in apps_data:
                    apps_data[app_name] = {
                        'hwnds': [],
                        'overlay_count': 0,
                        'visible_count': 0,
                        'is_alive': False
                    }

                # Добавляем HWND в список, если его там нет
                if target_hwnd not in apps_data[app_name]['hwnds']:
                    apps_data[app_name]['hwnds'].append(target_hwnd)

                apps_data[app_name]['overlay_count'] += 1
                if is_visible and is_window_alive:
                    apps_data[app_name]['visible_count'] += 1
                if is_window_alive:
                    apps_data[app_name]['is_alive'] = True

            if not apps_data:
                self.logger.info("[WINDOW_LIST] Нет приложений с оверлеями")
                return

            # Сортируем по имени приложения
            sorted_apps = sorted(apps_data.items(), key=lambda x: x[0].lower())

            idx = 0
            for app_name, data in sorted_apps:
                total_count = data['overlay_count']
                visible_count = data['visible_count']
                is_alive = data['is_alive']
                hwnds = data['hwnds']

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
                self._window_hwnd_map[idx] = hwnds[0] if hwnds else None
                self._window_app_map[idx] = app_name
                idx += 1

            self.logger.info(
                f"[WINDOW_LIST] Найдено {len(apps_data)} приложений с оверлеями (всего оверлеев: {sum(d['overlay_count'] for d in apps_data.values())})")

            # Если были обновлены имена в состоянии - сохраняем
            try:
                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(states, f, indent=4, ensure_ascii=False, default=str)
            except Exception as e:
                self.logger.warning(f"[WINDOW_LIST] Не удалось сохранить обновлённые имена: {e}")

        except Exception as e:
            self.logger.error(f"[WINDOW_LIST] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self.window_listbox.delete(0, 'end')
            self._window_hwnd_map.clear()
            self._window_app_map.clear()

    def get_selected_hwnd(self):
        """Возвращает HWND выбранного приложения (первый HWND из списка)"""
        selection = self.window_listbox.curselection()
        if not selection:
            return None
        return self._window_hwnd_map.get(selection[0])

    def get_selected_app_name(self):
        """Возвращает имя приложения выбранного пункта"""
        selection = self.window_listbox.curselection()
        if not selection:
            return None
        return self._window_app_map.get(selection[0])

    def remove_overlays_for_selected(self):
        """Удаляет оверлеи для выбранного приложения (по имени, а не по HWND)"""
        self.logger.info("[WINDOW_LIST] === remove_overlays_for_selected НАЧАЛО ===")

        selection = self.window_listbox.curselection()
        self.logger.info(f"[WINDOW_LIST] Выделено: {selection}")

        if not selection:
            self.logger.warning("[WINDOW_LIST] Нет выбранного элемента")
            return

        app_name = self._window_app_map.get(selection[0])
        self.logger.info(f"[WINDOW_LIST] Получено имя приложения: {app_name} для индекса {selection[0]}")

        if not app_name:
            self.logger.warning("[WINDOW_LIST] Имя приложения не найдено")
            return

        # Получаем все оверлеи из overlay_manager
        overlays = self.app.overlay_manager.overlays if self.app.overlay_manager else []

        if not overlays:
            self.logger.info("[WINDOW_LIST] Нет оверлеев для удаления")
            self.refresh()
            return

        # Фильтруем оверлеи по имени приложения
        overlays_to_remove = []
        for overlay in overlays:
            try:
                target_hwnd = overlay.get_target_hwnd()
                if target_hwnd:
                    overlay_app_name = get_process_name_by_hwnd(target_hwnd)
                    if overlay_app_name == app_name:
                        overlays_to_remove.append(overlay)
            except Exception as e:
                self.logger.warning(f"[WINDOW_LIST] Ошибка получения имени для оверлея: {e}")

        if not overlays_to_remove:
            self.logger.info(f"[WINDOW_LIST] Нет оверлеев для приложения {app_name}")
            self.refresh()
            return

        # Удаляем каждый оверлей
        removed_count = 0
        for overlay in overlays_to_remove:
            try:
                self.logger.info(f"[WINDOW_LIST] Удаление оверлея для {app_name}")
                self.app.overlay_manager.remove_overlay(overlay)
                removed_count += 1
            except Exception as e:
                self.logger.error(f"[WINDOW_LIST] Ошибка удаления оверлея: {e}")

        self.logger.info(f"[WINDOW_LIST] Удалено {removed_count} оверлеев для {app_name}")

        # Обновляем список окон
        self.refresh()
        self.logger.info("[WINDOW_LIST] === remove_overlays_for_selected ЗАВЕРШЕН ===")
