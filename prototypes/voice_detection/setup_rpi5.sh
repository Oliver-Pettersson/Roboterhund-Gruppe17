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
    alsa-utils \
    wget \
    unzip

# 2. Create and activate a virtual environment inside VoiceDetection
cd "$(dirname "$0")"
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies (Vosk + PyAudio + NumPy)
pip install --upgrade pip
pip install -r requirements.txt

# 4. Download compact German Vosk speech model (~45 MB) if not already present
mkdir -p models
if [ ! -d "models/vosk-model-small-de-0.15" ]; then
    echo "Downloading German speech recognition model..."
    wget -c https://alphacephei.com/vosk/models/vosk-model-small-de-0.15.zip -O models/vosk-model-small-de-0.15.zip
    unzip -q models/vosk-model-small-de-0.15.zip -d models/
    rm models/vosk-model-small-de-0.15.zip
fi

echo "Setup complete! Run 'python3 voice_control.py' to start voice control."
