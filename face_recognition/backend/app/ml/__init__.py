"""Warstwa ML: detektory (osoba, twarz), rozpoznawanie, zarządzanie modelami."""

import cv2
import numpy as np

from .. import roi as roi_mod
from ..roi import PolyROI, RectROI


def roi_crop(frame: np.ndarray, roi: RectROI | PolyROI) -> np.ndarray:
    """Kadruje klatkę do bboxu ROI i zeruje piksele poza wielokątem.

    Cała kaskada liczy się wyłącznie wewnątrz ROI — dla prostokąta to zwykłe
    przycięcie, dla wielokąta dodatkowo maska (tło na czarno).
    """
    h, w = frame.shape[:2]
    pixels = roi_mod.polygon_pixels(roi, w, h)
    x0, y0, x1, y1 = roi_mod.bbox(pixels)
    x1 = max(x1, x0 + 1)
    y1 = max(y1, y0 + 1)
    crop = frame[y0:y1, x0:x1]
    mask = roi_mod.local_mask(pixels, x0, y0, x1 - x0, y1 - y0)
    return cv2.bitwise_and(crop, crop, mask=mask)
