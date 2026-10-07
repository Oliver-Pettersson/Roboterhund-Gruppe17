#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Setup script for GestureRecognition on Raspberry Pi 5 (Debian Bookworm 64-bit)
# ==============================================================================

echo "=== [1/4] Installing system dependencies for OpenCV and MediaPipe ==="
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    libgl1 \
    libglib2.0-0 \
    v4l-utils

echo "=== [2/4] Setting up Python virtual environment ==="
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate

echo "=== [3/4] Installing Python packages ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== [4/4] Pre-downloading MediaPipe Hand Landmarker model ==="
python3 -c "
import urllib.request, os
url = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task'
target = 'hand_landmarker.task'
if not os.path.exists(target):
    print('Downloading model asset...')
    urllib.request.urlretrieve(url, target)
print(f'Model ready: {os.path.getsize(target)} bytes')
"

echo "=== Setup complete! ==="
echo "To run headless on Pi 5: python3 gesture_control.py --headless"
echo "To run with HDMI display: python3 gesture_control.py"
