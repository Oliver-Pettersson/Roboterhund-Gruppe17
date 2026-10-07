# Voice Detection

Offline-Spracherkennung für die deutschen Kommandos **Hier**, **Sitz**, **Platz**, **Auf** und **Such** mit Vosk.

## Windows

```powershell
python -m venv prototypes\voice_detection\.venv
prototypes\voice_detection\.venv\Scripts\pip install -r prototypes\voice_detection\requirements.txt
prototypes\voice_detection\.venv\Scripts\python prototypes\voice_detection\voice_control.py
```

Beim ersten Start wird das kompakte deutsche Vosk-Modell in `models/` geladen. Modellbinärdateien sind von Git ausgeschlossen.

## Raspberry Pi 5

```bash
chmod +x prototypes/voice_detection/setup_rpi5.sh
./prototypes/voice_detection/setup_rpi5.sh
```

## Test

Der Integrationstest simuliert Audiodaten und prüft unter anderem Rauschunterdrückung und das Unterdrücken direkt wiederholter Kommandos:

```powershell
prototypes\voice_detection\.venv\Scripts\python prototypes\voice_detection\test_vosk_integration.py
```
