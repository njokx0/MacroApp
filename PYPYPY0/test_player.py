import time

from core.recorder import MacroRecorder
from core.player import MacroPlayer

recorder = MacroRecorder()

print("Recording 5 detik...")

recorder.start()

time.sleep(5)

recorder.stop()

events = recorder.get_events()

print("Playback dimulai dalam 3 detik...")

time.sleep(3)

player = MacroPlayer()

player.play(events)

while player.playing:
    time.sleep(0.1)

print("Selesai")