"""Bit-for-bit comparison of native loops with the retained Python path."""

import math
import os
import random
import unittest
from array import array
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

import sounddevice as sd

from noiseclean import config, dsp
from noiseclean.audio.engine import _LinResampler, _mono_from_raw, _to_channels
from noiseclean.suppressors import RNNoiseSuppressor, SpeexSuppressor


NATIVE = dsp._load_native(os.path.join(config.LIBS_DIR, 'dsp_accel.dll'))


@unittest.skipIf(NATIVE is None, 'Optional native DSP library unavailable')
class NativeParityTests(unittest.TestCase):
    def setUp(self):
        rng = random.Random(7419)
        self.samples = array('f', [rng.uniform(-1.5, 1.5) for _ in range(480)])
        self.samples.extend([0.0, -0.0, 1e-40, -1e-40, 1.0, -1.0,
                             32767 / 32768, -1 / 32768, 1 / 32768])

    def compare_in_place(self, fn, factor):
        reference, fast = array('f', self.samples), array('f', self.samples)
        with patch.object(dsp, '_native', None):
            fn(reference, factor)
        with patch.object(dsp, '_native', NATIVE):
            fn(fast, factor)
        self.assertEqual(fast.tobytes(), reference.tobytes())

    def test_gain_clip_and_scaling_preserve_float32_rounding(self):
        for factor in [0.0, 0.7, 1.0, 2.51188643150958, 10 ** 1.5, 32767.0,
                       1.0 / 32767.0]:
            with self.subTest(factor=factor):
                self.compare_in_place(dsp.scale_in_place, factor)
                self.compare_in_place(dsp.gain_clip_in_place, factor)
                self.compare_in_place(dsp.scale_clip_in_place, factor)

    def test_pcm_conversion_boundaries_and_truncation(self):
        for scale in [32768.0, 32767.0]:
            with patch.object(dsp, '_native', None):
                reference = dsp.to_pcm16(self.samples, scale)
            with patch.object(dsp, '_native', NATIVE):
                fast = dsp.to_pcm16(self.samples, scale)
            self.assertEqual(fast.tobytes(), reference.tobytes())

    def test_every_int16_value_converts_identically(self):
        pcm = array('h', range(-32768, 32768))
        with patch.object(dsp, '_native', None):
            reference = dsp.from_pcm16(pcm)
        with patch.object(dsp, '_native', NATIVE):
            fast = dsp.from_pcm16(pcm)
        self.assertEqual(fast.tobytes(), reference.tobytes())

    def test_sum_squares_and_peak_match_exactly(self):
        for source in [self.samples, array('f'), array('f', [1e-40] * 480)]:
            with patch.object(dsp, '_native', None):
                expected = dsp.sum_squares(source), dsp.peak_abs(source)
            with patch.object(dsp, '_native', NATIVE):
                actual = dsp.sum_squares(source), dsp.peak_abs(source)
            self.assertEqual(actual, expected)

    def test_empty_buffers(self):
        with patch.object(dsp, '_native', NATIVE):
            data = array('f')
            dsp.scale_in_place(data, 2.0)
            dsp.gain_clip_in_place(data, 2.0)
            dsp.scale_clip_in_place(data, 2.0)
            self.assertEqual(dsp.to_pcm16(data), array('h'))
            self.assertEqual(dsp.from_pcm16(array('h')), data)

    def test_nonfinite_values_have_same_behavior(self):
        self.samples = array('f', [float('inf'), -float('inf'), float('nan')])
        self.compare_in_place(dsp.gain_clip_in_place, 2.0)
        self.compare_in_place(dsp.scale_clip_in_place, 0.7)
        for backend in [None, NATIVE]:
            with patch.object(dsp, '_native', backend):
                with self.assertRaises(ValueError):
                    dsp.to_pcm16(self.samples)

    def test_resampling_stream_lengths_phase_and_samples(self):
        for src, dst in [(44100, 48000), (48000, 44100), (32000, 48000),
                         (48000, 16000), (96000, 48000), (48000, 96000),
                         (48000, 48000)]:
            with self.subTest(rates=(src, dst)):
                slow, fast = _LinResampler(src, dst), _LinResampler(src, dst)
                for size in [0, 1, 2, 7, 441, 480, 960, 1, 3] * 5:
                    chunk = array('f', (math.sin(i * .03) for i in range(size)))
                    with patch.object(dsp, '_native', None):
                        expected = slow.process(chunk)
                    with patch.object(dsp, '_native', NATIVE):
                        actual = fast.process(chunk)
                    self.assertEqual(actual.tobytes(), expected.tobytes())
                    self.assertEqual((fast._pos, fast._prev), (slow._pos, slow._prev))

    def test_bad_buffer_types_are_rejected_before_native_call(self):
        with patch.object(dsp, '_native', NATIVE):
            for data in [array('h', [1, 2]), array('d', [1, 2]), [1.0, 2.0]]:
                with self.assertRaises(TypeError):
                    dsp.gain_clip_in_place(data, 1.0)
                with self.assertRaises(TypeError):
                    dsp.to_pcm16(data)

    def test_native_loop_is_stateless_across_threads(self):
        def run(_index):
            data = array('f', self.samples)
            for _ in range(50):
                dsp.scale_in_place(data, 0.7)
            return data.tobytes()

        with patch.object(dsp, '_native', NATIVE):
            with ThreadPoolExecutor(max_workers=4) as pool:
                results = list(pool.map(run, range(12)))
        self.assertTrue(all(result == results[0] for result in results))

    def test_real_suppressors_preserve_audio_and_vad(self):
        for kind, params in [(SpeexSuppressor, {}),
                             (RNNoiseSuppressor, {'threshold': 0.0}),
                             (RNNoiseSuppressor, {'threshold': 0.6, 'retro_blocks': 5})]:
            slow, fast = kind(**params), kind(**params)
            try:
                for k in range(80):
                    chunk = array('f', (0.1 * math.sin((k * 480 + i) * .037)
                                       for i in range(480)))
                    with patch.object(dsp, '_native', None):
                        expected, expected_vad = slow.process(chunk)
                    with patch.object(dsp, '_native', NATIVE):
                        actual, actual_vad = fast.process(chunk)
                    self.assertEqual(actual.tobytes(), expected.tobytes())
                    self.assertEqual(actual_vad, expected_vad)
            finally:
                slow.close()
                fast.close()


class FallbackAndBuffersTests(unittest.TestCase):
    def test_missing_or_incompatible_library_falls_back(self):
        self.assertIsNone(dsp._load_native('missing-micronoise-dsp-library.dll'))
        with patch.object(dsp.ctypes, 'CDLL', return_value=object()):
            self.assertIsNone(dsp._load_native('incompatible.dll'))

    def test_raw_portaudio_buffer_needs_no_intermediate_bytes_copy(self):
        source = array('f', [0.25, -0.75, 0.5, -1.0])
        cdata = sd._ffi.new('char[]', source.tobytes())
        raw = sd._ffi.buffer(cdata, len(source) * 4)
        mono = _mono_from_raw(raw, 2)
        self.assertEqual(mono, array('f', [0.25, 0.5]))
        self.assertEqual(_mono_from_raw(raw, 1), source)
        self.assertEqual(_mono_from_raw(memoryview(source), 1), source)
        raw[0:4] = array('f', [0.0]).tobytes()
        self.assertEqual(mono, array('f', [0.25, 0.5]))

    def test_channel_duplication_and_identity(self):
        mono = array('f', [0.1, -0.2, 0.3])
        self.assertIs(_to_channels(mono, 1), mono)
        for channels in [2, 4]:
            interleaved = _to_channels(mono, channels)
            for c in range(channels):
                self.assertEqual(interleaved[c::channels], mono)


if __name__ == '__main__':
    unittest.main()
