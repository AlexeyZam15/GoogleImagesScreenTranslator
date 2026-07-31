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
        self.overlays_by_hwnd = {}  # {hwnd: [overlay1, overlay2]}
        self.overlays = []  # Для обратной совместимости
        self._is_dragging_any = False
        self._show_all_sync_pending = False
        self._show_all_sync_timer = None
        self._esc_hook_active = False
        self._context_menu = None
        self._context_menu_overlay = None
        self._create_context_menu()
        self.logger.info("OverlayManager инициализирован")

    def _global_esc_handler(self, event):
        """Глобальный обработчик ESC - отменяет перевод или скрывает/удаляет оверлей под мышью."""

        # ===== ПРОВЕРКА: АКТИВЕН ЛИ РЕЖИМ ЗАХВАТА ОБЛАСТИ =====
        if self.parent and hasattr(self.parent, '_capture_mode') and self.parent._capture_mode:
            self.logger.info("[DEBUG] ESC: режим захвата области активен - пропускаем обработку")
            # Возвращаем True, чтобы событие передалось дальше (в окно выделения)
            return True

        self.logger.info("[DEBUG] ESC нажат - проверка состояния перевода")

        # Проверяем, идет ли перевод
        if hasattr(self.parent, '_translation_in_progress') and self.parent._translation_in_progress:
            self.logger.info("[DEBUG] ESC: обнаружен активный перевод - отменяем")
            if hasattr(self.parent, '_cancel_translation'):
                self.parent._cancel_translation()
            return False

        # Проверяем, активно ли окно выбора области
        try:
            import win32gui
            active_hwnd = win32gui.GetForegroundWindow()
            # Если активно окно выбора области — не обрабатываем ESC здесь
            if self.parent and hasattr(self.parent, '_capture_mode') and self.parent._capture_mode:
                self.logger.info("[DEBUG] ESC: активно окно выбора области — пропускаем")
                return True
        except:
            pass

        # Если перевода нет - пытаемся найти оверлей под мышью
        overlay_to_remove = self._find_overlay_under_cursor()

        if overlay_to_remove is None:
            self.logger.info("[DEBUG] ESC: оверлей под мышью не найден - скрываем все оверлеи")
            self.hide_all_overlays()
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

        target_hwnd = overlay_to_remove._target_hwnd

        # Для F2-оверлея всегда скрываем
        if hasattr(overlay_to_remove, '_is_window_screenshot') and overlay_to_remove._is_window_screenshot:
            self.logger.info("[DEBUG] ESC: F2-оверлей (скриншот окна) - СКРЫВАЕМ, а не удаляем")
            overlay_to_remove.hide()
            overlay_to_remove._is_visible_by_user = False
            self.logger.info("[DEBUG] ESC: F2-оверлей скрыт")
            if target_hwnd:
                try:
                    import win32gui
                    win32gui.SetForegroundWindow(target_hwnd)
                    self.logger.info(f"[DEBUG] Фокус возвращен на целевое окно: {target_hwnd}")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Не удалось вернуть фокус: {e}")
            return False

        # Для F3-оверлея (область) проверяем режим редактирования
        if not self.parent.is_edit_mode_enabled():
            self.logger.info("[DEBUG] ESC: режим редактирования ВЫКЛЮЧЕН - удаление оверлеев запрещено")
            overlay_to_remove.hide()
            overlay_to_remove._is_visible_by_user = False
            self.logger.info("[DEBUG] ESC: F3-оверлей скрыт (режим редактирования выключен)")
            if target_hwnd:
                try:
                    import win32gui
                    win32gui.SetForegroundWindow(target_hwnd)
                    self.logger.info(f"[DEBUG] Фокус возвращен на целевое окно: {target_hwnd}")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Не удалось вернуть фокус: {e}")
            return False

        # Режим редактирования ВКЛЮЧЕН - УДАЛЯЕМ оверлей И ШАБЛОН
        self.logger.info("[DEBUG] ESC: режим редактирования ВКЛЮЧЕН - УДАЛЯЕМ оверлей и шаблон")

        # === УДАЛЯЕМ ШАБЛОН ИЗ МОНИТОРА ===
        if hasattr(self.parent, 'translation_monitor') and self.parent.translation_monitor:
            for template in self.parent.translation_monitor.templates[:]:
                if template.get('overlay') is overlay_to_remove:
                    pair_index = template.get('pair_index')
                    self.logger.info(f"[MONITOR] Удаляем шаблон #{pair_index} при удалении оверлея через ESC")
                    self.parent.translation_monitor.remove_template(pair_index)
                    break

        self.remove_overlay(overlay_to_remove)

        if target_hwnd:
            try:
                import win32gui
                win32gui.SetForegroundWindow(target_hwnd)
                self.logger.info(f"[DEBUG] Фокус возвращен на целевое окно: {target_hwnd}")
            except Exception as e:
                self.logger.warning(f"[DEBUG] Не удалось вернуть фокус: {e}")

        return False

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

    def get_saved_position(self, overlay_id: str) -> Optional[Tuple[int, int]]:
        """Возвращает сохраненную позицию для указанного ID оверлея."""
        positions = self._load_overlay_positions()
        pos_data = positions.get(overlay_id)
        if pos_data:
            x = pos_data.get('x')
            y = pos_data.get('y')
            if x is not None and y is not None:
                return (x, y)
        return None

    def create_overlay(self, image_path: Path, window_rect: tuple,
                       target_hwnd: int = None, is_fullscreen: bool = None,
                       show_immediately: bool = True, is_window_screenshot: bool = False,
                       is_auto_replace: bool = False, template_id: str = None) -> Optional[OverlayWindow]:
        """Создает новый оверлей и добавляет его в список для конкретного окна."""

        auto_hide_enabled = True
        if self.parent and hasattr(self.parent, 'settings'):
            auto_hide_enabled = self.parent.settings.get_auto_hide_overlay()

        new_overlay = OverlayWindow(
            parent=self.parent.root,
            app_title=self.parent.app_title if hasattr(self.parent, 'app_title') else "Перевод скриншотов",
            auto_hide_enabled=auto_hide_enabled
        )

        new_overlay._is_window_screenshot = is_window_screenshot
        new_overlay._edit_mode_enabled = self.parent._edit_mode_enabled if hasattr(self.parent,
                                                                                   '_edit_mode_enabled') else False
        new_overlay._use_manager_esc = True
        new_overlay._overlay_manager = self
        new_overlay._template_id = template_id

        if is_auto_replace:
            new_overlay._is_visible_by_user = True
            if hasattr(new_overlay, '_hidden_by_mouse'):
                new_overlay._hidden_by_mouse = False

        new_overlay.show_for_window(
            image_path, window_rect, target_hwnd, is_fullscreen, show_immediately
        )

        self._enable_esc_hook()

        if target_hwnd not in self.overlays_by_hwnd:
            self.overlays_by_hwnd[target_hwnd] = []
        self.overlays_by_hwnd[target_hwnd].append(new_overlay)
        self.overlays.append(new_overlay)

        self.logger.info(
            f"Оверлей создан для окна {target_hwnd}. Оверлеев в этом окне: {len(self.overlays_by_hwnd[target_hwnd])}")
        return new_overlay

    def get_overlays_for_window(self, hwnd: int) -> List[OverlayWindow]:
        """Возвращает список оверлеев для конкретного окна."""
        return self.overlays_by_hwnd.get(hwnd, [])

    def remove_overlay(self, overlay: OverlayWindow, force: bool = False):
        """Удаляет оверлей из всех списков и очищает состояние окна."""
        target_hwnd = overlay.get_target_hwnd()

        # Удаляем из списка по HWND
        if target_hwnd in self.overlays_by_hwnd:
            if overlay in self.overlays_by_hwnd[target_hwnd]:
                self.overlays_by_hwnd[target_hwnd].remove(overlay)
                if not self.overlays_by_hwnd[target_hwnd]:
                    del self.overlays_by_hwnd[target_hwnd]

                    # === ОЧИЩАЕМ СОСТОЯНИЕ ОКНА ===
                    if hasattr(self.parent, '_clear_window_state'):
                        self.parent._clear_window_state(target_hwnd)

        # Удаляем из общего списка
        if overlay in self.overlays:
            self.overlays.remove(overlay)

        try:
            overlay.close()
        except Exception as e:
            self.logger.error(f"Ошибка при закрытии оверлея: {e}")

    def toggle_all_overlays(self):
        """Переключает видимость всех оверлеев одновременно."""
        if not self.overlays:
            self.logger.warning("Нет оверлеев для переключения.")
            return False

        first_visible = False
        for overlay in self.overlays:
            if overlay.is_visible():
                first_visible = True
                break

        new_state = not first_visible

        self.logger.info(
            f"Переключение всех {len(self.overlays)} оверлеев в состояние: {'показаны' if new_state else 'скрыты'}"
        )

        for overlay in self.overlays:
            try:
                if new_state:
                    # Показываем оверлей — сбрасываем флаг скрытия пользователем
                    overlay._hidden_by_user = False
                    overlay.show()
                else:
                    # Скрываем оверлей — устанавливаем флаг скрытия пользователем
                    overlay._hidden_by_user = True
                    overlay.hide()
            except Exception as e:
                self.logger.error(f"Ошибка при переключении оверлея: {e}")

        self.logger.info(f"Все {len(self.overlays)} оверлеев {'показаны' if new_state else 'скрыты'}")
        return new_state

    def show_all_overlays_for_window(self, hwnd: int):
        """Показывает все оверлеи для указанного окна."""
        for overlay in self.get_overlays_for_window(hwnd):
            if overlay._is_visible_by_user and not overlay.visible:
                overlay.show()
                self.logger.debug(f"[OVERLAY] Показан оверлей для окна {hwnd}")

    def get_active_window_overlays(self) -> List[OverlayWindow]:
        """Возвращает список оверлеев для активного окна."""
        try:
            import win32gui
            active_hwnd = win32gui.GetForegroundWindow()
            return self.get_overlays_for_window(active_hwnd)
        except:
            return []

    def hide_all_for_other_windows(self, active_hwnd: int):
        """Скрывает все оверлеи, кроме тех, что принадлежат активному окну."""
        for hwnd, overlays in self.overlays_by_hwnd.items():
            if hwnd != active_hwnd:
                for overlay in overlays:
                    if overlay.visible:
                        overlay.hide()
                        self.logger.debug(f"[OVERLAY] Скрыт оверлей для окна {hwnd} (не активно)")

    def show_all_for_window(self, hwnd: int):
        """Показывает все оверлеи для указанного окна (если они должны быть видны)."""
        for overlay in self.get_overlays_for_window(hwnd):
            if overlay._is_visible_by_user and not overlay.visible:
                overlay.show()
                self.logger.debug(f"[OVERLAY] Показан оверлей для окна {hwnd}")

    def hide_all_overlays(self):
        """Скрывает все оверлеи, но НЕ УДАЛЯЕТ их из списка."""
        self.logger.info(f"Скрытие всех {len(self.overlays)} оверлеев")
        for overlay in self.overlays:
            try:
                overlay.hide()
            except Exception as e:
                self.logger.error(f"Ошибка при скрытии оверлея: {e}")

    def show_all_overlays(self):
        """Показывает все оверлеи."""
        self.logger.info(f"Показ всех {len(self.overlays)} оверлеев")
        for overlay in self.overlays:
            try:
                overlay.show()
            except Exception as e:
                self.logger.error(f"Ошибка при показе оверлея: {e}")

    def _create_context_menu(self):
        """Создает контекстное меню для оверлеев."""
        try:
            import tkinter as tk
            if hasattr(self.parent, 'root'):
                self._context_menu = tk.Menu(self.parent.root, tearoff=0, bg='#2d2d2d', fg='white',
                                             activebackground='#4CAF50', activeforeground='white')
                self._context_menu.add_command(label="🗑️ Удалить", command=self._remove_overlay_under_cursor)
                self.logger.info("[DEBUG] Контекстное меню создано в OverlayManager")
            else:
                self.logger.warning("[DEBUG] Не удалось создать контекстное меню: нет root")
        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка создания контекстного меню: {e}")

    def show_context_menu(self, overlay, x, y):
        """Показывает контекстное меню для указанного оверлея."""
        if overlay is None:
            self.logger.warning("[DEBUG] show_context_menu: оверлей None")
            return

        if overlay not in self.overlays:
            self.logger.warning("[DEBUG] show_context_menu: оверлей не в списке")
            return

        if not overlay.visible:
            self.logger.warning("[DEBUG] show_context_menu: оверлей не виден")
            return

        try:
            if not overlay.root or not overlay.root.winfo_exists():
                self.logger.warning("[DEBUG] show_context_menu: окно оверлея закрыто")
                return
        except:
            self.logger.warning("[DEBUG] show_context_menu: ошибка проверки окна оверлея")
            return

        if not self._context_menu:
            self._create_context_menu()
            if not self._context_menu:
                return

        self._context_menu_overlay = overlay

        try:
            self._context_menu.post(x, y)
            self.logger.info(f"[DEBUG] Контекстное меню показано в ({x}, {y})")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось показать контекстное меню: {e}")
            self._context_menu_overlay = None

    def _remove_overlay_under_cursor(self):
        """Удаляет оверлей, для которого было показано контекстное меню."""
        self.logger.info("[DEBUG] Удаление оверлея через контекстное меню")

        try:
            if self._context_menu:
                try:
                    self._context_menu.unpost()
                    self._context_menu.update_idletasks()
                    self.logger.info("[DEBUG] Контекстное меню закрыто (unpost)")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Ошибка при unpost: {e}")

                try:
                    if hasattr(self._context_menu, 'tk') and self._context_menu.tk:
                        self._context_menu.tk.call('destroy', self._context_menu)
                        self.logger.info("[DEBUG] Контекстное меню уничтожено через tk.call")
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Ошибка при уничтожении меню: {e}")

                self._context_menu = None
                self._create_context_menu()
                self.logger.info("[DEBUG] Контекстное меню пересоздано")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось закрыть меню: {e}")

        overlay = None
        if hasattr(self, '_context_menu_overlay') and self._context_menu_overlay:
            overlay = self._context_menu_overlay
            self._context_menu_overlay = None
            self.logger.info("[DEBUG] Ссылка на оверлей сброшена")

        if overlay is None:
            self.logger.warning("[DEBUG] Нет оверлея для удаления")
            return

        try:
            if overlay in self.overlays:
                self.remove_overlay(overlay)
                self.logger.info("[DEBUG] Оверлей удален")
            else:
                self.logger.warning("[DEBUG] Оверлей уже удален из списка")
        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка при удалении оверлея: {e}")

    def update_edit_mode_for_all(self, edit_mode_enabled: bool):
        """
        Обновляет состояние режима редактирования для всех существующих оверлеев.
        """
        self.logger.info(
            f"Обновление режима редактирования для всех {len(self.overlays)} оверлеев: {edit_mode_enabled}")
        for overlay in self.overlays:
            try:
                if overlay is not None:
                    overlay.update_edit_mode(edit_mode_enabled)
            except Exception as e:
                self.logger.warning(f"Ошибка обновления режима редактирования для оверлея: {e}")

    def _find_overlay_under_cursor(self) -> Optional[OverlayWindow]:
        """Находит оверлей, под которым находится курсор мыши."""
        try:
            import win32gui
            import win32api

            # Получаем позицию курсора
            cursor_pos = win32api.GetCursorPos()
            cursor_x, cursor_y = cursor_pos

            self.logger.info(f"[DEBUG] _find_overlay_under_cursor: курсор в ({cursor_x}, {cursor_y})")

            # Проверяем все оверлеи в обратном порядке (последний созданный - самый верхний)
            for overlay in reversed(self.overlays):
                try:
                    if overlay is None:
                        continue

                    # Проверяем, существует ли окно
                    if not overlay.root or not overlay.root.winfo_exists():
                        continue

                    # Проверяем, виден ли оверлей
                    if not overlay.visible:
                        continue

                    # Получаем координаты окна оверлея
                    overlay_hwnd = int(overlay.root.winfo_id())
                    rect = win32gui.GetWindowRect(overlay_hwnd)
                    x1, y1, x2, y2 = rect

                    self.logger.info(f"[DEBUG] _find_overlay_under_cursor: оверлей rect=({x1},{y1})-({x2},{y2})")

                    # Проверяем, находится ли курсор внутри окна
                    if x1 <= cursor_x <= x2 and y1 <= cursor_y <= y2:
                        self.logger.info(f"[DEBUG] _find_overlay_under_cursor: найден оверлей под курсором")
                        return overlay

                except Exception as e:
                    self.logger.warning(f"[DEBUG] _find_overlay_under_cursor: ошибка проверки оверлея: {e}")
                    continue

            self.logger.info("[DEBUG] _find_overlay_under_cursor: оверлей под курсором не найден")
            return None

        except Exception as e:
            self.logger.warning(f"[DEBUG] _find_overlay_under_cursor: общая ошибка: {e}")
            return None

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

    def close_all(self):
        """Закрывает все оверлеи."""
        self.logger.info(f"Закрытие всех оверлеев. Количество: {len(self.overlays)}")
        self._disable_esc_hook()
        # Используем копию списка, так как remove_overlay изменяет оригинал
        for overlay in self.overlays[:]:
            try:
                self.remove_overlay(overlay)
            except Exception as e:
                self.logger.error(f"Ошибка при закрытии оверлея: {e}")
        self.logger.info("Все оверлеи закрыты.")

    def show_all_sync(self):
        """Показывает все оверлеи синхронно, без мигания."""
        if self._show_all_sync_pending:
            self.logger.debug("[DEBUG] show_all_sync уже запланирован, пропускаем")
            return

        if not self.overlays:
            return

        # Проверяем, все ли оверлеи уже видны
        all_visible = True
        for overlay in self.overlays:
            if overlay is not None and not overlay.visible:
                all_visible = False
                break

        if all_visible:
            self.logger.debug("[DEBUG] Все оверлеи уже видны, пропускаем")
            return

        self._show_all_sync_pending = True
        self.logger.debug(f"[DEBUG] Запланирован синхронный показ всех {len(self.overlays)} оверлеев")

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