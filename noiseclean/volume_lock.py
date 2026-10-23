"""Periodic system-volume restoration, independent of the audio/UI timers."""

import threading

from .audio.volume import WindowsVolumes


def _bounded_int(value, default, low, high):
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def normalize_settings(value):
    value = value if isinstance(value, dict) else {}
    extras = []
    seen = set()
    saved_extras = value.get('extra_inputs', [])
    if isinstance(saved_extras, list):
        for item in saved_extras[:64]:
            if not isinstance(item, dict):
                continue
            endpoint = item.get('endpoint_id')
            if not isinstance(endpoint, str) or not endpoint or len(endpoint) > 512 or endpoint in seen:
                continue
            name = item.get('name', endpoint)
            extras.append({'endpoint_id': endpoint,
                           'name': name[:512] if isinstance(name, str) else endpoint,
                           'enabled': item.get('enabled') is True,
                           'level': _bounded_int(item.get('level'), 100, 0, 100)})
            seen.add(endpoint)
    return {
        'enabled': value.get('enabled') is True,
        'input_enabled': value.get('input_enabled', True) is True,
        'output_enabled': value.get('output_enabled', True) is True,
        'input_level': _bounded_int(value.get('input_level'), 100, 0, 100),
        'output_level': _bounded_int(value.get('output_level'), 100, 0, 100),
        'interval_seconds': _bounded_int(value.get('interval_seconds'), 5, 1, 300),
        'extra_inputs': extras,
    }


class VolumeKeeper:
    def __init__(self, on_status=None, backend_factory=WindowsVolumes):
        self._on_status = on_status
        self._backend_factory = backend_factory
        self._lock = threading.RLock()
        self._wake = threading.Event()
        self._targets = ()
        self._interval = 5
        self._generation = 0
        self._closed = False
        self._thread = None
        self._last_status = None

    def configure(self, targets, interval):
        """An empty target list disables the keeper without polling."""
        targets = tuple((str(endpoint), int(level)) for endpoint, level in targets)
        if any(not endpoint or not 0 <= level <= 100 for endpoint, level in targets):
            raise ValueError('Invalid endpoint or volume')
        if not 1 <= interval <= 300:
            raise ValueError('Interval must be in 1..300 seconds')
        with self._lock:
            if self._closed:
                return
            self._targets, self._interval = targets, interval
            self._generation += 1
            generation = self._generation
            if targets and self._thread is None:
                self._thread = threading.Thread(target=self._run, daemon=True,
                                                name='MicroNoise-volume')
                self._thread.start()
        self._wake.set()
        if not targets:
            self._publish({'state': 'off'}, generation)

    def close(self):
        with self._lock:
            self._closed = True
            self._targets = ()
            self._generation += 1
        self._wake.set()
        if self._thread is not None:
            self._thread.join(timeout=1.5)

    def _publish(self, status, generation):
        with self._lock:
            if self._closed or generation != self._generation:
                return
            if status != self._last_status:
                self._last_status = status
                if self._on_status:
                    self._on_status(status)

    def _check_once(self, targets, generation):
        errors = []
        with self._backend_factory() as backend:
            for endpoint, level in targets:
                try:
                    with backend.open(endpoint) as volume:
                        current = volume.get()
                        if abs(current - level / 100.0) > 0.005:
                            # A device change/disable invalidates work already in flight.
                            with self._lock:
                                if self._closed or generation != self._generation:
                                    return None
                                volume.set(level / 100.0)
                except Exception as exc:
                    errors.append(str(exc))
        return {'state': 'error', 'message': '; '.join(errors)} if errors else {'state': 'on'}

    def _run(self):
        delay = None
        while True:
            self._wake.wait(delay)
            self._wake.clear()
            with self._lock:
                if self._closed:
                    return
                targets, interval, generation = self._targets, self._interval, self._generation
            if not targets:
                delay = None
                continue
            try:
                status = self._check_once(targets, generation)
            except Exception as exc:
                status = {'state': 'error', 'message': str(exc)}
            if status:
                self._publish(status, generation)
            delay = interval
