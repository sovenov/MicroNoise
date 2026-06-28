# -*- mode: python ; coding: utf-8 -*-
"""Сборка MicroNoise папкой (onedir, windowed) под Windows 7+.

    py -3.8 -m PyInstaller --noconfirm --clean MicroNoise.spec

Результат: dist\\MicroNoise\\MicroNoise.exe (распространять всю папку
dist\\MicroNoise целиком).
"""

import glob
import os

from PyInstaller.utils.hooks import collect_all

datas = [('noiseclean\\assets', 'assets')]
binaries = [('noiseclean\\libs\\rnnoise.dll', 'libs'),
            ('noiseclean\\libs\\libspeexdsp.dll', 'libs')]
hiddenimports = ['pystray._win32']

tmp_ret = collect_all('sounddevice')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]
tmp_ret = collect_all('_sounddevice_data')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# UCRT (Universal CRT): на «голой» Windows 7 этих системных DLL нет, без них
# python38.dll не загрузится. Берём редист из установленного Windows SDK.
_ucrt = None
for _base in (r"C:\Program Files (x86)\Windows Kits\10\Redist",
              r"C:\Program Files\Windows Kits\10\Redist"):
    _direct = os.path.join(_base, "ucrt", "DLLs", "x64")
    if os.path.isdir(_direct):
        _ucrt = _direct
    for _cand in glob.glob(os.path.join(_base, "*", "ucrt", "DLLs", "x64")):
        _ucrt = _cand
if _ucrt:
    for _dll in glob.glob(os.path.join(_ucrt, "*.dll")):
        binaries.append((_dll, "."))
    print("UCRT bundled from:", _ucrt)
else:
    print("WARNING: UCRT redist not found - exe may fail to start on Windows 7")


block_cipher = None


a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# Режим onedir (папка): надёжнее на Windows 7 — нет распаковки во временный
# каталог при каждом запуске, DLL грузятся прямо из папки рядом с exe.
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MicroNoise',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['noiseclean\\assets\\app.ico'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MicroNoise',
)
