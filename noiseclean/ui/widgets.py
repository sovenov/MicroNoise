"""Кастомные виджеты на Canvas в стиле index.html.

Tkinter не умеет скруглённые рамки у Frame и градиенты, поэтому ключевые
акцентные элементы (кнопка питания, переключатель, индикаторы, слайдер,
визуализация волны) нарисованы на Canvas вручную.
"""

import tkinter as tk

from .. import config
from . import assets

C = config.COLORS


def round_rect(canvas, x1, y1, x2, y2, r, **kw):
    """Скруглённый прямоугольник через сглаженный полигон."""
    r = max(0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [
        x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
        x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
        x1, y2, x1, y2 - r, x1, y1 + r, x1, y1,
    ]
    return canvas.create_polygon(pts, smooth=True, **kw)


# ---------------------------------------------------------------------------
# Иконки-глифы
# ---------------------------------------------------------------------------
def draw_equalizer(canvas, cx, cy, color, heights=(8, 16, 22, 14, 9), gap=4, w=3):
    n = len(heights)
    total = n * w + (n - 1) * gap
    x = cx - total / 2 + w / 2
    for h in heights:
        canvas.create_line(x, cy + h / 2, x, cy - h / 2, fill=color,
                           width=w, capstyle="round")
        x += w + gap


def draw_leaf(canvas, cx, cy, color):
    pts = [cx - 9, cy + 9, cx - 3, cy - 7, cx + 9, cy - 9, cx + 3, cy + 7]
    canvas.create_polygon(pts, smooth=True, fill=color, outline="")
    canvas.create_line(cx - 8, cy + 8, cx + 8, cy - 8, fill=C["panel"], width=1.5)


def draw_mic(canvas, cx, cy, color):
    round_rect(canvas, cx - 5, cy - 11, cx + 5, cy + 3, 5, outline=color,
               width=2, fill="")
    canvas.create_arc(cx - 9, cy - 6, cx + 9, cy + 8, start=200, extent=140,
                      style="arc", outline=color, width=2)
    canvas.create_line(cx, cy + 7, cx, cy + 11, fill=color, width=2)
    canvas.create_line(cx - 5, cy + 11, cx + 5, cy + 11, fill=color, width=2)


def draw_monitor(canvas, cx, cy, color):
    round_rect(canvas, cx - 10, cy - 9, cx + 10, cy + 5, 3, outline=color,
               width=2, fill="")
    canvas.create_line(cx, cy + 5, cx, cy + 9, fill=color, width=2)
    canvas.create_line(cx - 4, cy + 9, cx + 4, cy + 9, fill=color, width=2)


def draw_headphones(canvas, cx, cy, color):
    canvas.create_arc(cx - 11, cy - 11, cx + 11, cy + 11, start=20, extent=140,
                      style="arc", outline=color, width=2)
    round_rect(canvas, cx - 11, cy - 2, cx - 5, cy + 9, 2, fill=color, outline="")
    round_rect(canvas, cx + 5, cy - 2, cx + 11, cy + 9, 2, fill=color, outline="")


# ---------------------------------------------------------------------------
# Брендовая иконка (5 полос)
# ---------------------------------------------------------------------------
class EqIcon(tk.Canvas):
    def __init__(self, parent, bg, size=44, color=None):
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        img = assets.icon("brand")
        if img is not None:
            self.create_image(size / 2, size / 2, image=img)
        else:
            color = color or C["green"]
            draw_equalizer(self, size / 2, size / 2, color,
                           heights=(12, 22, 30, 22, 12), gap=4, w=3)


# ---------------------------------------------------------------------------
# Кнопка питания
# ---------------------------------------------------------------------------
class PowerButton(tk.Canvas):
    def __init__(self, parent, bg, command=None, size=92):
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self._command = command
        self._size = size
        self._on = True
        self._face_on = assets.icon("power_face_on")
        self._face_off = assets.icon("power_face_off")
        self._icon_on = assets.icon("power_on")
        self._icon_off = assets.icon("power_off")
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self.config(cursor="hand2"))
        self._render()

    def _click(self, _event):
        self._on = not self._on
        self._render()
        if self._command:
            self._command(self._on)

    def set_state(self, on):
        self._on = bool(on)
        self._render()

    def _render(self):
        self.delete("all")
        s = self._size
        cx = cy = s / 2
        face = self._face_on if self._on else self._face_off
        if face is not None:
            self.create_image(cx, cy, image=face)
            return
        r = s * 0.42
        if self._on:
            ring, fill, glyph = C["green"], "#10271b", C["green"]
            self.create_oval(cx - r - 6, cy - r - 6, cx + r + 6, cy + r + 6,
                             outline="#123322", width=1)
        else:
            ring, fill, glyph = C["border_strong"], "#161a21", C["muted_dim"]
        self.create_oval(cx - r, cy - r, cx + r, cy + r, fill=fill,
                         outline=ring, width=2)
        img = self._icon_on if self._on else self._icon_off
        if img is not None:
            self.create_image(cx, cy, image=img)
        else:
            gr = r * 0.45
            self.create_arc(cx - gr, cy - gr, cx + gr, cy + gr, start=65,
                            extent=290, style="arc", outline=glyph, width=3)
            self.create_line(cx, cy - gr - 3, cx, cy - 1, fill=glyph, width=3,
                             capstyle="round")


# ---------------------------------------------------------------------------
# Переключатель (toggle)
# ---------------------------------------------------------------------------
class ToggleSwitch(tk.Canvas):
    def __init__(self, parent, bg, command=None, width=52, height=30):
        super().__init__(parent, width=width, height=height, bg=bg,
                         highlightthickness=0, bd=0)
        self._command = command
        self._cw, self._ch = width, height
        self._on = False
        self.bind("<Button-1>", self._click)
        self.bind("<Enter>", lambda e: self.config(cursor="hand2"))
        self._render()

    def _click(self, _event):
        self._on = not self._on
        self._render()
        if self._command:
            self._command(self._on)

    def set(self, on):
        self._on = bool(on)
        self._render()

    def get(self):
        return self._on

    def _render(self):
        self.delete("all")
        w, h = self._cw, self._ch
        track = C["green"] if self._on else C["switch_off"]
        round_rect(self, 1, 1, w - 1, h - 1, (h - 2) / 2, fill=track, outline="")
        kr = h - 8
        if self._on:
            kx = w - 4 - kr
        else:
            kx = 4
        self.create_oval(kx, 4, kx + kr, 4 + kr, fill="white", outline="")


# ---------------------------------------------------------------------------
# Индикатор уровня
# ---------------------------------------------------------------------------
class Meter(tk.Canvas):
    def __init__(self, parent, bg, kind="input", height=12):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0)
        self._kind = kind
        self._h = height
        self._value = 0.0
        self.bind("<Configure>", lambda e: self._render())

    def set_value(self, pct):
        self._value = max(0.0, min(100.0, float(pct)))
        self._render()

    def _fill_color(self, pct):
        if self._kind == "record":
            return C["purple"]
        if pct >= 90:
            return C["danger"]
        if pct >= 74:
            return "#ffbd43"
        return C["green"] if self._kind == "input" else C["blue"]

    def _render(self):
        self.delete("all")
        w = self.winfo_width()
        h = self._h
        if w <= 1:
            w = 360
        round_rect(self, 0, 0, w, h, h / 2, fill=C["track"], outline="")
        fill_w = (self._value / 100.0) * w
        if fill_w >= 2:
            round_rect(self, 0, 0, fill_w, h, h / 2,
                       fill=self._fill_color(self._value), outline="")


# ---------------------------------------------------------------------------
# Слайдер усиления
# ---------------------------------------------------------------------------
class GainSlider(tk.Canvas):
    def __init__(self, parent, bg, minimum=0.0, maximum=30.0, step=0.5,
                 command=None, height=22):
        super().__init__(parent, height=height, bg=bg, highlightthickness=0, bd=0)
        self._min, self._max, self._step = minimum, maximum, step
        self._command = command
        self._h = height
        self._value = 0.0
        self._pad = 11
        self.bind("<Configure>", lambda e: self._render())
        self.bind("<Button-1>", self._on_drag)
        self.bind("<B1-Motion>", self._on_drag)
        self.bind("<Enter>", lambda e: self.config(cursor="hand2"))

    def set(self, value, notify=False):
        value = max(self._min, min(self._max, value))
        value = round(value / self._step) * self._step
        self._value = value
        self._render()
        if notify and self._command:
            self._command(self._value)

    def get(self):
        return self._value

    def _on_drag(self, event):
        w = self.winfo_width()
        usable = max(1, w - 2 * self._pad)
        frac = (event.x - self._pad) / usable
        value = self._min + frac * (self._max - self._min)
        self.set(value, notify=True)

    def _render(self):
        self.delete("all")
        w = self.winfo_width()
        if w <= 1:
            w = 360
        h = self._h
        cy = h / 2
        x0, x1 = self._pad, w - self._pad
        frac = (self._value - self._min) / (self._max - self._min)
        tx = x0 + frac * (x1 - x0)
        round_rect(self, x0, cy - 3, x1, cy + 3, 3, fill=C["track"], outline="")
        if tx > x0 + 1:
            round_rect(self, x0, cy - 3, tx, cy + 3, 3, fill=C["green"], outline="")
        timg = assets.icon("gain_thumb")
        if timg is not None:
            self.create_image(tx, cy, image=timg)
        else:
            r = 9
            self.create_oval(tx - r, cy - r, tx + r, cy + r, fill="white",
                             outline=C["green"], width=2)


# ---------------------------------------------------------------------------
# Карточка-вариант режима
# ---------------------------------------------------------------------------
class ModeOption(tk.Frame):
    def __init__(self, parent, icon_kind, title, subtitle, command=None):
        super().__init__(parent, bg=C["panel"], highlightthickness=1,
                         highlightbackground=C["border"],
                         highlightcolor=C["border"])
        self._command = command
        self._selected = False
        self._icon_kind = icon_kind

        self._icon = tk.Canvas(self, width=44, height=44, bg=C["panel"],
                               highlightthickness=0, bd=0)
        self._icon.grid(row=0, column=0, rowspan=2, padx=(14, 12), pady=12)

        self._title = tk.Label(self, text=title, bg=C["panel"], fg=C["text"],
                               font=(config.FONT_FAMILY, 11, "bold"), anchor="w")
        self._title.grid(row=0, column=1, sticky="sw", pady=(12, 0))
        # height=2 резервирует 2 строки, чтобы карточки с 1- и 2-строчными
        # подписями были одинаковой высоты
        self._sub = tk.Label(self, text=subtitle, bg=C["panel"], fg=C["muted"],
                             font=(config.FONT_FAMILY, 9), anchor="nw",
                             justify="left", height=2)
        self._sub.grid(row=1, column=1, sticky="nw", pady=(2, 12))

        self._radio = tk.Canvas(self, width=20, height=20, bg=C["panel"],
                                highlightthickness=0, bd=0)
        self._radio.grid(row=0, column=2, rowspan=2, padx=(12, 16))

        self.grid_columnconfigure(1, weight=1)

        for widget in (self, self._icon, self._title, self._sub, self._radio):
            widget.bind("<Button-1>", self._click)
            widget.bind("<Enter>", self._enter)
            widget.bind("<Leave>", self._leave)
            widget.config(cursor="hand2")
        self._render()

    def _click(self, _event):
        if self._command:
            self._command(self)

    def _enter(self, _event):
        if not self._selected:
            self._set_bg("#181d25")
            self.config(highlightbackground=C["border_strong"])

    def _leave(self, _event):
        if not self._selected:
            self._set_bg(C["panel"])
            self.config(highlightbackground=C["border"])

    def set_selected(self, selected):
        self._selected = bool(selected)
        self._render()

    def set_texts(self, title, subtitle):
        self._title.config(text=title)
        self._sub.config(text=subtitle)

    def _set_bg(self, color):
        for w in (self, self._icon, self._title, self._sub, self._radio):
            w.config(bg=color)

    def _render(self):
        bg = "#13261b" if self._selected else C["panel"]
        self._set_bg(bg)
        self.config(highlightbackground=C["green"] if self._selected
                    else C["border"])

        self._icon.delete("all")
        # подложка иконки
        round_rect(self._icon, 0, 0, 44, 44, 13,
                   fill="#13281c" if self._icon_kind == "light" else "#1d222b",
                   outline="")
        img = assets.icon("leaf" if self._icon_kind == "light" else "equalizer")
        if img is not None:
            self._icon.create_image(22, 22, image=img)
        else:
            icon_color = C["green"] if self._icon_kind == "light" else "#bac1cc"
            if self._icon_kind == "light":
                draw_leaf(self._icon, 22, 22, icon_color)
            else:
                draw_equalizer(self._icon, 22, 22, icon_color,
                               heights=(8, 16, 22, 14, 9), gap=3, w=3)

        self._radio.delete("all")
        rimg = assets.icon("radio_on" if self._selected else "radio_off")
        if rimg is not None:
            self._radio.create_image(10, 10, image=rimg)
        elif self._selected:
            self._radio.create_oval(2, 2, 18, 18, outline=C["green"], width=2)
            self._radio.create_oval(6, 6, 14, 14, fill=C["green"], outline="")
        else:
            self._radio.create_oval(2, 2, 18, 18, outline=C["border_strong"],
                                    width=2)


# ---------------------------------------------------------------------------
# Кнопка воспроизведения (круглая)
# ---------------------------------------------------------------------------
class PlayButton(tk.Canvas):
    def __init__(self, parent, bg, command=None, size=46):
        super().__init__(parent, width=size, height=size, bg=bg,
                         highlightthickness=0, bd=0)
        self._command = command
        self._size = size
        self._playing = False
        self._enabled = False
        self.bind("<Button-1>", self._click)
        self._render()

    def _click(self, _event):
        if self._enabled and self._command:
            self._command()

    def set_enabled(self, enabled):
        self._enabled = bool(enabled)
        self._render()

    def set_playing(self, playing):
        self._playing = bool(playing)
        self._render()

    def _render(self):
        self.delete("all")
        s = self._size
        color = C["text"] if self._enabled else C["muted_dim"]
        outline = C["border_strong"] if self._enabled else C["border"]
        self.create_oval(2, 2, s - 2, s - 2, outline=outline, width=1,
                         fill=C["panel_soft"])
        cx = cy = s / 2
        if self._playing:
            self.create_rectangle(cx - 6, cy - 7, cx - 2, cy + 7, fill=color,
                                  outline="")
            self.create_rectangle(cx + 2, cy - 7, cx + 6, cy + 7, fill=color,
                                  outline="")
        else:
            self.create_polygon(cx - 5, cy - 7, cx - 5, cy + 7, cx + 7, cy,
                                fill=color, outline="")
        self.config(cursor="hand2" if self._enabled else "arrow")


# ---------------------------------------------------------------------------
# Всплывающее уведомление (toast)
# ---------------------------------------------------------------------------
class Toast:
    def __init__(self, root, fonts):
        self._root = root
        self._fonts = fonts
        self._top = None
        self._after_id = None

    def show(self, message, duration=2600):
        self._cancel()
        if self._top is None or not self._top.winfo_exists():
            self._top = tk.Toplevel(self._root)
            self._top.overrideredirect(True)
            try:
                self._top.attributes("-topmost", True)
            except Exception:
                pass
            self._frame = tk.Frame(self._top, bg=C["panel_lighter"],
                                   highlightthickness=1,
                                   highlightbackground=C["border_strong"])
            self._frame.pack(fill="both", expand=True)
            self._label = tk.Label(self._frame, bg=C["panel_lighter"],
                                   fg=C["text"], font=self._fonts["body"],
                                   wraplength=320, justify="left")
            self._label.pack(padx=16, pady=12)

        self._label.config(text=message)
        self._top.update_idletasks()
        self._reposition()
        self._top.deiconify()
        try:
            self._top.attributes("-alpha", 0.97)
        except Exception:
            pass
        self._after_id = self._root.after(duration, self._hide)

    def _reposition(self):
        self._root.update_idletasks()
        rx = self._root.winfo_rootx()
        ry = self._root.winfo_rooty()
        rw = self._root.winfo_width()
        rh = self._root.winfo_height()
        tw = self._top.winfo_width()
        th = self._top.winfo_height()
        x = rx + rw - tw - 24
        y = ry + rh - th - 24
        self._top.geometry("+%d+%d" % (x, y))

    def _hide(self):
        if self._top is not None and self._top.winfo_exists():
            self._top.withdraw()

    def _cancel(self):
        if self._after_id is not None:
            try:
                self._root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None


# ---------------------------------------------------------------------------
# Текстовая кнопка (вторичная)
# ---------------------------------------------------------------------------
def make_button(parent, text, command, bg=None, fg=None, font=None,
                hover_bg=None, pad=(14, 9)):
    bg = bg or C["panel_lighter"]
    fg = fg or C["text"]
    hover_bg = hover_bg or C["border_strong"]
    btn = tk.Label(parent, text=text, bg=bg, fg=fg, font=font,
                   padx=pad[0], pady=pad[1], cursor="hand2")
    btn.bind("<Button-1>", lambda e: command())
    btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
    btn.bind("<Leave>", lambda e: btn.config(bg=bg))
    btn._base_bg = bg
    btn._hover_bg = hover_bg
    return btn
