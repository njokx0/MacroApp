import time
from core.recorder import MacroRecorder

recorder = MacroRecorder()

print("Recording selama 5 detik...")
recorder.start()

time.sleep(5)

recorder.stop()

print(f"Total event: {len(recorder.get_events())}")

for event in recorder.get_events()[:10]:
    print(event)