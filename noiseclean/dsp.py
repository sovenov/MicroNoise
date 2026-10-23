"""Small DSP operations with an optional native backend and Python fallback.

MICRONOISE_PYTHON_DSP=1 forces the original arithmetic for tests/diagnostics.
The DLL owns no buffers: array objects remain alive throughout each call.
"""

import ctypes
import os
from array import array

from . import config


def _load_native(path):
    try:
        lib = ctypes.CDLL(path)
        lib.nc_dsp_version.argtypes = []
        lib.nc_dsp_version.restype = ctypes.c_int
        if lib.nc_dsp_version() != 1:
            return None
        ptr, count, real = ctypes.c_void_p, ctypes.c_size_t, ctypes.c_double
        signatures = {
            'nc_scale': ([ptr, count, real], None),
            'nc_gain_clip': ([ptr, count, real], None),
            'nc_scale_clip': ([ptr, count, real], None),
            'nc_to_pcm16': ([ptr, ptr, count, real], ctypes.c_int),
            'nc_from_pcm16': ([ptr, ptr, count, real], None),
            'nc_sum_squares': ([ptr, count], real),
            'nc_peak': ([ptr, count], real),
            'nc_resample': ([ptr, count, ptr, count, real, real], ctypes.c_int),
        }
        for name, (args, result) in signatures.items():
            fn = getattr(lib, name)
            fn.argtypes, fn.restype = args, result
        return lib
    except (OSError, AttributeError):
        return None


_native = (None if os.environ.get('MICRONOISE_PYTHON_DSP') == '1'
           else _load_native(os.path.join(config.LIBS_DIR, 'dsp_accel.dll')))


def backend_name():
    return 'native' if _native is not None else 'python'


def _address(data, typecode='f'):
    if not isinstance(data, array) or data.typecode != typecode:
        raise TypeError("expected array({!r})".format(typecode))
    return data.buffer_info()[0]


def scale_in_place(data, factor):
    if _native is not None:
        _native.nc_scale(_address(data), len(data), factor)
        return
    for i in range(len(data)):
        data[i] *= factor


def gain_clip_in_place(data, gain):
    if _native is not None:
        _native.nc_gain_clip(_address(data), len(data), gain)
        return
    if gain != 1.0:
        scale_in_place(data, gain)
    for i in range(len(data)):
        v = data[i]
        if v > 1.0:
            data[i] = 1.0
        elif v < -1.0:
            data[i] = -1.0


def scale_clip_in_place(data, factor):
    if _native is not None:
        _native.nc_scale_clip(_address(data), len(data), factor)
        return
    for i in range(len(data)):
        v = data[i] * factor
        data[i] = 1.0 if v > 1.0 else (-1.0 if v < -1.0 else v)


def to_pcm16(data, scale=32768.0):
    pcm = array('h', bytes(2 * len(data)))
    if _native is not None:
        ok = _native.nc_to_pcm16(_address(data), _address(pcm, 'h'),
                                 len(data), scale)
        if not ok:
            raise ValueError('cannot convert float NaN to integer')
        return pcm
    for i in range(len(data)):
        v = data[i] * scale
        if v > 32767.0:
            v = 32767.0
        elif v < -32768.0:
            v = -32768.0
        pcm[i] = int(v)
    return pcm


def from_pcm16(pcm, scale=1.0 / 32768.0):
    out = array('f', bytes(4 * len(pcm)))
    if _native is not None:
        _native.nc_from_pcm16(_address(pcm, 'h'), _address(out),
                             len(pcm), scale)
        return out
    for i in range(len(pcm)):
        out[i] = pcm[i] * scale
    return out


def sum_squares(samples):
    if _native is not None and isinstance(samples, array) and samples.typecode == 'f':
        return _native.nc_sum_squares(_address(samples), len(samples))
    acc = 0.0
    for v in samples:
        acc += v * v
    return acc


def peak_abs(samples):
    if _native is not None and isinstance(samples, array) and samples.typecode == 'f':
        return _native.nc_peak(_address(samples), len(samples))
    peak = 0.0
    for v in samples:
        a = -v if v < 0.0 else v
        if a > peak:
            peak = a
    return peak


def resample_into(source, out, pos, step):
    if _native is not None:
        ok = _native.nc_resample(_address(source), len(source),
                                 _address(out), len(out), pos, step)
        if not ok:
            raise IndexError('resampler source index out of range')
        return
    last = len(source) - 1
    for k in range(len(out)):
        idx = pos + k * step
        i0 = int(idx)
        frac = idx - i0
        i1 = i0 + 1 if i0 + 1 <= last else last
        out[k] = source[i0] * (1.0 - frac) + source[i1] * frac
