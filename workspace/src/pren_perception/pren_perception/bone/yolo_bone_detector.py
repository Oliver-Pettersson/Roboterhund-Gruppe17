"""
Knochenerkennung mit einem trainierten YOLO-Modell (Ultralytics).

Ultralytics ist bewusst keine feste Abhaengigkeit, weil es sehr gross ist. Es wird
erst beim Erzeugen des Detektors importiert; ohne Modell laeuft der Rest weiter.
"""

from pathlib import Path
from typing import Optional

import numpy as np
from pren_perception.bone.bone_localizer import BoundingBox


class YoloBoneDetector:
    """Findet den Knochen mit der hoechsten Konfidenz im Bild."""

    def __init__(self, model_path: Path, min_confidence: float = 0.5, image_size: int = 640):
        if not model_path.exists():
            raise FileNotFoundError(f'YOLO-Modell nicht gefunden: {model_path}')
        from ultralytics import YOLO  # erst hier, siehe Moduldokumentation

        self._model = YOLO(str(model_path))
        self._min_confidence = min_confidence
        self._image_size = image_size

    def detect(self, bgr_image: np.ndarray) -> Optional[BoundingBox]:
        """Beste Knochen-Box im Bild oder None."""
        result = self._model.predict(bgr_image, imgsz=self._image_size,
                                     conf=self._min_confidence, verbose=False)[0]
        if len(result.boxes) == 0:
            return None
        best = max(result.boxes, key=lambda box: float(box.conf))
        x1, y1, x2, y2 = (float(value) for value in best.xyxy[0])
        return BoundingBox(x1, y1, x2 - x1, y2 - y1, float(best.conf))
