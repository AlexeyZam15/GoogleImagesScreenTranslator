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
        """Обновляет список окон с оверлеями"""
        try:
            self.logger.info("[WINDOW_LIST] Обновление списка окон с оверлеями")

            self.window_listbox.delete(0, 'end')
            self._window_hwnd_map.clear()

            if not self.app.overlay_manager:
                self.logger.info("[WINDOW_LIST] OverlayManager не инициализирован")
                return

            windows_with_overlays = []

            self.logger.info(
                f"[WINDOW_LIST] overlays_by_hwnd: {list(self.app.overlay_manager.overlays_by_hwnd.keys())}")
            self.logger.info(f"[WINDOW_LIST] Всего оверлеев: {len(self.app.overlay_manager.overlays)}")

            for hwnd, overlays in self.app.overlay_manager.overlays_by_hwnd.items():
                self.logger.info(f"[WINDOW_LIST] Проверка HWND={hwnd}, оверлеев={len(overlays)}")

                # Проверяем, что HWND валидный
                if not win32gui.IsWindow(hwnd):
                    self.logger.info(f"[WINDOW_LIST] HWND={hwnd} не является валидным окном, пропускаем")
                    continue

                # Проверяем наличие оверлеев (не только видимых!)
                if overlays:
                    # Проверяем хотя бы один оверлей на существование окна
                    overlay_exists = False
                    for overlay in overlays:
                        try:
                            if overlay.root and overlay.root.winfo_exists():
                                overlay_exists = True
                                break
                        except Exception as e:
                            self.logger.warning(f"[WINDOW_LIST] Ошибка проверки существования оверлея: {e}")

                    if overlay_exists:
                        # Пытаемся получить сохраненное имя приложения из состояния
                        app_name = self._get_app_name_from_state(hwnd)

                        if app_name:
                            title = app_name
                            self.logger.info(f"[WINDOW_LIST] Для HWND={hwnd} использовано имя из состояния: {title}")
                        else:
                            # Если нет в состоянии - пробуем заголовок окна
                            title = win32gui.GetWindowText(hwnd)

                            # Если заголовок пустой, используем имя процесса
                            if not title or not title.strip():
                                from src.window_utils import get_process_name_by_hwnd
                                title = get_process_name_by_hwnd(hwnd)
                                self.logger.info(f"[WINDOW_LIST] Для HWND={hwnd} использовано имя процесса: {title}")

                        # Считаем сколько оверлеев всего (не только видимых)
                        total_overlays = len(overlays)
                        # Считаем сколько видимых для отображения в скобках
                        visible_overlays = [o for o in overlays if o.visible]
                        visible_count = len(visible_overlays)

                        # Отображаем общее количество оверлеев и сколько из них видимых
                        windows_with_overlays.append((hwnd, title, total_overlays, visible_count))

                    else:
                        self.logger.info(f"[WINDOW_LIST] Оверлеи для HWND={hwnd} не имеют существующих окон")

            if not windows_with_overlays:
                self.logger.info("[WINDOW_LIST] Нет окон с оверлеями")
                return

            windows_with_overlays.sort(key=lambda x: x[1].lower())

            for idx, (hwnd, title, total_count, visible_count) in enumerate(windows_with_overlays):
                # Отображаем общее количество оверлеев и сколько видимых
                if visible_count > 0 and visible_count < total_count:
                    display = f"{title[:33] + '...' if len(title) > 36 else title} ({visible_count}/{total_count})"
                else:
                    display = f"{title[:37] + '...' if len(title) > 40 else title} ({total_count})"
                self.window_listbox.insert('end', display)
                self._window_hwnd_map[idx] = hwnd

            self.logger.info(f"[WINDOW_LIST] Найдено {len(windows_with_overlays)} окон с оверлеями")

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

    def show_overlays_for_selected(self):
        """Показывает оверлеи для выбранного окна"""
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            return
        overlays = self.app.overlay_manager.get_overlays_for_window(hwnd) if self.app.overlay_manager else []
        if not overlays:
            return

        for overlay in overlays:
            try:
                overlay.auto_hide_enabled = False
                overlay._stop_visibility_monitor()
                overlay._is_visible_by_user = True
                overlay._hidden_by_user = False
                overlay._hidden_by_mouse = False
                if not overlay.visible:
                    overlay.show()
                else:
                    overlay.root.lift()
                    overlay.root.attributes('-topmost', True)
            except Exception as e:
                self.logger.warning(f"[WINDOW_LIST] Ошибка показа оверлея: {e}")

    def hide_overlays_for_selected(self):
        """Скрывает оверлеи для выбранного окна"""
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            return
        overlays = self.app.overlay_manager.get_overlays_for_window(hwnd) if self.app.overlay_manager else []
        if not overlays:
            return

        for overlay in overlays:
            try:
                overlay.visible = False
                overlay.root.withdraw()
                overlay.auto_hide_enabled = True
                overlay._is_visible_by_user = False
                overlay._hidden_by_user = True
            except Exception as e:
                self.logger.warning(f"[WINDOW_LIST] Ошибка скрытия оверлея: {e}")

    def remove_overlays_for_selected(self):
        """Удаляет оверлеи для выбранного окна"""
        hwnd = self.get_selected_hwnd()
        if not hwnd:
            return
        overlays = self.app.overlay_manager.get_overlays_for_window(hwnd) if self.app.overlay_manager else []
        if not overlays:
            return

        for overlay in overlays[:]:
            try:
                self.app.overlay_manager.remove_overlay(overlay)
            except Exception as e:
                self.logger.warning(f"[WINDOW_LIST] Ошибка удаления оверлея: {e}")

        self.app.root.after(100, self.refresh)
