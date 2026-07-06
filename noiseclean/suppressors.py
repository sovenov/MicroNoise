"""ctypes-обёртки над движками шумоподавления.

* SpeexSuppressor  - libspeexdsp (тот же препроцессор, что в OBS).
* RNNoiseSuppressor - rnnoise.dll (нейросетевое подавление, основа
  проекта werman/noise-suppression-for-voice).

Все обёртки принимают кадр float32 в диапазоне [-1, 1] длиной FRAME_SIZE
и возвращают обработанный кадр float32 той же длины плюс оценку наличия
речи (0..1).
"""

import collections
import ctypes
import os
from array import array

from . import config


def _zeros_f32(n):
    """Массив float32 из n нулей (эквивалент np.zeros(n, float32))."""
    return array("f", bytes(4 * n))


def _float_ptr(buf):
    """ctypes-указатель POINTER(c_float) на память array('f') buf (без копии)."""
    carr = (ctypes.c_float * len(buf)).from_buffer(buf)
    return ctypes.cast(carr, ctypes.POINTER(ctypes.c_float)), carr


def _int16_ptr(buf):
    """ctypes-указатель POINTER(c_int16) на память array('h') buf (без копии)."""
    carr = (ctypes.c_int16 * len(buf)).from_buffer(buf)
    return ctypes.cast(carr, ctypes.POINTER(ctypes.c_int16)), carr


class SuppressorError(Exception):
    """Не удалось загрузить или инициализировать движок шумоподавления."""


class BaseSuppressor:
    name = "base"
    label = "Без обработки"

    def process(self, frame):
        """frame: np.float32[FRAME_SIZE] в [-1,1] -> (out_float32, speech_prob)."""
        raise NotImplementedError

    def close(self):
        pass


class PassthroughSuppressor(BaseSuppressor):
    """Запасной режим без обработки (если DLL не загрузилась)."""

    name = "passthrough"
    label = "Без обработки"

    def process(self, frame):
        return frame, 0.0


# ---------------------------------------------------------------------------
# RNNoise (интенсивный режим)
# ---------------------------------------------------------------------------
class RNNoiseSuppressor(BaseSuppressor):
    """RNNoise + VAD-гейт — как в werman/noise-suppression-for-voice.

    Нейросеть RNNoise подавляет шум в каждом кадре (480 сэмплов, 48 кГц) и
    выдаёт вероятность речи 0..1. Поверх неё работает VAD-гейт, портированный
    из RnNoiseCommonPlugin.cpp werman'а:

      * vad_threshold     — если вероятность речи ниже порога, выход глушится;
      * grace_blocks      — сколько блоков (×10 мс) держать открытым ПОСЛЕ речи
                            (не обрезает хвосты слов; минимум 20 = 200 мс);
      * retro_blocks      — сколько блоков ПЕРЕД речью открыть задним числом
                            (не обрезает начало слов; вносит задержку, макс. 99).
    """

    name = config.MODE_STRONG
    label = "Интенсивный (RNNoise + VAD)"

    _MUTED = 0
    _UNMUTED = 1

    def __init__(self, dll_path=None, threshold=None, grace_blocks=None,
                 retro_blocks=None):
        dll_path = dll_path or config.RNNOISE_DLL
        if not os.path.exists(dll_path):
            raise SuppressorError("Не найдена библиотека rnnoise.dll: %s" % dll_path)
        try:
            lib = ctypes.CDLL(dll_path)
        except OSError as exc:
            raise SuppressorError("Не удалось загрузить rnnoise.dll: %s" % exc)

        lib.rnnoise_create.argtypes = [ctypes.c_void_p]
        lib.rnnoise_create.restype = ctypes.c_void_p
        lib.rnnoise_destroy.argtypes = [ctypes.c_void_p]
        lib.rnnoise_get_frame_size.restype = ctypes.c_int
        lib.rnnoise_process_frame.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(ctypes.c_float),
            ctypes.POINTER(ctypes.c_float),
        ]
        lib.rnnoise_process_frame.restype = ctypes.c_float

        self._lib = lib
        self._frame_size = lib.rnnoise_get_frame_size()
        self._state = lib.rnnoise_create(None)
        if not self._state:
            raise SuppressorError("rnnoise_create вернул NULL")

        # параметры VAD-гейта
        self._threshold = (config.RNNOISE_VAD_THRESHOLD
                           if threshold is None else threshold)
        self._grace = (config.RNNOISE_VAD_GRACE_BLOCKS
                       if grace_blocks is None else grace_blocks)
        self._retro = (config.RNNOISE_RETRO_GRACE_BLOCKS
                       if retro_blocks is None else retro_blocks)
        self._clamp_params()

        # состояние гейта: очередь блоков [idx, frames(int16-scale), prob, state]
        self._queue = collections.deque()
        self._idx = 0
        self._last_over = -(10 ** 9)

    def _clamp_params(self):
        self._threshold = max(0.0, min(0.99, float(self._threshold)))
        self._grace = max(config.RNNOISE_MIN_GRACE_BLOCKS, int(self._grace))
        self._retro = max(0, min(config.RNNOISE_MAX_RETRO_BLOCKS, int(self._retro)))

    def set_params(self, threshold=None, grace_blocks=None, retro_blocks=None):
        if threshold is not None:
            self._threshold = threshold
        if grace_blocks is not None:
            self._grace = grace_blocks
        old_retro = self._retro
        if retro_blocks is not None:
            self._retro = retro_blocks
        self._clamp_params()
        # при уменьшении retro чистим очередь, иначе задержка не сократится
        if self._retro < old_retro:
            self._queue.clear()

    def process(self, frame):
        fs = self._frame_size
        # рабочий буфер в int16-масштабе, как требует RNNoise
        buf = array("f", frame[:fs]) if len(frame) >= fs else array("f", frame)
        for i in range(len(buf)):
            buf[i] *= 32767.0
        if len(buf) < fs:                       # добить нулями до кадра
            buf.extend(bytes(4 * (fs - len(buf))))
        ptr, _keep = _float_ptr(buf)            # _keep держит буфер живым
        prob = float(self._lib.rnnoise_process_frame(self._state, ptr, ptr))

        idx = self._idx
        self._idx += 1
        thr, grace, retro = self._threshold, self._grace, self._retro

        if prob >= thr:
            state = self._UNMUTED
            self._last_over = idx
        elif (idx - self._last_over) <= grace:
            state = self._UNMUTED
        else:
            state = self._MUTED

        self._queue.append([idx, buf, prob, state])

        # ретроактивный grace: открыть недавние заглушённые блоки перед речью
        if retro > 0 and prob >= thr:
            for b in reversed(self._queue):
                if (idx - b[0]) > retro:
                    break
                if b[3] == self._MUTED:
                    b[3] = self._UNMUTED

        # отдаём блок, отстающий на retro (retro=0 — сразу, без задержки)
        if len(self._queue) > retro:
            _, out_frames, out_prob, out_state = self._queue.popleft()
            if out_state == self._MUTED:
                return _zeros_f32(fs), 0.0
            inv = 1.0 / 32767.0
            for i in range(len(out_frames)):
                v = out_frames[i] * inv
                out_frames[i] = 1.0 if v > 1.0 else (-1.0 if v < -1.0 else v)
            return out_frames, out_prob
        return _zeros_f32(fs), 0.0

    def close(self):
        if getattr(self, "_state", None):
            self._lib.rnnoise_destroy(self._state)
            self._state = None


# ---------------------------------------------------------------------------
# Speex (лёгкий режим)
# ---------------------------------------------------------------------------
# ctl-запросы из speex_preprocess.h
_SPEEX_SET_DENOISE = 0
_SPEEX_SET_AGC = 2
_SPEEX_SET_VAD = 4
_SPEEX_SET_DEREVERB = 8
_SPEEX_SET_NOISE_SUPPRESS = 18


class SpeexSuppressor(BaseSuppressor):
    name = config.MODE_LIGHT
    label = "Лёгкий (Speex)"

    def __init__(self, dll_path=None, suppress_db=None,
                 frame_size=config.FRAME_SIZE, sample_rate=config.SAMPLE_RATE):
        dll_path = dll_path or config.SPEEX_DLL
        if suppress_db is None:
            suppress_db = config.SPEEX_NOISE_SUPPRESS_DB
        if not os.path.exists(dll_path):
            raise SuppressorError("Не найдена библиотека libspeexdsp.dll: %s" % dll_path)
        try:
            lib = ctypes.CDLL(dll_path)
        except OSError as exc:
            raise SuppressorError("Не удалось загрузить libspeexdsp.dll: %s" % exc)

        lib.speex_preprocess_state_init.argtypes = [ctypes.c_int, ctypes.c_int]
        lib.speex_preprocess_state_init.restype = ctypes.c_void_p
        lib.speex_preprocess_ctl.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
        lib.speex_preprocess_ctl.restype = ctypes.c_int
        lib.speex_preprocess_run.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int16)]
        lib.speex_preprocess_run.restype = ctypes.c_int
        lib.speex_preprocess_state_destroy.argtypes = [ctypes.c_void_p]

        self._lib = lib
        self._frame_size = frame_size
        self._state = lib.speex_preprocess_state_init(frame_size, sample_rate)
        if not self._state:
            raise SuppressorError("speex_preprocess_state_init вернул NULL")

        self._set_int(_SPEEX_SET_DENOISE, 1)
        self._set_int(_SPEEX_SET_NOISE_SUPPRESS, int(suppress_db))
        self._set_int(_SPEEX_SET_AGC, 0)
        self._set_int(_SPEEX_SET_VAD, 0)
        self._set_int(_SPEEX_SET_DEREVERB, 0)

    def _set_int(self, request, value):
        val = ctypes.c_int(int(value))
        self._lib.speex_preprocess_ctl(self._state, request, ctypes.byref(val))

    def set_suppress_db(self, suppress_db):
        self._set_int(_SPEEX_SET_NOISE_SUPPRESS, int(suppress_db))

    def process(self, frame):
        n = len(frame)
        pcm = array("h", bytes(2 * n))          # int16, n нулей
        for i in range(n):
            v = frame[i] * 32768.0
            if v > 32767.0:
                v = 32767.0
            elif v < -32768.0:
                v = -32768.0
            pcm[i] = int(v)                     # усечение к нулю, как astype(int16)
        ptr, _keep = _int16_ptr(pcm)            # _keep держит буфер живым
        vad = self._lib.speex_preprocess_run(self._state, ptr)
        inv = 1.0 / 32768.0
        out = array("f", bytes(4 * n))
        for i in range(n):
            out[i] = pcm[i] * inv
        return out, float(vad)

    def close(self):
        if getattr(self, "_state", None):
            self._lib.speex_preprocess_state_destroy(self._state)
            self._state = None


def create_suppressor(mode, rnn_threshold=None, rnn_grace=None, rnn_retro=None):
    """Фабрика: создаёт движок по имени режима. Бросает SuppressorError."""
    if mode == config.MODE_STRONG:
        return RNNoiseSuppressor(threshold=rnn_threshold, grace_blocks=rnn_grace,
                                 retro_blocks=rnn_retro)
    if mode == config.MODE_LIGHT:
        return SpeexSuppressor()
    raise SuppressorError("Неизвестный режим: %r" % mode)
