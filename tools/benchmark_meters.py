"""Offline CPU benchmark: synthetic audio, real suppressor DLLs, no devices.

py -3.8 tools/benchmark_meters.py
Use --engine-source path/to/old_engine.py to compare a saved engine version.
The UI is simulated at about 30 Hz; Canvas rendering and device I/O are excluded.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import statistics
import sys
import time
from array import array
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from noiseclean.audio.engine import AudioEngine
from noiseclean.suppressors import create_suppressor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames', type=int, default=6000)
    parser.add_argument('--repeats', type=int, default=4)
    parser.add_argument('--engine-source', type=Path)
    args = parser.parse_args()
    if args.frames < 1 or args.repeats < 1:
        parser.error('--frames and --repeats must be positive')
    engine_type = AudioEngine
    if args.engine_source:
        spec = importlib.util.spec_from_file_location(
            'noiseclean.audio.benchmark_engine', args.engine_source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        engine_type = module.AudioEngine

    samples = [array('f', (0.08 * math.sin((k * 480 + i) * 0.057)
                          + 0.015 * math.sin(i * 0.7) for i in range(480)))
               for k in range(80)]
    results = {}
    for mode in ('light', 'strong'):
        for visible in (True, False):
            times = []
            for _ in range(args.repeats):
                engine = engine_type()
                if hasattr(engine, 'set_metering_enabled'):
                    engine.set_metering_enabled(visible)
                engine._suppressor = create_suppressor(mode)
                engine._gain_lin = 2.51188643150958  # +8 dB
                counter = [0]
                digest = hashlib.sha256()

                def read(_frames):
                    data = samples[counter[0] % len(samples)].tobytes()
                    counter[0] += 1
                    if counter[0] == args.frames:
                        engine._stop.set()
                    return data, False

                def write(data):
                    digest.update(data.tobytes())
                    if visible and counter[0] % 3 == 0:
                        engine.get_levels()

                class Stream:
                    pass

                engine._in = Stream()
                engine._out = Stream()
                engine._in.read = read
                engine._out.write = write
                engine._open_streams = lambda: None
                engine._close_streams = lambda: None
                try:
                    started = time.process_time()
                    engine._worker()
                    times.append(time.process_time() - started)
                finally:
                    engine._suppressor.close()
            key = mode + ('_visible' if visible else '_hidden')
            results[key] = {'cpu_seconds': statistics.median(times),
                            'audio_seconds': args.frames * 0.01,
                            'sha256': digest.hexdigest()}
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    main()
