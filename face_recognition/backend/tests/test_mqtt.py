"""Testy budowy tematów i payloadów MQTT na atrapie klienta paho.

Bez sieci — sprawdzamy, co i na jaki temat trafiłoby do brokera.
"""

import json

import numpy as np

from app.mqtt import MqttPublisher, resolve_config
from app.schemas import Camera
from app.roi import DEFAULT_ROI


class FakeClient:
    """Atrapa paho.Client — zapisuje publikacje (topic, payload, retain)."""

    def __init__(self) -> None:
        self.published: list[tuple[str, object, bool]] = []

    def publish(self, topic, payload=None, retain=False, **_kw):
        self.published.append((topic, payload, retain))

    def by_topic(self, topic):
        return [p for (t, p, _r) in self.published if t == topic]


def _camera(cid=1, name="Wejście") -> Camera:
    return Camera(
        id=cid,
        name=name,
        source="front_door",
        roi=DEFAULT_ROI,
        interval_seconds=3.0,
        cooldown_seconds=45.0,
        motion_threshold=0.02,
        enabled=True,
        created_at="2026-01-01 00:00:00",
    )


def _pub() -> tuple[MqttPublisher, FakeClient]:
    client = FakeClient()
    return MqttPublisher(client, base_topic="face_recognition", discovery_prefix="homeassistant"), client


def test_discovery_publishes_three_entities() -> None:
    pub, client = _pub()
    pub.publish_discovery(_camera())

    topics = {t for (t, _p, _r) in client.published}
    assert "homeassistant/image/face_recognition_cam1/config" in topics
    assert "homeassistant/sensor/face_recognition_cam1/config" in topics
    assert "homeassistant/binary_sensor/face_recognition_cam1/config" in topics
    # wszystkie config-i retained
    assert all(r for (_t, _p, r) in client.published)

    image_cfg = json.loads(client.by_topic("homeassistant/image/face_recognition_cam1/config")[0])
    assert image_cfg["image_topic"] == "face_recognition/camera_1/image"
    assert image_cfg["unique_id"] == "face_recognition_cam1_image"
    assert image_cfg["device"]["identifiers"] == ["face_recognition"]


def test_remove_discovery_empties_configs() -> None:
    pub, client = _pub()
    pub.remove_discovery(1)
    payloads = [p for (_t, p, _r) in client.published]
    assert payloads == [b"", b"", b""]
    assert all(r for (_t, _p, r) in client.published)


def test_publish_alert_sends_image_and_state() -> None:
    pub, client = _pub()
    img = np.zeros((48, 64, 3), np.uint8)
    pub.publish_alert(_camera(), "unknown_face", None, 0.0, img)

    assert client.by_topic("face_recognition/camera_1/image"), "brak zdjęcia"
    assert client.by_topic("face_recognition/camera_1/state") == ["unknown_face"]
    assert client.by_topic("face_recognition/camera_1/unverified") == ["ON"]
    attrs = json.loads(client.by_topic("face_recognition/camera_1/attributes")[0])
    assert attrs["outcome"] == "unknown_face"
    assert attrs["label"] == "nieznana twarz"
    assert attrs["camera"] == "Wejście"


def test_publish_recognition_ok_clears_unverified() -> None:
    pub, client = _pub()
    pub.publish_recognition(_camera(), "ok", "Mateusz", 0.91, unverified=False)
    assert client.by_topic("face_recognition/camera_1/state") == ["ok"]
    assert client.by_topic("face_recognition/camera_1/unverified") == ["OFF"]
    attrs = json.loads(client.by_topic("face_recognition/camera_1/attributes")[0])
    assert attrs["name"] == "Mateusz"
    assert attrs["score"] == 0.91


def test_resolve_config_env_first() -> None:
    cfg = resolve_config(
        host="broker.local", port=8883, username="u", password="p", ssl=True, supervisor_token="tok"
    )
    assert cfg is not None
    assert (cfg.host, cfg.port, cfg.ssl) == ("broker.local", 8883, True)


def test_resolve_config_none_without_host_or_token() -> None:
    cfg = resolve_config(
        host=None, port=1883, username=None, password=None, ssl=False, supervisor_token=None
    )
    assert cfg is None
