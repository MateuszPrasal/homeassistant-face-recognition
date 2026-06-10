"""Pętla akwizycji w tle — jeden wątek na kamerę.

Co `interval_seconds`: pobierz snapshot z go2rtc → gate ruchu w ROI → log.
Świadomie wątki, nie asyncio: dekodowanie JPEG i OpenCV to praca CPU; w Fazie 2
dojdzie onnxruntime (zwalnia GIL na czas inferencji). Wspólna kolejka inferencji
przy wielu kamerach — temat Fazy 6.
"""

import logging
import threading
import time
from dataclasses import dataclass, field

import cv2

from . import config
from . import detections as det_repo
from .cascade import Cascade
from .config import ALERTS_DIR
from .motion import MotionDetector, decode_jpeg
from .mqtt import MqttPublisher
from .schemas import Camera
from .snapshot import SnapshotClient

log = logging.getLogger("face.worker")


@dataclass
class CameraStatus:
    camera_id: int
    running: bool = False
    checks: int = 0
    last_check: float | None = None  # epoch
    motion: bool | None = None
    ratio: float | None = None
    error: str | None = None
    # Wynik ostatniej kaskady (Faza 2).
    last_outcome: str | None = None  # none | ok | unknown_face | person_no_face
    last_match: str | None = None  # imię znanej osoby (jeśli rozpoznano)
    last_score: float | None = None
    last_alert: float | None = None  # epoch ostatniego wysłanego ALERT-u


@dataclass
class CameraWorker:
    camera: Camera
    cascade: Cascade | None = None
    mqtt: MqttPublisher | None = None
    # Współdzielony semafor inferencji (serializacja kaskady między kamerami).
    inference_sem: threading.Semaphore | None = None
    status: CameraStatus = field(init=False)

    def __post_init__(self) -> None:
        self.status = CameraStatus(camera_id=self.camera.id)
        self._stop = threading.Event()
        self._client = SnapshotClient()
        self._detector = MotionDetector(self.camera.roi, self.camera.motion_threshold)
        self._last_alert_mono = 0.0  # monotonic, do cooldownu
        self._thread = threading.Thread(
            target=self._run, name=f"camera-{self.camera.id}", daemon=True
        )

    def start(self) -> None:
        self.status.running = True
        self._thread.start()
        log.info("Kamera %s (%s): start pętli, interwał %.1fs",
                 self.camera.id, self.camera.name, self.camera.interval_seconds)

    def stop(self, timeout: float = 5.0) -> None:
        self._stop.set()
        self._thread.join(timeout=timeout)
        self._client.close()
        self.status.running = False
        log.info("Kamera %s (%s): stop pętli", self.camera.id, self.camera.name)

    def _run(self) -> None:
        interval = self.camera.interval_seconds
        while not self._stop.is_set():
            t0 = time.monotonic()
            try:
                frame = decode_jpeg(self._client.fetch(self.camera.source))
                result = self._detector.process(frame)
                self.status.checks += 1
                self.status.last_check = time.time()
                self.status.motion = result.motion
                self.status.ratio = result.ratio
                self.status.error = None
                log.info(
                    "Kamera %s: %s (ruch=%.1f%%)",
                    self.camera.id,
                    "RUCH" if result.motion else "brak ruchu",
                    result.ratio * 100,
                )
                # Gate ruchu przepuścił → odpal kaskadę (jeśli modele wczytane).
                if result.motion and self.cascade is not None:
                    self._run_cascade(frame)
            except Exception as exc:  # noqa: BLE001 — pętla nie może paść na błędzie sieci
                self.status.error = str(exc)
                log.warning("Kamera %s: błąd akwizycji: %s", self.camera.id, exc)

            elapsed = time.monotonic() - t0
            self._stop.wait(timeout=max(0.0, interval - elapsed))

    def _run_cascade(self, frame) -> None:
        assert self.cascade is not None
        # Semafor serializuje inferencję między kamerami (budżet CPU na RPi).
        if self.inference_sem is not None:
            with self.inference_sem:
                res = self.cascade.process(frame, self.camera.roi)
        else:
            res = self.cascade.process(frame, self.camera.roi)
        self.status.last_outcome = res.outcome
        self.status.last_match = res.known_name
        self.status.last_score = round(res.top_score, 3)

        if res.outcome == "none":
            return

        snapshot_path: str | None = None

        if res.outcome == "ok":
            log.info("Kamera %s: OK — %s (score=%.2f)",
                     self.camera.id, res.known_name, res.top_score)
            if self.mqtt is not None:
                self.mqtt.publish_recognition(
                    self.camera, "ok", res.known_name, res.top_score, unverified=False
                )
        else:
            # ALERT (unknown_face / person_no_face). Snapshot zapisujemy ZAWSZE —
            # jest miniaturą w logu zdarzeń (tani, przydatny do strojenia). Cooldown
            # bramkuje tylko publikację MQTT (push), żeby nie spamować telefonu.
            snapshot_path = self._save_snapshot(res.image)
            now = time.monotonic()
            if now - self._last_alert_mono < self.camera.cooldown_seconds:
                log.info("Kamera %s: ALERT %s — MQTT wyciszony (cooldown), snapshot zapisany",
                         self.camera.id, res.outcome)
            else:
                self._last_alert_mono = now
                self.status.last_alert = time.time()
                if self.mqtt is not None:
                    self.mqtt.publish_alert(
                        self.camera, res.outcome, res.known_name, res.top_score, res.image
                    )
                log.warning(
                    "Kamera %s: ALERT %s (osób=%d, twarzy=%d, score=%.2f) → %s",
                    self.camera.id, res.outcome, res.persons, res.faces,
                    res.top_score, snapshot_path,
                )

        # Log detekcji (do strojenia progu) — przy każdej wykrytej osobie,
        # niezależnie od cooldownu.
        self._log_detection(res, snapshot_path)

    def _log_detection(self, res, snapshot_path: str | None) -> None:
        try:
            det_repo.add_detection(
                camera_id=self.camera.id,
                person_detected=res.persons > 0,
                face_detected=res.faces > 0,
                matched_person_id=res.known_person_id,
                matched_name=res.known_name,
                score=res.top_score,
                outcome=res.outcome,
                snapshot_path=snapshot_path,
            )
        except Exception as exc:  # noqa: BLE001 — log nie może wywrócić pętli
            log.warning("Kamera %s: nie zapisano detekcji: %s", self.camera.id, exc)

    def _save_snapshot(self, image) -> str:
        """Zapisuje snapshot detekcji (miniatura w logu zdarzeń). Stare pliki
        sprząta `detections.add_detection` przy przycinaniu logu."""
        ALERTS_DIR.mkdir(parents=True, exist_ok=True)
        path = ALERTS_DIR / f"camera_{self.camera.id}_{int(time.time())}.jpg"
        if image is not None:
            cv2.imwrite(str(path), image)
        return str(path)


class WorkerManager:
    """Zarządza wątkami workerów. Mutacje konfiguracji kamery → reload workera."""

    def __init__(self, cascade: Cascade | None = None, mqtt: MqttPublisher | None = None) -> None:
        self._workers: dict[int, CameraWorker] = {}
        self._lock = threading.Lock()
        self._cascade = cascade
        self._mqtt = mqtt
        # Wspólny budżet inferencji dla wszystkich kamer (domyślnie 1 naraz).
        self._inference_sem = threading.Semaphore(config.INFERENCE_CONCURRENCY)

    @property
    def cascade(self) -> Cascade | None:
        return self._cascade

    def start_camera(self, camera: Camera) -> None:
        with self._lock:
            self._stop_locked(camera.id)
            # Discovery publikujemy też dla wyłączonej kamery — encje mają istnieć
            # w HA niezależnie od tego, czy pętla akurat chodzi.
            if self._mqtt is not None:
                self._mqtt.publish_discovery(camera)
            if not camera.enabled:
                return
            worker = CameraWorker(
                camera,
                cascade=self._cascade,
                mqtt=self._mqtt,
                inference_sem=self._inference_sem,
            )
            self._workers[camera.id] = worker
            worker.start()

    def _stop_locked(self, camera_id: int) -> None:
        worker = self._workers.pop(camera_id, None)
        if worker is not None:
            worker.stop()

    def stop_camera(self, camera_id: int) -> None:
        """Zatrzymanie + usunięcie encji HA (ścieżka kasowania kamery)."""
        with self._lock:
            self._stop_locked(camera_id)
            if self._mqtt is not None:
                self._mqtt.remove_discovery(camera_id)

    def start_all(self, cameras: list[Camera]) -> None:
        for camera in cameras:
            self.start_camera(camera)

    def stop_all(self) -> None:
        with self._lock:
            for camera_id in list(self._workers):
                self._stop_locked(camera_id)

    def status(self) -> dict[int, CameraStatus]:
        with self._lock:
            return {cid: w.status for cid, w in self._workers.items()}
