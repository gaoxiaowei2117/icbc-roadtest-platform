"""把 vendor 的 road.py 封装成 booking_engine 能调用的限时循环。

单用户阶段：凭据/偏好全来自 config.yml（settings.road_config_path）。
task 仅用于日志关联 booking_id。
"""
import logging
import time

from booking_engine import Result
from config import settings
from vendor import road

logger = logging.getLogger("worker.road_adapter")

# job() 返回这些状态视为"已成交"
_SUCCESS_STATES = {"booking_success", "already_booked"}


def run(task):
    config = road.load_config(settings.road_config_path)
    deadline = time.monotonic() + settings.booking_timeout_seconds
    rounds = 0
    try:
        while time.monotonic() < deadline:
            rounds += 1
            try:
                status = road.job(config)
            except Exception:  # noqa: BLE001 — 单轮异常不应中断整个限时循环
                logger.exception("booking #%s 第 %d 轮 job() 异常，继续重试", task.booking_id, rounds)
                status = None
            logger.info("booking #%s 第 %d 轮：job 返回 %s", task.booking_id, rounds, status)
            if status in _SUCCESS_STATES:
                return _success_result(config, status)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            time.sleep(min(settings.booking_poll_seconds, remaining))
        return Result(success=False,
                      error=f"到达时限（{settings.booking_timeout_seconds}s）仍未抢到号")
    finally:
        _best_effort_restore(config)


def _success_result(config, status):
    info = road.load_booking_status(config) or {}
    appt = info.get("appointment") or {}
    booked_at = None
    if appt.get("date"):
        booked_at = f"{appt.get('date')} {appt.get('time', '')}".strip()
    return Result(
        success=True,
        booked_at=booked_at,
        confirmation_no=appt.get("date"),  # ICBC 无独立确认号，用日期标识
        details={"job_status": status, **appt},
    )


def _best_effort_restore(config):
    """循环结束兜底：emailReplace 开启时，轻量登录后 restore 原邮箱。"""
    try:
        if not (config.get("emailReplace") or {}).get("enable"):
            return
        resp = road.get_weblogin(config)
        if not resp:
            logger.warning("兜底 restore：登录失败，跳过")
            return
        token = resp.headers.get("Authorization", "")
        road.restore_original_email(config, token, resp.json())
    except Exception:  # noqa: BLE001 — 兜底绝不能影响主结果
        logger.exception("兜底 restore 邮箱异常")
