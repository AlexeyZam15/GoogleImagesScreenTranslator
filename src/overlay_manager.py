"""
Модуль для управления множественными оверлейными окнами.
"""

import logging
import keyboard
import json
import time
import base64
from pathlib import Path
from typing import Optional, List, Dict, Tuple

# Локальные импорты
from src.overlay import OverlayWindow
from src.window_utils import get_process_name_by_hwnd


class OverlayManager:
    """Управляет списком оверлеев (оптимизированная версия)"""

    __slots__ = (
        'logger', 'parent', 'overlays_by_hwnd', 'overlays', '_is_dragging_any',
        '_show_all_sync_pending', '_show_all_sync_timer', '_esc_hook_active',
        '_context_menu', '_context_menu_overlay', '_restoring', '_suppress_save',
        '_save_timer', '_save_pending', '_last_save_time', '_save_batch',
        '_save_delay'  # <-- ДОБАВЛЯЕМ В __slots__
    )

    def __init__(self, parent):
        self.logger = logging.getLogger(__name__)
        self.parent = parent
        self.overlays_by_hwnd = {}
        self.overlays = []
        self._is_dragging_any = False
        self._show_all_sync_pending = False
        self._show_all_sync_timer = None
        self._esc_hook_active = False
        self._context_menu = None
        self._context_menu_overlay = None
        self._restoring = False
        self._suppress_save = False

        # Оптимизация сохранения состояния
        self._save_timer = None
        self._save_pending = False
        self._last_save_time = 0
        self._save_batch = []
        self._save_delay = 1000  # <-- ИНИЦИАЛИЗИРУЕМ ЗНАЧЕНИЕ

        self._create_context_menu()
        self.logger.info("OverlayManager инициализирован")

    def save_overlay_state(self, immediate: bool = False):
        """
        Сохраняет состояние всех оверлеев (с задержкой для оптимизации)

        Args:
            immediate: Если True - сохраняет немедленно
        """
        if self._suppress_save:
            self.logger.debug("[STATE] Сохранение состояния пропущено (_suppress_save=True)")
            return

        # Откладываем сохранение, если не требуется немедленно
        if not immediate:
            self._schedule_save()
            return

        # Немедленное сохранение
        self._do_save_overlay_state()

    def _schedule_save(self):
        """Планирует сохранение состояния с задержкой"""
        if self._save_timer is not None:
            return

        self._save_pending = True
        current_time = time.time()

        # Если прошло достаточно времени с последнего сохранения - сохраняем сразу
        if current_time - self._last_save_time > 1.0:
            self._do_save_overlay_state()
            return

        # Иначе планируем сохранение с задержкой
        if hasattr(self.parent, 'root') and self.parent.root.winfo_exists():
            self._save_timer = self.parent.root.after(
                self._save_delay,
                self._delayed_save
            )

    def _delayed_save(self):
        """Отложенное сохранение состояния"""
        self._save_timer = None
        if self._save_pending:
            self._do_save_overlay_state()

    def _do_save_overlay_state(self):
        """Реальное сохранение состояния оверлеев"""
        self._save_pending = False
        self._last_save_time = time.time()

        state_file = self._get_overlay_state_file()
        states = {}

        for overlay in self.overlays:
            try:
                if not overlay.root or not overlay.root.winfo_exists():
                    continue

                x = overlay.root.winfo_x()
                y = overlay.root.winfo_y()
                w = overlay.root.winfo_width()
                h = overlay.root.winfo_height()

                app_name = self._get_app_name_for_overlay(overlay)
                target_hwnd = overlay._target_hwnd

                overlay_data = {
                    'x': x, 'y': y, 'width': w, 'height': h,
                    'image_path': str(overlay._last_image_path) if overlay._last_image_path else None,
                    'visible': overlay.visible,
                    'is_visible_by_user': overlay._is_visible_by_user,
                    'hidden_by_user': overlay._hidden_by_user,
                    'is_window_screenshot': overlay._is_window_screenshot,
                    'is_auto_replace': overlay._is_auto_replace,
                    'template_id': overlay._template_id,
                    'target_hwnd': target_hwnd,
                    'creation_time': overlay._creation_time,
                    'monitor_stable_time': overlay._monitor_stable_time,
                    'app_name': app_name,
                    'offset_x': getattr(overlay, '_offset_x', 0),
                    'offset_y': getattr(overlay, '_offset_y', 0)
                }

                if overlay._last_window_rect:
                    overlay_data['window_rect'] = overlay._last_window_rect

                # --- СОХРАНЯЕМ ШАБЛОН ДЛЯ АВТОЗАМЕНЫ ---
                if overlay._is_auto_replace and overlay._template_id:
                    if self.parent and hasattr(self.parent, 'translation_monitor'):
                        monitor = self.parent.translation_monitor
                        if monitor:
                            for template in monitor.templates:
                                if template.get('hash') == overlay._template_id:
                                    # Сохраняем путь к файлу шаблона
                                    template_path = template.get('template_path')
                                    if template_path and Path(template_path).exists():
                                        overlay_data['region_path'] = str(template_path)

                                    # Сохраняем сам шаблон в base64 (если есть)
                                    template_img = template.get('template')
                                    if template_img is not None:
                                        try:
                                            import cv2
                                            import base64
                                            _, buffer = cv2.imencode('.png', template_img)
                                            overlay_data['template_base64'] = base64.b64encode(buffer).decode('utf-8')
                                            self.logger.debug(
                                                f"[STATE] Шаблон {overlay._template_id[:8]} сохранён в base64")
                                        except Exception as e:
                                            self.logger.warning(f"[STATE] Не удалось сохранить шаблон в base64: {e}")
                                    break

                # Формируем уникальный ключ
                if overlay._template_id:
                    key = f"{app_name}_{overlay._template_id}"
                    if key in states:
                        key = f"{app_name}_{overlay._template_id}_{int(overlay._creation_time * 1000)}"
                        self.logger.warning(
                            f"[STATE] Дублирующийся template_id {overlay._template_id}, используем ключ: {key}"
                        )
                else:
                    img_name = Path(overlay._last_image_path).stem if overlay._last_image_path else "unknown"
                    key = f"{app_name}_{img_name}_{int(overlay._creation_time * 1000)}"

                states[key] = overlay_data
                self.logger.debug(f"[STATE] Сохранен оверлей с ключом: {key}")

            except Exception as e:
                self.logger.warning(f"[STATE] Ошибка сохранения состояния оверлея: {e}")

        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(states, f, indent=4, ensure_ascii=False, default=str)
            self.logger.info(f"[STATE] Сохранено состояние {len(states)} оверлеев")
        except Exception as e:
            self.logger.error(f"[STATE] Ошибка сохранения состояния: {e}")

    def get_overlays_by_app_name(self, app_name: str):
        """
        Возвращает список оверлеев для указанного имени приложения.
        """
        from src.window_utils import get_process_name_by_hwnd

        result = []
        for overlay in self.overlays:
            try:
                target_hwnd = overlay.get_target_hwnd()
                if target_hwnd:
                    overlay_app_name = get_process_name_by_hwnd(target_hwnd)
                    if overlay_app_name == app_name:
                        result.append(overlay)
            except Exception as e:
                self.logger.warning(f"[OVERLAY] Ошибка получения имени для оверлея: {e}")
        return result

    def get_overlays_for_window(self, hwnd: int):
        """
        Возвращает список оверлеев для конкретного HWND.
        СОХРАНЯЕТСЯ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ.
        """
        return self.overlays_by_hwnd.get(hwnd, [])

    def show_all_overlays_for_app(self, app_name: str):
        """Показывает все оверлеи для указанного приложения"""
        for overlay in self.get_overlays_by_app_name(app_name):
            if overlay._is_visible_by_user and not overlay.visible:
                overlay.show()
                self.logger.debug(f"[OVERLAY] Показан оверлей для приложения {app_name}")

    def hide_all_overlays_for_other_apps(self, active_app_name: str):
        """Скрывает все оверлеи, кроме тех, что принадлежат активному приложению"""
        for overlay in self.overlays:
            try:
                target_hwnd = overlay.get_target_hwnd()
                if target_hwnd:
                    from src.window_utils import get_process_name_by_hwnd
                    overlay_app_name = get_process_name_by_hwnd(target_hwnd)
                    if overlay_app_name != active_app_name and overlay.visible:
                        overlay.hide()
                        self.logger.debug(f"[OVERLAY] Скрыт оверлей для {overlay_app_name} (не активно)")
            except Exception as e:
                self.logger.warning(f"[OVERLAY] Ошибка при скрытии оверлея: {e}")

    def _get_app_name_for_overlay(self, overlay) -> str:
        """Получает имя приложения для оверлея."""
        if overlay._target_hwnd:
            try:
                from src.window_utils import get_process_name_by_hwnd
                return get_process_name_by_hwnd(overlay._target_hwnd)
            except Exception as e:
                self.logger.warning(f"[STATE] Ошибка получения имени для оверлея: {e}")
        return "Неизвестно"

    def _hide_overlay_under_cursor(self):
        """Скрывает оверлей под курсором (через контекстное меню)."""
        self.logger.info("[DEBUG] Скрытие оверлея через контекстное меню")

        try:
            if self._context_menu:
                try:
                    self._context_menu.unpost()
                    self._context_menu.update_idletasks()
                except Exception as e:
                    self.logger.warning(f"[DEBUG] Ошибка при unpost: {e}")

            overlay = self._context_menu_overlay

            if overlay is None:
                self.logger.warning("[DEBUG] Нет оверлея для скрытия")
                return

            if overlay not in self.overlays:
                self.logger.warning("[DEBUG] Оверлей не найден в списке")
                return

            self.logger.info(f"[DEBUG] Скрываем оверлей: {overlay}")

            overlay._hidden_by_user = True
            overlay._is_visible_by_user = False
            overlay._hidden_by_mouse = False
            overlay._mouse_over = False
            overlay.auto_hide_enabled = True

            overlay.hide(by_user=True)

            self.logger.info("[DEBUG] Оверлей скрыт через контекстное меню")
            self.save_overlay_state()

        except Exception as e:
            self.logger.error(f"[DEBUG] Ошибка при скрытии оверлея: {e}")
            import traceback
            traceback.print_exc()

    def toggle_all_overlays(self):
        """Переключает видимость всех оверлеев."""
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
            f"Переключение всех {len(self.overlays)} оверлеев в состояние: {'показаны' if new_state else 'скрыты'}")

        for overlay in self.overlays:
            try:
                if new_state:
                    overlay._hidden_by_user = False
                    overlay._is_visible_by_user = True
                    overlay.show()
                else:
                    overlay._hidden_by_user = True
                    overlay._is_visible_by_user = False
                    overlay.hide(by_user=True)
            except Exception as e:
                self.logger.error(f"Ошибка при переключении оверлея: {e}")

        self.save_overlay_state()

        self.logger.info(f"Все {len(self.overlays)} оверлеев {'показаны' if new_state else 'скрыты'}")
        return new_state

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
            self._context_menu.delete(0, "end")

            # Пункт "Скрыть" - всегда доступен
            self._context_menu.add_command(
                label="👁️ Скрыть оверлей",
                command=self._hide_overlay_under_cursor
            )
            self._context_menu.add_separator()

            # Пункт "Удалить" - доступен только в режиме редактирования
            is_edit_mode = False
            if hasattr(self.parent, 'is_edit_mode_enabled'):
                is_edit_mode = self.parent.is_edit_mode_enabled()
            elif hasattr(self.parent, '_edit_mode_enabled'):
                is_edit_mode = self.parent._edit_mode_enabled

            if is_edit_mode:
                self._context_menu.add_command(
                    label="🗑️ Удалить оверлей",
                    command=self._remove_overlay_under_cursor
                )
            else:
                self._context_menu.add_command(
                    label="🗑️ Удалить оверлей",
                    state="disabled"
                )

        except Exception as e:
            self.logger.warning(f"[DEBUG] Ошибка обновления меню: {e}")

        try:
            self._context_menu.post(x, y)
            self.logger.info(f"[DEBUG] Контекстное меню показано в ({x}, {y})")
        except Exception as e:
            self.logger.warning(f"[DEBUG] Не удалось показать контекстное меню: {e}")
            self._context_menu_overlay = None

    def _global_esc_handler(self, event):
        """Глобальный обработчик ESC - только отменяет перевод."""

        # Проверяем режим захвата области
        if self.parent and hasattr(self.parent, '_capture_mode') and self.parent._capture_mode:
            self.logger.info("[DEBUG] ESC: режим захвата области активен - пропускаем обработку")
            return True

        self.logger.info("[DEBUG] ESC нажат - проверка состояния перевода")

        # Только отменяем перевод, если он выполняется
        if hasattr(self.parent, '_translation_in_progress') and self.parent._translation_in_progress:
            self.logger.info("[DEBUG] ESC: обнаружен активный перевод - отменяем")
            if hasattr(self.parent, '_cancel_translation'):
                self.parent._cancel_translation()
            return False

        # Ничего не делаем с оверлеями
        self.logger.info("[DEBUG] ESC: нет активного перевода, игнорируем")
        return True

    def restore_overlays_from_state(self, parent_app):
        """
        Восстанавливает оверлеи из сохранённого состояния.
        Использует app_name как основной идентификатор.
        """
        from pathlib import Path
        import base64
        import tempfile

        self.logger.info("[STATE] Начинаем восстановление оверлеев из состояния...")

        self._restoring = True

        states = self.load_overlay_state()

        if not states:
            self.logger.info("[STATE] Нет сохранённых оверлеев для восстановления")
            self._restoring = False
            return 0

        restored_count = 0

        # --- СОБИРАЕМ ШАБЛОНЫ ДЛЯ МОНИТОРА ---
        templates_to_restore = []

        for key, state in states.items():
            try:
                if not state.get('image_path'):
                    continue

                image_path = Path(state['image_path'])
                if not image_path.exists():
                    self.logger.warning(f"[STATE] Файл изображения не найден: {image_path}")
                    continue

                window_rect = state.get('window_rect')
                if not window_rect:
                    self.logger.warning(f"[STATE] Нет rect окна для оверлея: {key}")
                    continue

                app_name = state.get('app_name', 'Неизвестно')
                target_hwnd = state.get('target_hwnd')
                is_auto_replace = state.get('is_auto_replace', False)
                is_window_screenshot = state.get('is_window_screenshot', False)
                template_id = state.get('template_id')
                region_path_str = state.get('region_path')
                template_base64 = state.get('template_base64')

                saved_x = state.get('x', 0)
                saved_y = state.get('y', 0)
                saved_w = state.get('width', 300)
                saved_h = state.get('height', 200)

                offset_x = state.get('offset_x', 0)
                offset_y = state.get('offset_y', 0)

                self.logger.info(
                    f"[STATE] Восстановление оверлея: {key}, app_name={app_name}, "
                    f"auto_replace={is_auto_replace}, template_id={template_id}"
                )

                # Если имя приложения "Неизвестно" - пробуем определить по HWND
                if app_name == 'Неизвестно' and target_hwnd:
                    try:
                        from src.window_utils import get_process_name_by_hwnd
                        app_name = get_process_name_by_hwnd(target_hwnd, default_name=app_name)
                    except Exception as e:
                        self.logger.warning(f"[STATE] Ошибка получения имени по HWND: {e}")

                # Ищем окно с таким именем приложения
                target_hwnd_to_use = None
                if app_name != 'Неизвестно':
                    target_hwnd_to_use = self._find_window_by_app_name(app_name)
                    if target_hwnd_to_use:
                        self.logger.info(f"[STATE] Найдено окно для {app_name}: HWND={target_hwnd_to_use}")
                    else:
                        self.logger.info(
                            f"[STATE] Окно для {app_name} не найдено, оверлей будет скрыт до появления окна")

                # Создаём оверлей
                overlay = self._create_overlay_from_data(
                    image_path=image_path,
                    window_rect=window_rect,
                    target_hwnd=target_hwnd_to_use or target_hwnd,
                    is_auto_replace=is_auto_replace,
                    is_window_screenshot=is_window_screenshot,
                    template_id=template_id,
                    show_immediately=False,
                    saved_x=saved_x,
                    saved_y=saved_y,
                    saved_w=saved_w,
                    saved_h=saved_h,
                    is_startup=True,
                    offset_x=offset_x,
                    offset_y=offset_y
                )

                if overlay:
                    self.logger.info(
                        f"[STATE] Оверлей {key} загружен, app_name={app_name}"
                    )
                    restored_count += 1

                    if target_hwnd_to_use:
                        if target_hwnd_to_use not in self.overlays_by_hwnd:
                            self.overlays_by_hwnd[target_hwnd_to_use] = []
                        if overlay not in self.overlays_by_hwnd[target_hwnd_to_use]:
                            self.overlays_by_hwnd[target_hwnd_to_use].append(overlay)
                    if overlay not in self.overlays:
                        self.overlays.append(overlay)

                    # Для автозамены: сохраняем шаблон для восстановления
                    if is_auto_replace and template_id:
                        templates_to_restore.append({
                            'template_id': template_id,
                            'overlay': overlay,
                            'target_hwnd': target_hwnd_to_use or target_hwnd,
                            'saved_x': saved_x,
                            'saved_y': saved_y,
                            'saved_w': saved_w,
                            'saved_h': saved_h,
                            'offset_x': offset_x,
                            'offset_y': offset_y,
                            'region_path_str': region_path_str,
                            'template_base64': template_base64,
                            'translated_path': image_path,
                            'window_rect': window_rect
                        })

            except Exception as e:
                self.logger.error(f"[STATE] Ошибка восстановления оверлея {key}: {e}")
                import traceback
                traceback.print_exc()

        self._restoring = False

        # --- ВОССТАНАВЛИВАЕМ ШАБЛОНЫ В МОНИТОРЕ ---
        if parent_app and hasattr(parent_app, 'translation_monitor'):
            monitor = parent_app.translation_monitor
            if monitor and templates_to_restore:
                self.logger.info(f"[STATE] Восстановление {len(templates_to_restore)} шаблонов в мониторе...")

                for template_info in templates_to_restore:
                    try:
                        template_id = template_info['template_id']
                        overlay = template_info['overlay']
                        target_hwnd = template_info['target_hwnd']

                        # Проверяем, есть ли уже такой шаблон в мониторе
                        template_exists = False
                        for template in monitor.templates:
                            if template.get('hash') == template_id:
                                template_exists = True
                                template['overlay'] = overlay
                                template['found'] = False
                                template['offset_x'] = template_info['offset_x']
                                template['offset_y'] = template_info['offset_y']
                                template['offset_initialized'] = True
                                template['overlay_width'] = template_info['saved_w']
                                template['overlay_height'] = template_info['saved_h']
                                self.logger.info(
                                    f"[STATE] Обновлена ссылка на оверлей для шаблона #{template.get('pair_index')}"
                                )
                                break

                        if template_exists:
                            continue

                        # --- ВОССТАНАВЛИВАЕМ ШАБЛОН ИЗ СОХРАНЁННЫХ ДАННЫХ ---
                        template_data = None
                        region_path = None

                        # Пробуем восстановить из region_path_str
                        if template_info.get('region_path_str'):
                            region_path = Path(template_info['region_path_str'])
                            if not region_path.exists():
                                self.logger.warning(f"[STATE] Файл шаблона не найден: {region_path}")
                                region_path = None

                        # Если нет region_path, пробуем восстановить из base64
                        if not region_path and template_info.get('template_base64'):
                            try:
                                import cv2
                                import numpy as np
                                import tempfile

                                img_data = base64.b64decode(template_info['template_base64'])
                                nparr = np.frombuffer(img_data, np.uint8)
                                template_img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                                if template_img is not None:
                                    # Сохраняем во временный файл
                                    temp_dir = Path(tempfile.gettempdir()) / "screenshot_translator" / "templates"
                                    temp_dir.mkdir(parents=True, exist_ok=True)
                                    region_path = temp_dir / f"{template_id}.png"
                                    cv2.imwrite(str(region_path), template_img)
                                    self.logger.info(f"[STATE] Шаблон восстановлен из base64: {region_path}")
                            except Exception as e:
                                self.logger.warning(f"[STATE] Ошибка восстановления из base64: {e}")
                                region_path = None

                        # Если есть region_path, создаём шаблон в мониторе
                        if region_path and region_path.exists():
                            translated_path = template_info.get('translated_path')
                            if translated_path and Path(translated_path).exists():
                                # Добавляем шаблон в монитор
                                pair_index, file_hash = monitor.add_template(
                                    region_image=region_path,
                                    translated_image=translated_path,
                                    target_hwnd=target_hwnd
                                )

                                if pair_index >= 0:
                                    # Обновляем ссылку на оверлей
                                    for template in monitor.templates:
                                        if template.get('hash') == file_hash:
                                            template['overlay'] = overlay
                                            template['found'] = False
                                            template['offset_x'] = template_info['offset_x']
                                            template['offset_y'] = template_info['offset_y']
                                            template['offset_initialized'] = True
                                            template['overlay_width'] = template_info['saved_w']
                                            template['overlay_height'] = template_info['saved_h']
                                            self.logger.info(
                                                f"[STATE] Шаблон #{pair_index} восстановлен в мониторе"
                                            )
                                            break
                            else:
                                self.logger.warning(
                                    f"[STATE] Файл перевода не найден: {translated_path}"
                                )
                        else:
                            self.logger.warning(f"[STATE] Не удалось восстановить шаблон для {template_id}")

                    except Exception as e:
                        self.logger.error(f"[STATE] Ошибка восстановления шаблона: {e}")
                        import traceback
                        traceback.print_exc()

                # --- ЗАПУСКАЕМ МОНИТОР, ЕСЛИ ЕСТЬ ШАБЛОНЫ И ВКЛЮЧЕНА АВТОЗАМЕНА ---
                if parent_app.settings.get_auto_replace_translated() and monitor.templates:
                    if not monitor.is_running():
                        self.logger.info(f"[STATE] Запуск монитора автозамены с {len(monitor.templates)} шаблонами...")
                        monitor.start()
                        self.logger.info("[STATE] ✅ Монитор автозамены запущен")
                    else:
                        self.logger.info(f"[STATE] Монитор уже запущен, шаблонов: {len(monitor.templates)}")
                else:
                    self.logger.info(
                        f"[STATE] Монитор НЕ запущен: auto_replace={parent_app.settings.get_auto_replace_translated()}, templates={len(monitor.templates)}"
                    )

        self.logger.info(f"[STATE] Восстановлено {restored_count} оверлеев")

        if parent_app and hasattr(parent_app, 'window_list'):
            self.logger.info("[STATE] Обновляем список окон после восстановления")
            parent_app.window_list.refresh()

        return restored_count

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
                            return False  # Останавливаем поиск
                    except:
                        pass
                return True

            hwnds = []
            win32gui.EnumWindows(enum_callback, hwnds)
            return hwnds[0] if hwnds else None
        except Exception as e:
            self.logger.warning(f"[STATE] Ошибка поиска окна по имени {app_name}: {e}")
            return None

    def _create_overlay_from_data(self, image_path: Path, window_rect: tuple, target_hwnd: int,
                                  is_auto_replace: bool, is_window_screenshot: bool,
                                  template_id: str = None, show_immediately: bool = True,
                                  saved_x: int = 0, saved_y: int = 0,
                                  saved_w: int = 0, saved_h: int = 0,
                                  is_startup: bool = False,
                                  offset_x: int = 0, offset_y: int = 0,
                                  is_temporary: bool = False,
                                  lifetime_seconds: int = 180,
                                  region_path: Path = None) -> Optional[OverlayWindow]:
        """
        ЕДИНСТВЕННЫЙ метод для создания оверлея.

        Args:
            image_path: Путь к переведённому изображению
            window_rect: Прямоугольник окна (x1, y1, x2, y2)
            target_hwnd: HWND целевого окна
            is_auto_replace: Флаг автозамены
            is_window_screenshot: Флаг скриншота окна
            template_id: ID шаблона (hash)
            show_immediately: Показывать ли сразу
            saved_x, saved_y, saved_w, saved_h: Сохранённая позиция
            is_startup: Флаг запуска при старте
            offset_x, offset_y: Смещение
            is_temporary: Временный ли оверлей
            lifetime_seconds: Время жизни временного оверлея
            region_path: Путь к файлу шаблона (для автозамены)

        Returns:
            OverlayWindow или None
        """
        # === ВЫЧИСЛЯЕМ ФИНАЛЬНУЮ ПОЗИЦИЮ ===
        if saved_x != 0 or saved_y != 0:
            final_x = saved_x
            final_y = saved_y
            final_w = saved_w
            final_h = saved_h
            self.logger.info(f"[STATE] Используем сохраненную позицию: ({saved_x}, {saved_y})")
        else:
            rx1, ry1, rx2, ry2 = window_rect
            final_x = rx1
            final_y = ry1
            final_w = rx2 - rx1
            final_h = ry2 - ry1
            self.logger.info(f"[STATE] Используем позицию из window_rect: ({rx1}, {ry1})")

        # Создаем оверлей
        overlay = self.create_overlay(
            image_path=image_path,
            window_rect=window_rect,
            target_hwnd=target_hwnd,
            is_fullscreen=False,
            show_immediately=show_immediately,
            is_window_screenshot=is_window_screenshot,
            is_auto_replace=is_auto_replace,
            template_id=template_id,
            is_startup=is_startup,
            is_temporary=is_temporary,
            lifetime_seconds=lifetime_seconds
        )

        if overlay:
            overlay._created_at_startup = is_startup

            try:
                overlay.root.geometry(f"{final_w}x{final_h}+{final_x}+{final_y}")
                overlay._saved_position = (final_x, final_y)
                overlay._user_moved = True
                self.logger.info(f"[OVERLAY] Установлена финальная позиция: ({final_x}, {final_y})")
            except Exception as e:
                self.logger.warning(f"[OVERLAY] Ошибка установки позиции: {e}")

            overlay._is_visible_by_user = True
            overlay._hidden_by_user = False
            overlay._image_loaded = True

            # === СОХРАНЯЕМ СМЕЩЕНИЕ В ОВЕРЛЕЕ ===
            setattr(overlay, '_offset_x', offset_x)
            setattr(overlay, '_offset_y', offset_y)

            # === СОХРАНЯЕМ ПУТЬ К ШАБЛОНУ (для автозамены) ===
            if region_path is not None:
                setattr(overlay, '_region_path', region_path)
                self.logger.info(f"[OVERLAY] Сохранён путь к шаблону: {region_path}")

            if show_immediately:
                overlay.visible = True
                try:
                    overlay.root.deiconify()
                    overlay.root.lift()
                    overlay._ensure_topmost()
                except Exception as e:
                    self.logger.warning(f"[OVERLAY] Не удалось показать оверлей: {e}")
            else:
                overlay.visible = False
                try:
                    overlay.root.withdraw()
                except Exception as e:
                    self.logger.warning(f"[OVERLAY] Не удалось скрыть оверлей: {e}")

            if target_hwnd not in self.overlays_by_hwnd:
                self.overlays_by_hwnd[target_hwnd] = []
            if overlay not in self.overlays_by_hwnd[target_hwnd]:
                self.overlays_by_hwnd[target_hwnd].append(overlay)
            if overlay not in self.overlays:
                self.overlays.append(overlay)

        return overlay

    def create_overlay(self, image_path: Path, window_rect: tuple,
                       target_hwnd: int = None, is_fullscreen: bool = None,
                       show_immediately: bool = True, is_window_screenshot: bool = False,
                       is_auto_replace: bool = False, template_id: str = None,
                       auto_hide_enabled: bool = True,
                       is_startup: bool = False,
                       is_temporary: bool = False,
                       lifetime_seconds: int = 180) -> Optional[OverlayWindow]:
        """Создает новый оверлей и добавляет его в список для конкретного окна."""

        self.logger.info(f"[DEBUG] === create_overlay НАЧАЛО ===")
        self.logger.info(f"[DEBUG] image_path={image_path}")
        self.logger.info(f"[DEBUG] target_hwnd={target_hwnd}")
        self.logger.info(f"[DEBUG] show_immediately={show_immediately}")
        self.logger.info(f"[DEBUG] auto_hide_enabled={auto_hide_enabled}")
        self.logger.info(f"[DEBUG] is_startup={is_startup}")
        self.logger.info(f"[DEBUG] is_temporary={is_temporary}")
        self.logger.info(f"[DEBUG] lifetime_seconds={lifetime_seconds}")
        self.logger.info(f"[DEBUG] template_id={template_id}")  # --- ДОБАВЛЕНО ---

        if auto_hide_enabled is None:
            auto_hide_enabled = True
            if self.parent and hasattr(self.parent, 'settings'):
                auto_hide_enabled = self.parent.settings.get_auto_hide_overlay()

        self.logger.info("[DEBUG] Создаем OverlayWindow")
        new_overlay = OverlayWindow(
            parent=self.parent.root,
            app_title=self.parent.app_title if hasattr(self.parent, 'app_title') else "Перевод скриншотов",
            auto_hide_enabled=auto_hide_enabled
        )
        self.logger.info("[DEBUG] OverlayWindow создан")

        new_overlay._is_window_screenshot = is_window_screenshot
        new_overlay._edit_mode_enabled = self.parent._edit_mode_enabled if hasattr(self.parent,
                                                                                   '_edit_mode_enabled') else False
        new_overlay._use_manager_esc = True
        new_overlay._overlay_manager = self
        new_overlay._template_id = template_id
        new_overlay._target_hwnd = target_hwnd

        self.logger.info("[DEBUG] Устанавливаем _is_auto_replace")
        new_overlay._is_auto_replace = is_auto_replace
        self.logger.info(f"[DEBUG] _is_auto_replace={new_overlay._is_auto_replace}")

        if is_auto_replace:
            new_overlay._is_visible_by_user = True
            if hasattr(new_overlay, '_hidden_by_mouse'):
                new_overlay._hidden_by_mouse = False

        self.logger.info("[DEBUG] Вызываем show_for_window")
        new_overlay.show_for_window(
            image_path, window_rect, target_hwnd, is_fullscreen, show_immediately,
            is_startup=is_startup,
            is_temporary=is_temporary,
            lifetime_seconds=lifetime_seconds
        )
        self.logger.info("[DEBUG] show_for_window завершен")

        self._enable_esc_hook()
        self.logger.info("[DEBUG] ESC хук включен")

        # === ВАЖНО: ДОБАВЛЯЕМ ОВЕРЛЕЙ В СПИСКИ ===
        if target_hwnd not in self.overlays_by_hwnd:
            self.overlays_by_hwnd[target_hwnd] = []
        if new_overlay not in self.overlays_by_hwnd[target_hwnd]:
            self.overlays_by_hwnd[target_hwnd].append(new_overlay)
        if new_overlay not in self.overlays:
            self.overlays.append(new_overlay)

        self.logger.info(f"[DEBUG] Оверлей добавлен в списки, всего оверлеев: {len(self.overlays)}")
        self.logger.info(f"[DEBUG] overlays_by_hwnd: {list(self.overlays_by_hwnd.keys())}")

        # === СОХРАНЯЕМ СОСТОЯНИЕ ТОЛЬКО ЕСЛИ НЕ ИДЁТ ВОССТАНОВЛЕНИЕ ===
        if not self._restoring:
            self.save_overlay_state()
            self.logger.info("[DEBUG] Состояние сохранено")
        else:
            self.logger.info("[DEBUG] Пропускаем сохранение состояния (идет восстановление)")

        if self.parent and hasattr(self.parent, '_on_overlay_created'):
            try:
                self.parent._on_overlay_created(target_hwnd)
                self.logger.info("[DEBUG] Родитель уведомлен о создании оверлея")
            except Exception as e:
                self.logger.warning(f"[OVERLAY] Ошибка уведомления о создании оверлея: {e}")

        self.logger.info(f"[DEBUG] === create_overlay ЗАВЕРШЕН ===")
        return new_overlay

    def _get_app_name_for_hwnd(self, hwnd: int) -> str:
        """Получает ИМЯ ПРОЦЕССА для HWND (не заголовок окна)."""
        if not hwnd:
            return "Неизвестно"

        try:
            from src.window_utils import get_process_name_by_hwnd
            return get_process_name_by_hwnd(hwnd)
        except Exception as e:
            self.logger.warning(f"[STATE] Ошибка получения имени процесса для HWND={hwnd}: {e}")
            return "Неизвестно"

    def close_all(self):
        """Закрывает все оверлеи."""
        self.logger.info(f"Закрытие всех оверлеев. Количество: {len(self.overlays)}")

        # Отключаем ESC хук
        self._disable_esc_hook()

        # Используем копию списка, так как remove_overlay изменяет оригинал
        for overlay in self.overlays[:]:
            try:
                # Отвязываем оверлей от шаблона в мониторе
                if hasattr(self, 'parent') and self.parent and hasattr(self.parent, 'translation_monitor'):
                    monitor = self.parent.translation_monitor
                    if monitor:
                        for template in monitor.templates[:]:
                            if template.get('overlay') is overlay:
                                template['overlay'] = None
                                self.logger.info(
                                    f"[MONITOR] Ссылка на оверлей сброшена для шаблона #{template.get('pair_index')}")

                self.remove_overlay(overlay)
            except Exception as e:
                self.logger.error(f"Ошибка при закрытии оверлея: {e}")

        # Очищаем списки полностью
        self.overlays.clear()
        self.overlays_by_hwnd.clear()

        # Удаляем файл состояния
        try:
            state_file = self._get_overlay_state_file()
            if state_file.exists():
                state_file.unlink()
                self.logger.info("[STATE] Файл состояния удален")
        except Exception as e:
            self.logger.warning(f"[STATE] Не удалось удалить файл состояния: {e}")

        self.logger.info("Все оверлеи закрыты.")

    def set_dragging(self, dragging: bool):
        """Устанавливает глобальный флаг перетаскивания для всех оверлеев."""
        self._is_dragging_any = dragging
        self.logger.info(f"[DEBUG] Глобальный флаг перетаскивания установлен: {dragging}")

    def is_dragging(self) -> bool:
        """Возвращает состояние глобального флага перетаскивания."""
        return self._is_dragging_any

    def remove_overlay(self, overlay: OverlayWindow, force: bool = False):
        """Удаляет оверлей из всех списков и очищает состояние окна."""
        self.logger.info(f"[OVERLAY_MANAGER] === remove_overlay НАЧАЛО ===")
        self.logger.info(f"[OVERLAY_MANAGER] overlay={overlay}")
        self.logger.info(f"[OVERLAY_MANAGER] force={force}")

        # === ЗАЩИТА ОТ ПОВТОРНОГО УДАЛЕНИЯ ===
        if overlay not in self.overlays:
            self.logger.warning("[OVERLAY_MANAGER] Оверлей уже удалён из списка, пропускаем")
            return

        target_hwnd = overlay.get_target_hwnd()
        self.logger.info(f"[OVERLAY_MANAGER] target_hwnd={target_hwnd}")

        # === 1. УДАЛЯЕМ ШАБЛОН ИЗ МОНИТОРА (ЕСЛИ ЕСТЬ) ===
        if hasattr(overlay, '_template_id') and overlay._template_id:
            template_id = overlay._template_id
            self.logger.info(f"[OVERLAY_MANAGER] Найден template_id: {template_id}")

            if hasattr(self.parent, 'translation_monitor') and self.parent.translation_monitor:
                monitor = self.parent.translation_monitor
                self.logger.info("[OVERLAY_MANAGER] TranslationMonitor найден, ищем шаблон для удаления...")

                template_to_remove = None
                for template_data in monitor.templates:
                    if template_data.get('hash') == template_id:
                        template_to_remove = template_data
                        self.logger.info(
                            f"[OVERLAY_MANAGER] Найден шаблон #{template_data.get('pair_index')} для удаления"
                        )
                        break

                if template_to_remove:
                    pair_index = template_to_remove.get('pair_index')
                    self.logger.info(f"[OVERLAY_MANAGER] Удаление шаблона #{pair_index} из монитора...")
                    monitor.remove_template(pair_index)
                    self.logger.info(f"[OVERLAY_MANAGER] Шаблон #{pair_index} удален из монитора")
                else:
                    self.logger.warning(f"[OVERLAY_MANAGER] Шаблон с hash {template_id[:8]} не найден в мониторе")

        # === 2. УДАЛЯЕМ ОВЕРЛЕЙ ИЗ СПИСКОВ ===
        if target_hwnd in self.overlays_by_hwnd:
            self.logger.info(
                f"[OVERLAY_MANAGER] Найдено {len(self.overlays_by_hwnd[target_hwnd])} оверлеев для HWND={target_hwnd}"
            )
            if overlay in self.overlays_by_hwnd[target_hwnd]:
                self.overlays_by_hwnd[target_hwnd].remove(overlay)
                self.logger.info("[OVERLAY_MANAGER] Оверлей удален из overlays_by_hwnd")

                if not self.overlays_by_hwnd[target_hwnd]:
                    del self.overlays_by_hwnd[target_hwnd]
                    self.logger.info("[OVERLAY_MANAGER] Список оверлеев для HWND пуст, удален")

                    if hasattr(self.parent, '_clear_window_state'):
                        self.parent._clear_window_state(target_hwnd)
                        self.logger.info("[OVERLAY_MANAGER] Состояние окна очищено")

                    if self.parent and hasattr(self.parent, '_on_overlay_removed'):
                        try:
                            self.parent._on_overlay_removed(target_hwnd)
                            self.logger.info("[OVERLAY_MANAGER] Родитель уведомлен об удалении")
                        except Exception as e:
                            self.logger.warning(f"[OVERLAY_MANAGER] Ошибка уведомления: {e}")

        # Удаляем из общего списка (если ещё не удалён)
        if overlay in self.overlays:
            self.overlays.remove(overlay)
            self.logger.info("[OVERLAY_MANAGER] Оверлей удален из общего списка")
        else:
            self.logger.warning("[OVERLAY_MANAGER] Оверлей не найден в общем списке")

        # === 3. ЗАКРЫВАЕМ ОВЕРЛЕЙ ===
        try:
            self.logger.info("[OVERLAY_MANAGER] Вызов overlay.close()")
            overlay.close()
            self.logger.info("[OVERLAY_MANAGER] overlay.close() выполнен")
        except Exception as e:
            self.logger.error(f"[OVERLAY_MANAGER] Ошибка при закрытии оверлея: {e}")
            import traceback
            traceback.print_exc()

        # === 4. СОХРАНЯЕМ СОСТОЯНИЕ (ЕСЛИ НЕ ЗАПРЕЩЕНО) ===
        if not self._suppress_save:
            self.logger.info("[OVERLAY_MANAGER] Сохранение состояния...")
            self.save_overlay_state()
            self.logger.info("[OVERLAY_MANAGER] Состояние сохранено")
        else:
            self.logger.info("[OVERLAY_MANAGER] Сохранение состояния пропущено (_suppress_save=True)")

        self.logger.info("[OVERLAY_MANAGER] === remove_overlay ЗАВЕРШЕН ===")

    def save_position(self, overlay_id, art_x, art_y, art_w, art_h, icon_x=None, icon_y=None,
                      user_modified=False, offset_x=None, offset_y=None):
        """Сохраняет позицию арта относительно иконки/шаблона."""

        # Если offset передан, используем его
        if offset_x is not None and offset_y is not None and icon_x is not None and icon_y is not None:
            # Сохраняем смещение относительно шаблона
            self.saved_positions[overlay_id] = {
                'offset_x': offset_x,
                'offset_y': offset_y,
                'width': art_w,
                'height': art_h,
                'icon_x': icon_x,
                'icon_y': icon_y,
                'user_modified': user_modified
            }
            self.user_modified[overlay_id] = user_modified
            self.save_positions_to_settings()
            self.logger.info(f"[POSITION] Сохранено смещение для {overlay_id}: offset=({offset_x}, {offset_y})")
            return

        # Если icon_x/icon_y не переданы - получаем их через общий метод
        if icon_x is None or icon_y is None:
            icon_x, icon_y, found = self.get_icon_position(overlay_id)
            if not found:
                icon_x = art_x
                icon_y = art_y

        # Проверяем, изменилась ли позиция
        saved = self.saved_positions.get(overlay_id)
        if saved:
            old_offset_x = saved.get('offset_x', 0)
            old_offset_y = saved.get('offset_y', 0)
            new_offset_x = art_x - icon_x
            new_offset_y = art_y - icon_y
            old_w = saved.get('width', 0)
            old_h = saved.get('height', 0)

            if (abs(old_offset_x - new_offset_x) < 3 and
                    abs(old_offset_y - new_offset_y) < 3 and
                    abs(old_w - art_w) < 3 and
                    abs(old_h - art_h) < 3 and
                    saved.get('user_modified', False) == user_modified):
                return

        self.saved_positions[overlay_id] = {
            'offset_x': art_x - icon_x,
            'offset_y': art_y - icon_y,
            'width': art_w,
            'height': art_h,
            'icon_x': icon_x,
            'icon_y': icon_y,
            'user_modified': user_modified
        }
        self.user_modified[overlay_id] = user_modified
        self.save_positions_to_settings()
        self.logger.info(f"[POSITION] Сохранена позиция для {overlay_id}: offset=({art_x - icon_x}, {art_y - icon_y})")

    def _get_overlay_state_file(self) -> Path:
        """Возвращает путь к файлу с сохранённым состоянием оверлеев."""
        config_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "overlay_state.json"

    def load_overlay_state(self):
        """
        Загружает состояние оверлеев из JSON-файла.
        Возвращает словарь с состояниями оверлеев.
        """
        state_file = self._get_overlay_state_file()

        if not state_file.exists():
            self.logger.info("[STATE] Файл состояния оверлеев не найден")
            return {}

        try:
            with open(state_file, 'r', encoding='utf-8') as f:
                states = json.load(f)
            self.logger.info(f"[STATE] Загружено состояние {len(states)} оверлеев из {state_file}")
            return states
        except Exception as e:
            self.logger.error(f"[STATE] Ошибка загрузки состояния: {e}")
            return {}

    def _sync_overlay_with_window_manager(self, parent_app, overlay, target_hwnd, state):
        """
        Синхронизирует состояние оверлея с системой переключения окон.
        """
        if not parent_app or not hasattr(parent_app, '_window_states'):
            return

        # Создаём состояние для окна, если его нет
        if target_hwnd not in parent_app._window_states:
            parent_app._window_states[target_hwnd] = {
                'overlays': [],
                'templates': [],
                'was_visible': False,
                'visible': False
            }

        # Добавляем оверлей в состояние, если его там нет
        if overlay not in parent_app._window_states[target_hwnd]['overlays']:
            parent_app._window_states[target_hwnd]['overlays'].append(overlay)

        # Обновляем флаг видимости
        is_visible_by_user = state.get('is_visible_by_user', True)
        if is_visible_by_user:
            parent_app._window_states[target_hwnd]['was_visible'] = True
            parent_app._window_states[target_hwnd]['visible'] = True
        else:
            # Проверяем, есть ли другие видимые оверлеи в этом окне
            was_visible = False
            for ov in parent_app._window_states[target_hwnd]['overlays']:
                if ov is not overlay and ov._is_visible_by_user:
                    was_visible = True
                    break
            if not was_visible:
                parent_app._window_states[target_hwnd]['was_visible'] = False
                parent_app._window_states[target_hwnd]['visible'] = False

        self.logger.info(
            f"[STATE] Синхронизировано состояние для HWND={target_hwnd}: was_visible={parent_app._window_states[target_hwnd]['was_visible']}")

    def _save_overlay_position(self, overlay_id: str, x: int, y: int):
        """Сохраняет позицию конкретного оверлея в файл."""
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
                    # НЕ ПОКАЗЫВАЕМ ПАНЕЛЬ АВТОМАТИЧЕСКИ
                    # Панель будет показана только при наведении мыши
            except Exception as e:
                self.logger.warning(f"Ошибка обновления режима редактирования для оверлея: {e}")

    def _find_overlay_under_cursor(self) -> Optional[OverlayWindow]:
        """Находит оверлей, под которым находится курсор мыши."""
        try:
            import win32gui
            import win32api

            cursor_pos = win32api.GetCursorPos()
            cursor_x, cursor_y = cursor_pos

            self.logger.info(f"[DEBUG] _find_overlay_under_cursor: курсор в ({cursor_x}, {cursor_y})")

            for overlay in reversed(self.overlays):
                try:
                    if overlay is None:
                        continue

                    if not overlay.root or not overlay.root.winfo_exists():
                        continue

                    if not overlay.visible:
                        continue

                    overlay_hwnd = int(overlay.root.winfo_id())
                    rect = win32gui.GetWindowRect(overlay_hwnd)
                    x1, y1, x2, y2 = rect

                    self.logger.info(f"[DEBUG] _find_overlay_under_cursor: оверлей rect=({x1},{y1})-({x2},{y2})")

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

    def show_all_sync(self):
        """Показывает все оверлеи синхронно, без мигания."""
        if self._show_all_sync_pending:
            self.logger.debug("[DEBUG] show_all_sync уже запланирован, пропускаем")
            return

        if not self.overlays:
            return

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

        windows_to_show = []
        windows_to_load = []

        for overlay in self.overlays:
            try:
                if overlay is None:
                    continue

                if overlay.visible:
                    self.logger.info(f"[DEBUG] Оверлей уже виден, пропускаем")
                    continue

                if overlay._image_loaded and overlay.tk_image is not None:
                    windows_to_show.append(overlay)
                elif overlay._last_image_path and overlay._last_window_rect:
                    windows_to_load.append(overlay)
            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка при сборе данных оверлея: {e}")

        for overlay in windows_to_load:
            try:
                self.logger.info(f"[DEBUG] Загружаем изображение для оверлея")
                overlay._load_and_show_image(overlay._last_image_path, overlay._last_window_rect)
                overlay._image_loaded = True
            except Exception as e:
                self.logger.warning(f"[DEBUG] Ошибка при загрузке изображения: {e}")

        for overlay in windows_to_show + windows_to_load:
            try:
                if not overlay.visible:
                    overlay.root.deiconify()
                    overlay.root.lift()
                    overlay.visible = True
                    overlay._enable_esc_hook()

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

    def _get_overlay_position_file(self) -> Path:
        """Возвращает путь к файлу с сохраненными позициями оверлеев."""
        config_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "overlay_positions.json"

    def _load_overlay_positions(self) -> dict:
        """Загружает сохраненные позиции оверлеев из файла."""
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
