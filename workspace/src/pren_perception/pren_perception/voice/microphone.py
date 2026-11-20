"""Liest 16-Bit-Mono-Audio vom Mikrofon in eine Warteschlange."""

import queue
from typing import Optional

import sounddevice


class Microphone:
    """Mikrofon-Stream, der Bloecke fester Groesse liefert."""

    def __init__(self, sample_rate: int, chunk_samples: int, device: Optional[int] = None,
                 max_queued_chunks: int = 50):
        self._chunks: queue.Queue = queue.Queue(maxsize=max_queued_chunks)
        self._stream = sounddevice.RawInputStream(
            samplerate=sample_rate, blocksize=chunk_samples, device=device,
            channels=1, dtype='int16', callback=self._on_audio)

    @property
    def device_name(self) -> str:
        """Name des verwendeten Eingabegeraets."""
        return sounddevice.query_devices(self._stream.device)['name']

    def start(self) -> None:
        """Startet die Aufnahme."""
        self._stream.start()

    def stop(self) -> None:
        """Beendet die Aufnahme."""
        self._stream.stop()
        self._stream.close()

    def read(self, timeout_s: float) -> Optional[bytes]:
        """Naechster Audioblock oder None, wenn innerhalb von timeout_s keiner kommt."""
        try:
            return self._chunks.get(timeout=timeout_s)
        except queue.Empty:
            return None

    def _on_audio(self, data, _frames, _time, _status) -> None:
        if self._chunks.full():
            self._chunks.get_nowait()  # aeltesten Block verwerfen, damit es aktuell bleibt
        self._chunks.put_nowait(bytes(data))
