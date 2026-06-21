"""worker ↔ 云端 API 客户端。"""
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


class APIClient:
    def __init__(self) -> None:
        self._client = httpx.Client(
            base_url=settings.api_base_url,
            headers={"X-Worker-Key": settings.worker_api_key},
            timeout=10.0,
        )

    def claim(self) -> dict | None:
        r = self._client.post("/api/worker/claim")
        r.raise_for_status()
        return r.json() if r.content else None

    def report(self, booking_id: int, status: str, last_error: str | None, result: dict | None) -> None:
        r = self._client.post(
            f"/api/worker/bookings/{booking_id}/result",
            json={"status": status, "last_error": last_error, "result": result},
        )
        r.raise_for_status()

    def booking_status(self, booking_id: int) -> str | None:
        r = self._client.get(f"/api/worker/bookings/{booking_id}/status")
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.json()["status"]

    def close(self) -> None:
        self._client.close()
