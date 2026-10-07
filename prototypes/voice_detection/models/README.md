# Vosk German Offline Speech Recognition Model

This directory stores the offline acoustic model for the voice control system.

### Active Model: `vosk-model-small-de-0.15`
- **Language**: German (de)
- **Size**: ~45 MB (compressed) / ~120 MB (extracted)
- **Source**: [Alpha Cephei Vosk Models](https://alphacephei.com/vosk/models)
- **Automatic Setup**: `voice_control.py` automatically downloads and unpacks this model on first run if it is not found here.
- **Constrained Grammar**: The recognizer decodes strictly against the target keywords:
  `["hier", "sitz", "platz", "auf", "such", "[unk]"]`
