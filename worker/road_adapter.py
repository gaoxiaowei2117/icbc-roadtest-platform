"""把 vendor 的 road.py 封装成 booking_engine 能调用的限时循环。

多用户阶段：config 的 icbc 段来自 Task（网页档案）、gmail 凭据来自系统级 settings；
其余结构（通知禁用/autoBooking 策略/data_directory/gmail imap）来自系统级 base config
（settings.road_config_path 指向的 yaml）。对 Task 的每个 posID 逐个轮询抢号。
"""
import logging
import time

from booking_engine import Result
from config import settings
from vendor import road

logger = logging.getLogger("worker.road_adapter")

_SUCCESS_STATES = {"booking_success", "already_booked"}


def _icbc_from_task(task, pos_id: int) -> dict:
    """从 Task 构造 road.py 的 config['icbc'] 段（单个 posID）。"""
    return {
        "drvrLastName": task.drvr_last_name,
        "licenceNumber": task.licence_number,
        "keyword": task.keyword,
        "examClass": task.exam_class,
        "posID": pos_id,
        "prfDaysOfWeek": str(task.pref_days_of_week).replace(" ", ""),
        "prfPartsOfDay": str(task.pref_parts_of_day).replace(" ", ""),
        "expactAfterDate": task.expect_after_date,
        "expactBeforeDate": task.expect_before_date,
        "expactTimeRange": task.expect_time_range,
    }


def _build_config(task) -> dict:
    """系统级 base + 注入 gmail 凭据 + 强制真实下单/收码。icbc 段在轮询时逐 posID 覆盖。"""
    config = road.load_config(settings.road_config_path)
    config.setdefault("gmail", {})
    config["gmail"]["email"] = settings.gmail_email
    config["gmail"]["password"] = settings.gmail_app_password
    config.setdefault("autoBooking", {})["enable"] = True
    config.setdefault("emailReplace", {})["enable"] = True
    return config


def run(task):
    config = _build_config(task)
    pos_ids = task.pos_ids or []
    deadline = time.monotonic() + settings.booking_timeout_seconds
    rounds = 0
    try:
        while time.monotonic() < deadline:
            rounds += 1
            for pos_id in pos_ids:
                config["icbc"] = _icbc_from_task(task, pos_id)
                try:
                    status = road.job(config)
                except Exception:  # noqa: BLE001 — 单轮异常不中断循环
                    logger.exception("booking #%s 第 %d 轮 posID=%s job 异常", task.booking_id, rounds, pos_id)
                    status = None
                logger.info("booking #%s 第 %d 轮 posID=%s：job 返回 %s", task.booking_id, rounds, pos_id, status)
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
        confirmation_no=appt.get("date"),
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
