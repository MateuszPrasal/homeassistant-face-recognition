"""Rozpoznawanie twarzy — ArcFace (w600k_mbf z buffalo_s, ONNX).

Z wykrytej twarzy + 5 landmarków: wyrównanie (similarity transform do stałego
szablonu 112×112), inferencja, embedding 512-d. Embedding L2-normalizujemy, więc
cosine similarity = zwykły iloczyn skalarny (patrz matching.py).
"""

import cv2
import numpy as np
import onnxruntime as ort

from . import models

# Stały szablon 5 punktów dla 112×112 (oczy, nos, kąciki ust) — standard ArcFace.
_ARCFACE_TEMPLATE = np.array(
    [
        [38.2946, 51.6963],
        [73.5318, 51.5014],
        [56.0252, 71.7366],
        [41.5493, 92.3655],
        [70.7299, 92.2041],
    ],
    dtype=np.float32,
)


def align(frame_bgr: np.ndarray, kps: np.ndarray) -> np.ndarray:
    """Wyrównuje twarz do 112×112 na podstawie 5 landmarków."""
    matrix, _ = cv2.estimateAffinePartial2D(kps.astype(np.float32), _ARCFACE_TEMPLATE)
    return cv2.warpAffine(frame_bgr, matrix, (112, 112), borderValue=0)


class FaceRecognizer:
    def __init__(self) -> None:
        self._sess = ort.InferenceSession(
            str(models.path(models.ARCFACE)), providers=["CPUExecutionProvider"]
        )
        self._input = self._sess.get_inputs()[0].name

    def embed(self, frame_bgr: np.ndarray, kps: np.ndarray) -> np.ndarray:
        """Zwraca znormalizowany embedding 512-d (float32) dla jednej twarzy."""
        aligned = align(frame_bgr, kps)
        blob = cv2.dnn.blobFromImage(
            aligned, 1.0 / 127.5, (112, 112), (127.5, 127.5, 127.5), swapRB=True
        )
        emb = self._sess.run(None, {self._input: blob})[0].ravel()
        norm = np.linalg.norm(emb)
        return (emb / norm).astype(np.float32) if norm else emb.astype(np.float32)
