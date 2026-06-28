"""Загрузка PNG-иконок (сгенерированы из SVG макета) через tk.PhotoImage.

Tk 8.6 умеет PNG с прозрачностью нативно, поэтому Pillow в рантайме не нужен.
Если файла нет или загрузка не удалась — возвращается None, и виджет рисует
запасной глиф примитивами Canvas.
"""

import os
import tkinter as tk

from .. import config

_DIR = os.path.join(config.BASE_DIR, "assets")
_cache = {}


def icon(name):
    """PhotoImage по имени (без расширения) или None."""
    if name in _cache:
        return _cache[name]
    path = os.path.join(_DIR, name + ".png")
    img = None
    try:
        if os.path.exists(path):
            img = tk.PhotoImage(file=path)
    except Exception:
        img = None
    _cache[name] = img
    return img
