"""Локализация интерфейса MicroNoise: русский и английский.

Строки берутся по ключу через ``tr(lang, key)``. Тексты, не зависящие от языка
(имя бренда, проценты), в словаре не хранятся.
"""

DEFAULT_LANG = "ru"
LANGS = ("ru", "en")

TR = {
    "ru": {
        "topbar_subtitle": "Шумоподавление микрофона",
        "hero_title": "Шумоподавление микрофона",
        "hero_desc_on": "Обработанный голос направляется в выбранный виртуальный микрофон.",
        "hero_desc_off": "Обработка и передача звука временно остановлены.",
        "power_on": "Включено",
        "power_off": "Выключено",
        "mode_eyebrow": "Режим шумоподавления",
        "mode_light_title": "Лёгкий",
        "mode_light_desc": "Подавляет фоновый шум и гул вентиляторов",
        "mode_strong_title": "Интенсивный",
        "mode_strong_desc": "Дополнительно подавляет звуки клавиатуры,\nщелчки мыши и ваши вздохи в микрофон",
        "src_mic": "Исходный микрофон",
        "virt_mic": "Виртуальный микрофон",
        "signal_eyebrow": "Сигнал микрофона",
        "signal_title": "Входной и выходной уровень",
        "in_signal": "Входной сигнал",
        "out_signal": "Выходной сигнал",
        "meter_hint": "Говорите в микрофон, чтобы увидеть входной и выходной уровни.",
        "gain_title": "Усиление голоса (gain)",
        "gain_desc": "Применяется после шумоподавления",
        "reset": "Сбросить",
        "gain_unit": "дБ",
        "db_min": "0 дБ",
        "db_max": "+30 дБ",
        "tray_open": "Открыть",
        "tray_on": "Вкл",
        "tray_off": "Выкл",
        "tray_quit": "Завершить",
        "already_running": "MicroNoise уже запущен.",
    },
    "en": {
        "topbar_subtitle": "Microphone noise suppression",
        "hero_title": "Microphone noise suppression",
        "hero_desc_on": "The processed voice is routed to the selected virtual microphone.",
        "hero_desc_off": "Audio processing and routing are temporarily stopped.",
        "power_on": "On",
        "power_off": "Off",
        "mode_eyebrow": "Noise suppression mode",
        "mode_light_title": "Light",
        "mode_light_desc": "Suppresses background noise and fan hum",
        "mode_strong_title": "Intense",
        "mode_strong_desc": "Additionally suppresses keyboard sounds,\nmouse clicks and your breathing into the mic",
        "src_mic": "Source microphone",
        "virt_mic": "Virtual microphone",
        "signal_eyebrow": "Microphone signal",
        "signal_title": "Input and output level",
        "in_signal": "Input signal",
        "out_signal": "Output signal",
        "meter_hint": "Speak into the microphone to see the input and output levels.",
        "gain_title": "Voice gain",
        "gain_desc": "Applied after noise suppression",
        "reset": "Reset",
        "gain_unit": "dB",
        "db_min": "0 dB",
        "db_max": "+30 dB",
        "tray_open": "Open",
        "tray_on": "On",
        "tray_off": "Off",
        "tray_quit": "Quit",
        "already_running": "MicroNoise is already running.",
    },
}


def tr(lang, key):
    table = TR.get(lang, TR[DEFAULT_LANG])
    return table.get(key, TR[DEFAULT_LANG].get(key, key))
