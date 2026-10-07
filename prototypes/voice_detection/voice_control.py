#!/usr/bin/env python3
"""
Voice Recognition Demo & State Controller for Robot Dog (Gruppe 17)
Engine: Vosk (Kaldi Offline German Speech Recognizer)
Language: German
Keywords: "Hier", "Sitz", "Platz", "Auf", "Such"

Behavior:
- Direct demo mode: recognizes any of the 5 keywords immediately without waiting window.
- Noise filtering: audio frames below a configurable RMS volume threshold are discarded
  before classification to prevent false triggers from background noise.
- De-duplication rule: repeating the same command does not re-trigger until a different command is given.
- GUI: live visual dashboard highlighting triggered keywords, volume meter with threshold marker,
  real-time noise gate status, and event log.
"""

import argparse
import json
import os
import queue
import sys
import threading
import time
import urllib.request
import zipfile
from collections import deque
from pathlib import Path
from typing import Callable, Dict, List, Optional

import numpy as np
import pyaudio
from vosk import Model, KaldiRecognizer, SetLogLevel

# Suppress verbose Vosk/Kaldi C++ logging
SetLogLevel(-1)

# ============================================================================
# CONFIGURATION
# ============================================================================
CONFIG = {
    # Audio stream parameters (16 kHz, 16-bit mono PCM)
    "sample_rate": 16000,
    "chunk_size": 1600,  # 1600 samples @ 16kHz = 100 ms frame
    "channels": 1,
    "audio_queue_max_size": 50,
    "input_device_index": None,  # Set to int if using a specific microphone index
    "debug": False,

    # Noise filtering & Voice Activity Detection (VAD) settings
    # Frames with RMS below volume_threshold are ignored and never fed to the classifier
    "volume_threshold": 750.0,      # Minimum RMS volume required to classify input
    "silence_hangover_chunks": 4,   # Keep classifying for ~400ms of trailing audio after speech drops
    "pre_roll_chunks": 2,           # Keep ~200ms pre-trigger audio to prevent clipping word onsets

    # Vosk Model settings
    "model_dir": Path(__file__).parent / "models",
    "model_name": "vosk-model-small-de-0.15",
    "model_download_url": "https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip",

    # Target German Keywords: lowercase token -> Display Name
    "keywords": {
        "hier": "Hier",
        "sitz": "Sitz",
        "platz": "Platz",
        "auf": "Auf",
        "such": "Such",
    },
}


# ============================================================================
# VOICE DETECTOR ENGINE
# ============================================================================
class VoiceDetector:
    """
    Background audio processing engine running grammar-constrained Vosk recognition.
    Filters ambient noise using an RMS volume threshold gate, and enforces the
    de-duplication rule (identical repeated words do not re-trigger until a
    different valid keyword is spoken).
    """

    def __init__(
        self,
        config: dict,
        on_triggered: Optional[Callable[[str, str], None]] = None,
        on_ignored_repeat: Optional[Callable[[str], None]] = None,
        on_volume_update: Optional[Callable[[float, bool, float], None]] = None,
    ) -> None:
        self.cfg = config
        self.on_triggered = on_triggered
        self.on_ignored_repeat = on_ignored_repeat
        self.on_volume_update = on_volume_update

        # Noise filter parameters
        self.volume_threshold = float(self.cfg.get("volume_threshold", 750.0))
        self.silence_hangover = int(self.cfg.get("silence_hangover_chunks", 4))
        self.pre_roll_chunks = int(self.cfg.get("pre_roll_chunks", 2))

        self.last_triggered_word: Optional[str] = None
        self.is_running = False

        self.audio_queue: queue.Queue[bytes] = queue.Queue(
            maxsize=self.cfg["audio_queue_max_size"]
        )
        self.pa: Optional[pyaudio.PyAudio] = None
        self.stream: Optional[pyaudio.Stream] = None

        self.rec: KaldiRecognizer = self._init_vosk_engine()

    def set_volume_threshold(self, threshold: float) -> None:
        """Dynamically update the noise filter RMS volume threshold."""
        self.volume_threshold = max(0.0, float(threshold))

    def _ensure_model_exists(self) -> Path:
        """Verify the German Vosk model exists; download and extract automatically if missing."""
        model_dir = Path(self.cfg["model_dir"])
        model_path = model_dir / self.cfg["model_name"]

        if model_path.is_dir():
            return model_path

        model_dir.mkdir(parents=True, exist_ok=True)
        zip_path = model_dir / f"{self.cfg['model_name']}.zip"

        print(f"[MODEL] German Vosk model not found at '{model_path}'.", flush=True)
        print(f"[MODEL] Downloading compact model (~45 MB) from {self.cfg['model_download_url']}...", flush=True)

        try:
            urllib.request.urlretrieve(self.cfg["model_download_url"], zip_path)
            print("[MODEL] Download complete. Extracting archive...", flush=True)
            with zipfile.ZipFile(zip_path, "r") as zip_ref:
                zip_ref.extractall(model_dir)
            if zip_path.is_file():
                os.remove(zip_path)
            print(f"[MODEL] Successfully installed model to '{model_path}'.\n", flush=True)
            return model_path
        except Exception as exc:
            if zip_path.is_file():
                os.remove(zip_path)
            raise RuntimeError(
                f"Failed to automatically download Vosk model: {exc}. "
                f"Please manually extract '{self.cfg['model_name']}' into '{model_dir}'."
            ) from exc

    def _init_vosk_engine(self) -> KaldiRecognizer:
        """Initialize Vosk Model with constrained keyword grammar."""
        model_path = self._ensure_model_exists()
        print(f"[VOSK] Loading German acoustic model from '{model_path.name}'...", flush=True)
        t0 = time.time()
        vosk_model = Model(str(model_path.resolve()))

        # Grammar strictly limits search graph to the 5 target words + [unk]
        keywords = list(self.cfg["keywords"].keys()) + ["[unk]"]
        grammar_json = json.dumps(keywords)

        rec = KaldiRecognizer(vosk_model, self.cfg["sample_rate"], grammar_json)
        rec.SetWords(False)
        print(f"[VOSK] Engine ready in {time.time()-t0:.2f}s with grammar: {keywords}\n", flush=True)
        return rec

    def _audio_callback(self, in_data: bytes, frame_count: int, time_info: dict, status: int):
        """Hardware PyAudio stream callback."""
        if status & pyaudio.paInputOverflow:
            if self.audio_queue.full():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    pass

        try:
            self.audio_queue.put_nowait(in_data)
        except queue.Full:
            try:
                self.audio_queue.get_nowait()
                self.audio_queue.put_nowait(in_data)
            except queue.Empty:
                pass

        return (None, pyaudio.paContinue)

    def start_stream(self) -> None:
        """Initialize and start the microphone stream."""
        self.pa = pyaudio.PyAudio()

        try:
            device_index = self.cfg["input_device_index"]
            if device_index is None:
                default_info = self.pa.get_default_input_device_info()
                device_index = int(default_info["index"])
                device_name = default_info["name"]
            else:
                info = self.pa.get_device_info_by_index(device_index)
                device_name = info["name"]
            print(f"[AUDIO] Using microphone [Index {device_index}]: '{device_name}'", flush=True)
        except (IOError, OSError) as exc:
            self.stop()
            raise RuntimeError("No working microphone detected. Please check your mic connection.") from exc

        try:
            self.stream = self.pa.open(
                format=pyaudio.paInt16,
                channels=self.cfg["channels"],
                rate=self.cfg["sample_rate"],
                input=True,
                input_device_index=device_index,
                frames_per_buffer=self.cfg["chunk_size"],
                stream_callback=self._audio_callback,
            )
            self.stream.start_stream()
            self.is_running = True
        except (IOError, OSError) as exc:
            self.stop()
            raise RuntimeError(f"Failed to open microphone stream: {exc}") from exc

    def reset_state(self) -> None:
        """Clear the last triggered word so any word can trigger next."""
        self.last_triggered_word = None
        if self.rec:
            self.rec.Reset()

    def _handle_detected_text(self, detected_text: str) -> None:
        """Parse recognized text, filter [unk], and handle de-duplication."""
        if not detected_text or detected_text == "[unk]":
            return

        tokens = [w.strip().lower() for w in detected_text.split() if w.strip() != "[unk]"]
        if not tokens:
            return

        for tok in tokens:
            if tok in self.cfg["keywords"]:
                action_name = self.cfg["keywords"][tok]

                # DE-DUPLICATION RULE:
                # Repeated uses do not re-trigger until a different command is given!
                if tok == self.last_triggered_word:
                    if self.on_ignored_repeat:
                        self.on_ignored_repeat(action_name)
                    # Reset decoder buffer so it does not loop
                    self.rec.Reset()
                    break

                # New distinct word detected -> TRIGGER!
                self.last_triggered_word = tok
                self.rec.Reset()

                if self.on_triggered:
                    self.on_triggered(tok, action_name)
                break

    def process_loop(self) -> None:
        """
        Continuous audio decoding loop with RMS volume noise gate.
        Only feeds audio to Vosk when the input volume reaches or exceeds the threshold.
        """
        self.start_stream()

        pre_roll: deque[bytes] = deque(maxlen=self.pre_roll_chunks)
        speech_active = False
        silence_chunks = 0

        while self.is_running:
            try:
                raw_bytes = self.audio_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            # Compute RMS volume level of this 100ms frame
            pcm_arr = np.frombuffer(raw_bytes, dtype=np.int16)
            rms = float(np.sqrt(np.mean(pcm_arr.astype(np.float32) ** 2)))

            is_above_threshold = (rms >= self.volume_threshold)

            if is_above_threshold:
                # Volume reached the threshold: active speech / command!
                silence_chunks = 0
                if not speech_active:
                    speech_active = True
                    # Replay pre-roll frames so leading consonants (e.g. 'S' or 'H') aren't clipped
                    while pre_roll:
                        pr_bytes = pre_roll.popleft()
                        self.rec.AcceptWaveform(pr_bytes)
            else:
                # Volume below threshold (ambient noise or pause)
                if speech_active:
                    silence_chunks += 1
                    if silence_chunks > self.silence_hangover:
                        # Hangover window elapsed: finalize utterance
                        speech_active = False
                        silence_chunks = 0
                        final_res = json.loads(self.rec.Result())
                        final_text = final_res.get("text", "")
                        self._handle_detected_text(final_text)
                else:
                    # Pure noise below threshold: keep in pre-roll and skip classification
                    pre_roll.append(raw_bytes)

            is_gate_open = speech_active or is_above_threshold

            # Notify volume meter listeners
            if self.on_volume_update:
                try:
                    self.on_volume_update(rms, is_gate_open, self.volume_threshold)
                except TypeError:
                    self.on_volume_update(rms)

            # If input is below threshold and not in hangover window, SKIP CLASSIFICATION!
            if not is_gate_open:
                continue

            # Feed active frame to recognizer
            detected_text = ""
            if self.rec.AcceptWaveform(raw_bytes):
                res = json.loads(self.rec.Result())
                detected_text = res.get("text", "")
            else:
                part = json.loads(self.rec.PartialResult())
                detected_text = part.get("partial", "")

            self._handle_detected_text(detected_text)

    def stop(self) -> None:
        """Clean up audio streams."""
        self.is_running = False
        if self.stream is not None:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
            self.stream = None

        if self.pa is not None:
            try:
                self.pa.terminate()
            except Exception:
                pass
            self.pa = None


# ============================================================================
# MODERN TKINTER GUI
# ============================================================================
def launch_gui(config: dict):
    """Launch the graphical interface for the voice control demo."""
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("Roboterhund Gruppe 17 - Voice Control Demo")
    root.geometry("640x740")
    root.minsize(580, 640)
    root.configure(bg="#0F172A")  # Tailwind slate-900

    # Thread-safe event communication queue
    gui_queue = queue.Queue()

    # Callback bridges from background audio thread to GUI
    def on_triggered_cb(tok: str, action: str):
        gui_queue.put(("TRIGGER", action, time.strftime("%H:%M:%S")))

    def on_ignored_repeat_cb(action: str):
        gui_queue.put(("IGNORED", action, time.strftime("%H:%M:%S")))

    def on_volume_update_cb(rms: float, gate_open: bool, thresh: float):
        gui_queue.put(("VOLUME", rms, gate_open, thresh))

    detector = VoiceDetector(
        config,
        on_triggered=on_triggered_cb,
        on_ignored_repeat=on_ignored_repeat_cb,
        on_volume_update=on_volume_update_cb,
    )

    # ------------------ STYLES & LAYOUT ------------------
    header_frame = tk.Frame(root, bg="#0F172A")
    header_frame.pack(fill="x", padx=24, pady=(20, 10))

    title_lbl = tk.Label(
        header_frame,
        text="Roboterhund Gruppe 17",
        font=("Segoe UI", 18, "bold"),
        fg="#F8FAFC",
        bg="#0F172A",
    )
    title_lbl.pack(anchor="w")

    subtitle_lbl = tk.Label(
        header_frame,
        text="Offline German Speech Recognition (Vosk) - Noise-Filtered Demo",
        font=("Segoe UI", 10),
        fg="#94A3B8",
        bg="#0F172A",
    )
    subtitle_lbl.pack(anchor="w", pady=(2, 0))

    # Big Card Display for the Triggered Keyword
    hero_frame = tk.Frame(root, bg="#1E293B", highlightthickness=1, highlightbackground="#334155")
    hero_frame.pack(fill="x", padx=24, pady=10)

    hero_prompt = tk.Label(
        hero_frame,
        text="CURRENT ACTIVE COMMAND",
        font=("Segoe UI", 9, "bold"),
        fg="#94A3B8",
        bg="#1E293B",
    )
    hero_prompt.pack(pady=(14, 2))

    hero_label = tk.Label(
        hero_frame,
        text="Bereit...",
        font=("Segoe UI", 36, "bold"),
        fg="#38BDF8",  # Sky blue
        bg="#1E293B",
    )
    hero_label.pack(pady=2)

    status_sub = tk.Label(
        hero_frame,
        text="Say any keyword: Hier, Sitz, Platz, Auf, Such",
        font=("Segoe UI", 10),
        fg="#CBD5E1",
        bg="#1E293B",
    )
    status_sub.pack(pady=(0, 14))

    # Keyword Badges Row
    badge_container = tk.Frame(root, bg="#0F172A")
    badge_container.pack(fill="x", padx=24, pady=6)

    badge_labels: Dict[str, tk.Label] = {}
    for kw_key, kw_name in config["keywords"].items():
        box = tk.Label(
            badge_container,
            text=kw_name.upper(),
            font=("Segoe UI", 11, "bold"),
            fg="#64748B",
            bg="#1E293B",
            relief="flat",
            padx=12,
            pady=8,
            highlightthickness=1,
            highlightbackground="#334155",
        )
        box.pack(side="left", expand=True, fill="x", padx=4)
        badge_labels[kw_name] = box

    # Rule Explanation Banner
    rule_banner = tk.Label(
        root,
        text="Note: Repeating the same word is ignored until a different word is spoken.",
        font=("Segoe UI", 9, "italic"),
        fg="#94A3B8",
        bg="#0F172A",
    )
    rule_banner.pack(pady=(2, 6))

    # Real-Time Volume Level Bar & Noise Filter Controls Card
    filter_card = tk.Frame(root, bg="#1E293B", highlightthickness=1, highlightbackground="#334155")
    filter_card.pack(fill="x", padx=24, pady=6)

    vol_top_row = tk.Frame(filter_card, bg="#1E293B")
    vol_top_row.pack(fill="x", padx=14, pady=(10, 4))

    vol_title = tk.Label(
        vol_top_row,
        text="Microphone Input & Noise Gate",
        font=("Segoe UI", 10, "bold"),
        fg="#F1F5F9",
        bg="#1E293B",
    )
    vol_title.pack(side="left")

    gate_badge = tk.Label(
        vol_top_row,
        text="○ NOISE FILTERED",
        font=("Segoe UI", 9, "bold"),
        fg="#94A3B8",
        bg="#334155",
        padx=8,
        pady=2,
    )
    gate_badge.pack(side="right")

    # Meter canvas (shows volume bar + threshold marker line)
    vol_canvas = tk.Canvas(filter_card, width=540, height=14, bg="#0F172A", highlightthickness=0)
    vol_canvas.pack(fill="x", padx=14, pady=4)
    vol_rect = vol_canvas.create_rectangle(0, 0, 0, 14, fill="#38BDF8")
    thresh_line = vol_canvas.create_line(0, 0, 0, 14, fill="#F59E0B", width=2)

    # Threshold slider controls
    slider_row = tk.Frame(filter_card, bg="#1E293B")
    slider_row.pack(fill="x", padx=14, pady=(4, 10))

    slider_lbl = tk.Label(
        slider_row,
        text="Volume Threshold:",
        font=("Segoe UI", 9),
        fg="#94A3B8",
        bg="#1E293B",
    )
    slider_lbl.pack(side="left")

    thresh_val_lbl = tk.Label(
        slider_row,
        text=f"{detector.volume_threshold:.0f} RMS",
        font=("Segoe UI", 9, "bold"),
        fg="#F59E0B",
        bg="#1E293B",
        width=10,
        anchor="w",
    )
    thresh_val_lbl.pack(side="left", padx=(6, 12))

    def on_slider_change(val_str):
        new_val = float(val_str)
        detector.set_volume_threshold(new_val)
        thresh_val_lbl.config(text=f"{new_val:.0f} RMS")

    thresh_scale = tk.Scale(
        slider_row,
        from_=100,
        to=2500,
        orient="horizontal",
        resolution=25,
        showvalue=False,
        bg="#1E293B",
        fg="#F1F5F9",
        troughcolor="#0F172A",
        activebackground="#38BDF8",
        highlightthickness=0,
        bd=0,
        command=on_slider_change,
    )
    thresh_scale.set(int(detector.volume_threshold))
    thresh_scale.pack(side="left", fill="x", expand=True)

    # Command History / Event Log
    log_frame = tk.Frame(root, bg="#1E293B", highlightthickness=1, highlightbackground="#334155")
    log_frame.pack(fill="both", expand=True, padx=24, pady=(6, 10))

    log_title = tk.Label(
        log_frame,
        text="TRIGGER HISTORY",
        font=("Segoe UI", 9, "bold"),
        fg="#94A3B8",
        bg="#1E293B",
    )
    log_title.pack(anchor="w", padx=12, pady=(8, 4))

    log_listbox = tk.Listbox(
        log_frame,
        font=("Consolas", 10),
        fg="#F1F5F9",
        bg="#0F172A",
        selectbackground="#334155",
        highlightthickness=0,
        bd=0,
    )
    log_listbox.pack(fill="both", expand=True, padx=12, pady=(0, 8))

    # Bottom Button Controls
    btn_frame = tk.Frame(root, bg="#0F172A")
    btn_frame.pack(fill="x", padx=24, pady=(0, 16))

    def on_reset_click():
        detector.reset_state()
        hero_label.config(text="Bereit...", fg="#38BDF8")
        status_sub.config(text="State reset. Any word can trigger now.", fg="#CBD5E1")
        for b in badge_labels.values():
            b.config(bg="#1E293B", fg="#64748B", highlightbackground="#334155")
        log_listbox.insert(0, f"[{time.strftime('%H:%M:%S')}] --- State Reset ---")

    reset_btn = tk.Button(
        btn_frame,
        text="Reset Active Word",
        font=("Segoe UI", 10),
        bg="#334155",
        fg="#F8FAFC",
        activebackground="#475569",
        activeforeground="#F8FAFC",
        bd=0,
        padx=14,
        pady=6,
        command=on_reset_click,
    )
    reset_btn.pack(side="left")

    def on_clear_log():
        log_listbox.delete(0, tk.END)

    clear_btn = tk.Button(
        btn_frame,
        text="Clear Log",
        font=("Segoe UI", 10),
        bg="#1E293B",
        fg="#94A3B8",
        activebackground="#334155",
        activeforeground="#F8FAFC",
        bd=0,
        padx=12,
        pady=6,
        command=on_clear_log,
    )
    clear_btn.pack(side="right")

    # ------------------ EVENT PUMP ------------------
    def process_gui_events():
        while not gui_queue.empty():
            ev = gui_queue.get_nowait()
            ev_type = ev[0]

            if ev_type == "TRIGGER":
                _, action_name, t_str = ev
                # 1. Update big hero label
                hero_label.config(text=action_name.upper(), fg="#10B981")  # Emerald Green
                status_sub.config(
                    text=f"Triggered at {t_str} (repeat '{action_name}' blocked until other word)",
                    fg="#34D399",
                )

                # 2. Highlight badge
                for kw_name, b_lbl in badge_labels.items():
                    if kw_name.lower() == action_name.lower():
                        b_lbl.config(bg="#10B981", fg="#FFFFFF", highlightbackground="#059669")
                    else:
                        b_lbl.config(bg="#1E293B", fg="#64748B", highlightbackground="#334155")

                # 3. Log event
                log_entry = f"[{t_str}] >>> TRIGGER: {action_name.upper()} <<<"
                log_listbox.insert(0, log_entry)

            elif ev_type == "IGNORED":
                _, action_name, t_str = ev
                status_sub.config(
                    text=f"Ignored repeat: '{action_name}' already active!",
                    fg="#F59E0B",  # Amber/Yellow
                )
                log_entry = f"[{t_str}] Ignored repeat: '{action_name}'"
                log_listbox.insert(0, log_entry)

            elif ev_type == "VOLUME":
                _, rms, gate_open, thresh = ev
                canvas_w = vol_canvas.winfo_width()
                if canvas_w <= 1:
                    canvas_w = 540

                # Maximum meter range: 2500 RMS
                max_rms = 2500.0
                bar_len = min(canvas_w, int((rms / max_rms) * canvas_w))
                thresh_x = min(canvas_w, int((thresh / max_rms) * canvas_w))

                # Update threshold marker line position
                vol_canvas.coords(thresh_line, thresh_x, 0, thresh_x, 14)

                # Update volume bar color and gate badge
                if gate_open:
                    bar_color = "#10B981"  # Emerald green (active speech)
                    gate_badge.config(
                        text="● CLASSIFYING (Speech)",
                        bg="#065F46",
                        fg="#34D399",
                    )
                else:
                    bar_color = "#334155"  # Muted slate (filtered background noise)
                    gate_badge.config(
                        text="○ NOISE FILTERED",
                        bg="#334155",
                        fg="#94A3B8",
                    )

                vol_canvas.coords(vol_rect, 0, 0, bar_len, 14)
                vol_canvas.itemconfig(vol_rect, fill=bar_color)

        root.after(30, process_gui_events)

    root.after(30, process_gui_events)

    # Start audio worker thread
    audio_thread = threading.Thread(target=detector.process_loop, daemon=True)
    audio_thread.start()

    def on_closing():
        detector.stop()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()


# ============================================================================
# HEADLESS CONSOLE RUNNER
# ============================================================================
def run_headless(config: dict):
    """Run in terminal mode without GUI."""
    thresh = config.get("volume_threshold", 750.0)
    print("============================================================")
    print(" HSLU PREN - Roboterhund Gruppe 17 (Voice Control Demo)")
    print(" Mode: Headless Console")
    print(f" Noise Filter: Active (Volume Threshold = {thresh:.0f} RMS)")
    print(" Commands: 'Hier', 'Sitz', 'Platz', 'Auf', 'Such'")
    print(" Rule: Repeated words do not re-trigger until a different word is spoken.")
    print("============================================================\n")

    def on_triggered_cb(tok: str, action: str):
        t_str = time.strftime("%H:%M:%S")
        print(f"\n[{t_str}] >>> [ACTION EXECUTED] Command: {action.upper()} <<<", flush=True)

    def on_ignored_repeat_cb(action: str):
        t_str = time.strftime("%H:%M:%S")
        print(f"  [{t_str}] [IGNORED] Repeated '{action.upper()}' (say a different word to switch)", flush=True)

    detector = VoiceDetector(
        config,
        on_triggered=on_triggered_cb,
        on_ignored_repeat=on_ignored_repeat_cb,
    )

    try:
        detector.process_loop()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Exiting voice control...", flush=True)
    finally:
        detector.stop()


# ============================================================================
# HELPER: LIST AUDIO DEVICES
# ============================================================================
def list_input_devices() -> None:
    """List all available audio input devices for easy selection."""
    pa = pyaudio.PyAudio()
    print("\nAvailable Audio Input Devices:")
    print("=" * 60)
    for i in range(pa.get_device_count()):
        dev_info = pa.get_device_info_by_index(i)
        if dev_info.get("maxInputChannels", 0) > 0:
            print(f"  [{i:>2}] {dev_info.get('name')} (Max Channels: {dev_info.get('maxInputChannels')})")
    print("=" * 60 + "\n")
    pa.terminate()


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================
def main():
    parser = argparse.ArgumentParser(
        description="Voice Recognition Demo for Robot Dog (Gruppe 17)"
    )
    parser.add_argument(
        "--list-devices",
        action="store_true",
        help="List all connected microphone input devices and exit.",
    )
    parser.add_argument(
        "--device-index",
        type=int,
        default=None,
        help="PyAudio device index for the microphone (default: system default).",
    )
    parser.add_argument(
        "--volume-threshold",
        "-t",
        type=float,
        default=None,
        help="RMS volume threshold to filter ambient noise before classification (default: 750.0).",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run in console mode without launching the graphical dashboard.",
    )

    args = parser.parse_args()

    if args.list_devices:
        list_input_devices()
        return

    config = dict(CONFIG)
    if args.device_index is not None:
        config["input_device_index"] = args.device_index
    if args.volume_threshold is not None:
        config["volume_threshold"] = args.volume_threshold

    if args.headless:
        run_headless(config)
    else:
        launch_gui(config)


if __name__ == "__main__":
    main()
