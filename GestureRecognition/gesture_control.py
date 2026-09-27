#!/usr/bin/env python3
"""
Real-Time Gesture Control for Robot Dog (HSLU PREN1/PREN2 - Gruppe 17)
Tracks 21 3D Hand Landmarks using Google MediaPipe Tasks.

Recognized Commands:
- «AUF»   / UP   : Index pointing UP (with or without 'L' thumb)
- «PLATZ» / DOWN : Index pointing DOWN
- «SITZ»  / SIT  : Open palm facing camera
"""

import argparse
import os
from pathlib import Path
import sys
import time
from typing import Callable, List, Optional
import urllib.request

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions, RunningMode
import numpy as np

# Ensure local imports work regardless of execution working directory
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from gesture_classifier import GestureClassifier, GestureResult, GestureSmoother, GestureType


MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
MODEL_PATH = CURRENT_DIR / "hand_landmarker.task"

# MediaPipe Hand Landmark skeleton connections
HAND_CONNECTIONS = [
    # Thumb
    (0, 1), (1, 2), (2, 3), (3, 4),
    # Index
    (0, 5), (5, 6), (6, 7), (7, 8),
    # Middle
    (5, 9), (9, 10), (10, 11), (11, 12),
    # Ring
    (9, 13), (13, 14), (14, 15), (15, 16),
    # Pinky
    (13, 17), (0, 17), (17, 18), (18, 19), (19, 20)
]


def ensure_model_exists():
    """Ensure hand_landmarker.task is downloaded."""
    if not MODEL_PATH.exists() or MODEL_PATH.stat().st_size < 100000:
        print(f"[DOWNLOAD] Fetching MediaPipe hand landmarker model from Google Storage...")
        urllib.request.urlretrieve(MODEL_URL, str(MODEL_PATH))
        print(f"[OK] Model saved to {MODEL_PATH} ({MODEL_PATH.stat().st_size / 1e6:.1f} MB)")


class GestureController:
    """Captures camera frames, runs MediaPipe, and triggers robot dog gesture events."""

    def __init__(
        self,
        camera_id: int = 0,
        width: int = 640,
        height: int = 480,
        max_hands: int = 1,
        cooldown_seconds: float = 1.0,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        headless: bool = False,
        event_callback: Optional[Callable[[GestureType, GestureResult], None]] = None
    ):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.max_hands = max_hands
        self.cooldown_seconds = cooldown_seconds
        self.headless = headless
        self.event_callback = event_callback or self._default_event_handler

        ensure_model_exists()

        # Initialize MediaPipe HandLandmarker (single hand tracking by default)
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(MODEL_PATH)),
            running_mode=RunningMode.IMAGE,
            num_hands=self.max_hands,
            min_hand_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        self.landmarker = HandLandmarker.create_from_options(options)
        self.smoother = GestureSmoother(window_size=5, min_consensus=4, cooldown_seconds=cooldown_seconds)

        self.cap: Optional[cv2.VideoCapture] = None
        self.fps: float = 0.0

    def _default_event_handler(self, gesture: GestureType, result: GestureResult):
        """Standard console logger for triggered robot dog commands."""
        timestamp_str = time.strftime("%H:%M:%S")
        german = gesture.german_label
        print(f"\n============================================================")
        print(f" [GESTURE EVENT] Triggered Command: «{german}» ({gesture.value})")
        print(f" Time: {timestamp_str} | Hand: {result.hand_label} | Detail: {result.description}")
        print(f"============================================================\n", flush=True)

    def _draw_hand(self, image: np.ndarray, landmarks, h: int, w: int):
        """Draw 21 hand landmarks and connection lines on the frame."""
        points = []
        for lm in landmarks:
            cx, cy = int(lm.x * w), int(lm.y * h)
            points.append((cx, cy))

        # Draw bones
        for start_idx, end_idx in HAND_CONNECTIONS:
            cv2.line(image, points[start_idx], points[end_idx], (200, 200, 200), 2, cv2.LINE_AA)

        # Draw joints
        for i, (cx, cy) in enumerate(points):
            # Color fingertips in bright cyan, other joints in green
            color = (255, 255, 0) if i in [4, 8, 12, 16, 20] else (0, 255, 128)
            radius = 5 if i in [4, 8, 12, 16, 20] else 3
            cv2.circle(image, (cx, cy), radius, color, -1, cv2.LINE_AA)

    def _draw_hud(self, image: np.ndarray, current_gesture: GestureType, result: Optional[GestureResult], fps: float):
        """Draw real-time HUD with high-contrast color badge and stats."""
        h, w = image.shape[:2]

        # Top banner background (semi-transparent dark overlay)
        overlay = image.copy()
        cv2.rectangle(overlay, (0, 0), (w, 80), (20, 20, 20), -1)
        cv2.addWeighted(overlay, 0.75, image, 0.25, 0, image)

        # Determine color and text based on detected gesture
        if current_gesture == GestureType.SIT:
            badge_color = (0, 200, 50)      # Bright Green
            label_text = "SITZ / SIT (Open Palm)"
        elif current_gesture == GestureType.UP:
            badge_color = (255, 200, 0)     # Bright Cyan/Sky Blue
            label_text = "AUF / UP (Index Up)"
        elif current_gesture == GestureType.DOWN:
            badge_color = (0, 140, 255)     # Amber/Orange
            label_text = "PLATZ / DOWN (Index Down)"
        else:
            badge_color = (120, 120, 120)   # Neutral Gray
            label_text = "NONE (Idle)"

        # Draw active gesture badge
        cv2.rectangle(image, (15, 12), (w - 15, 58), badge_color, 2, cv2.LINE_AA)
        cv2.putText(image, f"CMD: {label_text}", (25, 44), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (255, 255, 255), 2, cv2.LINE_AA)

        # Info line (FPS & tracking state)
        conf_str = f"Conf: {result.confidence*100:.0f}%" if result and result.confidence > 0 else "Conf: --"
        info_text = f"FPS: {fps:4.1f} | {conf_str} | Robot Dog Gruppe 17"
        cv2.putText(image, info_text, (15, h - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (220, 220, 220), 1, cv2.LINE_AA)

    def run(self):
        """Main camera acquisition and processing loop."""
        print(f"\n[START] Opening camera (Device Index: {self.camera_id})...")
        self.cap = cv2.VideoCapture(self.camera_id)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        if not self.cap.isOpened():
            print(f"[ERROR] Could not open camera {self.camera_id}!", file=sys.stderr)
            print("Troubleshooting:", file=sys.stderr)
            print(" 1. Check that your webcam is connected.", file=sys.stderr)
            print(" 2. Ensure Windows Settings > Privacy & Security > Camera allows desktop apps.", file=sys.stderr)
            print(" 3. Try passing --camera-id 1 if you have multiple video devices.", file=sys.stderr)
            return

        print(f"[OK] Video stream started successfully! (Max Hands Tracked: {self.max_hands})")
        print("Supported Gestures:")
        print("  - 'AUF'   / UP   : Point index finger straight up (with or without 'L' thumb)")
        print("  - 'PLATZ' / DOWN : Point index finger straight down")
        print("  - 'SITZ'  / SIT  : Hold open palm facing the camera")
        if not self.headless:
            print("\nPress 'q' or 'ESC' in the video window to stop.")

        frame_count = 0
        t_start = time.time()

        try:
            while self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret:
                    print("[WARNING] Empty frame received from camera. Retrying...")
                    time.sleep(0.05)
                    continue

                frame_count += 1
                now = time.time()
                elapsed = now - t_start
                if elapsed >= 1.0:
                    self.fps = frame_count / elapsed
                    frame_count = 0
                    t_start = now

                h, w = frame.shape[:2]

                # Convert OpenCV BGR to RGB for MediaPipe
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)

                detection_result = self.landmarker.detect(mp_image)

                best_result: Optional[GestureResult] = None
                active_gesture = GestureType.NONE

                if detection_result.hand_landmarks:
                    # Process detected hands (prioritize primary hand)
                    for hand_idx, landmarks in enumerate(detection_result.hand_landmarks):
                        handedness = "Right"
                        if detection_result.handedness and len(detection_result.handedness) > hand_idx:
                            handedness = detection_result.handedness[hand_idx][0].category_name

                        res = GestureClassifier.classify(landmarks, handedness=handedness)
                        if best_result is None or res.confidence > best_result.confidence:
                            best_result = res

                        # Draw hand skeletons in UI mode
                        if not self.headless:
                            self._draw_hand(frame, landmarks, h, w)

                if best_result is None:
                    best_result = GestureResult(GestureType.NONE, 0.0, GestureType.NONE, "None", "No hands in view")

                # Apply temporal debouncing / smoothing
                stable_gesture, is_new_event = self.smoother.update(best_result, timestamp=now)

                if is_new_event:
                    self.event_callback(stable_gesture, best_result)

                if not self.headless:
                    self._draw_hud(frame, stable_gesture, best_result, self.fps)
                    cv2.imshow("Robot Dog - Gesture Recognition (Gruppe 17)", frame)
                    key = cv2.waitKey(1) & 0xFF
                    if key in [ord('q'), 27]:  # 'q' or ESC
                        print("\n[STOP] User requested exit.")
                        break

        except KeyboardInterrupt:
            print("\n[STOP] Interrupted by user.")
        finally:
            self._cleanup()

    def _cleanup(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.landmarker.close()
        if not self.headless:
            cv2.destroyAllWindows()
        print("[SHUTDOWN] Camera and MediaPipe resources released cleanly.")


def main():
    parser = argparse.ArgumentParser(description="MediaPipe Gesture Recognition for Robot Dog")
    parser.add_argument("--camera-id", type=int, default=0, help="Camera device index (default: 0)")
    parser.add_argument("--width", type=int, default=640, help="Frame width in pixels (default: 640)")
    parser.add_argument("--height", type=int, default=480, help="Frame height in pixels (default: 480)")
    parser.add_argument("--max-hands", type=int, default=1, help="Maximum number of hands to detect and track (default: 1)")
    parser.add_argument("--cooldown", type=float, default=1.0, help="Event cooldown in seconds (default: 1.0)")
    parser.add_argument("--min-confidence", type=float, default=0.5, help="Hand detection confidence threshold (default: 0.5)")
    parser.add_argument("--headless", action="store_true", help="Run without graphical display window (ideal for RPi5)")
    cli_args = parser.parse_args()

    controller = GestureController(
        camera_id=cli_args.camera_id,
        width=cli_args.width,
        height=cli_args.height,
        max_hands=cli_args.max_hands,
        cooldown_seconds=cli_args.cooldown,
        min_detection_confidence=cli_args.min_confidence,
        min_tracking_confidence=cli_args.min_confidence,
        headless=cli_args.headless
    )
    controller.run()


if __name__ == "__main__":
    main()
