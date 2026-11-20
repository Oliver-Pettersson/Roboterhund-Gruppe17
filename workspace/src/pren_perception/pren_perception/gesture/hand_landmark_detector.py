"""Duenne Huelle um den MediaPipe HandLandmarker: Bild rein, Handpunkte raus."""

from pathlib import Path
from typing import List, Sequence

import cv2
import mediapipe as mp
from mediapipe.tasks.python import BaseOptions
from mediapipe.tasks.python.vision import HandLandmarker, HandLandmarkerOptions, RunningMode
import numpy as np


class HandLandmarkDetector:
    """Findet Haende in einem BGR-Bild und liefert je Hand 21 Punkte."""

    def __init__(self, model_path: Path, max_hands: int = 1,
                 min_detection_confidence: float = 0.5):
        if not model_path.is_file():
            raise FileNotFoundError(f'MediaPipe-Modell nicht gefunden: {model_path}')
        options = HandLandmarkerOptions(
            base_options=BaseOptions(model_asset_path=str(model_path)),
            running_mode=RunningMode.IMAGE,
            num_hands=max_hands,
            min_hand_detection_confidence=min_detection_confidence,
        )
        self._landmarker = HandLandmarker.create_from_options(options)

    def detect(self, bgr_image: np.ndarray) -> List[Sequence]:
        """Handpunkte aller gefundenen Haende (leer, wenn keine Hand im Bild ist)."""
        rgb = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
        result = self._landmarker.detect(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb))
        return list(result.hand_landmarks)

    def close(self) -> None:
        """Gibt MediaPipe-Ressourcen frei."""
        self._landmarker.close()
