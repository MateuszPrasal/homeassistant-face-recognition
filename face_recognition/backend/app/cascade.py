"""Kaskada rozpoznawania: osoba → twarz → embedding → dopasowanie → outcome.

Liczona wyłącznie w ROI (kadr do bboxu + maska wielokąta). Kolejność i logika wg
tabeli z CLAUDE.md:
- brak osoby                → `none`            (bez reakcji),
- osoba + znana twarz       → `ok`             (log),
- osoba + nieznana twarz    → `unknown_face`   (ALERT),
- osoba + brak twarzy       → `person_no_face` (ALERT).

Priorytet przy wielu osobach w kadrze: nieznana twarz > osoba bez twarzy > ok.
Detektor twarzy odpalamy tylko na obszarze wykrytej osoby (drugi poziom
oszczędności CPU) — patrz „Wydajność" w CLAUDE.md.
"""

import logging
from dataclasses import dataclass, field

import numpy as np

from . import matching, persons
from .config import FACE_DET_THRESH, MATCH_THRESHOLD, PERSON_CONF
from .ml import roi_crop
from .ml.face import FaceDetector
from .ml.person import PersonDetector
from .ml.recognize import FaceRecognizer
from .matching import Match
from .roi import PolyROI, RectROI

log = logging.getLogger("face.cascade")

ALERT_OUTCOMES = {"unknown_face", "person_no_face"}


@dataclass
class CascadeResult:
    outcome: str  # none | ok | unknown_face | person_no_face
    persons: int = 0
    faces: int = 0
    matches: list[Match] = field(default_factory=list)
    top_score: float = 0.0
    image: np.ndarray | None = None  # kadr ROI (do snapshotu ALERT-u)

    @property
    def alert(self) -> bool:
        return self.outcome in ALERT_OUTCOMES

    @property
    def _best_known(self) -> Match | None:
        known = [m for m in self.matches if m.known]
        return max(known, key=lambda m: m.score) if known else None

    @property
    def known_name(self) -> str | None:
        m = self._best_known
        return m.name if m else None

    @property
    def known_person_id(self) -> int | None:
        m = self._best_known
        return m.person_id if m else None


class Cascade:
    """Trzy modele załadowane raz; `process` jest bezpieczne wielowątkowo
    (onnxruntime.Run jest thread-safe), więc jedna instancja obsługuje wszystkie
    kamery."""

    def __init__(self) -> None:
        self.person = PersonDetector(conf=PERSON_CONF)
        self.face = FaceDetector(thresh=FACE_DET_THRESH)
        self.recognizer = FaceRecognizer()
        self.threshold = MATCH_THRESHOLD

    def process(self, frame: np.ndarray, roi: RectROI | PolyROI) -> CascadeResult:
        crop = roi_crop(frame, roi)
        person_boxes = self.person.detect(crop)
        if not person_boxes:
            return CascadeResult(outcome="none", image=crop)

        gallery = persons.load_gallery()
        matches: list[Match] = []
        person_no_face = False

        for pb in person_boxes:
            person_img = crop[pb.y1 : pb.y2, pb.x1 : pb.x2]
            if person_img.size == 0:
                continue
            faces = self.face.detect(person_img)
            if not faces:
                person_no_face = True
                continue
            for f in faces:
                emb = self.recognizer.embed(person_img, f.kps)
                matches.append(matching.match(emb, gallery, self.threshold))

        if any(not m.known for m in matches):
            outcome = "unknown_face"
        elif person_no_face:
            outcome = "person_no_face"
        elif any(m.known for m in matches):
            outcome = "ok"
        else:
            outcome = "none"

        top = max((m.score for m in matches), default=0.0)
        return CascadeResult(
            outcome=outcome,
            persons=len(person_boxes),
            faces=len(matches),
            matches=matches,
            top_score=top,
            image=crop,
        )
