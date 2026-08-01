"""
Управление списком окон с оверлеями
"""

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
            for hwnd, overlays in self.app.overlay_manager.overlays_by_hwnd.items():
                if overlays and win32gui.IsWindow(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        windows_with_overlays.append((hwnd, title, len(overlays)))

            if not windows_with_overlays:
                self.logger.info("[WINDOW_LIST] Нет окон с оверлеями")
                return

            windows_with_overlays.sort(key=lambda x: x[1].lower())

            for idx, (hwnd, title, count) in enumerate(windows_with_overlays):
                display = f"{title[:37] + '...' if len(title) > 40 else title} ({count})"
                self.window_listbox.insert('end', display)
                self._window_hwnd_map[idx] = hwnd

            self.logger.info(f"[WINDOW_LIST] Найдено {len(windows_with_overlays)} окон")

        except Exception as e:
            self.logger.error(f"[WINDOW_LIST] Ошибка: {e}")
            self.window_listbox.delete(0, 'end')
            self._window_hwnd_map.clear()

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