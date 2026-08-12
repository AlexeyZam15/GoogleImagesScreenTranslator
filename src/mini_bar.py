"""
Модуль для мини-бара с кнопками функций программы.
Окно всегда поверх всех окон (overlay).
"""

import tkinter as tk
from tkinter import ttk
import logging


class MiniBarWindow:
    """Окно мини-бара с кнопками для всех функций программы (оверлей)."""

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(__name__)
        self._drag_data = {"x": 0, "y": 0}
        self._is_dragging = False
        self._topmost_timer_running = False

        # Проверяем, не открыто ли уже окно
        if hasattr(app, '_mini_bar_window') and app._mini_bar_window:
            try:
                app._mini_bar_window.lift()
                app._mini_bar_window.focus_force()
                return
            except:
                app._mini_bar_window = None

        # Создаем окно как оверлей
        self.window = tk.Toplevel(app.root)
        self.window.title("Мини-бар")
        self.window.overrideredirect(True)
        self.window.geometry("460x80")
        self.window.minsize(460, 80)
        self.window.maxsize(460, 80)
        self.window.resizable(False, False)

        # Настройки оверлея
        self.window.attributes('-topmost', True)
        self.window.attributes('-alpha', 0.92)
        self.window.configure(bg='#1e1e1e')

        # Сохраняем ссылку на себя в app
        app._mini_bar_window = self

        # Создаем кнопки
        self.create_widgets()

        # Настраиваем перетаскивание
        self._setup_drag()

        # Позиционируем окно
        self._position_window()

        # Устанавливаем TOPMOST через Win32 API
        self._ensure_topmost_win32()

        # Показываем окно
        self.window.deiconify()
        self.window.lift()

        # ============================================================
        # ЗАПУСКАЕМ ПЕРИОДИЧЕСКИЙ ТАЙМЕР ДЛЯ ПОДДЕРЖАНИЯ TOPMOST
        # ============================================================
        self._start_topmost_timer()

        # Привязываем ESC для закрытия
        self.window.bind('<Escape>', lambda e: self.on_close())

        self.logger.info("[MINI_BAR] Мини-бар-оверлей создан")

    def _start_topmost_timer(self):
        """Запускает периодический таймер для поддержания topmost."""
        self._topmost_timer_running = True
        self._topmost_tick()

    def _topmost_tick(self):
        """Периодическая проверка и восстановление topmost."""
        if not hasattr(self, '_topmost_timer_running') or not self._topmost_timer_running:
            return

        if not self.window or not self.window.winfo_exists():
            return

        try:
            import win32gui
            import win32con

            hwnd = int(self.window.winfo_id())
            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)

            if not (ex_style & win32con.WS_EX_TOPMOST):
                self._ensure_topmost_win32()
                self.window.lift()
                self.logger.debug("[MINI_BAR] Topmost восстановлен")
        except Exception as e:
            self.logger.debug(f"[MINI_BAR] Ошибка проверки topmost: {e}")

        # Планируем следующую проверку через 500мс
        if self.window and self.window.winfo_exists():
            self.window.after(500, self._topmost_tick)

    def _stop_topmost_timer(self):
        """Останавливает периодический таймер."""
        self._topmost_timer_running = False

    def _ensure_topmost_win32(self):
        """Устанавливает TOPMOST через Windows API."""
        try:
            import win32gui
            import win32con

            if not self.window or not self.window.winfo_exists():
                return

            hwnd = int(self.window.winfo_id())

            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOPMOST,
                0, 0, 0, 0,
                win32con.SWP_NOMOVE | win32con.SWP_NOSIZE | win32con.SWP_SHOWWINDOW
            )

            self.logger.debug("[MINI_BAR] TOPMOST установлен через Win32 API")
        except Exception as e:
            self.logger.warning(f"[MINI_BAR] Ошибка установки TOPMOST через Win32: {e}")
            try:
                self.window.attributes('-topmost', True)
                self.window.lift()
            except:
                pass

    def _position_window(self):
        """Позиционирует окно: загружает сохранённую позицию или ставит в правый нижний угол."""
        self.window.update_idletasks()

        # Пробуем загрузить сохранённую позицию
        saved_pos = self.app.settings.get_mini_bar_position() if hasattr(self.app, 'settings') else None

        if saved_pos:
            x, y = saved_pos
            # Проверяем, что позиция в пределах экрана
            screen_width = self.window.winfo_screenwidth()
            screen_height = self.window.winfo_screenheight()
            window_width = self.window.winfo_width()
            window_height = self.window.winfo_height()

            # Корректируем, если окно уехало за пределы экрана
            if x < 0:
                x = 10
            if y < 0:
                y = 10
            if x + window_width > screen_width:
                x = screen_width - window_width - 10
            if y + window_height > screen_height:
                y = screen_height - window_height - 10

            self.window.geometry(f"+{x}+{y}")
            self.logger.info(f"[MINI_BAR] Загружена сохранённая позиция: ({x}, {y})")
            return

        # Если позиция не сохранена — ставим в правый нижний угол
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        window_width = self.window.winfo_width()
        window_height = self.window.winfo_height()

        padding = 30
        x = screen_width - window_width - padding
        y = screen_height - window_height - padding

        self.window.geometry(f"+{x}+{y}")
        self.logger.info(f"[MINI_BAR] Установлена позиция по умолчанию: ({x}, {y})")

    def _save_position(self):
        """Сохраняет текущую позицию мини-бара в настройки."""
        try:
            if not self.window or not self.window.winfo_exists():
                return
            x = self.window.winfo_x()
            y = self.window.winfo_y()
            if hasattr(self.app, 'settings'):
                self.app.settings.set_mini_bar_position(x, y)
                self.logger.debug(f"[MINI_BAR] Сохранена позиция: ({x}, {y})")
        except Exception as e:
            self.logger.warning(f"[MINI_BAR] Ошибка сохранения позиции: {e}")

    def ensure_on_top(self):
        """Поднимает мини-бар поверх всех окон."""
        try:
            if not self.window or not self.window.winfo_exists():
                return

            self.window.lift()
            self.window.attributes('-topmost', True)
            self.window.update_idletasks()
            self._ensure_topmost_win32()
        except Exception as e:
            self.logger.warning(f"[MINI_BAR] Ошибка поднятия: {e}")

    def _setup_drag(self):
        """Настраивает перетаскивание окна — только по верхней области."""
        # Перетаскивание только по верхней части окна (drag_area)
        # Привязываем события к drag_area и к самому окну (для кликов вне drag_area)
        for widget in [self.drag_area, self.window]:
            widget.bind('<ButtonPress-1>', self._start_drag)
            widget.bind('<B1-Motion>', self._on_drag)
            widget.bind('<ButtonRelease-1>', self._stop_drag)

    def _start_drag(self, event):
        """Начинает перетаскивание."""
        self._is_dragging = True
        self._drag_data["x"] = event.x_root - self.window.winfo_x()
        self._drag_data["y"] = event.y_root - self.window.winfo_y()

    def _on_drag(self, event):
        """Перемещает окно при перетаскивании."""
        if self._is_dragging:
            x = event.x_root - self._drag_data["x"]
            y = event.y_root - self._drag_data["y"]
            self.window.geometry(f"+{x}+{y}")

    def _stop_drag(self, event):
        """Останавливает перетаскивание и сохраняет позицию."""
        if self._is_dragging:
            self._is_dragging = False
            self._save_position()

    def create_widgets(self):
        """Создает все виджеты мини-бара."""
        # Основной фрейм с увеличенным верхним отступом
        self.main_frame = tk.Frame(
            self.window,
            bg='#1e1e1e',
            bd=1,
            relief=tk.SOLID,
            highlightbackground='#3c3c3c',
            highlightthickness=1
        )
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # ============================================================
        # ОБЛАСТЬ ДЛЯ ПЕРЕТАСКИВАНИЯ (СВЕРХУ) — увеличенный отступ
        # ============================================================
        self.drag_area = tk.Frame(
            self.main_frame,
            bg='#2a2a2a',
            height=24,  # Увеличенная высота для удобного перетаскивания
            cursor='fleur'
        )
        self.drag_area.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0)
        self.drag_area.pack_propagate(False)  # Фиксируем высоту

        # Заголовок в области перетаскивания
        drag_label = tk.Label(
            self.drag_area,
            text="⠿ Мини-бар",
            bg='#2a2a2a',
            fg='#666666',
            font=('Segoe UI', 9),
            anchor='w'
        )
        drag_label.pack(side=tk.LEFT, padx=(10, 0), pady=2)

        # Кнопка закрытия справа в области перетаскивания
        self.close_btn = tk.Button(
            self.drag_area,
            text="✕",
            command=self.on_close,
            bg='#2a2a2a',
            fg='#888888',
            font=('Segoe UI', 10, 'bold'),
            relief=tk.FLAT,
            width=3,
            height=1,
            cursor='hand2',
            bd=0,
            activebackground='#d32f2f',
            activeforeground='white'
        )
        self.close_btn.pack(side=tk.RIGHT, padx=(0, 8), pady=2)
        self._add_tooltip(self.close_btn, "Закрыть мини-бар (ESC)")

        # ============================================================
        # ФРЕЙМ С КНОПКАМИ
        # ============================================================
        self.btn_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
        self.btn_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 6))

        # Стиль для кнопок
        btn_style = {
            'bg': '#2d2d2d',
            'fg': 'white',
            'font': ('Segoe UI', 14),
            'relief': tk.FLAT,
            'width': 4,
            'height': 1,
            'cursor': 'hand2',
            'bd': 0,
            'activebackground': '#4CAF50',
            'activeforeground': 'white'
        }

        # Кнопка F1 - Показать/скрыть оверлей
        self.btn_f1 = tk.Button(
            self.btn_frame,
            text="👁️",
            command=self.app.toggle_overlay,
            **btn_style
        )
        self.btn_f1.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f1, "F1 - Показать/скрыть оверлей")

        # Кнопка F2 - Скриншот окна
        self.btn_f2 = tk.Button(
            self.btn_frame,
            text="📸",
            command=self.app.process,
            **btn_style
        )
        self.btn_f2.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f2, "F2 - Скриншот окна")

        # Кнопка F3 - Выделение области
        self.btn_f3 = tk.Button(
            self.btn_frame,
            text="✂️",
            command=self.app.capture_area,
            **btn_style
        )
        self.btn_f3.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f3, "F3 - Выделение области")

        # Кнопка F3 (долгое нажатие) - OCR всего окна
        self.btn_f3_hold = tk.Button(
            self.btn_frame,
            text="📄",
            command=self.app.process_fullscreen_with_ocr,
            **btn_style
        )
        self.btn_f3_hold.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f3_hold, "F3 (зажатый) - OCR всего окна")

        # Кнопка F4 - Удалить все оверлеи
        self.btn_f4 = tk.Button(
            self.btn_frame,
            text="🗑️",
            command=self.app.clear_all_overlays,
            **btn_style
        )
        self.btn_f4.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f4, "F4 - Удалить все оверлеи")

        # Кнопка F5 - Режим редактирования
        self.btn_f5 = tk.Button(
            self.btn_frame,
            text="✏️",
            command=self.app.toggle_edit_mode,
            **btn_style
        )
        self.btn_f5.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f5, "F5 - Режим редактирования")

        # Кнопка F6 - Автозамена
        self.btn_f6 = tk.Button(
            self.btn_frame,
            text="🔄",
            command=self.app.toggle_auto_replace_mode,
            **btn_style
        )
        self.btn_f6.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f6, "F6 - Автозамена областей")

    def _add_tooltip(self, widget, text):
        """Добавляет всплывающую подсказку при наведении на виджет."""

        def enter(event):
            if hasattr(widget, '_tooltip') and widget._tooltip:
                try:
                    widget._tooltip.destroy()
                except:
                    pass
                widget._tooltip = None

            tooltip = tk.Toplevel(widget)
            tooltip.wm_overrideredirect(True)
            x = event.x_root + 10
            y = event.y_root + 20
            screen_width = tooltip.winfo_screenwidth()
            screen_height = tooltip.winfo_screenheight()
            label = tk.Label(
                tooltip,
                text=text,
                bg='#2d2d2d',
                fg='white',
                font=('Segoe UI', 10),
                relief=tk.SOLID,
                borderwidth=1,
                padx=10,
                pady=6,
                wraplength=350,
                justify='left'
            )
            label.pack()
            tooltip.update_idletasks()
            tw = tooltip.winfo_width()
            th = tooltip.winfo_height()
            if x + tw > screen_width:
                x = screen_width - tw - 10
            if y + th > screen_height:
                y = screen_height - th - 10
            tooltip.wm_geometry(f"+{x}+{y}")
            widget._tooltip = tooltip

        def leave(event):
            if hasattr(widget, '_tooltip') and widget._tooltip:
                try:
                    widget._tooltip.destroy()
                except:
                    pass
                widget._tooltip = None

        widget.bind('<Enter>', enter)
        widget.bind('<Leave>', leave)

    def on_close(self):
        """Закрывает окно мини-бара."""
        self.logger.info("[MINI_BAR] Закрытие мини-бара")

        # Останавливаем таймер
        self._stop_topmost_timer()

        self._save_position()

        try:
            self.window.destroy()
        except:
            pass
        if hasattr(self.app, '_mini_bar_window'):
            self.app._mini_bar_window = None

    def lift(self):
        """Поднимает окно наверх."""
        try:
            self.window.lift()
            self.window.attributes('-topmost', True)
        except:
            pass
