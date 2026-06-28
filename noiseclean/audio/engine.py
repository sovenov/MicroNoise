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
import os
import threading
import wave

import numpy as np
import sounddevice as sd

from .. import config
from ..suppressors import (PassthroughSuppressor, RNNoiseSuppressor,
                           SuppressorError, create_suppressor)

# Сколько секунд «ровной тишины» на входе ждать, прежде чем переключить host API
# (актуально только для VirtualBox, где WASAPI-захват отдаёт нули). Цифровая
# тишина видна с первых буферов, поэтому окно короткое — без задержки на старте.
_SILENCE_PROBE_SEC = 0.4


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


class _LinResampler:
    """Потоковый линейный ресемплер (сохраняет фазу между блоками).

    Нужен, когда устройство не поддерживает 48 кГц (например микрофон 44100 Гц):
    вход ресемплится до 48 кГц для обработки (RNNoise работает только на 48 кГц),
    а выход — обратно к частоте устройства. Фаза переносится между вызовами,
    поэтому на стыках блоков нет щелчков; длительного дрейфа длины тоже нет.
    """

    def __init__(self, src_sr, dst_sr):
        self._step = float(src_sr) / float(dst_sr)  # вход. сэмплов на 1 выходной
        self._pos = 0.0      # позиция чтения внутри буфера (с учётом prev)
        self._prev = None    # последний сэмпл предыдущего блока (для стыковки)

    def process(self, x):
        x = np.asarray(x, dtype=np.float32)
        if x.size == 0:
            return x
        if self._prev is None:
            self._prev = x[0]
        buf = np.empty(x.size + 1, dtype=np.float32)
        buf[0] = self._prev
        buf[1:] = x
        last = buf.size - 1
        if self._pos > last:
            self._pos -= last
            self._prev = buf[last]
            return np.zeros(0, dtype=np.float32)
        n = int(math.floor((last - self._pos) / self._step)) + 1
        if n < 1:
            self._pos -= last
            self._prev = buf[last]
            return np.zeros(0, dtype=np.float32)
        idx = self._pos + np.arange(n, dtype=np.float64) * self._step
        i0 = np.floor(idx).astype(np.int64)
        frac = (idx - i0).astype(np.float32)
        i1 = np.minimum(i0 + 1, last)
        out = (buf[i0] * (1.0 - frac) + buf[i1] * frac).astype(np.float32)
        self._pos = (self._pos + n * self._step) - last
        self._prev = buf[last]
        return out


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

        # частоты устройств и ресемплинг до/от частоты обработки (48 кГц)
        self._in_sr = config.SAMPLE_RATE
        self._out_sr = config.SAMPLE_RATE
        self._in_block = config.FRAME_SIZE
        self._rs_in = None      # ресемплер вход.частота -> 48 кГц
        self._rs_out = None     # ресемплер 48 кГц -> вых.частота
        self._proc_buf = np.zeros(0, dtype=np.float32)  # накопитель кадров 48 кГц
        self._in_attempts = []  # список вариантов открытия входа
        self._in_pos = 0        # текущий выбранный вариант

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
    @staticmethod
    def _candidate_rates(info, proc_sr):
        """Список частот для попытки открытия: 48 кГц, частота устройства, типовые."""
        cands = [proc_sr]
        try:
            d = int(round(float(info.get("default_samplerate") or 0)))
            if d > 0:
                cands.append(d)
        except Exception:
            pass
        cands += [48000, 44100, 32000, 16000]
        out = []
        seen = set()
        for r in cands:
            if r and r not in seen:
                seen.add(r)
                out.append(r)
        return out

    @staticmethod
    def _hostapi_name(hostapi_index):
        try:
            return sd.query_hostapis()[hostapi_index]["name"].lower()
        except Exception:
            return ""

    @staticmethod
    def _names_match(a, b):
        # Имена устройства под разными host API совпадают по началу (MME режет до 31).
        a = (a or "").strip().lower()
        b = (b or "").strip().lower()
        if not a or not b:
            return False
        k = min(len(a), len(b), 28)
        return a[:k] == b[:k]

    @staticmethod
    def _wasapi_autoconvert():
        # Встроенный ресемплинг WASAPI (shared): позволяет открыть устройство на
        # 48 кГц, даже если его микшер на 44100 — иначе PaErrorCode -9997.
        try:
            return sd.WasapiSettings(auto_convert=True)
        except Exception:
            return None

    def _alt_devices(self, idx, want_input):
        """То же физическое устройство под другими host API (для программного SRC)."""
        try:
            info = sd.query_devices(idx)
            target = info["name"]
            cur_api = info["hostapi"]
            apis = sd.query_hostapis()
            devs = sd.query_devices()

            def rank(api_i):
                n = apis[api_i]["name"].lower()
                if "directsound" in n:
                    return 0      # DirectSound умеет SRC
                if "mme" in n:
                    return 1      # MME умеет SRC
                if "wasapi" in n:
                    return 3
                return 4          # WDM-KS — последним (часто эксклюзив)

            res = []
            for i, d in enumerate(devs):
                if i == idx or d["hostapi"] == cur_api:
                    continue
                ch = (d["max_input_channels"] if want_input
                      else d["max_output_channels"])
                if ch <= 0:
                    continue
                if self._names_match(d["name"], target):
                    res.append(i)
            res.sort(key=lambda i: rank(devs[i]["hostapi"]))
            return res
        except Exception:
            return []

    def _attempts(self, idx, want_input):
        """Попытки открытия по порядку: (device_index, samplerate, extra_settings)."""
        proc = config.SAMPLE_RATE
        info = sd.query_devices(idx)
        out = []
        if "wasapi" in self._hostapi_name(info.get("hostapi", -1)):
            ws = self._wasapi_autoconvert()
            if ws is not None:
                out.append((idx, proc, ws))  # WASAPI auto-convert -> сразу 48 кГц
                try:
                    d = int(round(float(info.get("default_samplerate") or 0)))
                    if d and d != proc:
                        out.append((idx, d, ws))
                except Exception:
                    pass
        # обычные попытки на самом устройстве (его частоты)
        for sr in self._candidate_rates(info, proc):
            out.append((idx, sr, None))
        # то же устройство под host API с программным SRC (DirectSound, MME)
        for alt in self._alt_devices(idx, want_input):
            try:
                ainfo = sd.query_devices(alt)
                ad = int(round(float(ainfo.get("default_samplerate") or 0)))
            except Exception:
                ad = 0
            out.append((alt, proc, None))
            if ad and ad != proc:
                out.append((alt, ad, None))
        return out

    def _describe_dev(self, attempt):
        dev, sr, extra = attempt
        try:
            info = sd.query_devices(dev)
            name = info.get("name", str(dev))
            api = self._hostapi_name(info.get("hostapi", -1))
        except Exception:
            name, api = str(dev), "?"
        ac = bool(getattr(extra, "auto_convert", False))
        return "'%s' [%s] @%dHz%s" % (name, api, sr,
                                      " auto_convert" if ac else "")

    def _open_attempt_input(self, attempts, start):
        """Открыть первый рабочий вариант входа начиная с индекса start."""
        last_exc = None
        for pos in range(start, len(attempts)):
            dev, sr, extra = attempts[pos]
            try:
                max_ch = max(1, int(sd.query_devices(dev)["max_input_channels"]))
            except Exception:
                max_ch = 1
            block = max(1, int(round(sr / 100.0)))
            chans = (1, max_ch) if max_ch > 1 else (1,)
            for ch in chans:
                try:
                    st = sd.InputStream(samplerate=sr, blocksize=block, device=dev,
                                        channels=ch, dtype="float32",
                                        extra_settings=extra)
                    return st, sr, ch, pos
                except Exception as exc:
                    last_exc = exc
        raise last_exc if last_exc else RuntimeError("input open failed")

    def _switch_input(self):
        """Переоткрыть вход на следующем варианте с ДРУГИМ устройством/host API.

        Вызывается, если текущий вход отдаёт цифровую тишину (типично для
        захвата через WASAPI в VirtualBox) — пробуем DirectSound/MME и т.д.
        Возвращает True, если переключились.
        """
        if not self._in_attempts:
            return False
        cur_dev = self._in_attempts[self._in_pos][0]
        nxt = None
        for p in range(self._in_pos + 1, len(self._in_attempts)):
            if self._in_attempts[p][0] != cur_dev:
                nxt = p
                break
        if nxt is None:
            return False
        try:
            self._in.stop()
            self._in.close()
        except Exception:
            pass
        try:
            st, sr, ch, pos = self._open_attempt_input(self._in_attempts, nxt)
        except Exception as exc:
            self._log("switch_input failed: %s" % exc)
            return False
        self._in, self._in_sr, self._in_channels, self._in_pos = st, sr, ch, pos
        self._in_block = max(1, int(round(self._in_sr / 100.0)))
        self._rs_in = (_LinResampler(self._in_sr, config.SAMPLE_RATE)
                       if self._in_sr != config.SAMPLE_RATE else None)
        self._proc_buf = np.zeros(0, dtype=np.float32)
        try:
            self._in.start()
        except Exception as exc:
            self._log("switch_input start failed: %s" % exc)
            return False
        self._log("switched input -> %s" % self._describe_dev(self._in_attempts[pos]))
        return True

    def _open_output(self, idx):
        last_exc = None
        for dev, sr, extra in self._attempts(idx, False):
            try:
                ch = min(2, max(1, int(sd.query_devices(dev)["max_output_channels"])))
            except Exception:
                ch = 2
            try:
                st = sd.OutputStream(samplerate=sr, blocksize=0, device=dev,
                                     channels=ch, dtype="float32",
                                     extra_settings=extra)
                return st, sr, ch
            except Exception as exc:
                last_exc = exc
        raise last_exc if last_exc else RuntimeError("output open failed")

    def _open_streams(self):
        proc_sr = config.SAMPLE_RATE
        fs = config.FRAME_SIZE

        self._log("=== open streams: in_idx=%s out_idx=%s ==="
                  % (self._input_idx, self._output_idx))

        # Открываем на частоте/host API, которые устройство РЕАЛЬНО поддерживает.
        # WASAPI -> auto-convert на 48 кГц; иначе подбор частоты + ресемплинг.
        self._in_attempts = self._attempts(self._input_idx, True)
        self._in, self._in_sr, self._in_channels, self._in_pos = \
            self._open_attempt_input(self._in_attempts, 0)
        self._in_block = max(1, int(round(self._in_sr / 100.0)))
        self._log("input  -> %s ch=%d"
                  % (self._describe_dev(self._in_attempts[self._in_pos]),
                     self._in_channels))

        self._out, self._out_sr, self._out_channels = self._open_output(
            self._output_idx)
        self._log("output -> idx=%s @%dHz ch=%d"
                  % (self._output_idx, self._out_sr, self._out_channels))

        self._rs_in = (_LinResampler(self._in_sr, proc_sr)
                       if self._in_sr != proc_sr else None)
        self._rs_out = (_LinResampler(proc_sr, self._out_sr)
                        if self._out_sr != proc_sr else None)
        self._proc_buf = np.zeros(0, dtype=np.float32)

        self._in.start()
        self._out.start()

        # мониторинг — опционально, на частоте обработки (48 кГц), ошибки не критичны
        self._mon = None
        self._mon_ring = None
        if self._monitor_enabled and self._monitor_idx is not None:
            try:
                mon_info = sd.query_devices(self._monitor_idx)
                mch = min(2, max(1, int(mon_info["max_output_channels"])))
                self._mon_ring = _MonitorRing(mch)
                self._mon = sd.OutputStream(samplerate=proc_sr, blocksize=fs,
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
        # Детектор «цифровой тишины» на входе (типично для захвата через WASAPI
        # в VirtualBox): если выбранный путь ~2 c отдаёт ровно нули — пробуем
        # следующий host API (DirectSound/MME). Проверяем по СЫРОЙ амплитуде,
        # чтобы тихий, но реальный микрофон не вызывал ложного переключения.
        probe_active = len(self._in_attempts) > 1
        probe_amp = 0.0
        probe_samples = 0
        probe_limit = int(_SILENCE_PROBE_SEC * self._in_sr)
        try:
            while not self._stop.is_set():
                try:
                    data, _overflowed = self._in.read(self._in_block)
                except sd.PortAudioError as exc:
                    self._notify_error("Ошибка чтения с микрофона: %s" % exc)
                    break

                mono = np.ascontiguousarray(data[:, 0], dtype=np.float32)
                in_level = _level_percent(mono)

                if probe_active:
                    if mono.size:
                        amp = float(np.max(np.abs(mono)))
                        if amp > probe_amp:
                            probe_amp = amp
                    probe_samples += mono.size
                    if probe_amp > 1e-5:
                        probe_active = False
                        self._log("input audio OK (peak_amp=%.6f) on %s"
                                  % (probe_amp, self._describe_dev(
                                      self._in_attempts[self._in_pos])))
                    elif probe_samples >= probe_limit:
                        self._log("input SILENT (peak_amp=%.6f) on %s -> next API"
                                  % (probe_amp, self._describe_dev(
                                      self._in_attempts[self._in_pos])))
                        if self._switch_input():
                            probe_amp = 0.0
                            probe_samples = 0
                            probe_limit = int(_SILENCE_PROBE_SEC * self._in_sr)
                            continue
                        probe_active = False
                        self._log("no more input candidates (likely VM/host "
                                  "capture limitation)")

                with self._lock:
                    supp = self._suppressor
                    gain = self._gain_lin
                monitor_on = self._monitor_enabled

                # к частоте обработки (48 кГц) и накопление до кадров по 480
                sig = self._rs_in.process(mono) if self._rs_in is not None else mono
                if self._proc_buf.size:
                    self._proc_buf = np.concatenate((self._proc_buf, sig))
                else:
                    self._proc_buf = np.ascontiguousarray(sig)

                out_parts = []
                out_level = self._out_level
                last_prob = self._speech
                while self._proc_buf.size >= fs:
                    frame = np.ascontiguousarray(self._proc_buf[:fs])
                    self._proc_buf = self._proc_buf[fs:]
                    try:
                        out, prob = supp.process(frame)
                    except Exception:
                        out, prob = frame.copy(), 0.0
                    if gain != 1.0:
                        out = out * gain
                    np.clip(out, -1.0, 1.0, out=out)
                    out_level = _level_percent(out)
                    last_prob = prob
                    out_parts.append(out)

                    if monitor_on and self._mon_ring is not None:
                        self._mon_ring.push(out * config.MONITOR_VOLUME)
                    if self._rec_active:
                        self._rec_frames.append((out * 32767.0).astype(np.int16))
                        self._rec_count += len(out)
                        if self._rec_count >= self._rec_target:
                            self._finalize_recording()

                if out_parts:
                    proc_out = (out_parts[0] if len(out_parts) == 1
                                else np.concatenate(out_parts))
                    snd = (self._rs_out.process(proc_out)
                           if self._rs_out is not None else proc_out)
                    if snd.size:
                        try:
                            self._out.write(_to_channels(snd, self._out_channels))
                        except sd.PortAudioError as exc:
                            self._notify_error(
                                "Ошибка вывода в виртуальный микрофон: %s" % exc)
                            break

                self._in_level = in_level
                self._out_level = out_level
                self._speech = last_prob
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
    def _log(self, msg):
        """Диагностический лог в %APPDATA%\\MicroNoise\\engine.log (для поддержки)."""
        try:
            import datetime
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            path = os.path.join(base, "MicroNoise", "engine.log")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(path, "a", encoding="utf-8") as f:
                f.write("%s  %s\n" % (stamp, msg))
        except Exception:
            pass

    def _notify_error(self, message):
        if self._on_error is not None:
            self._on_error(message)

    def _notify_status(self, state):
        if self._on_status is not None:
            self._on_status(state)
