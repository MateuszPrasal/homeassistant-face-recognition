"""Klient MQTT + MQTT discovery encji Home Assistant (Faza 4).

Encje per kamera (jedno urządzenie HA = ten add-on):
- `image`         — ostatni snapshot ALERT-u (źródło zdjęcia do pusha),
- `sensor`        — ostatnie rozpoznanie (`outcome` + atrybuty: imię, score, czas),
- `binary_sensor` — „ktoś niezweryfikowany" (nieznana twarz / osoba bez twarzy).

Dane brokera: w add-onie podaje je Supervisor (`services: mqtt:want`), pobieramy
z `http://supervisor/services/mqtt`. Lokalnie/dev — jawne `FACE_MQTT_*`.

Publikacja jest świadomie „best-effort": gdy broker nie odpowiada, serwis działa
dalej (jak przy braku kaskady). Discovery i stany publikujemy z `retain=True`,
żeby HA odtworzył encje po restarcie.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

import cv2
import httpx
import numpy as np
import paho.mqtt.client as mqtt

from .schemas import Camera

log = logging.getLogger("face.mqtt")

# Etykiety outcome'ów po polsku (atrybut sensora — wygodne w UI HA).
OUTCOME_LABEL = {
    "ok": "rozpoznano",
    "unknown_face": "nieznana twarz",
    "person_no_face": "osoba bez twarzy",
    "none": "brak",
}


@dataclass
class MqttConfig:
    host: str
    port: int = 1883
    username: str | None = None
    password: str | None = None
    ssl: bool = False


def resolve_config(
    *,
    host: str | None,
    port: int,
    username: str | None,
    password: str | None,
    ssl: bool,
    supervisor_token: str | None,
) -> MqttConfig | None:
    """Buduje konfigurację brokera: najpierw jawne env, inaczej Supervisor.

    Zwraca None, gdy nie ma ani jawnego hosta, ani tokenu Supervisora (MQTT off).
    """
    if host:
        return MqttConfig(host=host, port=port, username=username, password=password, ssl=ssl)
    if supervisor_token:
        return _config_from_supervisor(supervisor_token)
    return None


def _config_from_supervisor(token: str) -> MqttConfig | None:
    """Pobiera dane brokera z API Supervisora (add-on HA OS)."""
    try:
        resp = httpx.get(
            "http://supervisor/services/mqtt",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()["data"]
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        log.warning("Nie udało się pobrać konfiguracji MQTT z Supervisora: %s", exc)
        return None
    return MqttConfig(
        host=data["host"],
        port=int(data["port"]),
        username=data.get("username") or None,
        password=data.get("password") or None,
        ssl=bool(data.get("ssl", False)),
    )


class MqttPublisher:
    """Buduje tematy/payloady i publikuje przez wstrzyknięty klient paho.

    Klient jest wstrzykiwany (a nie tworzony w środku), żeby budowę tematów dało
    się testować na atrapie bez sieci. Fabryka `connect()` składa realny klient.
    """

    def __init__(
        self,
        client: mqtt.Client,
        *,
        base_topic: str = "face_recognition",
        discovery_prefix: str = "homeassistant",
    ) -> None:
        self._c = client
        self.base = base_topic
        self.disc = discovery_prefix

    # --- tematy ---

    @property
    def availability_topic(self) -> str:
        return f"{self.base}/status"

    def cam_topic(self, camera_id: int, suffix: str) -> str:
        return f"{self.base}/camera_{camera_id}/{suffix}"

    def _config_topic(self, component: str, camera_id: int) -> str:
        return f"{self.disc}/{component}/{self.base}_cam{camera_id}/config"

    def _device(self) -> dict:
        return {
            "identifiers": [self.base],
            "name": "Rozpoznawanie twarzy",
            "manufacturer": "homeassistant-face-recognition",
            "model": "Kaskada osoba→twarz",
        }

    # --- discovery ---

    def publish_discovery(self, camera: Camera) -> None:
        """Publikuje konfiguracje encji (retain) dla danej kamery."""
        dev = self._device()
        avail = self.availability_topic
        uid = f"{self.base}_cam{camera.id}"

        self._publish(
            self._config_topic("image", camera.id),
            {
                "name": f"{camera.name} — alert",
                "unique_id": f"{uid}_image",
                "image_topic": self.cam_topic(camera.id, "image"),
                "content_type": "image/jpeg",
                "availability_topic": avail,
                "device": dev,
            },
            retain=True,
        )
        self._publish(
            self._config_topic("sensor", camera.id),
            {
                "name": f"{camera.name} — rozpoznanie",
                "unique_id": f"{uid}_outcome",
                "state_topic": self.cam_topic(camera.id, "state"),
                "json_attributes_topic": self.cam_topic(camera.id, "attributes"),
                "icon": "mdi:face-recognition",
                "availability_topic": avail,
                "device": dev,
            },
            retain=True,
        )
        self._publish(
            self._config_topic("binary_sensor", camera.id),
            {
                "name": f"{camera.name} — niezweryfikowany",
                "unique_id": f"{uid}_unverified",
                "state_topic": self.cam_topic(camera.id, "unverified"),
                "payload_on": "ON",
                "payload_off": "OFF",
                "device_class": "occupancy",
                "availability_topic": avail,
                "device": dev,
            },
            retain=True,
        )
        log.info("MQTT discovery opublikowane dla kamery %s (%s)", camera.id, camera.name)

    def remove_discovery(self, camera_id: int) -> None:
        """Usuwa encje (pusty retained payload na temat config) — przy kasowaniu kamery."""
        for component in ("image", "sensor", "binary_sensor"):
            self._c.publish(self._config_topic(component, camera_id), b"", retain=True)

    # --- stany ---

    def publish_recognition(
        self, camera: Camera, outcome: str, name: str | None, score: float, *, unverified: bool
    ) -> None:
        """Publikuje stan rozpoznania (sensor + binary_sensor)."""
        self._c.publish(self.cam_topic(camera.id, "state"), outcome, retain=True)
        self._publish(
            self.cam_topic(camera.id, "attributes"),
            {
                "outcome": outcome,
                "label": OUTCOME_LABEL.get(outcome, outcome),
                "name": name or "",
                "score": round(float(score), 3),
                "camera_id": camera.id,
                "camera": camera.name,
            },
            retain=True,
        )
        self._c.publish(
            self.cam_topic(camera.id, "unverified"), "ON" if unverified else "OFF", retain=True
        )

    def publish_alert(
        self, camera: Camera, outcome: str, name: str | None, score: float, image: np.ndarray | None
    ) -> None:
        """Publikuje ALERT: zdjęcie + stan rozpoznania (binary_sensor = ON)."""
        if image is not None:
            ok, buf = cv2.imencode(".jpg", image)
            if ok:
                self._c.publish(self.cam_topic(camera.id, "image"), buf.tobytes(), retain=True)
        self.publish_recognition(camera, outcome, name, score, unverified=True)

    def online(self) -> None:
        self._c.publish(self.availability_topic, "online", retain=True)

    def _publish(self, topic: str, payload: dict, *, retain: bool = False) -> None:
        self._c.publish(topic, json.dumps(payload, ensure_ascii=False), retain=retain)

    def close(self) -> None:
        try:
            self._c.publish(self.availability_topic, "offline", retain=True)
            self._c.loop_stop()
            self._c.disconnect()
        except Exception as exc:  # noqa: BLE001
            log.debug("Błąd przy zamykaniu MQTT: %s", exc)


def connect(
    config: MqttConfig, *, base_topic: str = "face_recognition", discovery_prefix: str = "homeassistant"
) -> MqttPublisher:
    """Składa klient paho (LWT, auth), łączy w tle i zwraca publisher.

    Łączenie jest nieblokujące (`connect_async` + `loop_start`) — gdy broker
    chwilowo nie odpowiada, start serwisu nie wisi; paho dołączy później.
    """
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=base_topic)
    if config.username:
        client.username_pw_set(config.username, config.password)
    if config.ssl:
        client.tls_set()
    availability = f"{base_topic}/status"
    client.will_set(availability, "offline", retain=True)

    publisher = MqttPublisher(client, base_topic=base_topic, discovery_prefix=discovery_prefix)

    def on_connect(_c, _userdata, _flags, reason_code, _props=None) -> None:
        if reason_code == 0:
            log.info("MQTT połączony z %s:%s", config.host, config.port)
            publisher.online()
        else:
            log.warning("MQTT połączenie odrzucone: %s", reason_code)

    client.on_connect = on_connect
    client.connect_async(config.host, config.port)
    client.loop_start()
    return publisher
