#!/usr/bin/env python3
"""
Voice-Controlled State Machine for Raspberry Pi 5 (Robot Dog - Gruppe 17)
Engine: openWakeWord (ONNX Runtime)
Language: German
Activation Phrase: "Hier"
Command Keywords: "Sitz", "Platz", "Auf", "Such"
"""

import inspect
import os
import queue
import sys
import time
from enum import Enum, auto
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pyaudio
import openwakeword
from openwakeword.model import Model


# ============================================================================
# CONFIGURATION
# ============================================================================
CONFIG = {
    # Audio stream parameters required by openWakeWord (16 kHz, 16-bit mono, 80ms chunks)
    "sample_rate": 16000,
    "chunk_size": 1280,  # 1280 samples @ 16kHz = 80 ms frame
    "channels": 1,
    "audio_queue_max_size": 50,
    "input_device_index": None,  # Set to int if using a specific USB/I2S mic index

    # Inference settings
    "inference_framework": "onnx",
    "default_threshold": 0.5,
    "active_window_seconds": 5.0,
    "cooldown_seconds": 0.6,  # Brief refractory window after state change

    # Directory containing your trained custom .onnx wakeword models
    "model_dir": Path(__file__).parent / "models",

    # 1 Activation Phrase (German: "Hier")
    "activation_phrase": {
        "label": "Hier",
        "model_path": "hier.onnx",
        "threshold": 0.5,
    },

    # 4 Custom Command Keywords (German: "Sitz", "Platz", "Auf", "Such")
    "commands": {
        "Sitz": {
            "action_name": "Sitz",
            "model_path": "sitz.onnx",
            "threshold": 0.5,
        },
        "Platz": {
            "action_name": "Platz",
            "model_path": "platz.onnx",
            "threshold": 0.5,
        },
        "Auf": {
            "action_name": "Auf",
            "model_path": "auf.onnx",
            "threshold": 0.5,
        },
        "Such": {
            "action_name": "Such",
            "model_path": "such.onnx",
            "threshold": 0.5,
        },
    },
}


# ============================================================================
# STATE MACHINE DEFINITIONS
# ============================================================================
class ListeningState(Enum):
    PASSIVE = auto()  # State A (IDLE): Only listens for Activation Phrase ("Hier")
    ACTIVE = auto()   # State B (ACTIVE): 5-second window listening for the 4 commands


class VoiceStateMachine:
    """
    Non-blocking voice state machine running 5 concurrent ONNX models on a
    single shared openWakeWord audio feature extraction pipeline.
    """

    def __init__(self, config: dict) -> None:
        self.cfg = config
        self.state = ListeningState.PASSIVE
        self.active_since: float = 0.0
        self.ignore_until: float = 0.0

        self.audio_queue: queue.Queue[bytes] = queue.Queue(
            maxsize=self.cfg["audio_queue_max_size"]
        )
        self.pa: Optional[pyaudio.PyAudio] = None
        self.stream: Optional[pyaudio.Stream] = None

        # Map openWakeWord internal model key -> metadata
        self.activation_key: str = ""
        self.command_key_map: Dict[str, dict] = {}

        self.oww_model = self._init_wakeword_engine()

    def _resolve_model_path(self, filename: str) -> str:
        """Resolve model path relative to model_dir or current path."""
        candidate = Path(filename)
        if candidate.is_file():
            return str(candidate.resolve())

        in_model_dir = Path(self.cfg["model_dir"]) / filename
        if in_model_dir.is_file():
            return str(in_model_dir.resolve())

        return str(in_model_dir)

    def _init_wakeword_engine(self) -> Model:
        """Load the 1 activation model + 4 keyword models into a single ONNX engine."""
        # Ensure base feature extraction models (melspectrogram & embedding) exist
        try:
            openwakeword.utils.download_models()
        except Exception:
            # Offline fallback if base models are already cached locally
            pass

        act_cfg = self.cfg["activation_phrase"]
        act_path = self._resolve_model_path(act_cfg["model_path"])
        self.activation_key = Path(act_path).stem

        model_paths = [act_path]
        for label, cmd_cfg in self.cfg["commands"].items():
            cmd_path = self._resolve_model_path(cmd_cfg["model_path"])
            cmd_key = Path(cmd_path).stem
            self.command_key_map[cmd_key] = {
                "label": label,
                "action_name": cmd_cfg["action_name"],
                "threshold": cmd_cfg.get("threshold", self.cfg["default_threshold"]),
            }
            model_paths.append(cmd_path)

        missing = [p for p in model_paths if not os.path.isfile(p)]
        if missing:
            print("[ERROR] Missing custom ONNX model file(s):", file=sys.stderr)
            for m in missing:
                print(f"  - {m}", file=sys.stderr)
            print(
                "\nPlace your 5 German ONNX models (hier.onnx, sitz.onnx, platz.onnx, "
                "auf.onnx, such.onnx) in the 'VoiceDetection/models' directory.",
                file=sys.stderr,
            )
            sys.exit(1)

        # Support both openwakeword >=0.5 (`wakeword_models`) and legacy versions
        init_params = inspect.signature(Model.__init__).parameters
        model_arg_name = (
            "wakeword_models"
            if "wakeword_models" in init_params
            else "wakeword_model_paths"
        )

        kwargs = {
            model_arg_name: model_paths,
            "inference_framework": self.cfg["inference_framework"],
        }

        return Model(**kwargs)

    def _audio_callback(self, in_data: bytes, frame_count: int, time_info: dict, status: int):
        """
        Lightweight PyAudio hardware callback.
        Pushes raw 16-bit PCM chunks into a thread-safe queue without blocking the audio driver.
        """
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

    def _start_audio_stream(self) -> None:
        """Initialize PyAudio and verify microphone availability."""
        self.pa = pyaudio.PyAudio()

        try:
            device_index = self.cfg["input_device_index"]
            if device_index is None:
                default_info = self.pa.get_default_input_device_info()
                device_index = int(default_info["index"])
            else:
                self.pa.get_device_info_by_index(device_index)
        except (IOError, OSError) as exc:
            self._cleanup()
            raise RuntimeError(
                "No working microphone detected. Please check USB/I2S audio connection "
                "and ALSA/PipeWire settings (`arecord -l`)."
            ) from exc

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
        except (IOError, OSError) as exc:
            self._cleanup()
            raise RuntimeError(
                f"Failed to open microphone stream at {self.cfg['sample_rate']} Hz: {exc}"
            ) from exc

    def _transition_to_active(self, now: float) -> None:
        """Transition from State A (PASSIVE) -> State B (ACTIVE)."""
        self.state = ListeningState.ACTIVE
        self.active_since = now
        self.ignore_until = now + self.cfg["cooldown_seconds"]
        self.oww_model.reset()  # Flush prediction buffer to avoid residual triggers
        print(
            f"[ACTIVE] Activation '{self.cfg['activation_phrase']['label']}' detected! "
            f"Listening for keywords ({self.cfg['active_window_seconds']:.0f}s window)...",
            flush=True,
        )

    def _transition_to_passive(self, now: float, reason_log: str) -> None:
        """Transition from State B (ACTIVE) -> State A (PASSIVE)."""
        self.state = ListeningState.PASSIVE
        self.ignore_until = now + self.cfg["cooldown_seconds"]
        self.oww_model.reset()  # Clear rolling buffer before returning to IDLE
        print(reason_log, flush=True)
        print(
            f"[IDLE] Waiting for activation phrase ('{self.cfg['activation_phrase']['label']}')...",
            flush=True,
        )

    def _execute_command(self, action_name: str) -> None:
        """Execute the triggered robot command."""
        print(f"Executing: {action_name}", flush=True)

    def run(self) -> None:
        """Main non-blocking inference and state machine loop."""
        self._start_audio_stream()
        print(
            f"[IDLE] Waiting for activation phrase ('{self.cfg['activation_phrase']['label']}')...",
            flush=True,
        )

        act_threshold = self.cfg["activation_phrase"].get(
            "threshold", self.cfg["default_threshold"]
        )
        window_sec = self.cfg["active_window_seconds"]

        try:
            while True:
                now = time.monotonic()

                # Check timeout first so State B expires accurately even between audio chunks
                if (
                    self.state == ListeningState.ACTIVE
                    and (now - self.active_since) >= window_sec
                ):
                    self._transition_to_passive(
                        now, "[TIMEOUT] Returning to IDLE"
                    )

                try:
                    raw_bytes = self.audio_queue.get(timeout=0.05)
                except queue.Empty:
                    continue

                # Convert raw 16-bit PCM bytes to int16 numpy array expected by openWakeWord
                pcm_frame = np.frombuffer(raw_bytes, dtype=np.int16)

                # Single inference pass updates all 5 models simultaneously
                predictions: Dict[str, float] = self.oww_model.predict(pcm_frame)

                # Skip decisions during brief post-transition cooldown
                if now < self.ignore_until:
                    continue

                # ------------------------------------------------------------
                # STATE A: PASSIVE (IDLE)
                # Ignore all 4 command keywords; only respond to "Hier"
                # ------------------------------------------------------------
                if self.state == ListeningState.PASSIVE:
                    act_score = predictions.get(self.activation_key, 0.0)
                    if act_score >= act_threshold:
                        self._transition_to_active(now)

                # ------------------------------------------------------------
                # STATE B: ACTIVE (5-SECOND WINDOW)
                # Listen for "Sitz", "Platz", "Auf", "Such"
                # ------------------------------------------------------------
                elif self.state == ListeningState.ACTIVE:
                    for cmd_key, cmd_meta in self.command_key_map.items():
                        score = predictions.get(cmd_key, 0.0)
                        if score >= cmd_meta["threshold"]:
                            self._execute_command(cmd_meta["action_name"])
                            self._transition_to_passive(
                                now,
                                f"[RESET] Action '{cmd_meta['action_name']}' triggered. Returning to IDLE",
                            )
                            break

        except KeyboardInterrupt:
            print("\n[SHUTDOWN] Stopping voice controller...", flush=True)
        finally:
            self._cleanup()

    def _cleanup(self) -> None:
        """Cleanly close PyAudio stream and terminate PortAudio."""
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


if __name__ == "__main__":
    try:
        controller = VoiceStateMachine(CONFIG)
        controller.run()
    except RuntimeError as err:
        print(f"[FATAL] {err}", file=sys.stderr)
        sys.exit(1)
