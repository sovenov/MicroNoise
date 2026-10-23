"""Read-only CPU cost of checking selected and virtual capture devices.

No volume setters or audio streams are used. The 1s/2s percentages are estimates
for unchanged levels, expressed as a fraction of ONE logical CPU, not the PC.
"""

import argparse
import json
from pathlib import Path
import statistics
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from noiseclean import settings
from noiseclean.audio import devices
from noiseclean.audio.volume import WindowsVolumes, list_virtual_capture_endpoints, resolve_endpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checks', type=int, default=500)
    parser.add_argument('--repeats', type=int, default=3)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--input-name')
    parser.add_argument('--output-name')
    args = parser.parse_args()
    if args.checks < 1 or args.repeats < 1:
        parser.error('checks and repeats must be positive')
    saved = settings.load()
    selected = list_virtual_capture_endpoints()
    for flow, candidates, fallback in [
            ('input', devices.list_inputs(), devices.default_input_index),
            ('output', devices.list_outputs(), devices.guess_virtual_output)]:
        requested = getattr(args, flow + '_name')
        name = requested or saved.get(flow + '_name')
        match = next((d for d in candidates if d['name'] == name), None)
        if requested and match is None:
            parser.error('Device not found: ' + requested)
        index = match['index'] if match else fallback()
        selected.append({'endpoint_id': resolve_endpoint(index, flow), 'name': devices.device_name(index)})
    selected = list({item['endpoint_id']: item for item in selected}.values())

    def check():
        with WindowsVolumes() as backend:
            for item in selected:
                with backend.open(item['endpoint_id']) as volume:
                    volume.get()

    for _ in range(10):
        check()
    cpu, wall = [], []
    for _ in range(args.repeats):
        started_cpu, started_wall = time.process_time(), time.perf_counter()
        for _ in range(args.checks):
            check()
        cpu.append((time.process_time() - started_cpu) / args.checks)
        wall.append((time.perf_counter() - started_wall) / args.checks)
    cost = statistics.median(cpu)
    report = {
        'device_count': len(selected), 'devices': [item['name'] for item in selected],
        'checks_per_repeat': args.checks, 'repeats': args.repeats,
        'cpu_ms_per_check': round(cost * 1000, 3),
        'elapsed_ms_per_check': round(statistics.median(wall) * 1000, 3),
        'estimated_percent_of_one_logical_cpu_at_1s': round(cost * 100, 4),
        'estimated_percent_of_one_logical_cpu_at_2s': round(cost / 2 * 100, 4),
        'volume_writes': 0,
    }
    output = json.dumps(report, indent=2, ensure_ascii=True) + '\n'
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output, encoding='utf-8')
    print(output)


if __name__ == '__main__':
    main()
