"""Compare complete DSP paths offline; no microphone or audio device is opened.

py -3.8 tools/benchmark_dsp.py --output build/dsp-results.json
--baseline-dir can contain saved engine.py and suppressors.py from before edits.
Without it, compare the current Python fallback with the native backend.
"""

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import statistics
import sys
import time
from array import array
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from noiseclean import dsp, suppressors
from noiseclean.audio import engine as engine_module


def load_source(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure(module, factory, mode, scenario, samples, frames):
    engine = module.AudioEngine()
    engine.set_metering_enabled(scenario['visible'])
    kwargs = {'rnn_threshold': 0.0} if mode == 'strong_open' else {}
    engine._suppressor = factory('light' if mode == 'light' else 'strong', **kwargs)
    engine._gain_lin = 10 ** (8 / 20.0)
    sr, ch = scenario['rate'], scenario['channels']
    engine._in_sr = engine._out_sr = sr
    engine._in_channels = ch
    engine._in_block = sr // 100
    if sr != 48000:
        engine._rs_in = module._LinResampler(sr, 48000)
        engine._rs_out = module._LinResampler(48000, sr)
    count = [0]
    digest = hashlib.sha256()
    monitor_digest = hashlib.sha256()

    class Input:
        def read(self, _frames):
            block = samples[count[0] % len(samples)]
            count[0] += 1
            if count[0] == frames:
                engine._stop.set()
            return memoryview(block), False

    class Output:
        def write(self, data):
            digest.update(data.tobytes())
            if scenario['visible'] and count[0] % 3 == 0:
                engine.get_levels()

    class Monitor:
        def __init__(self):
            self.ring = module._MonitorRing(2)
            self.raw = bytearray(480 * 2 * 4)

        def push(self, data):
            self.ring.push(data)
            self.ring.callback(self.raw, 480, None, None)
            monitor_digest.update(self.raw)

    if scenario['aux']:
        engine._monitor_enabled = True
        engine._mon_ring = Monitor()
        engine._rec_active = True
        engine._rec_target = (frames + 100) * 480
    engine._in, engine._out = Input(), Output()
    engine._open_streams = lambda: None
    engine._close_streams = lambda: None
    try:
        started = time.process_time()
        engine._worker()
        elapsed = time.process_time() - started
        recording = hashlib.sha256()
        for frame in engine._rec_frames:
            recording.update(frame.tobytes())
        return elapsed, (digest.hexdigest(), monitor_digest.hexdigest(),
                         recording.hexdigest())
    finally:
        engine._suppressor.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames', type=int, default=2000)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--baseline-dir', type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    if args.frames < 1 or args.repeats < 1:
        parser.error('--frames and --repeats must be positive')
    native = dsp._native
    if native is None:
        parser.error('Native backend is not loaded; build dsp_accel.dll first')
    before_engine, before_suppressors = engine_module, suppressors
    source_hashes = {}
    if args.baseline_dir:
        before_suppressors = load_source('noiseclean.baseline_suppressors',
                                        args.baseline_dir / 'suppressors.py')
        before_engine = load_source('noiseclean.audio.baseline_engine',
                                    args.baseline_dir / 'engine.py')
        source_hashes = {name: hashlib.sha256((args.baseline_dir / name).read_bytes()).hexdigest()
                         for name in ('engine.py', 'suppressors.py')}
    scenarios = {
        '48k_visible': {'rate': 48000, 'channels': 1, 'visible': True, 'aux': False},
        '48k_hidden': {'rate': 48000, 'channels': 1, 'visible': False, 'aux': False},
        '44k1_hidden': {'rate': 44100, 'channels': 2, 'visible': False, 'aux': False},
        '48k_monitor_record': {'rate': 48000, 'channels': 1, 'visible': False, 'aux': True},
    }
    results = {}
    for scenario_name, scenario in scenarios.items():
        block = scenario['rate'] // 100
        samples = []
        for k in range(80):
            mono = array('f', (0.08 * math.sin((k * block + i) * .057)
                               + .015 * math.sin(i * .7) for i in range(block)))
            samples.append(engine_module._to_channels(mono, scenario['channels']))
        for mode in ('light', 'strong', 'strong_open'):
            times = {'before': [], 'after': []}
            expected_hashes = None
            for repeat in range(args.repeats):
                # Alternate ordering to reduce warmup/frequency bias.
                order = ('before', 'after') if repeat % 2 == 0 else ('after', 'before')
                for version in order:
                    old = version == 'before'
                    with patch.object(dsp, '_native', None if old else native):
                        elapsed, hashes = measure(
                            before_engine if old else engine_module,
                            (before_suppressors if old else suppressors).create_suppressor,
                            mode, scenario, samples, args.frames)
                    times[version].append(elapsed)
                    if expected_hashes is None:
                        expected_hashes = hashes
                    if hashes != expected_hashes:
                        raise RuntimeError('Audio/monitor/recording mismatch: ' + scenario_name + '/' + mode)
            before, after = statistics.median(times['before']), statistics.median(times['after'])
            results[scenario_name + '/' + mode] = {
                'before_cpu_seconds': before, 'after_cpu_seconds': after,
                'reduction_percent': round((1 - after / before) * 100, 1) if before else None,
                'audio_sha256': expected_hashes[0], 'monitor_sha256': expected_hashes[1],
                'recording_sha256': expected_hashes[2], 'identical': True,
            }
    report = {'python': platform.python_version(), 'audio_seconds_per_run': args.frames / 100,
              'repeats': args.repeats, 'baseline_sources_sha256': source_hashes,
              'native_dll_bytes': (ROOT / 'noiseclean/libs/dsp_accel.dll').stat().st_size,
              'results': results}
    encoded = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded + '\n', encoding='utf-8')
    print(encoded)


if __name__ == '__main__':
    main()
