"""Пользовательские настройки (выбор устройств) в JSON.

Файл: %APPDATA%\\MicroNoise\\settings.json

Его отсутствие означает ПЕРВЫЙ запуск — тогда виртуальный микрофон выбирается
автоматически (CABLE Input в приоритете). При последующих запусках берётся
сохранённый выбор пользователя. Устройства сохраняются по ИМЕНИ, т.к. числовые
индексы устройств не стабильны между перезапусками.
"""

import json
import os


def _path():
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    return os.path.join(base, "MicroNoise", "settings.json")


PATH = _path()


def load():
    try:
        # utf-8-sig — на случай, если файл сохранён с BOM (например из Блокнота)
        with open(PATH, "r", encoding="utf-8-sig") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save(data):
    try:
        os.makedirs(os.path.dirname(PATH), exist_ok=True)
        with open(PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False
