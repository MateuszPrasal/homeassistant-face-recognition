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

from .motion import MotionDetector, decode_jpeg
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


@dataclass
class CameraWorker:
    camera: Camera
    status: CameraStatus = field(init=False)

    def __post_init__(self) -> None:
        self.status = CameraStatus(camera_id=self.camera.id)
        self._stop = threading.Event()
        self._client = SnapshotClient()
        self._detector = MotionDetector(self.camera.roi, self.camera.motion_threshold)
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
            except Exception as exc:  # noqa: BLE001 — pętla nie może paść na błędzie sieci
                self.status.error = str(exc)
                log.warning("Kamera %s: błąd akwizycji: %s", self.camera.id, exc)

            elapsed = time.monotonic() - t0
            self._stop.wait(timeout=max(0.0, interval - elapsed))


class WorkerManager:
    """Zarządza wątkami workerów. Mutacje konfiguracji kamery → reload workera."""

    def __init__(self) -> None:
        self._workers: dict[int, CameraWorker] = {}
        self._lock = threading.Lock()

    def start_camera(self, camera: Camera) -> None:
        with self._lock:
            self._stop_locked(camera.id)
            if not camera.enabled:
                return
            worker = CameraWorker(camera)
            self._workers[camera.id] = worker
            worker.start()

    def _stop_locked(self, camera_id: int) -> None:
        worker = self._workers.pop(camera_id, None)
        if worker is not None:
            worker.stop()

    def stop_camera(self, camera_id: int) -> None:
        with self._lock:
            self._stop_locked(camera_id)

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
