"""Build the optional DSP helper with an installed MSVC x64 compiler.

No Windows SDK, Python headers, CRT, or additional packages are needed.
py -3.8 tools/build_dsp.py [--compiler path/to/cl.exe]
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess


def find_compiler():
    configured = shutil.which('cl.exe')
    if configured:
        return Path(configured)
    candidates = []
    for key, default in (('ProgramFiles(x86)', 'C:/Program Files (x86)'),
                         ('ProgramFiles', 'C:/Program Files')):
        base = Path(os.environ.get(key, default)) / 'Microsoft Visual Studio'
        candidates.extend(base.glob('*/BuildTools/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))
        candidates.extend(base.glob('*/Community/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))
        candidates.extend(base.glob('*/Professional/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))
        candidates.extend(base.glob('*/Enterprise/VC/Tools/MSVC/*/bin/Hostx64/x64/cl.exe'))
    if not candidates:
        raise SystemExit('MSVC x64 compiler not found. Use --compiler or a developer prompt.')
    return sorted(candidates)[-1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler', type=Path)
    args = parser.parse_args()
    compiler = args.compiler or find_compiler()
    root = Path(__file__).resolve().parents[1]
    work = root / 'build' / 'dsp'
    work.mkdir(parents=True, exist_ok=True)
    target = root / 'noiseclean' / 'libs' / 'dsp_accel.dll'
    env = dict(os.environ)
    env['PATH'] = str(compiler.parent) + os.pathsep + env.get('PATH', '')
    subprocess.run([
        str(compiler), '/nologo', '/TC', '/O2', '/W4', '/WX', '/fp:strict',
        '/GS-', '/Zl', '/LD', str(root / 'native' / 'dsp_accel.c'),
        '/Fo' + str(work / 'dsp_accel.obj'), '/link',
        '/NODEFAULTLIB', '/ENTRY:DllMain', '/MACHINE:X64',
        '/SUBSYSTEM:WINDOWS,6.01', '/OUT:' + str(target),
        '/IMPLIB:' + str(work / 'dsp_accel.lib'),
    ], cwd=str(work), env=env, check=True)
    print('Built {} ({} bytes)'.format(target, target.stat().st_size))


if __name__ == '__main__':
    main()
