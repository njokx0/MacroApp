import tempfile
import time
import unittest
from pathlib import Path

from core.autoclicker import AutoClicker
from core.controller import MacroController
from core.player import MacroPlayer
from core.recorder import MacroRecorder
from core.storage import MacroStorage


class FakeKeyboard:
    def __init__(self):
        self.actions = []

    def press(self, key):
        self.actions.append(("press", str(key)))

    def release(self, key):
        self.actions.append(("release", str(key)))


class FakeMouse:
    def __init__(self):
        self.actions = []
        self.position = (0, 0)

    def press(self, button):
        self.actions.append(("press", str(button)))

    def release(self, button):
        self.actions.append(("release", str(button)))

    def click(self, button):
        self.actions.append(("click", str(button)))

    def scroll(self, dx, dy):
        self.actions.append(("scroll", dx, dy))


class StubRecorder:
    def __init__(self):
        self.running = False
        self.events = [{"event_type": "key_press", "timestamp": 0.0, "key": "'a'"}]

    def start(self):
        self.running = True
        return True

    def stop(self):
        was_running, self.running = self.running, False
        return was_running

    def get_events(self):
        return list(self.events)

    def get_event_count(self):
        return len(self.events)

    def duration(self):
        return 0


class StubAutoClicker:
    def __init__(self):
        self.running = False
        self.clicks_completed = 0

    def start(self, *_args):
        self.running = True
        return True

    def stop(self):
        was_running, self.running = self.running, False
        return was_running


class MacroCoreTests(unittest.TestCase):
    def test_storage_is_versioned_and_reads_legacy_event_list(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = MacroStorage(Path(folder))
            storage.save("keuangan", [{"event_type": "mouse_move", "timestamp": 0.0, "x": 4, "y": 9}])
            loaded = storage.load("keuangan")
            self.assertEqual(loaded["version"], 1)
            self.assertEqual(loaded["events"][0]["x"], 4)
            self.assertEqual(storage.get_all_macros()[0]["event_count"], 1)
            with self.assertRaises(ValueError):
                storage.save("../unsafe", [])

    def test_recorder_validates_timestamp_order_when_loading(self):
        recorder = MacroRecorder()
        recorder.replace_events([{"event_type": "key_press", "timestamp": 0.0, "key": "'a'"}])
        self.assertEqual(recorder.get_event_count(), 1)
        with self.assertRaises(ValueError):
            recorder.replace_events([
                {"event_type": "key_press", "timestamp": 2, "key": "'a'"},
                {"event_type": "key_release", "timestamp": 1, "key": "'a'"},
            ])

    def test_player_replays_order_without_native_input(self):
        player = MacroPlayer()
        player.keyboard = FakeKeyboard()
        player.mouse = FakeMouse()
        events = [
            {"event_type": "mouse_move", "timestamp": 0.0, "x": 12, "y": 8},
            {"event_type": "key_press", "timestamp": 0.01, "key": "'a'"},
            {"event_type": "key_release", "timestamp": 0.02, "key": "'a'"},
        ]
        self.assertTrue(player.play(events))
        player.thread.join(timeout=1)
        self.assertFalse(player.playing)
        self.assertEqual(player.mouse.position, (12, 8))
        self.assertEqual(player.keyboard.actions, [("press", "a"), ("release", "a")])

    def test_player_repeats_the_requested_loop_count(self):
        player = MacroPlayer()
        player.keyboard = FakeKeyboard()
        player.mouse = FakeMouse()
        events = [
            {"event_type": "key_press", "timestamp": 0.0, "key": "'a'"},
            {"event_type": "key_release", "timestamp": 0.0, "key": "'a'"},
        ]
        self.assertTrue(player.play(events, speed=3, loop=3))
        player.thread.join(timeout=1)
        self.assertFalse(player.playing)
        self.assertEqual(player.keyboard.actions, [
            ("press", "a"), ("release", "a"),
            ("press", "a"), ("release", "a"),
            ("press", "a"), ("release", "a"),
        ])

    def test_player_scales_timing_by_speed(self):
        events = [
            {"event_type": "key_press", "timestamp": 0.0, "key": "'a'"},
            {"event_type": "key_release", "timestamp": 0.12, "key": "'a'"},
        ]

        def elapsed_at(speed):
            player = MacroPlayer()
            player.keyboard = FakeKeyboard()
            player.mouse = FakeMouse()
            started = time.monotonic()
            self.assertTrue(player.play(events, speed=speed))
            player.thread.join(timeout=1)
            return time.monotonic() - started

        normal_duration = elapsed_at(1)
        accelerated_duration = elapsed_at(3)
        self.assertGreater(normal_duration, 0.09)
        self.assertLess(accelerated_duration, normal_duration * 0.65)

    def test_controller_preserves_recording_while_autoclicker_runs(self):
        controller = MacroController(start_hotkeys=False)
        controller.recorder = StubRecorder()
        controller.autoclicker = StubAutoClicker()
        try:
            self.assertTrue(controller.start_record())
            self.assertEqual(controller.state, controller.RECORDING)
            self.assertTrue(controller.start_autoclicker())
            self.assertTrue(controller.autoclicker.running)
            self.assertEqual(controller.state, controller.RECORDING)
            self.assertTrue(controller.stop_all())
            self.assertFalse(controller.recorder.running)
            self.assertFalse(controller.autoclicker.running)
            self.assertEqual(controller.state, controller.IDLE)
        finally:
            controller.shutdown()

    def test_controller_uses_saved_playback_options_for_hotkeys(self):
        controller = MacroController(start_hotkeys=False)
        controller.recorder = StubRecorder()
        controller.player.keyboard = FakeKeyboard()
        controller.player.mouse = FakeMouse()
        try:
            controller.set_playback_options(speed=2, loop=2)
            self.assertTrue(controller.toggle_play_pause())
            controller.player.thread.join(timeout=1)
            self.assertEqual(controller.player.keyboard.actions, [("press", "a"), ("press", "a"), ("release", "a")])
            self.assertEqual(controller.state, controller.IDLE)
        finally:
            controller.shutdown()

    def test_autoclicker_finishes_exact_requested_count(self):
        clicker = AutoClicker()
        clicker.mouse = FakeMouse()
        self.assertTrue(clicker.start(interval=0.001, count=3))
        clicker._thread.join(timeout=1)
        self.assertFalse(clicker.running)
        self.assertEqual(clicker.clicks_completed, 3)
        self.assertEqual(len(clicker.mouse.actions), 3)


if __name__ == "__main__":
    unittest.main()
