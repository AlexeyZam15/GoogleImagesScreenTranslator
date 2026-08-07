import logging
import json
from pathlib import Path
from typing import Optional  # <-- ДОБАВИТЬ ЭТУ СТРОКУ

# Windows API
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

    def refresh(self, skip_restore: bool = False):
        """Обновляет список окон с оверлеями - группирует по имени приложения"""
        try:
            self.logger.info("[WINDOW_LIST] Обновление списка окон с оверлеями (группировка по имени приложения)")

            if skip_restore:
                self.logger.info("[WINDOW_LIST] Пропускаем восстановление оверлеев (skip_restore=True)")

            self.window_listbox.delete(0, 'end')
            self._window_hwnd_map.clear()
            self._window_app_map.clear()

            if not self.app.overlay_manager:
                self.logger.info("[WINDOW_LIST] OverlayManager не инициализирован")
                return

            overlays_by_app = self.app.overlay_manager.overlays_by_app_name

            if not overlays_by_app:
                self.logger.info("[WINDOW_LIST] Нет приложений с оверлеями")
                return

            total_overlays = sum(len(overlays) for overlays in overlays_by_app.values())
            self.logger.info(f"[WINDOW_LIST] Всего оверлеев по приложениям: {total_overlays}")

            sorted_apps = sorted(overlays_by_app.items(), key=lambda x: x[0].lower())

            idx = 0
            for app_name, overlays in sorted_apps:
                total_count = len(overlays)
                visible_count = sum(1 for ov in overlays if ov.visible)

                is_alive = False
                if app_name != "Неизвестно":
                    try:
                        hwnd = self._find_window_by_app_name(app_name)
                        is_alive = hwnd is not None
                    except:
                        pass

                status_icon = "🟢 " if is_alive else "🔴 "

                if visible_count > 0 and visible_count < total_count:
                    display = f"{status_icon}{app_name[:30] + '...' if len(app_name) > 33 else app_name} ({visible_count}/{total_count})"
                else:
                    display = f"{status_icon}{app_name[:34] + '...' if len(app_name) > 37 else app_name} ({total_count})"

                self.window_listbox.insert('end', display)
                self._window_app_map[idx] = app_name
                if overlays and overlays[0]._target_hwnd:
                    self._window_hwnd_map[idx] = overlays[0]._target_hwnd
                else:
                    self._window_hwnd_map[idx] = None
                idx += 1

                self.logger.info(f"[WINDOW_LIST] Добавлено приложение: {app_name} ({total_count} оверлеев)")

            self.logger.info(
                f"[WINDOW_LIST] Найдено {len(overlays_by_app)} приложений с оверлеями (всего оверлеев: {total_overlays})"
            )

        except Exception as e:
            self.logger.error(f"[WINDOW_LIST] Ошибка: {e}")
            import traceback
            traceback.print_exc()
            self.window_listbox.delete(0, 'end')
            self._window_hwnd_map.clear()
            self._window_app_map.clear()

    def _find_window_by_app_name(self, app_name: str) -> Optional[int]:
        """Находит HWND окна по имени приложения."""
        try:
            import win32gui

            def enum_callback(hwnd, hwnds):
                if win32gui.IsWindowVisible(hwnd):
                    try:
                        from src.window_utils import get_process_name_by_hwnd
                        if get_process_name_by_hwnd(hwnd) == app_name:
                            hwnds.append(hwnd)
                            return False
                    except:
                        pass
                return True

            hwnds = []
            win32gui.EnumWindows(enum_callback, hwnds)
            return hwnds[0] if hwnds else None
        except Exception as e:
            self.logger.warning(f"[WINDOW_LIST] Ошибка поиска окна по имени {app_name}: {e}")
            return None

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
        """Удаляет оверлеи для выбранного приложения (массово, быстро)"""
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

        # Получаем оверлеи по имени приложения
        overlays_to_remove = self.app.overlay_manager.get_overlays_by_app_name(
            app_name) if self.app.overlay_manager else []

        if not overlays_to_remove:
            self.logger.info(f"[WINDOW_LIST] Нет оверлеев для приложения {app_name}")
            self.refresh()
            return

        self.logger.info(f"[WINDOW_LIST] Быстрое удаление {len(overlays_to_remove)} оверлеев для {app_name}")

        # === ИСПОЛЬЗУЕМ МАССОВОЕ УДАЛЕНИЕ ===
        if hasattr(self.app.overlay_manager, 'remove_all_overlays_for_app'):
            self.app.overlay_manager.remove_all_overlays_for_app(app_name, force=True)
        else:
            # Fallback на поштучное удаление
            if hasattr(self.app.overlay_manager, '_suppress_save'):
                self.app.overlay_manager._suppress_save = True

            for overlay in overlays_to_remove[:]:
                try:
                    self.app.overlay_manager.remove_overlay(overlay, force=True)
                except Exception as e:
                    self.logger.error(f"[WINDOW_LIST] Ошибка удаления оверлея: {e}")

            if hasattr(self.app.overlay_manager, '_suppress_save'):
                self.app.overlay_manager._suppress_save = False
                self.app.overlay_manager.save_overlay_state(immediate=True)

        # === УДАЛЯЕМ ВСЕ ЗАПИСИ ДЛЯ ЭТОГО ПРИЛОЖЕНИЯ ИЗ ФАЙЛА СОСТОЯНИЯ ===
        try:
            import json
            from pathlib import Path
            state_file = Path.home() / "Documents" / "GoogleScreenTranslate" / "config" / "overlay_state.json"
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    states = json.load(f)

                keys_to_remove = [key for key in states.keys() if key.startswith(f"{app_name}_")]
                for key in keys_to_remove:
                    del states[key]
                    self.logger.info(f"[WINDOW_LIST] Удалена запись состояния: {key}")

                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(states, f, indent=4, ensure_ascii=False)
                self.logger.info(f"[WINDOW_LIST] Состояние для {app_name} удалено из файла")
        except Exception as e:
            self.logger.warning(f"[WINDOW_LIST] Не удалось обновить файл состояния: {e}")

        # Обновляем список окон
        self.refresh()
        self.logger.info("[WINDOW_LIST] === remove_overlays_for_selected ЗАВЕРШЕН ===")
