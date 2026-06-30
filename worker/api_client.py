"""worker ↔ 云端 API 客户端。"""
import logging

import httpx

from config import settings

logger = logging.getLogger(__name__)


class StaleClaimError(Exception):
    """本 worker 的认领已过期：任务被重排并由其他 worker 接管（后端返回 409）。"""


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

    def report(self, booking_id: int, attempt: int, status: str, last_error: str | None, result: dict | None) -> None:
        r = self._client.post(
            f"/api/worker/bookings/{booking_id}/result",
            json={"attempt": attempt, "status": status, "last_error": last_error, "result": result},
        )
        if r.status_code == 409:
            raise StaleClaimError(f"任务 #{booking_id} 回写被拒：{r.text}")
        r.raise_for_status()

    def report_progress(self, booking_id: int, attempt: int, message: str) -> None:
        r = self._client.post(
            f"/api/worker/bookings/{booking_id}/progress",
            json={"attempt": attempt, "message": message},
        )
        if r.status_code == 409:
            raise StaleClaimError(f"任务 #{booking_id} 进度上报被拒：{r.text}")
        r.raise_for_status()

    def booking_status(self, booking_id: int, attempt: int) -> str | None:
        r = self._client.get(
            f"/api/worker/bookings/{booking_id}/status",
            params={"attempt": attempt},
        )
        # 404=任务不存在，409=认领已过期，两者都表示本 worker 应停止本轮执行
        if r.status_code in (404, 409):
            return None
        r.raise_for_status()
        return r.json()["status"]

    def close(self) -> None:
        self._client.close()
