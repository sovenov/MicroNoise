"""Аудиодвижок: захват с микрофона -> шумоподавление -> виртуальный микрофон.

Критический путь (микрофон -> обработка -> виртуальный кабель) выполняется в
рабочем потоке на блокирующих потоках sounddevice. У виртуального кабеля нет
собственного аппаратного тактового генератора, поэтому блокирующая запись в
него стабильна и не «уплывает».

Локальный мониторинг ("прослушивать свой микрофон") развязан через небольшой
кольцевой буфер и callback-поток вывода: возможные рассинхроны тактовых частот
дают лишь редкие микропровалы в прослушке и НИКОГДА не тормозят основной путь.
"""

import collections
import math
import threading
import wave

import numpy as np
import sounddevice as sd

from .. import config
from ..suppressors import (PassthroughSuppressor, RNNoiseSuppressor,
                           SuppressorError, create_suppressor)


def _level_percent(samples):
    """RMS сигнала -> уровень 0..100 % (диапазон -60..0 dBFS)."""
    if samples.size == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(samples.astype(np.float64) ** 2)))
    if rms <= 1e-7:
        return 0.0
    dbfs = 20.0 * math.log10(rms)
    pct = (dbfs + 60.0) / 60.0 * 100.0
    return max(0.0, min(100.0, pct))


def _to_channels(mono, channels):
    if channels == 1:
        return mono.reshape(-1, 1)
    return np.repeat(mono.reshape(-1, 1), channels, axis=1)


class _MonitorRing:
    """Потокобезопасный кольцевой буфер кадров для callback-вывода мониторинга."""

    def __init__(self, channels, max_frames=8):
        self.channels = channels
        self._q = collections.deque(maxlen=max_frames)
        self._lock = threading.Lock()

    def push(self, mono):
        buf = _to_channels(mono, self.channels).astype(np.float32)
        with self._lock:
            self._q.append(buf)

    def callback(self, outdata, frames, time_info, status):  # noqa: D401
        with self._lock:
            buf = self._q.popleft() if self._q else None
        if buf is None or len(buf) != frames:
            outdata.fill(0.0)
        else:
            outdata[:] = buf


class AudioEngine:
    def __init__(self, on_error=None, on_status=None):
        self._on_error = on_error
        self._on_status = on_status

        # выбор устройств
        self._input_idx = None
        self._output_idx = None
        self._monitor_idx = None

        # параметры обработки
        self._mode = config.MODE_LIGHT
        self._gain_lin = 1.0
        self._monitor_enabled = False

        # параметры VAD-гейта RNNoise (интенсивный режим)
        self._rnn_threshold = config.RNNOISE_VAD_THRESHOLD
        self._rnn_grace = config.RNNOISE_VAD_GRACE_BLOCKS
        self._rnn_retro = config.RNNOISE_RETRO_GRACE_BLOCKS

        # выполнение
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None
        self._running = False
        self._suppressor = None

        # потоки sounddevice
        self._in = None
        self._out = None
        self._mon = None
        self._mon_ring = None
        self._in_channels = 1
        self._out_channels = 2

        # уровни сигналов (публикуются для UI)
        self._in_level = 0.0
        self._out_level = 0.0
        self._speech = 0.0

        # запись
        self._rec_active = False
        self._rec_frames = []
        self._rec_count = 0
        self._rec_target = 0
        self._rec_done_cb = None
        self._recording = None

        # воспроизведение тестовой записи
        self._play_thread = None

    # ------------------------------------------------------------------ config
    def configure(self, input_idx=None, output_idx=None, monitor_idx=None,
                  mode=None, gain_db=None, monitor_enabled=None):
        if input_idx is not None:
            self._input_idx = input_idx
        if output_idx is not None:
            self._output_idx = output_idx
        if monitor_idx is not None:
            self._monitor_idx = monitor_idx
        if mode is not None:
            self._mode = mode
        if gain_db is not None:
            self._gain_lin = 10.0 ** (gain_db / 20.0)
        if monitor_enabled is not None:
            self._monitor_enabled = monitor_enabled

    def _build_suppressor(self, mode):
        try:
            return create_suppressor(mode, rnn_threshold=self._rnn_threshold,
                                     rnn_grace=self._rnn_grace,
                                     rnn_retro=self._rnn_retro)
        except SuppressorError as exc:
            self._notify_error(str(exc))
            return PassthroughSuppressor()

    def set_mode(self, mode):
        self._mode = mode
        if not self._running:
            return
        new = self._build_suppressor(mode)
        with self._lock:
            old = self._suppressor
            self._suppressor = new
        if old is not None:
            old.close()

    def set_rnnoise_params(self, threshold=None, grace=None, retro=None):
        if threshold is not None:
            self._rnn_threshold = threshold
        if grace is not None:
            self._rnn_grace = grace
        if retro is not None:
            self._rnn_retro = retro
        with self._lock:
            supp = self._suppressor
        if isinstance(supp, RNNoiseSuppressor):
            supp.set_params(threshold=threshold, grace_blocks=grace,
                            retro_blocks=retro)

    def set_gain_db(self, gain_db):
        self._gain_lin = 10.0 ** (gain_db / 20.0)

    def set_monitor_enabled(self, enabled):
        enabled = bool(enabled)
        if enabled == self._monitor_enabled:
            return
        self._monitor_enabled = enabled
        # монитор-устройство открываем/закрываем только по необходимости
        self._restart_if_running()

    def set_input_device(self, index):
        self._input_idx = index
        self._restart_if_running()

    def set_output_device(self, index):
        self._output_idx = index
        self._restart_if_running()

    def set_monitor_device(self, index):
        self._monitor_idx = index
        self._restart_if_running()

    # ------------------------------------------------------------------ status
    def is_running(self):
        return self._running

    def get_levels(self):
        return self._in_level, self._out_level, self._speech

    def current_mode(self):
        with self._lock:
            supp = self._suppressor
        if supp is not None:
            return supp.name
        return self._mode

    # ----------------------------------------------------------------- control
    def start(self):
        if self._running:
            return
        self._suppressor = self._build_suppressor(self._mode)
        self._stop.clear()
        self._thread = threading.Thread(target=self._worker, name="audio-engine",
                                        daemon=True)
        self._running = True
        self._thread.start()

    def stop(self):
        if not self._running:
            return
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=2.0)
        self._thread = None
        self._running = False
        if self._suppressor is not None:
            self._suppressor.close()
            self._suppressor = None
        self._in_level = self._out_level = self._speech = 0.0

    def shutdown(self):
        self.stop_playback()
        self.stop()

    def _restart_if_running(self):
        if self._running:
            self.stop()
            self.start()

    # ------------------------------------------------------------------ worker
    def _open_streams(self):
        sr = config.SAMPLE_RATE
        fs = config.FRAME_SIZE

        in_info = sd.query_devices(self._input_idx)
        self._in_channels = 1
        try:
            self._in = sd.InputStream(samplerate=sr, blocksize=fs,
                                      device=self._input_idx, channels=1,
                                      dtype="float32")
        except Exception:
            self._in_channels = max(1, int(in_info["max_input_channels"]))
            self._in = sd.InputStream(samplerate=sr, blocksize=fs,
                                      device=self._input_idx,
                                      channels=self._in_channels, dtype="float32")

        out_info = sd.query_devices(self._output_idx)
        self._out_channels = min(2, max(1, int(out_info["max_output_channels"])))
        self._out = sd.OutputStream(samplerate=sr, blocksize=fs,
                                    device=self._output_idx,
                                    channels=self._out_channels, dtype="float32")

        self._in.start()
        self._out.start()

        # мониторинг — опционально, ошибки не критичны
        self._mon = None
        self._mon_ring = None
        if self._monitor_enabled and self._monitor_idx is not None:
            try:
                mon_info = sd.query_devices(self._monitor_idx)
                mch = min(2, max(1, int(mon_info["max_output_channels"])))
                self._mon_ring = _MonitorRing(mch)
                self._mon = sd.OutputStream(samplerate=sr, blocksize=fs,
                                            device=self._monitor_idx, channels=mch,
                                            dtype="float32",
                                            callback=self._mon_ring.callback)
                self._mon.start()
            except Exception:
                self._mon = None
                self._mon_ring = None

    def _close_streams(self):
        for stream in (self._in, self._out, self._mon):
            if stream is not None:
                try:
                    stream.stop()
                    stream.close()
                except Exception:
                    pass
        self._in = self._out = self._mon = None
        self._mon_ring = None

    def _worker(self):
        fs = config.FRAME_SIZE
        try:
            self._open_streams()
        except Exception as exc:
            self._running = False
            self._notify_error("Не удалось открыть аудио-устройства: %s" % exc)
            self._close_streams()
            return

        self._notify_status("running")
        try:
            while not self._stop.is_set():
                try:
                    data, _overflowed = self._in.read(fs)
                except sd.PortAudioError as exc:
                    self._notify_error("Ошибка чтения с микрофона: %s" % exc)
                    break

                mono = np.ascontiguousarray(data[:, 0], dtype=np.float32)
                in_level = _level_percent(mono)

                with self._lock:
                    supp = self._suppressor
                    gain = self._gain_lin
                monitor_on = self._monitor_enabled

                try:
                    out, prob = supp.process(mono)
                except Exception:
                    out, prob = mono.copy(), 0.0

                if gain != 1.0:
                    out = out * gain
                np.clip(out, -1.0, 1.0, out=out)
                out_level = _level_percent(out)

                try:
                    self._out.write(_to_channels(out, self._out_channels))
                except sd.PortAudioError as exc:
                    self._notify_error("Ошибка вывода в виртуальный микрофон: %s" % exc)
                    break

                if monitor_on and self._mon_ring is not None:
                    self._mon_ring.push(out * config.MONITOR_VOLUME)

                if self._rec_active:
                    self._rec_frames.append((out * 32767.0).astype(np.int16))
                    self._rec_count += len(out)
                    if self._rec_count >= self._rec_target:
                        self._finalize_recording()

                self._in_level = in_level
                self._out_level = out_level
                self._speech = prob
        finally:
            self._running = False
            self._close_streams()
            self._in_level = self._out_level = self._speech = 0.0
            self._notify_status("stopped")

    # --------------------------------------------------------------- recording
    def start_recording(self, seconds=config.RECORD_SECONDS, on_done=None):
        if not self._running:
            return False
        with self._lock:
            self._rec_frames = []
            self._rec_count = 0
            self._rec_target = int(seconds * config.SAMPLE_RATE)
            self._rec_done_cb = on_done
            self._recording = None
            self._rec_active = True
        return True

    def cancel_recording(self):
        self._rec_active = False
        self._rec_frames = []
        self._rec_count = 0

    def stop_recording(self):
        """Досрочно завершить запись тем, что уже захвачено."""
        if self._rec_active:
            self._finalize_recording()

    def recording_progress(self):
        if self._rec_active and self._rec_target:
            return min(1.0, self._rec_count / float(self._rec_target))
        return 0.0

    def _finalize_recording(self):
        self._rec_active = False
        frames = self._rec_frames
        self._rec_frames = []
        if frames:
            self._recording = np.concatenate(frames)
        else:
            self._recording = np.zeros(0, dtype=np.int16)
        cb = self._rec_done_cb
        self._rec_done_cb = None
        if cb is not None:
            cb()

    def is_recording(self):
        return self._rec_active

    def has_recording(self):
        return self._recording is not None and len(self._recording) > 0

    def save_recording(self, path):
        if not self.has_recording():
            return False
        with wave.open(path, "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(config.SAMPLE_RATE)
            wav.writeframes(self._recording.tobytes())
        return True

    # --------------------------------------------------------------- playback
    def play_recording(self, device=None, on_done=None):
        if not self.has_recording():
            return False
        dev = device if device is not None else self._monitor_idx
        data = self._recording.astype(np.float32) / 32768.0

        def _run():
            try:
                sd.play(data, config.SAMPLE_RATE, device=dev)
                sd.wait()
            except Exception:
                pass
            if on_done is not None:
                on_done()

        self._play_thread = threading.Thread(target=_run, daemon=True)
        self._play_thread.start()
        return True

    def stop_playback(self):
        try:
            sd.stop()
        except Exception:
            pass

    # ---------------------------------------------------------------- helpers
    def _notify_error(self, message):
        if self._on_error is not None:
            self._on_error(message)

    def _notify_status(self, state):
        if self._on_status is not None:
            self._on_status(state)
