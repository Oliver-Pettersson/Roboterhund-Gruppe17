# Gesture Recognition - Robot Dog (PREN Gruppe 17)

Real-time hand gesture recognition system powered by **Google MediaPipe Hands** for the HSLU PREN1 / PREN2 interactive Robot Dog competition.

---

## Recognized Competition Gestures

As specified in **Section 3.1 (Page 5, Abbildung 4)** of the PREN1 specification:

| Gesture | German Command | English Command | Hand Sign Description | Visual Pose |
| :--- | :--- | :--- | :--- | :--- |
| **`UP`** | **«AUF»** | Up / Stand Up | Index finger pointing straight up, or shaping an **"L"** with thumb flared out laterally | `☝️` or `👆` / `🫲` |
| **`DOWN`** | **«PLATZ»** | Down / Lie Down | Index finger pointing straight down toward the floor | `👇` |
| **`SIT`** | **«SITZ»** | Sit | Open palm facing the camera (held in front of chest) | `✋` |

---

## Quick Start (Windows)

### 1. Run the Interactive Camera Visualizer
Open PowerShell in the project root:
```powershell
GestureRecognition\.venv\Scripts\python GestureRecognition\gesture_control.py
```

### 2. Controls & Flags
- Press **`q`** or **`ESC`** in the video window to quit.
- To use a different camera device:
  ```powershell
  GestureRecognition\.venv\Scripts\python GestureRecognition\gesture_control.py --camera-id 1
  ```
- To adjust the cooldown window between repeated events (default: 1.0s):
  ```powershell
  GestureRecognition\.venv\Scripts\python GestureRecognition\gesture_control.py --cooldown 0.5
  ```
- To track multiple hands if needed (defaults to 1):
  ```powershell
  GestureRecognition\.venv\Scripts\python GestureRecognition\gesture_control.py --max-hands 2
  ```
- To run without a GUI window (e.g. headless on robot):
  ```powershell
  GestureRecognition\.venv\Scripts\python GestureRecognition\gesture_control.py --headless
  ```

---

## Running Automated Tests

Run the headless unit test suite verifying geometric classification logic:
```powershell
GestureRecognition\.venv\Scripts\pytest GestureRecognition\test_gestures.py -v
```

---

## Deployment on Raspberry Pi 5

1. Run the automated setup script:
   ```bash
   chmod +x GestureRecognition/setup_rpi5.sh
   ./GestureRecognition/setup_rpi5.sh
   ```
2. Activate environment and run:
   ```bash
   source GestureRecognition/.venv/bin/activate
   python3 GestureRecognition/gesture_control.py --headless
   ```

---

## Architecture

- **`gesture_classifier.py`**:
  - `GestureClassifier`: Analyzes 21 3D hand joints from MediaPipe, calculating finger extension ratios and 3D pointing vectors.
  - `GestureSmoother`: 5-frame rolling majority vote filter and refractory cooldown tracker to eliminate transient detection glitches.
- **`gesture_control.py`**:
  - Main streaming pipeline with OpenCV video capture and MediaPipe Tasks.
  - Renders a real-time HUD with colored status badges, landmark skeletons, and trigger logs.
- **`test_gestures.py`**:
  - Automated test suite validating mathematical correctness against synthetic landmark fixtures.
