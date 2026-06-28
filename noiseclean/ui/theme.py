"""Тёмная тема: шрифты и стили ttk (выпадающие списки устройств)."""

from tkinter import font as tkfont
from tkinter import ttk

from .. import config

C = config.COLORS


def build_fonts():
    fam = config.FONT_FAMILY
    return {
        "hero": tkfont.Font(family=fam, size=20, weight="bold"),
        "brand": tkfont.Font(family=fam, size=14, weight="bold"),
        "section": tkfont.Font(family=fam, size=13, weight="bold"),
        "strong": tkfont.Font(family=fam, size=10, weight="bold"),
        "body": tkfont.Font(family=fam, size=10),
        "muted": tkfont.Font(family=fam, size=9),
        "small": tkfont.Font(family=fam, size=8),
        "eyebrow": tkfont.Font(family=fam, size=8, weight="bold"),
        "value": tkfont.Font(family=fam, size=10, weight="bold"),
        "big_value": tkfont.Font(family=fam, size=12, weight="bold"),
        "icon": tkfont.Font(family=fam, size=11, weight="bold"),
        # отрицательный размер = пиксели (для футера нужен ровно 10px)
        "footer": tkfont.Font(family=fam, size=-10),
        "footer_b": tkfont.Font(family=fam, size=-10, weight="bold"),
        "lang": tkfont.Font(family=fam, size=-12),  # переключатель языка, 12px
    }


def setup_styles(root, fonts):
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:
        pass

    # Выпадающие списки устройств
    style.configure(
        "Dark.TCombobox",
        foreground=C["text"],
        fieldbackground="#12161d",
        background="#12161d",
        arrowcolor=C["blue"],
        bordercolor=C["border"],
        lightcolor=C["border"],
        darkcolor=C["border"],
        relief="flat",
        padding=6,
    )
    style.map(
        "Dark.TCombobox",
        fieldbackground=[("readonly", "#12161d"), ("focus", "#12161d")],
        foreground=[("readonly", C["text"])],
        bordercolor=[("focus", C["blue"])],
        arrowcolor=[("active", C["text"])],
    )

    # Маленький combobox для переключения языка в футере.
    # selectbackground/selectforeground = цвету поля/текста, чтобы выбранный
    # пункт не оставался подсвеченным (выделение визуально не видно).
    style.configure(
        "Lang.TCombobox",
        foreground=C["muted"],
        fieldbackground="#0d1014",
        background="#0d1014",
        selectbackground="#0d1014",
        selectforeground=C["muted"],
        arrowcolor=C["muted"],
        bordercolor=C["border"],
        lightcolor=C["border"],
        darkcolor=C["border"],
        relief="flat",
        padding=1,
    )
    style.map(
        "Lang.TCombobox",
        fieldbackground=[("readonly", "#0d1014"), ("focus", "#0d1014")],
        foreground=[("readonly", C["muted"])],
        selectbackground=[("readonly", "#0d1014"), ("focus", "#0d1014")],
        selectforeground=[("readonly", C["muted"]), ("focus", C["muted"])],
        # никакой синей рамки/подсветки при фокусе — все границы остаются тёмными
        bordercolor=[("focus", C["border"]), ("active", C["border"])],
        lightcolor=[("focus", C["border"]), ("active", C["border"])],
        darkcolor=[("focus", C["border"]), ("active", C["border"])],
        arrowcolor=[("active", C["muted"])],
    )

    # Выпадающий список (popdown) — через базу опций
    root.option_add("*TCombobox*Listbox.background", "#12161d")
    root.option_add("*TCombobox*Listbox.foreground", C["text"])
    root.option_add("*TCombobox*Listbox.selectBackground", C["green"])
    root.option_add("*TCombobox*Listbox.selectForeground", "#07090c")
    root.option_add("*TCombobox*Listbox.font", fonts["body"])
    root.option_add("*TCombobox*Listbox.borderWidth", 0)
    root.option_add("*TCombobox*Listbox.relief", "flat")

    # Тёмный вертикальный скроллбар (на случай длинных списков)
    style.configure(
        "Dark.Vertical.TScrollbar",
        background=C["panel_lighter"],
        troughcolor=C["panel"],
        bordercolor=C["panel"],
        arrowcolor=C["muted"],
        relief="flat",
    )
    return style
