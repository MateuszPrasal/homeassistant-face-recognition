"""Detektor osoby — MobileNet-SSD v1 (ONNX, onnxruntime).

Pierwszy, tani poziom kaskady: czy w ROI jest człowiek. Model ma NMS wbudowany
w graf, więc dostajemy gotowe boxy. Klasa `person` to indeks 1 (etykiety COCO
w wariancie TF, 1-indeksowane). Wejście: uint8 NHWC RGB.

Boxy zwracamy w pikselach **wejściowej klatki** (znormalizowane wyjście SSD ×
wymiary klatki), niezależnie od rozmiaru, do jakiego skalujemy na potrzeby modelu.
"""

from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort

from . import models

_PERSON_CLASS = 1
_INPUT_SIZE = 300  # MobileNet-SSD v1 trenowany ~300x300


@dataclass
class PersonBox:
    x1: int
    y1: int
    x2: int
    y2: int
    score: float


class PersonDetector:
    def __init__(self, conf: float) -> None:
        self._conf = conf
        self._sess = ort.InferenceSession(
            str(models.path(models.SSD)), providers=["CPUExecutionProvider"]
        )
        self._input = self._sess.get_inputs()[0].name

    def detect(self, frame_bgr: np.ndarray) -> list[PersonBox]:
        h, w = frame_bgr.shape[:2]
        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        resized = cv2.resize(rgb, (_INPUT_SIZE, _INPUT_SIZE))
        blob = resized.astype(np.uint8)[None, ...]  # NHWC, batch 1

        boxes, classes, scores, _ = self._sess.run(None, {self._input: blob})
        boxes, classes, scores = boxes[0], classes[0], scores[0]

        out: list[PersonBox] = []
        for box, cls, score in zip(boxes, classes, scores):
            if int(cls) != _PERSON_CLASS or score < self._conf:
                continue
            ymin, xmin, ymax, xmax = box  # znormalizowane [0,1]
            out.append(
                PersonBox(
                    x1=max(0, int(xmin * w)),
                    y1=max(0, int(ymin * h)),
                    x2=min(w, int(xmax * w)),
                    y2=min(h, int(ymax * h)),
                    score=float(score),
                )
            )
        return out
