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

            # Используем overlays_by_app_name напрямую
            overlays_by_app = self.app.overlay_manager.overlays_by_app_name

            if not overlays_by_app:
                self.logger.info("[WINDOW_LIST] Нет приложений с оверлеями")
                return

            total_overlays = sum(len(overlays) for overlays in overlays_by_app.values())
            self.logger.info(f"[WINDOW_LIST] Всего оверлеев по приложениям: {total_overlays}")

            # Сортируем по имени приложения
            sorted_apps = sorted(overlays_by_app.items(), key=lambda x: x[0].lower())

            idx = 0
            for app_name, overlays in sorted_apps:
                total_count = len(overlays)
                visible_count = sum(1 for ov in overlays if ov.visible)

                # Проверяем, запущено ли приложение
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
                # Для обратной совместимости сохраняем HWND (берем первый попавшийся)
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

        # Получаем оверлеи по имени приложения
        overlays_to_remove = self.app.overlay_manager.get_overlays_by_app_name(
            app_name) if self.app.overlay_manager else []

        if not overlays_to_remove:
            self.logger.info(f"[WINDOW_LIST] Нет оверлеев для приложения {app_name}")
            self.refresh()
            return

        self.logger.info(f"[WINDOW_LIST] Удаление {len(overlays_to_remove)} оверлеев для {app_name}")

        # Останавливаем монитор
        if hasattr(self.app, 'translation_monitor') and self.app.translation_monitor:
            monitor = self.app.translation_monitor
            was_running = monitor.is_running()
            if was_running:
                monitor.stop()
                self.logger.info("[WINDOW_LIST] Монитор остановлен на время удаления")

        # Отключаем сохранение состояния
        if hasattr(self.app.overlay_manager, '_suppress_save'):
            self.app.overlay_manager._suppress_save = True

        # Удаляем все оверлеи
        removed_count = 0
        for overlay in overlays_to_remove[:]:  # Используем копию списка
            try:
                self.app.overlay_manager.remove_overlay(overlay)
                removed_count += 1
            except Exception as e:
                self.logger.error(f"[WINDOW_LIST] Ошибка удаления оверлея: {e}")

        # Включаем сохранение
        if hasattr(self.app.overlay_manager, '_suppress_save'):
            self.app.overlay_manager._suppress_save = False

        # Сохраняем состояние
        if hasattr(self.app.overlay_manager, 'save_overlay_state'):
            self.app.overlay_manager.save_overlay_state(immediate=True)
            self.logger.info("[WINDOW_LIST] Состояние сохранено после удаления всех оверлеев")

        # Перезапускаем монитор
        if hasattr(self.app, 'translation_monitor') and self.app.translation_monitor:
            monitor = self.app.translation_monitor
            if was_running and monitor.templates:
                monitor.start()
                self.logger.info(f"[WINDOW_LIST] Монитор перезапущен, осталось {len(monitor.templates)} шаблонов")

        self.logger.info(f"[WINDOW_LIST] Удалено {removed_count} оверлеев для {app_name}")
        self.refresh()
        self.logger.info("[WINDOW_LIST] === remove_overlays_for_selected ЗАВЕРШЕН ===")
