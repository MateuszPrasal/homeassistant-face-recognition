"""Testy API osób. Kaskada wyłączona, więc enrollment twarzy zwraca 503."""

from fastapi.testclient import TestClient


def test_persons_crud(client: TestClient) -> None:
    assert client.get("/api/persons").json() == []

    created = client.post("/api/persons", json={"name": "Ala"})
    assert created.status_code == 201
    person = created.json()
    assert person["name"] == "Ala" and person["face_count"] == 0
    pid = person["id"]

    assert client.get(f"/api/persons/{pid}").json()["name"] == "Ala"
    assert client.get("/api/persons/999").status_code == 404

    assert client.delete(f"/api/persons/{pid}").status_code == 204
    assert client.get("/api/persons").json() == []


def test_add_face_without_models_503(client: TestClient) -> None:
    pid = client.post("/api/persons", json={"name": "Bob"}).json()["id"]
    resp = client.post(
        f"/api/persons/{pid}/faces",
        files={"file": ("x.jpg", b"not-a-real-jpeg", "image/jpeg")},
    )
    assert resp.status_code == 503  # modele niezaładowane (kaskada off)


def test_list_faces_empty_and_404(client: TestClient) -> None:
    pid = client.post("/api/persons", json={"name": "Ola"}).json()["id"]
    assert client.get(f"/api/persons/{pid}/faces").json() == []
    assert client.get("/api/persons/999/faces").status_code == 404


def test_detect_without_models_503(client: TestClient) -> None:
    resp = client.post(
        "/api/detect", files={"file": ("x.jpg", b"not-a-real-jpeg", "image/jpeg")}
    )
    assert resp.status_code == 503  # kaskada off
