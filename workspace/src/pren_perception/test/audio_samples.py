"""Kuenstliche Audiobloecke fuer Tests (16-Bit-PCM, 100 ms)."""

import numpy as np

CHUNK_SAMPLES = 1600


def chunk_with_level(rms: float) -> bytes:
    """Rechteck-Signal, dessen RMS-Wert genau rms ist."""
    samples = np.full(CHUNK_SAMPLES, rms, dtype=np.float32)
    samples[::2] *= -1
    return samples.astype(np.int16).tobytes()


QUIET = chunk_with_level(100.0)
LOUD = chunk_with_level(2000.0)
