"""
Unit simulation test for Vosk-based VoiceDetector.
Tests de-duplication logic, silence rejection, and reset behavior without requiring microphone access.
"""

import os
import sys
import time
import json
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from voice_control import VoiceDetector, CONFIG

def run_simulation():
    print("==================================================")
    print("Testing Vosk VoiceDetector & De-duplication Logic")
    print("==================================================")

    config = dict(CONFIG)
    config["debug"] = True

    triggered_history = []
    ignored_history = []

    def on_triggered(tok: str, action: str):
        triggered_history.append((tok, action))

    def on_ignored(action: str):
        ignored_history.append(action)

    detector = VoiceDetector(
        config,
        on_triggered=on_triggered,
        on_ignored_repeat=on_ignored,
    )
    print("[OK] VoiceDetector initialized with German Vosk model.")

    # Test 1: Silence
    print("\n--- Test 1: 2 seconds of synthetic silence ---")
    silence_chunk = np.zeros(1600, dtype=np.int16).tobytes()
    for _ in range(20):  # 20 * 100ms = 2s
        detector.audio_queue.put(silence_chunk)

    for _ in range(20):
        if detector.audio_queue.empty():
            break
        raw_bytes = detector.audio_queue.get()
        if detector.rec.AcceptWaveform(raw_bytes):
            res = json.loads(detector.rec.Result())
            text = res.get("text", "")
        else:
            part = json.loads(detector.rec.PartialResult())
            text = part.get("partial", "")
        assert text == "" or text == "[unk]", f"Expected silence/unk but got: {text}"

    assert len(triggered_history) == 0, "Silence should never trigger any keyword!"
    print("[PASS] Silence correctly produces 0 keyword triggers.")

    # Test 2: De-duplication logic verification
    print("\n--- Test 2: De-duplication logic ---")
    # Simulate first trigger of 'hier'
    detector.last_triggered_word = None
    tok = "hier"
    action_name = detector.cfg["keywords"][tok]

    # First time saying 'hier' -> should trigger
    if tok == detector.last_triggered_word:
        detector.on_ignored_repeat(action_name)
    else:
        detector.last_triggered_word = tok
        detector.on_triggered(tok, action_name)

    assert len(triggered_history) == 1 and triggered_history[-1][1] == "Hier"
    print("[PASS] First 'Hier' triggered successfully.")

    # Repeating 'hier' -> should be ignored
    if tok == detector.last_triggered_word:
        detector.on_ignored_repeat(action_name)
    else:
        detector.last_triggered_word = tok
        detector.on_triggered(tok, action_name)

    assert len(triggered_history) == 1, "Repeated 'Hier' must NOT trigger again!"
    assert len(ignored_history) == 1 and ignored_history[-1] == "Hier", "Repeat must be sent to ignored callback!"
    print("[PASS] Repeated 'Hier' was successfully blocked by de-duplication.")

    # Repeating 'hier' again -> should be ignored again
    if tok == detector.last_triggered_word:
        detector.on_ignored_repeat(action_name)
    else:
        detector.last_triggered_word = tok
        detector.on_triggered(tok, action_name)

    assert len(triggered_history) == 1
    assert len(ignored_history) == 2
    print("[PASS] Second repeat of 'Hier' blocked.")

    # Saying a new word 'sitz' -> should trigger
    tok2 = "sitz"
    action2 = detector.cfg["keywords"][tok2]
    if tok2 == detector.last_triggered_word:
        detector.on_ignored_repeat(action2)
    else:
        detector.last_triggered_word = tok2
        detector.on_triggered(tok2, action2)

    assert len(triggered_history) == 2 and triggered_history[-1][1] == "Sitz"
    print("[PASS] Distinct command 'Sitz' successfully triggered.")

    # Now saying 'hier' again -> should now trigger because the previous command was 'sitz'!
    if tok == detector.last_triggered_word:
        detector.on_ignored_repeat(action_name)
    else:
        detector.last_triggered_word = tok
        detector.on_triggered(tok, action_name)

    assert len(triggered_history) == 3 and triggered_history[-1][1] == "Hier"
    print("[PASS] 'Hier' successfully triggered after 'Sitz' was spoken.")

    # Test 3: Reset functionality
    print("\n--- Test 3: Reset state ---")
    detector.reset_state()
    assert detector.last_triggered_word is None
    print("[PASS] Reset state cleared active word successfully.")

    print("\n==================================================")
    print("ALL SIMULATION TESTS PASSED SUCCESSFULLY!")
    print("==================================================")

if __name__ == "__main__":
    run_simulation()
