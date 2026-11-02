import threading
import time

from pynput.keyboard import Controller as KeyboardController
from pynput.keyboard import Key

from pynput.mouse import Controller as MouseController
from pynput.mouse import Button


class MacroPlayer:
    """Threaded macro player with real pause/resume support."""

    def __init__(self, on_finished=None):
        self.keyboard = KeyboardController()
        self.mouse = MouseController()

        self.playing = False
        self.paused = False
        self.thread = None

        self._pause_event = threading.Event()
        self._pause_event.set()
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._held_keys = set()
        self._held_buttons = set()
        self.on_finished = on_finished

    def play(self, events, speed=1.0, loop=1):
        with self._lock:
            if self.playing:
                return False

            if not events:
                return False

            try:
                speed = max(0.01, float(speed))
                loop = int(loop)
            except (TypeError, ValueError):
                raise ValueError("Kecepatan atau jumlah loop tidak valid.")
            if loop < 0:
                raise ValueError("Jumlah loop tidak boleh negatif.")
            previous = -1.0
            for event in events:
                timestamp = float(event["timestamp"])
                if timestamp < 0 or timestamp < previous:
                    raise ValueError("Timestamp event macro tidak valid.")
                previous = timestamp
            self.playing = True
            self.paused = False
            self._pause_event.set()
            self._stop_event.clear()

            self.thread = threading.Thread(
                target=self._play,
                args=(list(events), speed, loop),
                daemon=True,
            )
            self.thread.start()

        return True

    def pause(self):
        with self._lock:
            if not self.playing or self.paused:
                return False
            self.paused = True
            self._pause_event.clear()
        return True

    def resume(self):
        with self._lock:
            if not self.playing or not self.paused:
                return False
            self.paused = False
            self._pause_event.set()
        return True

    def toggle_pause(self):
        return self.resume() if self.paused else self.pause()

    def stop(self):
        with self._lock:
            self.playing = False
            self.paused = False
            self._pause_event.set()
            self._stop_event.set()
        self._release_held_inputs()

    def _wait_with_pause(self, delay):
        """Wait for delay while still responding quickly to pause/stop."""
        remaining = max(0.0, delay)
        while remaining > 0:
            if self._stop_event.is_set() or not self.playing:
                return False
            if self.paused:
                # Do not spend a macro's timing budget while paused.
                self._pause_event.wait(0.05)
                continue
            started = time.monotonic()
            if self._stop_event.wait(min(remaining, 0.05)):
                return False
            remaining -= time.monotonic() - started
        return self.playing and not self._stop_event.is_set()

    def _play(self, events, speed, loop):
        try:
            infinite = int(loop) == 0
            count = 0

            while self.playing and (infinite or count < int(loop)):
                previous = 0.0
                for event in events:
                    if not self.playing:
                        break

                    while self.paused and self.playing:
                        self._pause_event.wait(0.1)
                    if not self.playing:
                        break

                    delay = (float(event["timestamp"]) - previous) / speed
                    if delay > 0 and not self._wait_with_pause(delay):
                        break

                    if not self.playing:
                        break

                    previous = float(event["timestamp"])
                    self.execute(event)

                if not self.playing:
                    break

                count += 1

        finally:
            with self._lock:
                was_playing = self.playing
                self.playing = False
                self.paused = False
                self._pause_event.set()
                self._stop_event.set()

            self._release_held_inputs()

            if was_playing and self.on_finished:
                self.on_finished()

    def execute(self, event):
        event_type = event["event_type"]

        if event_type == "mouse_move":
            self.mouse.position = (event["x"], event["y"])

        elif event_type == "mouse_click":
            self.mouse.position = (event["x"], event["y"])
            button = self.convert_button(event["button"])
            if event["pressed"]:
                self.mouse.press(button)
                self._held_buttons.add(button)
            else:
                self.mouse.release(button)
                self._held_buttons.discard(button)

        elif event_type == "mouse_scroll":
            self.mouse.position = (event["x"], event["y"])
            self.mouse.scroll(event["dx"], event["dy"])

        elif event_type == "key_press":
            key = self.convert_key(event["key"])
            self.keyboard.press(key)
            self._held_keys.add(key)

        elif event_type == "key_release":
            key = self.convert_key(event["key"])
            self.keyboard.release(key)
            self._held_keys.discard(key)

    def _release_held_inputs(self):
        """Avoid leaving a modifier or mouse button held after an emergency stop."""
        for key in tuple(self._held_keys):
            try:
                self.keyboard.release(key)
            except Exception:
                pass
        self._held_keys.clear()
        for button in tuple(self._held_buttons):
            try:
                self.mouse.release(button)
            except Exception:
                pass
        self._held_buttons.clear()

    def convert_button(self, button):
        if "left" in button:
            return Button.left
        if "right" in button:
            return Button.right
        if "middle" in button:
            return Button.middle
        return Button.left

    def convert_key(self, key):
        if key.startswith("Key."):
            name = key.replace("Key.", "")
            if hasattr(Key, name):
                return getattr(Key, name)
        return key.replace("'", "")
