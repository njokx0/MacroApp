"""Single owner for macro state, input workers, persistence, and hotkeys."""

import atexit
import subprocess
import threading

from pynput import keyboard

from core.autoclicker import AutoClicker
from core.player import MacroPlayer
from core.recorder import MacroRecorder
from core.storage import MacroStorage


class MacroController:
    IDLE = "IDLE"
    RECORDING = "RECORDING"
    PAUSED_RECORDING = "PAUSED_RECORDING"
    PLAYING = "PLAYING"
    PAUSED_PLAYBACK = "PAUSED_PLAYBACK"
    AUTOCLICKING = "AUTOCLICKING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"

    HOTKEYS = {
        "record": keyboard.Key.f6,
        "play_pause": keyboard.Key.f7,
        "stop": keyboard.Key.f8,
        "autoclicker": keyboard.Key.f9,
        "click": keyboard.Key.ctrl,
    }

    def __init__(self, storage=None, start_hotkeys=True):
        self.recorder = MacroRecorder()
        self.player = MacroPlayer(on_finished=self._playback_finished)
        self.autoclicker = AutoClicker(on_finished=self._autoclicker_finished)
        self.storage = storage or MacroStorage()
        self.state = self.IDLE
        self.message = "Siap digunakan"
        self.loaded_macro = None
        self._loaded_metadata = {}
        # Playback preferences are kept separately from the activity state so
        # the global F7 shortcut honours the existing Settings controls too.
        self.playback_speed = 1.0
        self.playback_loop = 1
        self._state_lock = threading.RLock()
        self._hotkey_listener = None
        self.hotkey_error = None
        self.shutdown_mode = False  # Kept for compatibility with the original app.
        self._shutdown_scheduled = False
        if start_hotkeys:
            self._start_global_shortcuts()
        atexit.register(self.shutdown)

    @property
    def status(self):
        # Compatibility for existing routes/callers.
        return self.state

    def _set_state(self, state, message=None):
        with self._state_lock:
            self.state = state
            if message:
                self.message = message

    def _start_global_shortcuts(self):
        try:
            self._hotkey_listener = keyboard.Listener(on_press=self._on_hotkey)
            self._hotkey_listener.daemon = True
            self._hotkey_listener.start()
        except Exception as error:
            self.hotkey_error = f"Hotkey global tidak tersedia: {error}"
            self._hotkey_listener = None

    def _on_hotkey(self, key):
        try:
            if key == self.HOTKEYS["record"]:
                self.toggle_record()
            elif key == self.HOTKEYS["play_pause"]:
                self.toggle_play_pause()
            elif key == self.HOTKEYS["stop"]:
                self.stop_all()
            elif key == self.HOTKEYS["autoclicker"]:
                self.toggle_autoclicker()
        except Exception as error:
            self._set_state(self.ERROR, f"Hotkey gagal dijalankan: {error}")

    # Recording ---------------------------------------------------------
    def start_record(self):
        with self._state_lock:
            # Recording and the autoclicker are intentionally allowed to run
            # together. The recorder's listeners capture the generated clicks
            # just like any other mouse input.
            if self.state not in {self.IDLE, self.ERROR, self.AUTOCLICKING}:
                return False
            self.player.stop()
            try:
                self.recorder.start()
            except Exception as error:
                self._set_state(self.ERROR, f"Gagal memulai recording: {error}")
                return False
            self._set_state(self.RECORDING, "Sedang merekam input")
            return True

    def pause_record(self):
        if self.recorder.pause():
            self._set_state(self.PAUSED_RECORDING, "Recording dijeda")
            return True
        return False

    def resume_record(self):
        if self.recorder.resume():
            self._set_state(self.RECORDING, "Sedang merekam input")
            return True
        return False

    def toggle_record(self):
        if self.state == self.RECORDING:
            return self.stop_record()
        if self.state == self.PAUSED_RECORDING:
            return self.resume_record()
        return self.start_record()

    def stop_record(self):
        if self.state not in {self.RECORDING, self.PAUSED_RECORDING}:
            return False
        self._set_state(self.STOPPING, "Menghentikan recording")
        success = self.recorder.stop()
        next_state = self.AUTOCLICKING if self.autoclicker.running else self.IDLE
        self._set_state(next_state, f"Recording selesai: {self.recorder.get_event_count()} event")
        return success

    # Playback ----------------------------------------------------------
    def set_playback_options(self, speed=1.0, loop=1):
        """Validate and retain the existing UI's speed and loop selections."""
        try:
            speed = max(0.01, float(speed))
            loop = int(loop)
        except (TypeError, ValueError) as error:
            raise ValueError("Kecepatan atau jumlah loop tidak valid.") from error
        if loop < 0:
            raise ValueError("Jumlah loop tidak boleh negatif.")
        with self._state_lock:
            self.playback_speed = speed
            self.playback_loop = loop
        return speed, loop

    def play(self, speed=None, loop=None):
        with self._state_lock:
            if self.state not in {self.IDLE, self.ERROR} or self.autoclicker.running:
                return False
            events = self.recorder.get_events()
            if not events:
                self.message = "Belum ada event untuk diputar"
                return False
            try:
                speed, loop = self.set_playback_options(
                    self.playback_speed if speed is None else speed,
                    self.playback_loop if loop is None else loop,
                )
            except (ValueError, KeyError, TypeError) as error:
                self._set_state(self.ERROR, f"Gagal memutar macro: {error}")
                return False

            # Set this before starting the thread. Otherwise a zero-duration
            # macro can finish and call _playback_finished before the state is
            # changed, leaving the dashboard permanently in PLAYING.
            self._set_state(self.PLAYING, "Macro sedang diputar")
            try:
                success = self.player.play(events, speed=speed, loop=loop)
            except (ValueError, KeyError, TypeError) as error:
                self._set_state(self.ERROR, f"Gagal memutar macro: {error}")
                return False
            if success:
                return True
            self._set_state(self.IDLE, "Macro tidak dapat diputar")
            return success

    def pause(self):
        if self.state == self.RECORDING:
            return self.pause_record()
        if self.player.pause():
            self._set_state(self.PAUSED_PLAYBACK, "Playback dijeda")
            return True
        return False

    def resume(self):
        if self.state == self.PAUSED_RECORDING:
            return self.resume_record()
        if self.player.resume():
            self._set_state(self.PLAYING, "Macro sedang diputar")
            return True
        return False

    def toggle_play_pause(self):
        if self.state == self.PLAYING:
            return self.pause()
        if self.state == self.PAUSED_PLAYBACK:
            return self.resume()
        return self.play()

    def stop_play(self):
        if self.state not in {self.PLAYING, self.PAUSED_PLAYBACK}:
            return False
        self._set_state(self.STOPPING, "Menghentikan playback")
        self.player.stop()
        self._set_state(self.IDLE, "Playback dihentikan")
        return True

    def _playback_finished(self):
        if self.shutdown_mode:
            self.schedule_shutdown()
        elif self.state in {self.PLAYING, self.PAUSED_PLAYBACK}:
            self._set_state(self.IDLE, "Playback selesai")

    # Autoclicker -------------------------------------------------------
    def start_autoclicker(self, interval=0.1, count=0, button="left", jitter=0):
        with self._state_lock:
            if self.state not in {self.IDLE, self.ERROR, self.RECORDING, self.PAUSED_RECORDING}:
                return False
            try:
                success = self.autoclicker.start(interval, count, button, jitter)
            except (ValueError, TypeError) as error:
                self._set_state(self.ERROR, f"Pengaturan autoclicker tidak valid: {error}")
                return False
            if success:
                # Do not replace the recorder state: the dashboard must keep
                # showing that input is being captured while clicks are made.
                if self.state not in {self.RECORDING, self.PAUSED_RECORDING}:
                    self._set_state(self.AUTOCLICKING, "Autoclicker aktif")
            return success

    def stop_autoclicker(self):
        if not self.autoclicker.running:
            return False
        self.autoclicker.stop()
        if self.state == self.AUTOCLICKING:
            self._set_state(self.IDLE, "Autoclicker dihentikan")
        return True

    def toggle_autoclicker(self):
        return self.stop_autoclicker() if self.autoclicker.running else self.start_autoclicker()

    def _autoclicker_finished(self):
        if self.state == self.AUTOCLICKING:
            self._set_state(self.IDLE, "Autoclicker selesai")

    def stop_all(self):
        """Emergency-stop every active worker, including record + autoclick."""
        stopped = False
        if self.state in {self.RECORDING, self.PAUSED_RECORDING}:
            stopped = self.recorder.stop() or stopped
        if self.state in {self.PLAYING, self.PAUSED_PLAYBACK}:
            self.player.stop()
            stopped = True
        if self.autoclicker.running:
            stopped = self.autoclicker.stop() or stopped
        if stopped:
            self._set_state(self.IDLE, "Semua aktivitas dihentikan")
        return stopped

    # Persistence -------------------------------------------------------
    def save(self, filename):
        path = self.storage.save(filename, self.recorder.get_events(), self._loaded_metadata)
        self.loaded_macro = str(filename).removesuffix(".json")
        return path

    def load(self, filename):
        if self.state not in {self.IDLE, self.ERROR}:
            raise RuntimeError("Hentikan aktivitas yang berjalan sebelum memuat macro.")
        document = self.storage.load(filename)
        self.recorder.replace_events(document["events"])
        self.loaded_macro = document.get("name") or str(filename)
        self._loaded_metadata = {"created_at": document.get("created_at")}
        self._set_state(self.IDLE, f"Macro '{self.loaded_macro}' dimuat")
        return document

    def delete_macro(self, filename):
        if self.state not in {self.IDLE, self.ERROR}:
            raise RuntimeError("Hentikan aktivitas yang berjalan sebelum menghapus macro.")
        return self.storage.delete(filename)

    # Original optional shutdown mode ----------------------------------
    def toggle_shutdown_mode(self):
        self.shutdown_mode = not self.shutdown_mode
        return self.shutdown_mode

    def schedule_shutdown(self, seconds=5):
        if self._shutdown_scheduled:
            return False
        try:
            subprocess.run(["shutdown", "/s", "/t", str(int(seconds))], check=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self._shutdown_scheduled = True
            self._set_state(self.IDLE, "Shutdown terjadwal")
            return True
        except (OSError, subprocess.SubprocessError):
            self._set_state(self.ERROR, "Gagal menjadwalkan shutdown")
            return False

    def cancel_shutdown(self):
        if not self._shutdown_scheduled:
            return False
        try:
            subprocess.run(["shutdown", "/a"], check=True,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            self._shutdown_scheduled = False
            self._set_state(self.IDLE, "Shutdown dibatalkan")
            return True
        except (OSError, subprocess.SubprocessError):
            return False

    def snapshot(self):
        return {
            "state": self.state,
            "message": self.message,
            "event_count": self.recorder.get_event_count(),
            "duration": self.recorder.duration(),
            "mouse_position": self.recorder.current_mouse_position,
            "loaded_macro": self.loaded_macro,
            "playback_active": self.player.playing,
            "autoclicker_active": self.autoclicker.running,
            "autoclicker_clicks": self.autoclicker.clicks_completed,
            "hotkeys": {name: key.name.upper() for name, key in self.HOTKEYS.items()},
            "hotkey_error": self.hotkey_error,
            "shutdown_mode": self.shutdown_mode,
            "playback_speed": self.playback_speed,
            "playback_loop": self.playback_loop,
        }

    def get_status(self):
        return self.state

    def get_events(self):
        return self.recorder.get_events()

    def get_macro_list(self):
        return self.storage.get_all_macros()

    def shutdown(self):
        self.stop_all()
        if self._hotkey_listener is not None:
            try:
                self._hotkey_listener.stop()
            except Exception:
                pass
            self._hotkey_listener = None
