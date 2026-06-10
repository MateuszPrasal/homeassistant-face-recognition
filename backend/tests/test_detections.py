"""Log detekcji: repo (zapis/lista/przycinanie) + API (lista, snapshot, ochrona)."""

import app.config as config
import app.detections as det
import app.persons as persons


def _add(camera_id=1, outcome="ok", score=0.8, pid=None, name=None, snapshot=None):
    return det.add_detection(
        camera_id=camera_id,
        person_detected=True,
        face_detected=outcome != "person_no_face",
        matched_person_id=pid,
        matched_name=name,
        score=score,
        outcome=outcome,
        snapshot_path=snapshot,
    )


def test_list_pusty(client) -> None:
    assert client.get("/api/detections").json() == []


def test_add_i_lista_kolejnosc(client) -> None:
    pid = persons.create_person("Mateusz").id
    _add(outcome="ok", score=0.9, pid=pid, name="Mateusz")
    _add(outcome="unknown_face", score=0.2)
    rows = client.get("/api/detections").json()
    assert [r["outcome"] for r in rows] == ["unknown_face", "ok"]  # malejąco po id
    assert rows[1]["matched_name"] == "Mateusz"
    assert rows[1]["score"] == 0.9
    assert rows[0]["has_snapshot"] is False


def test_filtr_po_kamerze(client) -> None:
    _add(camera_id=1)
    _add(camera_id=2)
    rows = client.get("/api/detections", params={"camera_id": 2}).json()
    assert len(rows) == 1 and rows[0]["camera_id"] == 2


def test_przycinanie_do_max(client, monkeypatch) -> None:
    monkeypatch.setattr(det, "MAX_DETECTIONS", 3)
    for i in range(6):
        _add(score=i / 10)
    rows = client.get("/api/detections").json()
    assert len(rows) == 3  # zostały ostatnie 3


def test_snapshot_404_bez_zdjecia(client) -> None:
    did = _add(outcome="ok")
    assert client.get(f"/api/detections/{did}/snapshot").status_code == 404


def test_snapshot_serwuje_plik(client) -> None:
    config.ALERTS_DIR.mkdir(parents=True, exist_ok=True)
    img = config.ALERTS_DIR / "camera_1_test.jpg"
    img.write_bytes(b"\xff\xd8\xff\xe0JPEGDATA")
    did = _add(outcome="unknown_face", snapshot=str(img))
    r = client.get(f"/api/detections/{did}/snapshot")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content == b"\xff\xd8\xff\xe0JPEGDATA"


def test_snapshot_ochrona_przed_traversal(client, tmp_path) -> None:
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"x")
    did = _add(outcome="unknown_face", snapshot=str(outside))
    assert client.get(f"/api/detections/{did}/snapshot").status_code == 404
