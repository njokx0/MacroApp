import threading
import time
from pynput import keyboard, mouse

from core.event import MacroEvent


class MacroRecorder:
    """Records global input callbacks without touching Flask's request thread."""

    CONTROL_KEYS = {keyboard.Key.f6, keyboard.Key.f7, keyboard.Key.f8, keyboard.Key.f9}

    def __init__(self, minimum_move=0):
        self.events = []
        self.recording = False
        self.keyboard_listener = None
        self.mouse_listener = None
        self.start_time = 0.0
        self.paused = False
        self._paused_at = None
        self._paused_duration = 0.0
        self.last_mouse_position = None
        # Zero preserves every trajectory point; callers can opt into a small
        # threshold for exceptionally noisy devices.
        self.minimum_move = max(0, int(minimum_move))
        self.event_count = 0
        self.current_mouse_position = None
        self._lock = threading.RLock()

    def _time(self):
        paused = time.perf_counter() - self._paused_at if self.paused and self._paused_at else 0.0
        return round(max(0.0, time.perf_counter() - self.start_time - self._paused_duration - paused), 6)

    def start(self):
        with self._lock:
            if self.recording:
                return False
            self.events.clear()
            self.event_count = 0
            self.last_mouse_position = None
            self._paused_duration = 0.0
            self._paused_at = None
            self.start_time = time.perf_counter()
            self.recording = True
            self.paused = False
            try:
                self.keyboard_listener = keyboard.Listener(on_press=self.on_press, on_release=self.on_release)
                self.mouse_listener = mouse.Listener(on_move=self.on_move, on_click=self.on_click, on_scroll=self.on_scroll)
                self.keyboard_listener.start()
                self.mouse_listener.start()
            except Exception:
                self.recording = False
                self._stop_listeners()
                raise
        return True

    def _stop_listeners(self):
        for listener_name in ("keyboard_listener", "mouse_listener"):
            listener = getattr(self, listener_name)
            if listener is not None:
                try:
                    listener.stop()
                finally:
                    setattr(self, listener_name, None)

    def stop(self):
        with self._lock:
            if not self.recording:
                return False
            self.recording = False
            self.paused = False
            self._paused_at = None
            self._stop_listeners()
        return True

    def pause(self):
        with self._lock:
            if not self.recording or self.paused:
                return False
            self.paused = True
            self._paused_at = time.perf_counter()
        return True

    def resume(self):
        with self._lock:
            if not self.recording or not self.paused:
                return False
            self._paused_duration += time.perf_counter() - self._paused_at
            self._paused_at = None
            self.paused = False
        return True

    def _is_control_shortcut(self, key):
        return key in self.CONTROL_KEYS

    def _append(self, event):
        with self._lock:
            if not self.recording or self.paused:
                return
            self.events.append(event)
            self.event_count += 1

    def on_press(self, key):
        if not self.recording or self.paused or self._is_control_shortcut(key):
            return
        self._append(MacroEvent("key_press", self._time(), key=str(key)))

    def on_release(self, key):
        if not self.recording or self.paused or self._is_control_shortcut(key):
            return
        self._append(MacroEvent("key_release", self._time(), key=str(key)))

    def on_move(self, x, y):
        if not self.recording or self.paused:
            return
        point = (int(x), int(y))
        self.current_mouse_position = point
        if self.last_mouse_position is not None and self.minimum_move:
            old_x, old_y = self.last_mouse_position
            if abs(old_x - point[0]) < self.minimum_move and abs(old_y - point[1]) < self.minimum_move:
                return
        self.last_mouse_position = point
        self._append(MacroEvent("mouse_move", self._time(), x=point[0], y=point[1]))

    def on_click(self, x, y, button, pressed):
        self.current_mouse_position = (int(x), int(y))
        if not self.recording or self.paused:
            return
        self._append(
            MacroEvent(
                "mouse_click", self._time(), x=int(x), y=int(y),
                button=str(button), pressed=pressed,
            )
        )

    def on_scroll(self, x, y, dx, dy):
        self.current_mouse_position = (int(x), int(y))
        if not self.recording or self.paused:
            return
        self._append(
            MacroEvent(
                "mouse_scroll", self._time(), x=int(x), y=int(y), dx=int(dx), dy=int(dy),
            )
        )

    def get_events(self):
        with self._lock:
            return [event.to_dict() for event in self.events]

    def replace_events(self, events):
        parsed = [self.event_from_dict(event) for event in events]
        if any(event.timestamp < 0 for event in parsed):
            raise ValueError("Timestamp macro tidak boleh negatif.")
        if any(right.timestamp < left.timestamp for left, right in zip(parsed, parsed[1:])):
            raise ValueError("Urutan timestamp macro tidak valid.")
        with self._lock:
            self.events = parsed
            self.event_count = len(parsed)

    def duration(self):
        with self._lock:
            return self._time() if self.recording else (self.events[-1].timestamp if self.events else 0.0)

    def get_event_count(self):
        with self._lock:
            return self.event_count

    def event_from_dict(self, data):
        allowed = {"event_type", "timestamp", "x", "y", "key", "button", "pressed", "dx", "dy"}
        clean = {key: value for key, value in data.items() if key in allowed}
        if not isinstance(clean.get("event_type"), str) or "timestamp" not in clean:
            raise ValueError("Event macro tidak valid.")
        clean["timestamp"] = float(clean["timestamp"])
        return MacroEvent(**clean)
