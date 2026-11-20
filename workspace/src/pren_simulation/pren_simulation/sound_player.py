"""Spielt WAV-Dateien auf dem Windows-Host ab. Auf anderen Systemen passiert nichts."""

from pathlib import Path
import threading

try:
    import winsound
except ImportError:  # Linux / Raspberry Pi
    winsound = None


class SoundPlayer:
    """Spielt Toene aus einem Ordner asynchron ab."""

    def __init__(self, sounds_dir: Path):
        self._sounds_dir = sounds_dir

    def play(self, file_name: str) -> None:
        """Stoppt laufende Toene und spielt die Datei einmal ab."""
        path = self._sounds_dir / file_name
        if winsound is None or not path.exists():
            return
        self.stop()
        threading.Thread(
            target=winsound.PlaySound, args=(str(path), winsound.SND_FILENAME), daemon=True,
        ).start()

    def stop(self) -> None:
        """Stoppt alle laufenden Toene sofort."""
        if winsound is not None:
            winsound.PlaySound(None, winsound.SND_PURGE)
