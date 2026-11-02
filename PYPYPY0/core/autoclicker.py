"""A stoppable, low-CPU autoclicker."""

import random
import threading

from pynput.mouse import Button, Controller as MouseController


class AutoClicker:
    def __init__(self, on_finished=None):
        self.mouse = MouseController()
        self.running = False
        self.clicks_completed = 0
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._thread = None
        self.on_finished = on_finished

    @staticmethod
    def button_from_name(name):
        return {"left": Button.left, "right": Button.right, "middle": Button.middle}.get(name, Button.left)

    def start(self, interval=0.1, count=0, button="left", jitter=0.0):
        interval = max(0.001, float(interval))
        count = int(count)
        if count < 0:
            raise ValueError("Jumlah klik tidak boleh negatif.")
        with self._lock:
            if self.running:
                return False
            self.running = True
            self.clicks_completed = 0
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run,
                args=(interval, count, self.button_from_name(button), max(0.0, float(jitter))),
                daemon=True,
                name="macro-autoclicker",
            )
            self._thread.start()
        return True

    def stop(self):
        with self._lock:
            if not self.running:
                return False
            self.running = False
            self._stop_event.set()
        return True

    def _run(self, interval, count, button, jitter):
        naturally_finished = False
        try:
            while not self._stop_event.is_set() and (count == 0 or self.clicks_completed < count):
                self.mouse.click(button)
                self.clicks_completed += 1
                wait_for = max(0.001, interval + random.uniform(-jitter, jitter)) if jitter else interval
                if self._stop_event.wait(wait_for):
                    break
            naturally_finished = count > 0 and self.clicks_completed >= count
        finally:
            with self._lock:
                self.running = False
            if naturally_finished and self.on_finished:
                self.on_finished()
