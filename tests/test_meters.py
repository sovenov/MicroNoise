"""Индикаторы не должны влиять на звук или работать в скрытом окне.

Запуск: py -3.8 -m unittest discover -s tests -v
Микрофон и виртуальный кабель в тестах не открываются.
"""

import queue
import sys
import tkinter as tk
import unittest
from array import array
from types import SimpleNamespace
from unittest.mock import Mock, patch

from noiseclean import config
from noiseclean.audio.engine import AudioEngine, _level_percent
from noiseclean.suppressors import PassthroughSuppressor
from noiseclean.ui.app import NoiseCleanApp, _smooth_level
from noiseclean.ui.widgets import Meter


class EngineMeterTests(unittest.TestCase):
    def test_rms_scale(self):
        self.assertEqual(_level_percent([]), 0.0)
        self.assertEqual(_level_percent([0.0] * 480), 0.0)
        self.assertAlmostEqual(_level_percent([0.001] * 480), 0.0)
        self.assertAlmostEqual(_level_percent([0.1] * 480), 200.0 / 3)
        self.assertEqual(_level_percent([1.0] * 480), 100.0)

    def test_levels_are_calculated_on_request(self):
        engine = AudioEngine()
        engine._meter_samples = ([0.1] * 480, [0.01] * 480, 0.7)
        with patch('noiseclean.audio.engine._level_percent',
                   wraps=_level_percent) as rms:
            il, ol, speech = engine.get_levels()
        self.assertEqual(rms.call_count, 2)
        self.assertAlmostEqual(il, 200.0 / 3)
        self.assertAlmostEqual(ol, 100.0 / 3)
        self.assertEqual(speech, 0.7)

    def test_disable_drops_snapshot_and_skips_rms(self):
        engine = AudioEngine()
        engine._meter_samples = ([1.0] * 480, [1.0] * 480, 1.0)
        engine.set_metering_enabled(False)
        self.assertEqual(engine._meter_samples, ((), (), 0.0))
        with patch('noiseclean.audio.engine._level_percent') as rms:
            self.assertEqual(engine.get_levels(), (0.0, 0.0, 0.0))
        rms.assert_not_called()
        engine.set_metering_enabled(True)
        self.assertEqual(engine.get_levels(), (0.0, 0.0, 0.0))

    def run_worker(self, metering):
        engine = AudioEngine()
        engine.set_metering_enabled(metering)
        engine._suppressor = PassthroughSuppressor()
        frame = array('f', [-0.6, -0.01, 0.0, 0.2, 0.7] * 96)
        engine._gain_lin = 2.0
        written = []
        snapshots = []

        def read(_frames):
            if len(written) == 7:
                engine._stop.set()
            return frame.tobytes(), False

        def write(data):
            written.append(array('f', data))

        def close():
            snapshots.append(engine._meter_samples)

        engine._in = SimpleNamespace(read=read)
        engine._out = SimpleNamespace(write=write)
        engine._open_streams = lambda: None
        engine._close_streams = close
        with patch('noiseclean.audio.engine._level_percent') as rms:
            engine._worker()
        rms.assert_not_called()
        self.assertEqual(engine.get_levels(), (0.0, 0.0, 0.0))
        return written, snapshots[0]

    def test_worker_never_calculates_rms_and_keeps_identical_audio(self):
        visible_audio, visible_snapshot = self.run_worker(True)
        hidden_audio, hidden_snapshot = self.run_worker(False)
        self.assertEqual(len(visible_audio), 8)
        self.assertEqual(visible_audio, hidden_audio)
        self.assertEqual(visible_audio[0][0], -1.0)  # gain + clipping
        self.assertEqual(visible_audio[0][6], array('f', [0.4])[0])
        self.assertEqual(len(visible_snapshot[0]), 480)
        self.assertEqual(len(visible_snapshot[1]), 480)
        self.assertEqual(hidden_snapshot, ((), (), 0.0))


class SmoothingTests(unittest.TestCase):
    def test_attack_is_faster_than_release(self):
        rise = _smooth_level(0.0, 100.0, 0.033)
        fall = 100.0 - _smooth_level(100.0, 0.0, 0.033)
        self.assertGreater(rise, fall)

    def test_smoothing_is_independent_of_refresh_rate(self):
        for start, target in [(0.0, 80.0), (80.0, 0.0)]:
            one_step = _smooth_level(start, target, 0.132)
            four_steps = start
            for _ in range(4):
                four_steps = _smooth_level(four_steps, target, 0.033)
            self.assertAlmostEqual(one_step, four_steps)

    def test_settles_without_overshoot(self):
        value = 80.0
        for _ in range(120):
            nxt = _smooth_level(value, 0.0, 0.033)
            self.assertGreaterEqual(nxt, 0.0)
            self.assertLessEqual(nxt, value)
            value = nxt
        self.assertEqual(value, 0.0)


class AppMeterTests(unittest.TestCase):
    def setUp(self):
        # Только логика окна; без чтения настроек и запуска аудиоустройств.
        self.app = NoiseCleanApp.__new__(NoiseCleanApp)
        self.app.root = Mock()
        self.app.engine = Mock()
        self.app.engine.get_levels.return_value = (65.0, 55.0, 0.0)
        self.app._alive = True
        self.app.power_on = True
        self.app._meters_active = True
        self.app._meter_updated_at = 0.0
        self.app._disp_in = self.app._disp_out = 0.0
        self.app._in_text = self.app._out_text = None
        self.app._tick_after_id = None
        self.app.in_meter = Mock()
        self.app.out_meter = Mock()
        self.app.in_val = Mock()
        self.app.out_val = Mock()
        self.app._tray_q = queue.Queue()
        self.app._window_is_visible = Mock(return_value=True)

    def test_hidden_window_skips_levels_and_drawing(self):
        self.app._window_is_visible.return_value = False
        self.app._tick()
        self.app.engine.set_metering_enabled.assert_called_once_with(False)
        self.app.engine.get_levels.assert_not_called()
        self.app.in_meter.set_value.assert_not_called()
        self.app.out_meter.set_value.assert_not_called()
        self.app.root.after.assert_called_once_with(
            config.UI_HIDDEN_TICK_MS, self.app._tick)

    def test_restore_reenables_meters(self):
        self.app._meters_active = False
        self.app._tick()
        self.app.engine.set_metering_enabled.assert_called_once_with(True)
        self.app.engine.get_levels.assert_called_once()
        self.app.in_meter.set_value.assert_called_once()
        self.app.root.after.assert_called_once_with(
            config.UI_TICK_MS, self.app._tick)

    def test_repeated_ticks_do_not_reenable_or_rewrite_same_labels(self):
        self.app.engine.get_levels.return_value = (0.0, 0.0, 0.0)
        self.app._tick()
        self.app._tick()
        self.app.engine.set_metering_enabled.assert_not_called()
        self.app.in_val.config.assert_called_once_with(text='0%')
        self.app.out_val.config.assert_called_once_with(text='0%')

    def test_tray_commands_are_processed_while_hidden(self):
        self.app._meters_active = False
        self.app._window_is_visible.return_value = False
        self.app._show_window = Mock()
        self.app._tray_q.put('open')
        self.app._tick()
        self.app._show_window.assert_called_once()

    def test_power_off_drives_display_to_zero(self):
        self.app.power_on = False
        self.app._tick()
        self.app.in_meter.set_value.assert_called_once_with(0.0)
        self.app.out_meter.set_value.assert_called_once_with(0.0)


class CanvasMeterTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.meter = Meter(self.root, bg='#000000')
        self.meter.pack()
        self.root.update_idletasks()

    def tearDown(self):
        self.root.destroy()

    def test_canvas_items_are_reused_and_zero_hides_fill(self):
        items = self.meter.find_all()
        self.assertEqual(len(items), 2)
        for value in [10, 50, 75, 95, 100, 0]:
            self.meter.set_value(value)
            self.assertEqual(self.meter.find_all(), items)
        self.assertEqual(self.meter.itemcget(items[1], 'state'), 'hidden')

    def test_same_pixel_and_color_do_not_redraw(self):
        self.meter.set_value(50.0)
        with patch.object(self.meter, 'coords') as coords:
            with patch.object(self.meter, 'itemconfigure') as itemconfig:
                self.meter.set_value(50.001)
        coords.assert_not_called()
        itemconfig.assert_not_called()

    def test_warning_color_and_clamped_width(self):
        for value, color in [(40, config.COLORS['green']),
                             (80, '#ffbd43'), (120, config.COLORS['danger'])]:
            self.meter.set_value(value)
            self.assertEqual(self.meter.itemcget(self.meter._fill, 'fill'), color)
        self.assertEqual(self.meter._value, 100.0)


@unittest.skipUnless(sys.platform == 'win32', 'Нативное сворачивание Windows')
class WindowVisibilityTests(unittest.TestCase):
    def test_native_minimize_restore_and_tray_hide(self):
        import ctypes

        root = tk.Tk()
        root.withdraw()
        root.overrideredirect(True)
        root.geometry('240x100+10000+10000')
        app = NoiseCleanApp.__new__(NoiseCleanApp)
        app.root = root
        app.engine = AudioEngine()
        app._alive = True
        app._tray = object()
        app._meters_active = True
        app._disp_in = app._disp_out = 0.0
        try:
            root.deiconify()
            root.update()
            self.assertTrue(app._window_is_visible())
            for _ in range(3):
                app._minimize()
                root.update()
                self.assertFalse(app._window_is_visible())
                self.assertFalse(app.engine._metering_enabled)
                hwnd = ctypes.windll.user32.GetAncestor(root.winfo_id(), 2)
                ctypes.windll.user32.ShowWindow(ctypes.c_void_p(hwnd), 9)
                root.update()
                # Эта же проверка выполняется фоновым тиком: Tk state()
                # может оставаться normal у нативного безрамочного окна.
                app._set_meters_active(app._window_is_visible())
                self.assertTrue(app._meters_active)
                self.assertTrue(app.engine._metering_enabled)
            app._on_close()
            root.update()
            self.assertFalse(app._meters_active)
            root.deiconify()
            root.update()
            app._set_meters_active(app._window_is_visible())
            self.assertTrue(app._meters_active)
        finally:
            root.destroy()


if __name__ == '__main__':
    unittest.main()
