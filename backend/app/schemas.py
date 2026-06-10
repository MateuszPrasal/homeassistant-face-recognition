"""Schematy API (pydantic) dla kamer.

ROI w żądaniach/odpowiedziach to dyskryminowana unia rect/poly z roi.py.
W bazie ROI ląduje jako JSON (kolumna `cameras.roi`).
"""

from pydantic import BaseModel, Field

from .roi import ROI, DEFAULT_ROI


class CameraBase(BaseModel):
    name: str = Field(min_length=1)
    source: str = Field(min_length=1, description="Nazwa streamu go2rtc lub URL snapshotu")
    roi: ROI = Field(default=DEFAULT_ROI, description="Region detekcji (znormalizowany)")
    interval_seconds: float = Field(default=3.0, gt=0.0, description="Co ile pobierać klatkę")
    cooldown_seconds: float = Field(default=45.0, ge=0.0, description="Wyciszenie po alercie")
    motion_threshold: float = Field(
        default=0.02, ge=0.0, le=1.0, description="Frakcja zmienionych pikseli ROI = ruch"
    )
    enabled: bool = True


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    """Wszystkie pola opcjonalne — aktualizacja częściowa (PATCH)."""

    name: str | None = Field(default=None, min_length=1)
    source: str | None = Field(default=None, min_length=1)
    roi: ROI | None = None
    interval_seconds: float | None = Field(default=None, gt=0.0)
    cooldown_seconds: float | None = Field(default=None, ge=0.0)
    motion_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    enabled: bool | None = None


class Camera(CameraBase):
    """Pełna reprezentacja (z bazy)."""

    id: int
    created_at: str


class PersonCreate(BaseModel):
    name: str = Field(min_length=1)


class Person(BaseModel):
    id: int
    name: str
    created_at: str
    face_count: int = 0
