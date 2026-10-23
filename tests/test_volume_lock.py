"""System volume restoration tests: all writes use fake endpoints only."""

from contextlib import contextmanager
import ctypes
import queue
import threading
import tkinter as tk
import unittest
from unittest.mock import Mock, patch

from noiseclean.audio import volume
from noiseclean.ui.app import NoiseCleanApp
from noiseclean.ui.theme import build_fonts
from noiseclean.ui.volume_dialog import VolumeLockDialog
from noiseclean.volume_lock import VolumeKeeper, normalize_settings


class FakeEndpoint:
    def __init__(self, level):
        self.level = level
        self.writes = []

    def get(self):
        return self.level

    def set(self, level):
        self.level = level
        self.writes.append(level)


class FakeBackend:
    def __init__(self):
        self.endpoints = {'mic-id': FakeEndpoint(.5), 'cable-in-id': FakeEndpoint(1.0)}
        self.endpoints.update({'cable-out-id': FakeEndpoint(.6),
                               'line-1-id': FakeEndpoint(.7), 'line-2-id': FakeEndpoint(.8)})
        self.opened = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass

    @contextmanager
    def open(self, endpoint):
        self.opened.append(endpoint)
        if endpoint not in self.endpoints:
            raise RuntimeError('Device disconnected')
        yield self.endpoints[endpoint]


class KeeperTests(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.factory = Mock(return_value=self.backend)
        self.keeper = VolumeKeeper(backend_factory=self.factory)

    def tearDown(self):
        self.keeper.close()

    def test_disabled_does_not_start_thread_or_touch_devices(self):
        self.keeper.configure([], 5)
        self.assertIsNone(self.keeper._thread)
        self.factory.assert_not_called()

    def test_restores_only_changed_levels_and_only_selected_endpoints(self):
        self.keeper._generation = 1
        targets = [('mic-id', 99), ('cable-in-id', 100)]
        self.assertEqual(self.keeper._check_once(targets, 1), {'state': 'on'})
        self.assertEqual(self.backend.endpoints['mic-id'].writes, [.99])
        self.assertEqual(self.backend.endpoints['cable-in-id'].writes, [])
        self.keeper._check_once(targets, 1)
        self.assertEqual(self.backend.endpoints['mic-id'].writes, [.99])
        self.assertEqual(self.backend.opened, ['mic-id', 'cable-in-id'] * 2)

    def test_zero_and_rounding_tolerance(self):
        self.backend.endpoints['cable-in-id'].level = .996
        self.keeper._check_once([('mic-id', 0), ('cable-in-id', 100)], 0)
        self.assertEqual(self.backend.endpoints['mic-id'].writes, [0.0])
        self.assertEqual(self.backend.endpoints['cable-in-id'].writes, [])

    def test_missing_device_does_not_prevent_other_target(self):
        status = self.keeper._check_once([('missing-id', 100), ('mic-id', 99)], 0)
        self.assertEqual(status['state'], 'error')
        self.assertIn('disconnected', status['message'])
        self.assertEqual(self.backend.endpoints['mic-id'].writes, [.99])

    def test_disable_invalidates_work_before_write(self):
        endpoint = self.backend.endpoints['mic-id']
        endpoint.get = lambda: (self.keeper.configure([], 5) or .1)
        result = self.keeper._check_once([('mic-id', 99)], 0)
        self.assertIsNone(result)
        self.assertEqual(endpoint.writes, [])

    def test_old_status_cannot_overwrite_new_configuration(self):
        reports = []
        self.keeper._on_status = reports.append
        self.keeper.configure([], 5)
        self.keeper._publish({'state': 'on'}, 0)
        self.assertEqual(reports, [{'state': 'off'}])

    def test_background_check_runs_and_stops_without_audio_or_ui(self):
        done = threading.Event()
        self.keeper._on_status = lambda status: done.set()
        self.keeper.configure([('mic-id', 99)], 1)
        self.assertTrue(done.wait(2))
        self.assertEqual(self.backend.endpoints['mic-id'].writes, [.99])
        self.keeper.close()
        self.assertFalse(self.keeper._thread.is_alive())

    def test_rechecks_after_interval_without_redundant_writes(self):
        checked = threading.Event()
        original = self.backend.endpoints['mic-id'].get
        reads = []

        def read():
            reads.append(1)
            if len(reads) >= 2:
                checked.set()
            return original()

        self.backend.endpoints['mic-id'].get = read
        self.keeper.configure([('mic-id', 99)], 1)
        self.assertTrue(checked.wait(3))
        self.assertEqual(self.backend.endpoints['mic-id'].writes, [.99])


class ConfigurationTests(unittest.TestCase):
    def test_extra_devices_are_bounded_deduplicated_and_saved(self):
        options = normalize_settings({'extra_inputs': [
            {'endpoint_id': 'cable-out-id', 'name': 'CABLE Output', 'enabled': True, 'level': 101},
            {'endpoint_id': 'cable-out-id', 'enabled': True, 'level': 5},
            {'endpoint_id': 'line-1-id', 'name': 'Line 1', 'enabled': 'false', 'level': -1},
            None, {'endpoint_id': ''}]})
        self.assertEqual(len(options['extra_inputs']), 2)
        self.assertEqual(options['extra_inputs'][0]['level'], 100)
        self.assertFalse(options['extra_inputs'][1]['enabled'])
        self.assertEqual(options['extra_inputs'][1]['level'], 0)

    def test_virtual_capture_targets_are_included_without_duplicate_writes(self):
        app = self.app()
        app._volume_options['extra_inputs'] = [
            {'endpoint_id': 'cable-out-id', 'enabled': True, 'level': 100},
            {'endpoint_id': 'line-1-id', 'enabled': True, 'level': 95},
            {'endpoint_id': 'line-2-id', 'enabled': False, 'level': 100},
            {'endpoint_id': 'mic-id', 'enabled': True, 'level': 50}]
        with patch('noiseclean.ui.app.resolve_endpoint', side_effect=['mic-id', 'cable-in-id']):
            self.assertEqual(app._volume_targets(app._volume_options),
                             [('mic-id', 99), ('cable-in-id', 100), ('cable-out-id', 100), ('line-1-id', 95)])

    def test_invalid_saved_data_is_disabled_and_bounded(self):
        for invalid in [None, [], 'enabled']:
            self.assertFalse(normalize_settings(invalid)['enabled'])
        options = normalize_settings({'enabled': 'false', 'input_level': -10,
                                      'output_level': 900, 'interval_seconds': 0})
        self.assertFalse(options['enabled'])
        self.assertEqual((options['input_level'], options['output_level'], options['interval_seconds']),
                         (0, 100, 1))

    def app(self):
        app = NoiseCleanApp.__new__(NoiseCleanApp)
        app.input_idx, app.output_idx = 36, 27
        app._volume_options = normalize_settings({'enabled': True, 'input_level': 99})
        app._volume_keeper = Mock()
        app._tray_q = queue.Queue()
        return app

    def test_targets_follow_the_two_selected_devices_in_the_right_direction(self):
        app = self.app()
        with patch('noiseclean.ui.app.resolve_endpoint', side_effect=['mic-id', 'cable-in-id']) as resolve:
            self.assertEqual(app._volume_targets(app._volume_options), [('mic-id', 99), ('cable-in-id', 100)])
        self.assertEqual(resolve.call_args_list[0].args, (36, 'input'))
        self.assertEqual(resolve.call_args_list[1].args, (27, 'output'))

    def test_disabled_options_do_not_resolve_devices(self):
        app = self.app()
        app._volume_options['enabled'] = False
        with patch('noiseclean.ui.app.resolve_endpoint') as resolve:
            app._sync_volume_lock()
        resolve.assert_not_called()
        app._volume_keeper.configure.assert_called_once_with([], 5)

    def test_unresolvable_new_selection_cancels_old_targets(self):
        app = self.app()
        with patch('noiseclean.ui.app.resolve_endpoint', side_effect=RuntimeError('not unique')):
            app._sync_volume_lock()
        app._volume_keeper.configure.assert_called_once_with([], 5)
        self.assertEqual(app._tray_q.get()[1]['state'], 'error')


class ComBindingTests(unittest.TestCase):
    def test_discovery_lists_only_active_wasapi_virtual_capture_devices(self):
        devices = [
            {'name': 'EarPods', 'max_input_channels': 1, 'hostapi': 0},
            {'name': 'CABLE Input (VB-Audio)', 'max_input_channels': 0, 'hostapi': 0},
            {'name': 'CABLE Output (VB-Audio)', 'max_input_channels': 1, 'hostapi': 0},
            {'name': 'Line 1 (Virtual Audio Cable)', 'max_input_channels': 2, 'hostapi': 0},
            {'name': 'Line 2 (Virtual Audio Cable)', 'max_input_channels': 2, 'hostapi': 1}]
        with patch.object(volume.sd, 'query_devices', return_value=devices), \
                patch.object(volume.sd, 'query_hostapis', side_effect=lambda i: {'name': 'Windows WASAPI' if i == 0 else 'MME'}), \
                patch.object(volume, 'resolve_endpoint', side_effect=lambda i, flow: str(i)) as resolve:
            found = volume.list_virtual_capture_endpoints()
        self.assertEqual([item['endpoint_id'] for item in found], ['2', '3'])
        self.assertEqual([call.args for call in resolve.call_args_list], [(2, 'input'), (3, 'input')])

    def test_endpoint_setter_passes_scalar_and_context_to_correct_slot(self):
        captured = []
        get_type = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_float))
        set_type = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_float, ctypes.c_void_p)

        @get_type
        def get(_self, out):
            out[0] = .42
            return 0

        @set_type
        def set_level(_self, level, context):
            captured.append((level, ctypes.string_at(context, 16)))
            return 0

        table = (ctypes.c_void_p * 21)()
        table[9] = ctypes.cast(get, ctypes.c_void_p)
        table[7] = ctypes.cast(set_level, ctypes.c_void_p)
        instance = ctypes.pointer(ctypes.cast(table, ctypes.POINTER(ctypes.c_void_p)))
        endpoint = volume.EndpointVolume(ctypes.cast(instance, ctypes.c_void_p))
        self.assertAlmostEqual(endpoint.get(), .42, places=6)
        endpoint.set(.99)
        self.assertAlmostEqual(captured[0][0], .99, places=6)
        self.assertEqual(captured[0][1], bytes(volume._EVENT_CONTEXT.data))
        with self.assertRaises(ValueError):
            endpoint.set(1.1)

    def test_wrong_device_direction_is_rejected(self):
        with patch.object(volume.sd, 'query_devices', return_value={'max_input_channels': 0}):
            with self.assertRaises(volume.VolumeError):
                volume.resolve_endpoint(27, 'input')


class DialogTests(unittest.TestCase):
    def extras_dialog(self, options=None):
        self.dialog.close()
        self.dialog = VolumeLockDialog(
            self.root, self.fonts, 'ru', normalize_settings(options), ('EarPods', 'CABLE Input'),
            self.callback, extra_devices=[
                {'endpoint_id': 'cable-out-id', 'name': 'CABLE Output (VB-Audio Virtual Cable)'},
                {'endpoint_id': 'line-1-id', 'name': 'Line 1 (Virtual Audio Cable)'},
                {'endpoint_id': 'line-2-id', 'name': 'Line 2 (Virtual Audio Cable)'}])
        return self.dialog

    def test_extra_devices_have_individual_levels_and_can_be_the_only_targets(self):
        dialog = self.extras_dialog()
        self.callback.assert_not_called()
        dialog.enabled.set(True)
        dialog.input_enabled.set(False)
        dialog.output_enabled.set(False)
        dialog.extra_inputs[0]['level'].set('99')
        dialog.extra_inputs[1]['level'].set('95')
        dialog.extra_inputs[2]['enabled'].set(False)
        dialog.apply()
        selected = self.callback.call_args.args[0]['extra_inputs']
        self.assertEqual([(item['enabled'], item['level']) for item in selected],
                         [(True, 99), (True, 95), (False, 100)])

    def test_saved_extra_preferences_are_restored_and_missing_devices_can_be_disabled(self):
        dialog = self.extras_dialog({'extra_inputs': [
            {'endpoint_id': 'cable-out-id', 'name': 'CABLE Output', 'enabled': False, 'level': 87},
            {'endpoint_id': 'missing-id', 'name': 'Old cable', 'enabled': True, 'level': 91}]})
        self.assertFalse(dialog.extra_inputs[0]['enabled'].get())
        self.assertEqual(dialog.extra_inputs[0]['level'].get(), '87')
        missing = dialog.extra_inputs[-1]
        self.assertEqual(missing['endpoint_id'], 'missing-id')
        missing['enabled'].set(False)
        dialog.apply()
        self.assertFalse(self.callback.call_args.args[0]['extra_inputs'][-1]['enabled'])

    def setUp(self):
        self.root = tk.Tk()
        self.root.geometry('940x696+10000+10000')
        self.root.update_idletasks()
        self.fonts = build_fonts()
        self.callback = Mock()
        self.dialog = VolumeLockDialog(
            self.root, self.fonts, 'ru', normalize_settings(None),
            ('Головной телефон (2- EarPods)', 'CABLE Input (VB-Audio Virtual Cable)'), self.callback)
        self.root.update()

    def tearDown(self):
        self.root.destroy()

    def test_opening_dialog_does_not_apply_settings(self):
        self.callback.assert_not_called()
        self.assertFalse(self.dialog.enabled.get())

    def test_explicit_apply_uses_separate_values_and_interval(self):
        self.dialog.enabled.set(True)
        self.dialog.input_level.set('99')
        self.dialog.output_level.set('100')
        self.dialog.interval.set('7')
        self.dialog.apply()
        options = self.callback.call_args.args[0]
        self.assertEqual((options['input_level'], options['output_level'], options['interval_seconds']),
                         (99, 100, 7))
        self.assertTrue(options['enabled'])

    def test_invalid_input_does_not_apply(self):
        self.dialog.enabled.set(True)
        self.dialog.input_level.set('101')
        self.dialog.apply()
        self.callback.assert_not_called()
        self.assertTrue(self.dialog.error.cget('text'))

    def test_can_disable_even_with_unfinished_numeric_input(self):
        self.dialog.input_level.set('')
        self.dialog.enabled.set(False)
        self.dialog.apply()
        self.assertFalse(self.callback.call_args.args[0]['enabled'])

    def test_all_controls_fit_even_with_error_status(self):
        self.extras_dialog()
        self.dialog.set_status({'state': 'error', 'message': 'Device error ' * 20}, 5)
        self.root.update_idletasks()
        height = self.dialog.window.winfo_height()
        def visit(widget):
            for child in widget.winfo_children():
                relative_bottom = child.winfo_rooty() - self.dialog.window.winfo_rooty() + child.winfo_height()
                self.assertLessEqual(relative_bottom, height)
                visit(child)
        visit(self.dialog.window)


class FullWindowTests(unittest.TestCase):
    def test_settings_follow_selection_and_survive_tray_without_real_writes(self):
        root = tk.Tk()
        backend = FakeBackend()
        engine = Mock()
        engine.get_levels.return_value = (0.0, 0.0, 0.0)
        status_ready = threading.Event()

        def make_keeper(on_status):
            def report(status):
                on_status(status)
                if status['state'] == 'on':
                    status_ready.set()
            return VolumeKeeper(report, backend_factory=lambda: backend)

        inputs = [{'index': 36, 'name': 'Головной телефон (2- EarPods)', 'channels': 1}]
        outputs = [{'index': 27, 'name': 'CABLE Input (VB-Audio Virtual Cable)', 'channels': 2}]
        with patch('noiseclean.ui.app.settings.load', return_value={'power_on': False}), \
                patch('noiseclean.ui.app.settings.save') as save, \
                patch('noiseclean.ui.app.AudioEngine', return_value=engine), \
                patch('noiseclean.ui.app.VolumeKeeper', side_effect=make_keeper), \
                patch.object(NoiseCleanApp, '_build_tray'), \
                patch.object(NoiseCleanApp, '_post_show', lambda self: None), \
                patch('noiseclean.ui.app.devmod.list_inputs', return_value=inputs), \
                patch('noiseclean.ui.app.devmod.list_outputs', return_value=outputs), \
                patch('noiseclean.ui.app.devmod.default_input_index', return_value=36), \
                patch('noiseclean.ui.app.devmod.guess_virtual_output', return_value=27), \
                patch('noiseclean.ui.app.devmod.device_name', side_effect=lambda i: inputs[0]['name'] if i == 36 else outputs[0]['name']), \
                patch('noiseclean.ui.app.resolve_endpoint', side_effect=lambda i, f: 'mic-id' if f == 'input' else 'cable-in-id'), \
                patch('noiseclean.ui.app.list_virtual_capture_endpoints', return_value=[
                    {'endpoint_id': 'cable-out-id', 'name': 'CABLE Output'},
                    {'endpoint_id': 'line-1-id', 'name': 'Line 1'},
                    {'endpoint_id': 'line-2-id', 'name': 'Line 2'}]), \
                patch('noiseclean.ui.app.assets._cache', {}):
            app = NoiseCleanApp(root)
            try:
                root.geometry('940x696+10000+10000')
                root.deiconify()
                root.update()
                app._drain_tray()
                self.assertIsNone(app._volume_keeper._thread)
                self.assertLessEqual(app.volume_button.winfo_rooty() - root.winfo_rooty()
                                     + app.volume_button.winfo_height(), root.winfo_height())
                app._open_volume_settings()
                dialog = app._volume_dialog
                dialog.enabled.set(True)
                dialog.input_level.set('99')
                dialog.output_level.set('100')
                dialog.apply()
                self.assertTrue(status_ready.wait(2))
                app._drain_tray()
                self.assertEqual(app._volume_status['state'], 'on')
                self.assertEqual(backend.endpoints['mic-id'].writes, [.99])
                self.assertEqual(save.call_args.args[0]['volume_lock']['input_level'], 99)
                self.assertEqual(len(save.call_args.args[0]['volume_lock']['extra_inputs']), 3)
                self.assertEqual(backend.endpoints['cable-out-id'].writes, [1.0])
                self.assertEqual(backend.endpoints['line-1-id'].writes, [1.0])
                self.assertEqual(backend.endpoints['line-2-id'].writes, [1.0])
                dialog.close()
                app._tray = Mock()
                app._on_close()
                self.assertEqual(root.state(), 'withdrawn')
                self.assertTrue(app._volume_keeper._thread.is_alive())
                engine.start.assert_not_called()
            finally:
                app._quit()
            self.assertFalse(app._volume_keeper._thread.is_alive())


if __name__ == '__main__':
    unittest.main()
