#!/usr/bin/env bash
set -euo pipefail

# 1. Install system-level PortAudio and ALSA dependencies on Raspberry Pi OS (Bookworm 64-bit)
sudo apt update
sudo apt install -y \
    python3-pip \
    python3-venv \
    python3-dev \
    portaudio19-dev \
    libasound2-dev \
    alsa-utils

# 2. Create and activate a virtual environment inside VoiceDetection
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies (openWakeWord + ONNX Runtime + PyAudio)
pip install --upgrade pip
pip install -r requirements.txt

# 4. Pre-download openWakeWord base feature extraction ONNX models
python3 -c "import openwakeword; openwakeword.utils.download_models()"

mkdir -p models
echo "Setup complete! Place hier.onnx, sitz.onnx, platz.onnx, auf.onnx, and such.onnx in VoiceDetection/models/"
