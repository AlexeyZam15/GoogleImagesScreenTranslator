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

    def save_overlay_state(self):
        """
        Сохраняет состояние всех оверлеев в JSON-файл.
        Сохраняет: позицию, путь к изображению, хеш шаблона, видимость, тип,
        а также путь к файлу региона для автозамены.
        """
        import json
        import time

        state_file = self._get_overlay_state_file()
        states = {}

        # Сохраняем состояние каждого оверлея
        for overlay in self.overlays:
            try:
                if not overlay.root or not overlay.root.winfo_exists():
                    continue

                # Получаем позицию
                x = overlay.root.winfo_x()
                y = overlay.root.winfo_y()
                w = overlay.root.winfo_width()
                h = overlay.root.winfo_height()

                # Получаем данные об оверлее
                overlay_data = {
                    'x': x,
                    'y': y,
                    'width': w,
                    'height': h,
                    'image_path': str(overlay._last_image_path) if overlay._last_image_path else None,
                    'visible': overlay.visible,
                    'is_visible_by_user': overlay._is_visible_by_user,
                    'hidden_by_user': overlay._hidden_by_user,
                    'is_window_screenshot': overlay._is_window_screenshot,
                    'is_auto_replace': overlay._is_auto_replace,
                    'template_id': overlay._template_id,
                    'target_hwnd': overlay._target_hwnd,
                    'creation_time': overlay._creation_time,
                    'monitor_stable_time': overlay._monitor_stable_time,
                }

                # Получаем rect окна
                if overlay._last_window_rect:
                    overlay_data['window_rect'] = overlay._last_window_rect

                # === ДОБАВЛЯЕМ ПУТЬ К ФАЙЛУ РЕГИОНА ДЛЯ АВТОЗАМЕНЫ ===
                if overlay._is_auto_replace and overlay._template_id:
                    # Ищем шаблон в TranslationMonitor
                    if self.parent and hasattr(self.parent, 'translation_monitor'):
                        monitor = self.parent.translation_monitor
                        if monitor:
                            for template in monitor.templates:
                                if template.get('hash') == overlay._template_id:
                                    region_path = template.get('template_path')
                                    if region_path and Path(region_path).exists():
                                        overlay_data['region_path'] = str(region_path)
                                        self.logger.info(
                                            f"[STATE] Сохранён путь к региону для шаблона {overlay._template_id[:8]}: {region_path}")
                                    break

                # Используем template_id как ключ, если есть, иначе путь к изображению
                key = overlay._template_id if overlay._template_id else str(overlay._last_image_path)
                if key:
                    states[key] = overlay_data

            except Exception as e:
                self.logger.warning(f"[STATE] Ошибка сохранения состояния оверлея: {e}")

        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(states, f, indent=4, ensure_ascii=False, default=str)
            self.logger.info(f"[STATE] Сохранено состояние {len(states)} оверлеев в {state_file}")
        except Exception as e:
            self.logger.error(f"[STATE] Ошибка сохранения состояния: {e}")

    def restore_overlays_from_state(self, parent_app):
        """
        Восстанавливает оверлеи из сохранённого состояния.
        Используется при запуске приложения.
        """
        self.logger.info("[STATE] Начинаем восстановление оверлеев из состояния...")
        states = self.load_overlay_state()

        if not states:
            self.logger.info("[STATE] Нет сохранённых оверлеев для восстановления")
            return 0

        restored_count = 0
        restored_auto_replace_overlays = []

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

                target_hwnd = state.get('target_hwnd')
                is_auto_replace = state.get('is_auto_replace', False)
                is_window_screenshot = state.get('is_window_screenshot', False)
                template_id = state.get('template_id')
                region_path_str = state.get('region_path')

                # Получаем сохранённую позицию
                x = state.get('x', 0)
                y = state.get('y', 0)
                w = state.get('width', 300)
                h = state.get('height', 200)

                # Создаём оверлей, НО НЕ ПОКАЗЫВАЕМ ЕГО
                overlay = self.create_overlay(
                    image_path=image_path,
                    window_rect=window_rect,
                    target_hwnd=target_hwnd,
                    is_fullscreen=False,
                    show_immediately=False,  # ВАЖНО: НЕ ПОКАЗЫВАТЬ
                    is_window_screenshot=is_window_screenshot,
                    is_auto_replace=is_auto_replace,
                    template_id=template_id
                )

                if overlay:
                    # Восстанавливаем позицию
                    try:
                        if x != 0 or y != 0:
                            overlay.root.geometry(f"{w}x{h}+{x}+{y}")
                            overlay._saved_position = (x, y)
                            self.logger.info(f"[STATE] Восстановлена позиция для {key}: ({x}, {y}) {w}x{h}")
                        else:
                            # Если позиция не сохранена (0,0), используем window_rect
                            if window_rect:
                                rx1, ry1, rx2, ry2 = window_rect
                                if rx2 - rx1 > 10 and ry2 - ry1 > 10:
                                    overlay.root.geometry(f"{rx2 - rx1}x{ry2 - ry1}+{rx1}+{ry1}")
                                    self.logger.info(
                                        f"[STATE] Установлена позиция из window_rect для {key}: ({rx1}, {ry1})")
                    except Exception as e:
                        self.logger.warning(f"[STATE] Ошибка восстановления позиции: {e}")

                    # ВАЖНО: оверлей ОСТАЁТСЯ СКРЫТЫМ независимо от состояния visible
                    overlay.visible = False
                    overlay._is_visible_by_user = False  # Оверлей скрыт до нахождения шаблона
                    overlay._hidden_by_user = False
                    overlay._hidden_by_mouse = False
                    overlay._mouse_over = False

                    try:
                        overlay.root.withdraw()
                    except:
                        pass

                    # Сохраняем для восстановления в мониторе
                    if is_auto_replace and template_id:
                        restored_auto_replace_overlays.append({
                            'overlay': overlay,
                            'template_id': template_id,
                            'target_hwnd': target_hwnd,
                            'image_path': image_path,
                            'window_rect': window_rect,
                            'is_visible_by_user': state.get('is_visible_by_user', True),
                            'region_path_str': region_path_str
                        })

                    # Синхронизируем с системой переключения окон
                    self._sync_overlay_with_window_manager(parent_app, overlay, target_hwnd, state)
                    restored_count += 1
                    self.logger.info(
                        f"[STATE] Восстановлен оверлей: {key} (auto_replace={is_auto_replace}, скрыт до нахождения шаблона)")

            except Exception as e:
                self.logger.error(f"[STATE] Ошибка восстановления оверлея {key}: {e}")

        # === ВОССТАНАВЛИВАЕМ ШАБЛОНЫ В TRANSLATIONMONITOR ===
        if restored_auto_replace_overlays and parent_app and hasattr(parent_app, 'translation_monitor'):
            monitor = parent_app.translation_monitor
            if monitor:
                self.logger.info(
                    f"[STATE] Восстанавливаем {len(restored_auto_replace_overlays)} шаблонов в TranslationMonitor...")

                for overlay_data in restored_auto_replace_overlays:
                    try:
                        template_id = overlay_data['template_id']
                        overlay = overlay_data['overlay']
                        target_hwnd = overlay_data['target_hwnd']
                        image_path = overlay_data['image_path']
                        region_path_str = overlay_data.get('region_path_str')

                        # Проверяем, есть ли уже шаблон с таким хешем в мониторе
                        template_exists = False
                        for template in monitor.templates:
                            if template.get('hash') == template_id:
                                template['overlay'] = overlay
                                template['found'] = False  # Ещё не найден, будет найден при сканировании
                                template_exists = True
                                self.logger.info(
                                    f"[STATE] Шаблон {template_id[:8]} уже есть в мониторе, привязываем оверлей")
                                break

                        if not template_exists:
                            # Восстанавливаем шаблон из файла региона
                            region_path = None
                            if region_path_str and Path(region_path_str).exists():
                                region_path = Path(region_path_str)
                                self.logger.info(f"[STATE] Найден сохранённый файл региона: {region_path}")
                            else:
                                # Ищем рядом с переведённым изображением
                                temp_dir = image_path.parent
                                for f in temp_dir.glob("region_*.png"):
                                    if f.stat().st_mtime >= image_path.stat().st_mtime - 10:
                                        region_path = f
                                        break

                            if region_path and region_path.exists():
                                self.logger.info(f"[STATE] Восстанавливаем шаблон из файла: {region_path}")

                                add_result = monitor.add_template(
                                    region_path,
                                    image_path,
                                    target_hwnd=target_hwnd
                                )

                                if add_result is not None and len(add_result) == 2:
                                    pair_index, file_hash = add_result
                                    if pair_index >= 0 and file_hash:
                                        self.logger.info(f"[STATE] Шаблон восстановлен с индексом {pair_index}")
                                        for template in monitor.templates:
                                            if template.get('pair_index') == pair_index:
                                                template['overlay'] = overlay
                                                template['found'] = False  # Будет найден при сканировании
                                                break
                            else:
                                self.logger.warning(f"[STATE] Не найден файл региона для шаблона {template_id[:8]}")

                    except Exception as e:
                        self.logger.error(f"[STATE] Ошибка восстановления шаблона: {e}")

        # После восстановления всех оверлеев — обновляем состояние в менеджере окон
        if parent_app and hasattr(parent_app, '_window_states'):
            for target_hwnd in self.overlays_by_hwnd:
                if target_hwnd in parent_app._window_states:
                    parent_app._window_states[target_hwnd]['overlays'] = self.overlays_by_hwnd[target_hwnd]
                    # Сохраняем was_visible как False, чтобы оверлеи не показывались принудительно
                    parent_app._window_states[target_hwnd]['was_visible'] = False
                    parent_app._window_states[target_hwnd]['visible'] = False
                    self.logger.info(f"[STATE] Обновлено состояние для HWND={target_hwnd}: was_visible=False")

        self.logger.info(f"[STATE] Восстановлено {restored_count} оверлеев")

        # === НЕ ЗАПУСКАЕМ МОНИТОР СРАЗУ — он запустится при первом сканировании ===
        if restored_count > 0 and parent_app and hasattr(parent_app, 'translation_monitor'):
            monitor = parent_app.translation_monitor
            if monitor and monitor.templates and not monitor.is_running():
                auto_replace_enabled = False
                if hasattr(parent_app, 'settings'):
                    auto_replace_enabled = parent_app.settings.get_auto_replace_translated()

                if auto_replace_enabled:
                    if not monitor.is_running():
                        monitor.start()
                        self.logger.info("[STATE] ✅ Монитор автозамены запущен")

        return restored_count

    def create_overlay(self, image_path: Path, window_rect: tuple,
                       target_hwnd: int = None, is_fullscreen: bool = None,
                       show_immediately: bool = True, is_window_screenshot: bool = False,
                       is_auto_replace: bool = False, template_id: str = None) -> Optional[OverlayWindow]:
        """Создает новый оверлей и добавляет его в список для конкретного окна."""

        self.logger.info(
            f"[DEBUG] create_overlay: image_path={image_path}, target_hwnd={target_hwnd}, is_auto_replace={is_auto_replace}, template_id={template_id}, show_immediately={show_immediately}")

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

        # Устанавливаем флаг автозамены ДО вызова show_for_window
        new_overlay._is_auto_replace = is_auto_replace
        self.logger.info(
            f"[DEBUG] create_overlay: new_overlay._is_auto_replace установлен в {new_overlay._is_auto_replace}")

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

        # Сохраняем состояние после создания
        self.save_overlay_state()

        self.logger.info(
            f"Оверлей создан для окна {target_hwnd}. Оверлеев в этом окне: {len(self.overlays_by_hwnd[target_hwnd])}. "
            f"is_auto_replace={new_overlay._is_auto_replace}, template_id={template_id}"
        )
        return new_overlay

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

        # Сохраняем состояние после удаления
        self.save_overlay_state()

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
                    overlay._hidden_by_user = False
                    overlay.show()
                else:
                    overlay._hidden_by_user = True
                    overlay.hide()
            except Exception as e:
                self.logger.error(f"Ошибка при переключении оверлея: {e}")

        # Сохраняем состояние после переключения
        self.save_overlay_state()

        self.logger.info(f"Все {len(self.overlays)} оверлеев {'показаны' if new_state else 'скрыты'}")
        return new_state

    def _get_overlay_state_file(self) -> Path:
        """Возвращает путь к файлу с сохранённым состоянием оверлеев."""
        import json
        from pathlib import Path
        config_dir = Path.home() / "Documents" / "GoogleScreenTranslate" / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir / "overlay_state.json"

    def load_overlay_state(self):
        """
        Загружает состояние оверлеев из JSON-файла.
        Возвращает словарь с состояниями оверлеев.
        """
        import json
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

    def get_overlays_for_window(self, hwnd: int) -> List[OverlayWindow]:
        """Возвращает список оверлеев для конкретного окна."""
        return self.overlays_by_hwnd.get(hwnd, [])

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