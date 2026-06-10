"""API osób i twarzy (enrollment).

Dodawanie twarzy: user wgrywa zdjęcie → detektor wykrywa twarz → liczymy
embedding → zapis do bazy. Detektor/recognizer biorą się z załadowanej kaskady
(jeśli modele nie wczytane → 503). UI do tego dojdzie w Fazie 3.
"""

from fastapi import APIRouter, File, HTTPException, Request, Response, UploadFile, status

from . import persons as repo
from .cascade import Cascade
from .motion import decode_jpeg
from .schemas import DetectedFace, DetectResult, Face, Person, PersonCreate

router = APIRouter(prefix="/api")


def _cascade(request: Request) -> Cascade:
    cascade = request.app.state.manager.cascade
    if cascade is None:
        raise HTTPException(status_code=503, detail="Modele ML niezaładowane.")
    return cascade


@router.get("/persons", response_model=list[Person])
def list_persons() -> list[Person]:
    return repo.list_persons()


@router.post("/persons", response_model=Person, status_code=status.HTTP_201_CREATED)
def create_person(data: PersonCreate) -> Person:
    return repo.create_person(data.name)


@router.get("/persons/{person_id}", response_model=Person)
def get_person(person_id: int) -> Person:
    person = repo.get_person(person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Nie ma takiej osoby.")
    return person


@router.delete("/persons/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_person(person_id: int) -> Response:
    if not repo.delete_person(person_id):
        raise HTTPException(status_code=404, detail="Nie ma takiej osoby.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/persons/{person_id}/faces", response_model=list[Face])
def list_faces(person_id: int) -> list[Face]:
    if repo.get_person(person_id) is None:
        raise HTTPException(status_code=404, detail="Nie ma takiej osoby.")
    return repo.list_faces(person_id)


@router.post("/detect", response_model=DetectResult)
async def detect(request: Request, file: UploadFile = File(...)) -> DetectResult:
    """Wykrywa twarze na wgranym obrazie BEZ zapisu — podgląd ramki w UI."""
    cascade = _cascade(request)
    try:
        frame = decode_jpeg(await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    h, w = frame.shape[:2]
    faces = [
        DetectedFace(
            x1=float(f.x1), y1=float(f.y1), x2=float(f.x2), y2=float(f.y2), score=round(f.score, 3)
        )
        for f in cascade.face.detect(frame)
    ]
    return DetectResult(width=int(w), height=int(h), faces=faces)


@router.post("/persons/{person_id}/faces", status_code=status.HTTP_201_CREATED)
async def add_face(person_id: int, request: Request, file: UploadFile = File(...)) -> dict:
    """Wykrywa twarz na wgranym zdjęciu, liczy embedding i zapisuje do osoby."""
    if repo.get_person(person_id) is None:
        raise HTTPException(status_code=404, detail="Nie ma takiej osoby.")
    cascade = _cascade(request)

    try:
        frame = decode_jpeg(await file.read())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    faces = cascade.face.detect(frame)
    if not faces:
        raise HTTPException(status_code=422, detail="Nie wykryto twarzy na zdjęciu.")
    if len(faces) > 1:
        raise HTTPException(
            status_code=422, detail="Na zdjęciu jest więcej niż jedna twarz."
        )

    embedding = cascade.recognizer.embed(frame, faces[0].kps)
    face_id = repo.add_face(person_id, embedding)
    return {"face_id": face_id, "detection_score": round(faces[0].score, 3)}


@router.delete("/faces/{face_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_face(face_id: int) -> Response:
    if not repo.delete_face(face_id):
        raise HTTPException(status_code=404, detail="Nie ma takiej twarzy.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
