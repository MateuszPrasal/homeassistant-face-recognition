"""ROI — region zainteresowania (byt pierwszej klasy).

Jeden zaznaczony fragment kadru per kamera, na którym działa cała kaskada
(w Fazie 1: gate ruchu). Współrzędne **znormalizowane** [0..1], niezależne od
rozdzielczości snapshotu. Wspieramy prostokąt i wielokąt; rysowanie w UI dojdzie
w Fazie 3, na razie ROI ustawia się przez API/config.
"""

from typing import Annotated, Literal, Union

import cv2
import numpy as np
from pydantic import BaseModel, Field, field_validator


class RectROI(BaseModel):
    """Prostokąt znormalizowany: lewy-górny róg (x, y) + szerokość/wysokość."""

    shape: Literal["rect"] = "rect"
    x: float = Field(ge=0.0, le=1.0)
    y: float = Field(ge=0.0, le=1.0)
    w: float = Field(gt=0.0, le=1.0)
    h: float = Field(gt=0.0, le=1.0)

    def points_norm(self) -> list[tuple[float, float]]:
        return [
            (self.x, self.y),
            (self.x + self.w, self.y),
            (self.x + self.w, self.y + self.h),
            (self.x, self.y + self.h),
        ]


class PolyROI(BaseModel):
    """Wielokąt znormalizowany: lista wierzchołków (min. 3)."""

    shape: Literal["poly"] = "poly"
    points: list[tuple[float, float]] = Field(min_length=3)

    @field_validator("points")
    @classmethod
    def _in_range(cls, pts: list[tuple[float, float]]) -> list[tuple[float, float]]:
        for px, py in pts:
            if not (0.0 <= px <= 1.0 and 0.0 <= py <= 1.0):
                raise ValueError("Wierzchołki ROI muszą być znormalizowane do [0, 1].")
        return pts

    def points_norm(self) -> list[tuple[float, float]]:
        return self.points


# Dyskryminowana unia po polu `shape` — pydantic sam wybierze właściwy wariant.
ROI = Annotated[Union[RectROI, PolyROI], Field(discriminator="shape")]

# Domyślne ROI = cały kadr (dopóki user nie zaznaczy fragmentu).
DEFAULT_ROI = RectROI(shape="rect", x=0.0, y=0.0, w=1.0, h=1.0)


def polygon_pixels(roi: RectROI | PolyROI, width: int, height: int) -> np.ndarray:
    """Wierzchołki ROI w pikselach (Nx2, int32), przycięte do wymiarów kadru."""
    pts = np.array(roi.points_norm(), dtype=np.float64)
    pts[:, 0] = np.clip(pts[:, 0] * width, 0, width)
    pts[:, 1] = np.clip(pts[:, 1] * height, 0, height)
    return pts.astype(np.int32)


def bbox(pixels: np.ndarray) -> tuple[int, int, int, int]:
    """Prostokąt otaczający (x0, y0, x1, y1) dla wielokąta w pikselach."""
    x0, y0 = pixels.min(axis=0)
    x1, y1 = pixels.max(axis=0)
    return int(x0), int(y0), int(x1), int(y1)


def local_mask(pixels: np.ndarray, x0: int, y0: int, w: int, h: int) -> np.ndarray:
    """Maska (uint8, 255 wewnątrz ROI) w układzie współrzędnych bboxu (po przesunięciu)."""
    mask = np.zeros((h, w), dtype=np.uint8)
    shifted = pixels - np.array([x0, y0], dtype=np.int32)
    cv2.fillPoly(mask, [shifted], 255)
    return mask
