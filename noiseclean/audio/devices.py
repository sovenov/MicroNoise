"""Перечисление аудиоустройств через sounddevice (PortAudio).

Чтобы список не засорялся дублями одного устройства из разных Host API
(MME / DirectSound / WASAPI / WDM-KS), показываем устройства только одного
выбранного API. По умолчанию предпочитаем WASAPI (полные имена, низкая
задержка), с откатом на MME (максимальная совместимость, в т.ч. Windows 7).
"""

import sounddevice as sd

# Порядок предпочтения Host API.
PREFERRED_HOSTAPIS = ["Windows WASAPI", "MME", "Windows DirectSound", "Windows WDM-KS"]

# Шаблоны имён виртуальных кабелей (куда отправляется обработанный голос),
# в порядке приоритета. CABLE Input — самый высокий приоритет.
VIRTUAL_OUTPUT_PATTERNS = [
    "cable input",            # VB-Audio Virtual Cable (приоритет)
    "line 1",                 # Virtual Audio Cable
    "line 2",
    "vb-audio virtual cable",
    "virtual audio cable",
    "voicemeeter input",      # VoiceMeeter
    "voicemeeter aux",
    "virtual",                # любое прочее «виртуальное»
    "cable",
]


def _hostapi_index():
    apis = sd.query_hostapis()
    names = [a["name"] for a in apis]
    for pref in PREFERRED_HOSTAPIS:
        if pref in names:
            return names.index(pref)
    # запасной вариант — Host API устройства ввода по умолчанию
    try:
        return sd.query_devices(kind="input")["hostapi"]
    except Exception:
        return 0


def hostapi_name():
    try:
        return sd.query_hostapis()[_hostapi_index()]["name"]
    except Exception:
        return "?"


def _list(kind):
    """kind: 'input' | 'output' -> [{'index', 'name', 'channels'}]."""
    api = _hostapi_index()
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    result = []
    for idx, dev in enumerate(sd.query_devices()):
        if dev["hostapi"] != api:
            continue
        if dev[key] > 0:
            result.append({"index": idx, "name": dev["name"], "channels": dev[key]})
    return result


def list_inputs():
    return _list("input")


def list_outputs():
    return _list("output")


def default_input_index():
    api = _hostapi_index()
    try:
        default = sd.query_hostapis()[api].get("default_input_device", -1)
    except Exception:
        default = -1
    if default is not None and default >= 0:
        return default
    inputs = list_inputs()
    return inputs[0]["index"] if inputs else None


def default_monitor_index():
    """Устройство по умолчанию для локального прослушивания (наушники/колонки)."""
    api = _hostapi_index()
    try:
        default = sd.query_hostapis()[api].get("default_output_device", -1)
    except Exception:
        default = -1
    if default is not None and default >= 0:
        return default
    outputs = list_outputs()
    return outputs[0]["index"] if outputs else None


def guess_virtual_output():
    """Подобрать выходное устройство-«виртуальный микрофон»."""
    outputs = list_outputs()
    for pattern in VIRTUAL_OUTPUT_PATTERNS:
        for dev in outputs:
            if pattern in dev["name"].lower():
                return dev["index"]
    return default_monitor_index()


def device_name(index):
    if index is None:
        return "—"
    try:
        return sd.query_devices(index)["name"]
    except Exception:
        return "—"
