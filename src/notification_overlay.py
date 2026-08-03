import tkinter as tk


class NotificationOverlay:
    def __init__(self, parent_root):
        self.parent = parent_root
        self.root = None
        self.label = None
        self.visible = False
        self._hide_timer = None

    def show(self, text, duration_ms=1500):
        if self._hide_timer:
            try:
                self.parent.after_cancel(self._hide_timer)
            except:
                pass
            self._hide_timer = None

        if self.root is None or not self.root.winfo_exists():
            self.root = tk.Toplevel(self.parent)
            self.root.overrideredirect(True)
            self.root.attributes('-topmost', True)
            self.root.attributes('-transparentcolor', '#010101')
            self.root.configure(bg='#010101')

            self.label = tk.Label(
                self.root,
                text=text,
                font=('Segoe UI', 16, 'bold'),
                fg='#4CAF50',
                bg='#010101',
                padx=20,
                pady=10
            )
            self.label.pack()

            self.root.bind('<Button-1>', self.hide)

        self.label.config(text=text)

        screen_width = self.root.winfo_screenwidth()
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (screen_width - width) // 2
        y = 30
        self.root.geometry(f'+{x}+{y}')

        if not self.visible:
            self.root.deiconify()
            self.root.lift()
            self.visible = True

        self._hide_timer = self.parent.after(duration_ms, self.hide)

    def hide(self, event=None):
        if self._hide_timer:
            try:
                self.parent.after_cancel(self._hide_timer)
            except:
                pass
            self._hide_timer = None
        if self.root and self.root.winfo_exists():
            self.root.withdraw()
        self.visible = False