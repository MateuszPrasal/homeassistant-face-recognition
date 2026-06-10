"""Klient snapshotów go2rtc.

Nie otwieramy RTSP samodzielnie — go2rtc już dekoduje strumień, my pobieramy
pojedynczą klatkę JPEG z jego API. `source` kamery może być:
- nazwą streamu go2rtc  → składamy {GO2RTC_URL}/api/frame.jpeg?src=<nazwa>,
- pełnym URL-em snapshotu (http/https) → bierzemy go wprost.
"""

from urllib.parse import quote

import httpx

from .config import GO2RTC_URL, SNAPSHOT_TIMEOUT


def snapshot_url(source: str) -> str:
    """URL snapshotu dla danego źródła kamery."""
    if source.startswith(("http://", "https://")):
        return source
    return f"{GO2RTC_URL}/api/frame.jpeg?src={quote(source)}"


class SnapshotClient:
    """Synchroniczny klient (używany w wątkach workerów). Trzyma pulę połączeń."""

    def __init__(self, timeout: float = SNAPSHOT_TIMEOUT) -> None:
        self._client = httpx.Client(timeout=timeout)

    def fetch(self, source: str) -> bytes:
        """Pobiera pojedynczy JPEG. Rzuca httpx.HTTPError przy problemie."""
        resp = self._client.get(snapshot_url(source))
        resp.raise_for_status()
        return resp.content

    def close(self) -> None:
        self._client.close()
