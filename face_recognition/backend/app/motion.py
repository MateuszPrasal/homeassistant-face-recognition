"""Gate ruchu — tani pre-filtr przed kaskadą ML.

Różnica względem poprzedniej klatki, liczona **wyłącznie w ROI**. Sens: nie
odpalać drogiego detektora osoby na każdej klatce, tylko gdy w obszarze coś się
zmieniło. W Fazie 1 to końcowy efekt (log ruch/brak); w Fazie 2 wynik gate'u
warunkuje uruchomienie kaskady.

Kadrujemy do bounding-boxu ROI i maskujemy wielokątem, więc dla skośnego/
wielokątnego ROI liczą się tylko piksele wewnątrz.
"""

from dataclasses import dataclass

import cv2
import numpy as np

from . import roi as roi_mod
from .roi import PolyROI, RectROI


@dataclass
class MotionResult:
    motion: bool
    ratio: float  # frakcja zmienionych pikseli ROI (0..1)


def decode_jpeg(data: bytes) -> np.ndarray:
    """Dekoduje bajty JPEG do obrazu BGR. Rzuca ValueError przy złych danych."""
    arr = np.frombuffer(data, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        raise ValueError("Nie udało się zdekodować klatki JPEG.")
    return frame


# Próg różnicy intensywności piksela (0..255), powyżej którego uznajemy zmianę.
_PIXEL_DELTA = 25


class MotionDetector:
    """Stan gate'u dla jednej kamery. ROI stałe przez życie obiektu (reload =
    nowy detektor). Maska przeliczana, gdy zmieni się rozdzielczość snapshotu.
    """

    def __init__(self, roi: RectROI | PolyROI, threshold: float) -> None:
        self._roi = roi
        self._threshold = threshold
        self._prev: np.ndarray | None = None
        self._mask: np.ndarray | None = None
        self._mask_area = 0
        self._frame_size: tuple[int, int] | None = None  # (W, H)
        self._box: tuple[int, int, int, int] = (0, 0, 0, 0)

    def _ensure_mask(self, width: int, height: int) -> None:
        if self._frame_size == (width, height) and self._mask is not None:
            return
        pixels = roi_mod.polygon_pixels(self._roi, width, height)
        x0, y0, x1, y1 = roi_mod.bbox(pixels)
        # Co najmniej 1 px w każdą stronę, żeby kadr nie był pusty.
        x1 = max(x1, x0 + 1)
        y1 = max(y1, y0 + 1)
        w, h = x1 - x0, y1 - y0
        self._mask = roi_mod.local_mask(pixels, x0, y0, w, h)
        self._mask_area = int(cv2.countNonZero(self._mask))
        self._box = (x0, y0, x1, y1)
        self._frame_size = (width, height)
        self._prev = None  # zmiana geometrii unieważnia poprzednią klatkę

    def process(self, frame: np.ndarray) -> MotionResult:
        """Porównuje klatkę z poprzednią w ROI. Pierwsza klatka → brak ruchu."""
        height, width = frame.shape[:2]
        self._ensure_mask(width, height)
        x0, y0, x1, y1 = self._box

        crop = frame[y0:y1, x0:x1]
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (5, 5), 0)

        if self._prev is None:
            self._prev = gray
            return MotionResult(motion=False, ratio=0.0)

        diff = cv2.absdiff(gray, self._prev)
        _, thresh = cv2.threshold(diff, _PIXEL_DELTA, 255, cv2.THRESH_BINARY)
        thresh = cv2.bitwise_and(thresh, self._mask)
        changed = int(cv2.countNonZero(thresh))
        ratio = changed / self._mask_area if self._mask_area else 0.0

        self._prev = gray
        return MotionResult(motion=ratio >= self._threshold, ratio=ratio)
