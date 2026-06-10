"""Detektor twarzy — SCRFD (det_500m z buffalo_s, ONNX).

Drugi poziom kaskady, odpalany na obszarze wykrytej osoby. Zwraca box twarzy
oraz 5 punktów charakterystycznych (oczy, nos, kąciki ust) — landmarki są
potrzebne do wyrównania twarzy przed ArcFace.

Dekoder jak w insightface: 3 poziomy FPN (stride 8/16/32), 2 kotwice na komórkę,
predykcje to odległości od środka kotwicy (distance2bbox / distance2kps).
"""

from dataclasses import dataclass

import cv2
import numpy as np
import onnxruntime as ort

from . import models

_STRIDES = (8, 16, 32)
_NUM_ANCHORS = 2
_DET_SIZE = 640  # bok kwadratowego wejścia (podzielny przez 32)
_NMS_THRESH = 0.4


@dataclass
class Face:
    x1: float
    y1: float
    x2: float
    y2: float
    score: float
    kps: np.ndarray  # (5, 2), piksele oryginalnej klatki


def _distance2bbox(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    return np.stack([x1, y1, x2, y2], axis=-1)


def _distance2kps(points: np.ndarray, distance: np.ndarray) -> np.ndarray:
    preds = []
    for i in range(0, distance.shape[1], 2):
        preds.append(points[:, 0] + distance[:, i])
        preds.append(points[:, 1] + distance[:, i + 1])
    return np.stack(preds, axis=-1)


def _nms(dets: np.ndarray, thresh: float) -> list[int]:
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(int(i))
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        iou = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[1:][iou <= thresh]
    return keep


class FaceDetector:
    def __init__(self, thresh: float) -> None:
        self._thresh = thresh
        self._sess = ort.InferenceSession(
            str(models.path(models.SCRFD)), providers=["CPUExecutionProvider"]
        )
        self._input = self._sess.get_inputs()[0].name
        self._centers: dict[tuple[int, int], np.ndarray] = {}

    def _anchor_centers(self, height: int, width: int, stride: int) -> np.ndarray:
        key = (height, width)
        centers = self._centers.get(key)
        if centers is None:
            grid = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
            centers = (grid * stride).reshape(-1, 2)
            if _NUM_ANCHORS > 1:
                centers = np.stack([centers] * _NUM_ANCHORS, axis=1).reshape(-1, 2)
            self._centers[key] = centers
        return centers

    def detect(self, frame_bgr: np.ndarray) -> list[Face]:
        h, w = frame_bgr.shape[:2]
        im_ratio = h / w
        if im_ratio > 1:  # wyższy niż szerszy
            new_h, new_w = _DET_SIZE, int(_DET_SIZE / im_ratio)
        else:
            new_w, new_h = _DET_SIZE, int(_DET_SIZE * im_ratio)
        det_scale = new_h / h

        resized = cv2.resize(frame_bgr, (new_w, new_h))
        canvas = np.zeros((_DET_SIZE, _DET_SIZE, 3), dtype=np.uint8)
        canvas[:new_h, :new_w] = resized
        blob = cv2.dnn.blobFromImage(
            canvas, 1.0 / 128, (_DET_SIZE, _DET_SIZE), (127.5, 127.5, 127.5), swapRB=True
        )

        outputs = self._sess.run(None, {self._input: blob})
        # Kolejność wyjść: scores[0:3], bboxes[3:6], kps[6:9] — po stridach 8/16/32.
        scores_list, bboxes_list, kps_list = [], [], []
        for idx, stride in enumerate(_STRIDES):
            scores = outputs[idx]
            bbox_preds = outputs[idx + 3] * stride
            kps_preds = outputs[idx + 6] * stride
            grid = _DET_SIZE // stride
            centers = self._anchor_centers(grid, grid, stride)

            keep = np.where(scores.ravel() >= self._thresh)[0]
            if keep.size == 0:
                continue
            scores_list.append(scores[keep])
            bboxes_list.append(_distance2bbox(centers, bbox_preds)[keep])
            kps_list.append(_distance2kps(centers, kps_preds)[keep])

        if not scores_list:
            return []

        scores = np.vstack(scores_list).ravel()
        bboxes = np.vstack(bboxes_list) / det_scale
        kpss = np.vstack(kps_list) / det_scale

        dets = np.hstack([bboxes, scores[:, None]]).astype(np.float32)
        keep = _nms(dets, _NMS_THRESH)

        faces = []
        for i in keep:
            x1, y1, x2, y2 = bboxes[i]
            faces.append(
                Face(
                    x1=float(x1),
                    y1=float(y1),
                    x2=float(x2),
                    y2=float(y2),
                    score=float(scores[i]),
                    kps=kpss[i].reshape(5, 2),
                )
            )
        return faces
