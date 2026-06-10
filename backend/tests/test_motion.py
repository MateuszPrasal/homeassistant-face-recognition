"""Testy gate'u ruchu i ROI — bez sieci, na syntetycznych klatkach."""

import cv2
import numpy as np

from app.motion import MotionDetector, decode_jpeg
from app.roi import PolyROI, RectROI


def _frame() -> np.ndarray:
    return np.zeros((480, 640, 3), dtype=np.uint8)


def test_first_frame_no_motion() -> None:
    det = MotionDetector(RectROI(x=0.25, y=0.25, w=0.5, h=0.5), threshold=0.02)
    assert det.process(_frame()).motion is False


def test_change_inside_roi_is_motion() -> None:
    det = MotionDetector(RectROI(x=0.25, y=0.25, w=0.5, h=0.5), threshold=0.02)
    det.process(_frame())  # inicjalizacja
    moved = _frame()
    cv2.rectangle(moved, (300, 240), (360, 300), (255, 255, 255), -1)
    assert det.process(moved).motion is True


def test_change_outside_roi_ignored() -> None:
    det = MotionDetector(RectROI(x=0.4, y=0.4, w=0.2, h=0.2), threshold=0.02)
    det.process(_frame())
    outside = _frame()
    cv2.rectangle(outside, (0, 0), (60, 60), (255, 255, 255), -1)  # poza ROI
    assert det.process(outside).motion is False


def test_poly_roi_mask() -> None:
    det = MotionDetector(PolyROI(points=[(0.1, 0.1), (0.9, 0.1), (0.5, 0.9)]), threshold=0.01)
    det.process(_frame())
    moved = _frame()
    cv2.rectangle(moved, (300, 240), (360, 300), (255, 255, 255), -1)
    assert det.process(moved).motion is True


def test_decode_roundtrip() -> None:
    img = _frame()
    cv2.rectangle(img, (10, 10), (50, 50), (0, 255, 0), -1)
    data = cv2.imencode(".jpg", img)[1].tobytes()
    decoded = decode_jpeg(data)
    assert decoded.shape == img.shape
