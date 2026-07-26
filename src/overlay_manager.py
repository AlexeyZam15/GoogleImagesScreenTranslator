"""
Модуль для управления множественными оверлейными окнами.
"""

import logging
import keyboard
from pathlib import Path
from typing import Optional, List, Dict, Tuple

from src.overlay import OverlayWindow


class OverlayManager:
    """Управляет списком оверлеев."""

    def __init__(self, parent):
        self.logger = logging.getLogger(__name__)
        self.parent = parent
        self.overlays: List[OverlayWindow] = []
        self._is_dragging_any = False
        self._show_all_sync_pending = False
        self._show_all_sync_timer = None
        self._esc_hook_active = False
        self.logger.info("OverlayManager инициализирован")

    def _global_esc_handler(self, event):
        """Глобальный обработчик ESC - отменяет перевод или скрывает оверлеи."""
        self.logger.info("[DEBUG] ESC нажат - проверка состояния перевода")

        # Проверяем, идет ли перевод
        if hasattr(self.parent, '_translation_in_progress') and self.parent._translation_in_progress:
            self.logger.info("[DEBUG] ESC: обнаружен активный перевод - отменяем")
            if hasattr(self.parent, '_cancel_translation'):
                self.parent._cancel_translation()
            return False

        # Если перевода нет - скрываем все оверлеи
        self.logger.info("[DEBUG] ESC: перевода нет - скрываем все оверлеи")
        self.hide_all_overlays()

        # Возвращаем фокус на целевое окно (последнего оверлея)
        if self.overlays:
            last_overlay = self.overlays[-1]
            if last_overlay._target_hwnd:
                try:
                    import win32gui
                    win32gui.SetForegroundWindow(last_overlay._target_hwnd)
                    self.logger.info(f"[DEBUG] Фокус возвращен на целевое окно: {last_overlay._target_hwnd}")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Не удалось вернуть фокус: {e}")

        return False

    def _enable_esc_hook(self):
        """Включает глобальный хук ESC."""
        if not self._esc_hook_active:
            try:
                keyboard.on_press_key('esc', self._global_esc_handler)
                self._esc_hook_active = True
                self.logger.info("Глобальный хук ESC включен (OverlayManager)")
            except Exception as e:
                self.logger.warning(f"Не удалось включить глобальный хук ESC: {e}")

    def _disable_esc_hook(self):
        """Отключает глобальный хук ESC."""
        if self._esc_hook_active:
            try:
                keyboard.unhook_key('esc')
                self._esc_hook_active = False
                self.logger.info("Глобальный хук ESC отключен (OverlayManager)")
            except Exception as e:
                self.logger.warning(f"Не удалось отключить глобальный хук ESC: {e}")

    def create_overlay(self, image_path: Path, window_rect: tuple,
                       target_hwnd: int = None, is_fullscreen: bool = None,
                       show_immediately: bool = True) -> Optional[OverlayWindow]:
        """
        Создает новый оверлей на основе переданных данных.
        """
        self.logger.info(f"Создание нового оверлея: image_path={image_path}")

        auto_hide_enabled = False
        if hasattr(self.parent, 'settings') and self.parent.settings:
            auto_hide_enabled = self.parent.settings.get_auto_hide_overlay()

        new_overlay = OverlayWindow(
            parent=self.parent.root,
            app_title=self.parent.app_title if hasattr(self.parent, 'app_title') else "Перевод скриншотов",
            auto_hide_enabled=auto_hide_enabled
        )

        # Отключаем собственный хук ESC у оверлея - используем менеджер
        new_overlay._use_manager_esc = True

        # Передаем управление видимостью и автоскрытием OverlayManager
        new_overlay._overlay_manager = self
        new_overlay.show_for_window(
            image_path, window_rect, target_hwnd, is_fullscreen, show_immediately
        )

        # Включаем глобальный хук ESC через менеджер
        self._enable_esc_hook()

        self.overlays.append(new_overlay)
        self.logger.info(f"Оверлей создан. Всего активных оверлеев: {len(self.overlays)}")
        return new_overlay

    def hide_all_overlays(self):
        """Скрывает все оверлеи, но НЕ УДАЛЯЕТ их из списка."""
        self.logger.info(f"Скрытие всех {len(self.overlays)} оверлеев")
        for overlay in self.overlays:
            try:
                overlay.hide()
            except Exception as e:
                self.logger.error(f"Ошибка при скрытии оверлея: {e}")

    def close_all(self):
        """Закрывает все оверлеи."""
        self.logger.info(f"Закрытие всех оверлеев. Количество: {len(self.overlays)}")
        self._disable_esc_hook()
        for overlay in self.overlays:
            try:
                overlay.close()
            except Exception as e:
                self.logger.error(f"Ошибка при закрытии оверлея: {e}")
        self.overlays.clear()
        self.logger.info("Все оверлеи закрыты.")

    def show_all_sync(self):
        """Показывает все оверлеи синхронно, без мигания."""
        # Защита от множественных вызовов
        if self._show_all_sync_pending:
            self.logger.info("[DEBUG] show_all_sync уже запланирован, пропускаем")
            return

        self._show_all_sync_pending = True
        self.logger.info(f"[DEBUG] Запланирован синхронный показ всех {len(self.overlays)} оверлеев")

        # Откладываем показ на 50мс, чтобы собрать все события
        if self._show_all_sync_timer:
            try:
                if hasattr(self.parent, 'root') and self.parent.root.winfo_exists():
                    self.parent.root.after_cancel(self._show_all_sync_timer)
            except:
                pass
            self._show_all_sync_timer = None

        def do_show_all():
            self._show_all_sync_pending = False
            self._show_all_sync_timer = None
            self._show_all_sync_impl()

        if hasattr(self.parent, 'root') and self.parent.root.winfo_exists():
            self._show_all_sync_timer = self.parent.root.after(50, do_show_all)
        else:
            # Если нет root - выполняем сразу
            self._show_all_sync_pending = False
            self._show_all_sync_impl()

    def _show_all_sync_impl(self):
        """Реальная реализация синхронного показа."""
        self.logger.info(f"[DEBUG] Синхронный показ всех {len(self.overlays)} оверлеев")

        # Сначала собираем все данные о оверлеях
        windows_to_show = []
        windows_to_load = []

        for overlay in self.overlays:
            try:
                if overlay is None:
                    continue

                # Если оверлей уже виден - пропускаем
                if overlay.visible:
                    self.logger.info(f"[DEBUG] Оверлей уже виден, пропускаем")
                    continue

                if overlay._image_loaded and overlay.tk_image is not None:
                    # Изображение уже загружено - показываем
                    windows_to_show.append(overlay)
                elif overlay._last_image_path and overlay._last_window_rect:
                    # Изображение не загружено - загружаем
                    windows_to_load.append(overlay)
            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка при сборе данных оверлея: {e}")

        # --- ШАГ 1: Загружаем изображения для всех оверлеев, которым это нужно ---
        for overlay in windows_to_load:
            try:
                self.logger.info(f"[DEBUG] Загружаем изображение для оверлея")
                overlay._load_and_show_image(overlay._last_image_path, overlay._last_window_rect)
                overlay._image_loaded = True
            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка при загрузке изображения: {e}")

        # --- ШАГ 2: ПОКАЗЫВАЕМ ВСЕ ОВЕРЛЕИ ОДНОВРЕМЕННО ---
        # Сначала обновляем все окна
        for overlay in windows_to_show + windows_to_load:
            try:
                if not overlay.visible:
                    overlay.root.deiconify()
                    overlay.root.lift()
                    overlay.visible = True
                    overlay._enable_esc_hook()

                    # Восстанавливаем сохраненную позицию
                    if overlay._saved_position:
                        x, y = overlay._saved_position
                        current_x = overlay.root.winfo_x()
                        current_y = overlay.root.winfo_y()
                        if abs(current_x - x) > 5 or abs(current_y - y) > 5:
                            overlay.root.geometry(f"+{x}+{y}")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка при показе оверлея: {e}")

        self.logger.info(
            f"[DEBUG] Синхронный показ завершен, показано {len(windows_to_show) + len(windows_to_load)} оверлеев")

    def set_dragging(self, dragging: bool):
        """Устанавливает глобальный флаг перетаскивания для всех оверлеев."""
        self._is_dragging_any = dragging
        self.logger.info(f"[DEBUG] Глобальный флаг перетаскивания установлен: {dragging}")

    def is_dragging(self) -> bool:
        """Возвращает состояние глобального флага перетаскивания."""
        return self._is_dragging_any

    def _get_overlay_position_file(self) -> Path:
        """Возвращает путь к файлу с сохраненными позициями оверлеев."""
        import json
        from pathlib import Path
        # Используем ту же директорию, что и для других настроек
        config_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "overlay_positions.json"

    def _load_overlay_positions(self) -> dict:
        """Загружает сохраненные позиции оверлеев из файла."""
        import json
        pos_file = self._get_overlay_position_file()
        if pos_file.exists():
            try:
                with open(pos_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                self.logger.error(f"Ошибка загрузки позиций оверлеев: {e}")
        return {}

    def _save_overlay_position(self, overlay_id: str, x: int, y: int):
        """Сохраняет позицию конкретного оверлея в файл."""
        import json
        positions = self._load_overlay_positions()
        positions[overlay_id] = {'x': x, 'y': y}
        pos_file = self._get_overlay_position_file()
        try:
            with open(pos_file, 'w', encoding='utf-8') as f:
                json.dump(positions, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.logger.error(f"Ошибка сохранения позиции оверлея: {e}")

    def toggle_all_overlays(self):
        """Переключает видимость всех оверлеев одновременно."""
        if not self.overlays:
            self.logger.warning("Нет оверлеев для переключения.")
            return False

        # Проверяем, виден ли первый оверлей
        first_visible = False
        for overlay in self.overlays:
            if overlay.is_visible():
                first_visible = True
                break

        new_state = not first_visible

        self.logger.info(
            f"Переключение всех {len(self.overlays)} оверлеев в состояние: {'показаны' if new_state else 'скрыты'}")

        for overlay in self.overlays:
            try:
                if new_state:
                    overlay.show()
                else:
                    overlay.hide()
            except Exception as e:
                self.logger.error(f"Ошибка при переключении оверлея: {e}")

        self.logger.info(f"Все {len(self.overlays)} оверлеев {'показаны' if new_state else 'скрыты'}")
        return new_state

    def show_all_overlays(self):
        """Показывает все оверлеи."""
        self.logger.info(f"Показ всех {len(self.overlays)} оверлеев")
        for overlay in self.overlays:
            try:
                overlay.show()
            except Exception as e:
                self.logger.error(f"Ошибка при показе оверлея: {e}")

    def show_last_overlay(self):
        """Показывает последний созданный оверлей."""
        if not self.overlays:
            self.logger.warning("Нет оверлеев для отображения.")
            return

        last_overlay = self.overlays[-1]
        if last_overlay.is_visible():
            self.logger.info("Последний оверлей уже виден.")
            return

        self.logger.info("Показ последнего оверлея.")
        last_overlay.show()

    def hide_last_overlay(self):
        """Скрывает последний созданный оверлей."""
        if not self.overlays:
            self.logger.warning("Нет оверлеев для скрытия.")
            return

        last_overlay = self.overlays[-1]
        if not last_overlay.is_visible():
            self.logger.info("Последний оверлей уже скрыт.")
            return

        self.logger.info("Скрытие последнего оверлея.")
        last_overlay.hide()

    def toggle_last_overlay(self):
        """Переключает видимость последнего созданного оверлея."""
        if not self.overlays:
            self.logger.warning("Нет оверлеев для переключения.")
            return

        last_overlay = self.overlays[-1]
        self.logger.info("Переключение видимости последнего оверлея.")
        last_overlay.toggle()

    def get_last_overlay_hwnd(self) -> Optional[int]:
        """Возвращает HWND последнего созданного оверлея."""
        if not self.overlays:
            return None
        return self.overlays[-1].get_overlay_hwnd()

    def get_last_overlay(self) -> Optional[OverlayWindow]:
        """Возвращает последний созданный оверлей."""
        if not self.overlays:
            return None
        return self.overlays[-1]

    def is_last_overlay_visible(self) -> bool:
        """Проверяет, виден ли последний оверлей."""
        if not self.overlays:
            return False
        return self.overlays[-1].is_visible()

    def set_auto_hide_for_all(self, enabled: bool):
        """Устанавливает режим автоскрытия для всех оверлеев."""
        self.logger.info(f"Установка режима автоскрытия для всех оверлеев: {enabled}")
        for overlay in self.overlays:
            try:
                overlay.set_auto_hide(enabled)
            except Exception as e:
                self.logger.error(f"Ошибка установки автоскрытия для оверлея: {e}")