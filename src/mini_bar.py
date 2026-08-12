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
        self._emoji_images = []

        # Проверяем, не открыто ли уже окно
        if hasattr(app, '_mini_bar_window') and app._mini_bar_window:
            try:
                app._mini_bar_window.lift()
                app._mini_bar_window.focus_force()
                return
            except:
                app._mini_bar_window = None

        # Создаем окно как оверлей — БЕЗ ФИКСИРОВАННОЙ ШИРИНЫ
        self.window = tk.Toplevel(app.root)
        self.window.title("Мини-бар")
        self.window.overrideredirect(True)
        # Убираем фиксированную геометрию — размер будет по содержимому
        self.window.wm_geometry('')  # <-- АВТОМАТИЧЕСКИЙ РАЗМЕР
        self.window.minsize(200, 70)
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

        # Запускаем периодический таймер
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

    def create_emoji_image(self, emoji: str, size: int = 22, color: str = 'white') -> tk.PhotoImage:
        """
        Создаёт PhotoImage из эмодзи для использования в кнопках.
        Эмодзи центрируется в изображении.
        """
        try:
            from PIL import Image, ImageDraw, ImageFont, ImageTk
        except ImportError:
            # Fallback, если PIL не установлен
            return None

        # Создаём прозрачное изображение
        img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        try:
            # Пробуем использовать шрифт с поддержкой эмодзи
            font = ImageFont.truetype("seguiemj.ttf", size - 2)
        except:
            try:
                font = ImageFont.truetype("Segoe UI Emoji", size - 2)
            except:
                font = ImageFont.load_default()

        # Рисуем эмодзи по центру
        draw.text((size // 2, size // 2), emoji, fill=color, anchor='mm', font=font)

        return ImageTk.PhotoImage(img)

    def create_widgets(self):
        """Создает все виджеты мини-бара с выровненными иконками."""
        # Основной фрейм
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
        # ОБЛАСТЬ ДЛЯ ПЕРЕТАСКИВАНИЯ (СВЕРХУ)
        # ============================================================
        self.drag_area = tk.Frame(
            self.main_frame,
            bg='#2a2a2a',
            height=26,  # чуть выше
            cursor='fleur'
        )
        self.drag_area.pack(fill=tk.X, side=tk.TOP, padx=0, pady=0)
        self.drag_area.pack_propagate(False)

        # Заголовок в области перетаскивания
        drag_text = self.app.get_string('mini_bar_drag_label') if hasattr(self.app, 'get_string') else "⠿ Мини-бар"
        self.drag_label = tk.Label(
            self.drag_area,
            text=drag_text,
            bg='#2a2a2a',
            fg='#666666',
            font=('Segoe UI', 9),
            anchor='w'
        )
        self.drag_label.pack(side=tk.LEFT, padx=(10, 0), pady=2)

        # Кнопка закрытия справа
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
        close_tooltip = self.app.get_string('mini_bar_close') if hasattr(self.app,
                                                                         'get_string') else "Закрыть мини-бар (ESC)"
        self._add_tooltip(self.close_btn, close_tooltip)

        # ============================================================
        # ФРЕЙМ С КНОПКАМИ
        # ============================================================
        self.btn_frame = tk.Frame(self.main_frame, bg='#1e1e1e')
        self.btn_frame.pack(fill=tk.BOTH, expand=True, padx=6, pady=(4, 6))

        # Получаем текущие горячие клавиши
        hotkeys = self.app.settings.get_all_hotkeys() if hasattr(self.app, 'settings') else {}

        def format_tooltip(key, default_hotkey):
            hotkey = hotkeys.get(key, default_hotkey)
            hotkey_display = hotkey.upper() if hotkey else "?"
            if '+' in hotkey:
                parts = hotkey.split('+')
                hotkey_display = '+'.join(p.upper() for p in parts)
            template = self.app.get_string(f'mini_bar_tooltip_{key}') if hasattr(self.app, 'get_string') else None
            if template:
                return template.format(hotkey=hotkey_display)
            return f"{key} ({hotkey_display})"

        tooltip_f1 = format_tooltip('f1', 'F1')
        tooltip_f2 = format_tooltip('f2', 'F2')
        tooltip_f3 = format_tooltip('f3', 'F3')
        tooltip_f3_hold = format_tooltip('f3_hold', 'F3 (held)')
        tooltip_f4 = format_tooltip('f4', 'F4')
        tooltip_f5 = format_tooltip('f5', 'F5')
        tooltip_f6 = format_tooltip('f6', 'F6')

        # ============================================================
        # СОЗДАЁМ ИЗОБРАЖЕНИЯ ЭМОДЗИ (УВЕЛИЧЕННЫЙ РАЗМЕР)
        # ============================================================
        self._emoji_images = []

        emoji_size = 26  # <-- УВЕЛИЧЕНО С 22 ДО 26
        emoji_f1 = self.create_emoji_image('👁️', emoji_size)
        emoji_f2 = self.create_emoji_image('📸', emoji_size)
        emoji_f3 = self.create_emoji_image('✂️', emoji_size)
        emoji_f3_hold = self.create_emoji_image('📄', emoji_size)
        emoji_f4 = self.create_emoji_image('🗑️', emoji_size)
        emoji_f5 = self.create_emoji_image('✏️', emoji_size)
        emoji_f6 = self.create_emoji_image('🔄', emoji_size)

        self._emoji_images.extend([emoji_f1, emoji_f2, emoji_f3, emoji_f3_hold, emoji_f4, emoji_f5, emoji_f6])

        # Стиль кнопок — УВЕЛИЧЕННЫЙ РАЗМЕР
        btn_style = {
            'bg': '#2d2d2d',
            'fg': 'white',
            'relief': tk.FLAT,
            'cursor': 'hand2',
            'bd': 0,
            'activebackground': '#4CAF50',
            'activeforeground': 'white',
            'width': 44,  # <-- УВЕЛИЧЕНО С 36 ДО 44
            'height': 34,  # <-- УВЕЛИЧЕНО С 30 ДО 34
            'compound': 'center',
        }

        # F1 - 👁️
        self.btn_f1 = tk.Button(
            self.btn_frame,
            image=emoji_f1,
            command=self.app.toggle_overlay,
            **btn_style
        )
        self.btn_f1.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f1, tooltip_f1)

        # F2 - 📸
        self.btn_f2 = tk.Button(
            self.btn_frame,
            image=emoji_f2,
            command=self.app.process,
            **btn_style
        )
        self.btn_f2.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f2, tooltip_f2)

        # F3 - ✂️
        self.btn_f3 = tk.Button(
            self.btn_frame,
            image=emoji_f3,
            command=self.app.capture_area,
            **btn_style
        )
        self.btn_f3.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f3, tooltip_f3)

        # F3_hold - 📄
        self.btn_f3_hold = tk.Button(
            self.btn_frame,
            image=emoji_f3_hold,
            command=self.app.process_fullscreen_with_ocr,
            **btn_style
        )
        self.btn_f3_hold.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f3_hold, tooltip_f3_hold)

        # F4 - 🗑️
        self.btn_f4 = tk.Button(
            self.btn_frame,
            image=emoji_f4,
            command=self.app.clear_all_overlays,
            **btn_style
        )
        self.btn_f4.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f4, tooltip_f4)

        # F5 - ✏️
        self.btn_f5 = tk.Button(
            self.btn_frame,
            image=emoji_f5,
            command=self.app.toggle_edit_mode,
            **btn_style
        )
        self.btn_f5.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f5, tooltip_f5)

        # F6 - 🔄
        self.btn_f6 = tk.Button(
            self.btn_frame,
            image=emoji_f6,
            command=self.app.toggle_auto_replace_mode,
            **btn_style
        )
        self.btn_f6.pack(side=tk.LEFT, padx=2)
        self._add_tooltip(self.btn_f6, tooltip_f6)

        # ============================================================
        # ДОБАВЛЯЕМ ОТСТУП ПОСЛЕ ПОСЛЕДНЕЙ КНОПКИ
        # ============================================================
        # Создаём пустой Label для отступа справа
        padding_label = tk.Label(
            self.btn_frame,
            text=" ",
            bg='#1e1e1e',
            width=1
        )
        padding_label.pack(side=tk.RIGHT, padx=4)  # <-- ОТСТУП СПРАВА

        # Обновляем окно для пересчёта размера
        self.window.update_idletasks()

    def _on_label_enter(self, event, label):
        """Обработчик наведения на кнопку-лейбл."""
        label.config(bg='#4CAF50')

    def _on_label_leave(self, event, label):
        """Обработчик ухода с кнопки-лейбла."""
        label.config(bg='#2d2d2d')

    def _add_tooltip(self, widget, text):
        """Добавляет всплывающую подсказку при наведении на виджет.
        Тултип появляется фиксированно под мини-баром, не зависит от позиции мыши.
        """

        def enter(event):
            if hasattr(widget, '_tooltip') and widget._tooltip:
                try:
                    widget._tooltip.destroy()
                except:
                    pass
                widget._tooltip = None

            # Получаем позицию мини-бара
            try:
                window_x = self.window.winfo_x()
                window_y = self.window.winfo_y()
                window_width = self.window.winfo_width()
            except:
                # Fallback: используем позицию мыши
                window_x = event.x_root - 50
                window_y = event.y_root + 20
                window_width = 200

            tooltip = tk.Toplevel(self.window)
            tooltip.wm_overrideredirect(True)
            tooltip.attributes('-topmost', True)

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
                wraplength=400,
                justify='left'
            )
            label.pack()
            tooltip.update_idletasks()

            tw = tooltip.winfo_width()
            th = tooltip.winfo_height()

            # ============================================================
            # ФИКСИРОВАННАЯ ПОЗИЦИЯ: всегда под мини-баром по центру
            # ============================================================
            screen_width = tooltip.winfo_screenwidth()
            screen_height = tooltip.winfo_screenheight()

            # Позиционируем под мини-баром по центру
            x = window_x + (window_width - tw) // 2
            y = window_y + 80  # Под мини-баром

            # Корректировка, чтобы не выходил за экран
            if x < 0:
                x = 5
            if x + tw > screen_width:
                x = screen_width - tw - 5
            if y < 0:
                y = 5
            if y + th > screen_height:
                y = screen_height - th - 5

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
