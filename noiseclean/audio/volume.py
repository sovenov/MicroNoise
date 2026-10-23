"""Windows endpoint volumes, separate from the audio DSP and its gain.

Only the exact devices selected in MicroNoise are addressed. COM pointers stay
on their owning thread; only endpoint ID strings are sent to the keeper thread.
"""

from contextlib import contextmanager
import ctypes
import sys
import uuid

import sounddevice as sd


class VolumeError(RuntimeError):
    pass


class _GUID(ctypes.Structure):
    _fields_ = [('data', ctypes.c_ubyte * 16)]

    def __init__(self, value):
        super().__init__()
        self.data[:] = uuid.UUID(value).bytes_le


_CLSID_ENUMERATOR = _GUID('bcde0395-e52f-467c-8e3d-c4579291692e')
_IID_ENUMERATOR = _GUID('a95664d2-9614-4f35-a746-de8db63617e6')
_IID_VOLUME = _GUID('5cdf2c82-841e-4546-9722-0cf74078229a')
_EVENT_CONTEXT = _GUID('a77b58ef-2b43-443d-9c25-21165c308051')
_PTR = ctypes.c_void_p
_PPTR = ctypes.POINTER(_PTR)
_HRESULT = ctypes.c_long


def _check(hr, operation):
    if hr < 0:
        raise VolumeError('%s: HRESULT 0x%08X' % (operation, hr & 0xffffffff))


def _call(pointer, slot, argtypes=(), args=(), restype=_HRESULT):
    table = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(_PTR))).contents
    fn = ctypes.WINFUNCTYPE(restype, _PTR, *argtypes)(table[slot])
    return fn(pointer, *args)


def _release(pointer):
    if pointer:
        _call(pointer, 2, restype=ctypes.c_ulong)


def _ole():
    if sys.platform != 'win32':
        raise VolumeError('System volume control requires Windows')
    # WinDLL avoids OleDLL's automatic HRESULT exceptions: check them ourselves.
    lib = ctypes.WinDLL('ole32')
    lib.CoInitializeEx.argtypes = [_PTR, ctypes.c_ulong]
    lib.CoInitializeEx.restype = _HRESULT
    lib.CoUninitialize.argtypes, lib.CoUninitialize.restype = [], None
    lib.CoCreateInstance.argtypes = [_PTR, _PTR, ctypes.c_ulong, _PTR, _PPTR]
    lib.CoCreateInstance.restype = _HRESULT
    lib.CoTaskMemFree.argtypes, lib.CoTaskMemFree.restype = [_PTR], None
    return lib


@contextmanager
def _com():
    ole = _ole()
    hr = ole.CoInitializeEx(None, 0)  # MTA; accept an existing STA on the UI thread.
    owned = hr in (0, 1)
    if not owned and (hr & 0xffffffff) != 0x80010106:  # RPC_E_CHANGED_MODE
        _check(hr, 'CoInitializeEx')
    try:
        yield ole
    finally:
        if owned:
            ole.CoUninitialize()


def _device_id(device, ole):
    value = _PTR()
    _check(_call(device, 5, [_PPTR], [ctypes.byref(value)]), 'IMMDevice.GetId')
    try:
        return ctypes.wstring_at(value)
    finally:
        ole.CoTaskMemFree(value)


def resolve_endpoint(index, flow):
    """Resolve a selected PortAudio device to its exact Windows endpoint ID.

    Run on the application's main thread, where PortAudio was initialized.
    PaWasapi_GetIMMDevice returns a borrowed pointer: do NOT Release it.
    For another host API accept only one identical full-name WASAPI counterpart.
    """
    if index is None:
        raise VolumeError('No device selected')
    info = sd.query_devices(index)
    key = 'max_input_channels' if flow == 'input' else 'max_output_channels'
    if info[key] <= 0:
        raise VolumeError('Selected device has the wrong direction')
    if sd.query_hostapis(info['hostapi'])['name'] != 'Windows WASAPI':
        matches = [i for i, d in enumerate(sd.query_devices())
                   if d['name'] == info['name'] and d[key] > 0
                   and sd.query_hostapis(d['hostapi'])['name'] == 'Windows WASAPI']
        if len(matches) != 1:
            raise VolumeError('Cannot uniquely match selected device to Windows WASAPI')
        index = matches[0]
    with _com() as ole:
        try:
            lib = ctypes.CDLL(sd._libname)
            get_device = lib.PaWasapi_GetIMMDevice
        except (OSError, AttributeError) as exc:
            raise VolumeError('PortAudio does not expose Windows endpoint IDs') from exc
        get_device.argtypes = [ctypes.c_int, _PPTR]
        get_device.restype = ctypes.c_int
        device = _PTR()
        error = get_device(index, ctypes.byref(device))
        if error < 0 or not device:
            raise VolumeError('PaWasapi_GetIMMDevice: %s' % error)
        return _device_id(device, ole)


def list_virtual_capture_endpoints():
    """Active virtual devices on Windows' Recording tab, with exact IDs."""
    result = []
    seen = set()
    for index, info in enumerate(sd.query_devices()):
        name = info['name']
        if info['max_input_channels'] <= 0:
            continue
        if sd.query_hostapis(info['hostapi'])['name'] != 'Windows WASAPI':
            continue
        if not any(part in name.casefold() for part in
                   ('vb-audio', 'virtual audio cable', 'voicemeeter', 'cable output')):
            continue
        endpoint_id = resolve_endpoint(index, 'input')
        if endpoint_id not in seen:
            result.append({'endpoint_id': endpoint_id, 'name': name})
            seen.add(endpoint_id)
    return sorted(result, key=lambda item: item['name'].casefold())


class EndpointVolume:
    def __init__(self, pointer):
        self._pointer = pointer

    def get(self):
        value = ctypes.c_float()
        _check(_call(self._pointer, 9, [ctypes.POINTER(ctypes.c_float)],
                     [ctypes.byref(value)]), 'GetMasterVolumeLevelScalar')
        return float(value.value)

    def set(self, value):
        if not 0.0 <= value <= 1.0:
            raise ValueError('Volume must be in 0..1')
        _check(_call(self._pointer, 7, [ctypes.c_float, _PTR],
                     [value, ctypes.byref(_EVENT_CONTEXT)]),
               'SetMasterVolumeLevelScalar')


class WindowsVolumes:
    """One COM session per check. No audio streams are opened or restarted."""
    def __enter__(self):
        self._context = _com()
        self._ole = self._context.__enter__()
        self._enumerator = _PTR()
        try:
            _check(self._ole.CoCreateInstance(
                ctypes.byref(_CLSID_ENUMERATOR), None, 1,
                ctypes.byref(_IID_ENUMERATOR), ctypes.byref(self._enumerator)),
                'CoCreateInstance(MMDeviceEnumerator)')
        except Exception:
            self._context.__exit__(*sys.exc_info())
            raise
        return self

    def __exit__(self, *exc):
        try:
            _release(self._enumerator)
        finally:
            self._context.__exit__(*exc)

    @contextmanager
    def open(self, endpoint_id):
        device, volume = _PTR(), _PTR()
        try:
            _check(_call(self._enumerator, 5, [ctypes.c_wchar_p, _PPTR],
                         [endpoint_id, ctypes.byref(device)]), 'IMMDeviceEnumerator.GetDevice')
            _check(_call(device, 3, [_PTR, ctypes.c_ulong, _PTR, _PPTR],
                         [ctypes.byref(_IID_VOLUME), 1, None, ctypes.byref(volume)]),
                   'IMMDevice.Activate(IAudioEndpointVolume)')
            yield EndpointVolume(volume)
        finally:
            _release(volume)
            _release(device)
