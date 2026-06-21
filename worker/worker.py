"""worker 主循环：轮询拉任务 → 调度执行 → 回写结果。"""
import logging
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from api_client import APIClient
from booking_engine import BookingEngineError, Result, Task, run
from config import settings
from crypto import decrypt_secret

logger = logging.getLogger("worker")


def _setup_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(settings.log_file, encoding="utf-8"),
        ],
    )


def build_task(raw: dict, keyword: str) -> Task:
    return Task(
        booking_id=raw["booking_id"],
        user_id=raw["user_id"],
        drvr_last_name=raw["drvr_last_name"],
        licence_number=raw["licence_number"],
        keyword=keyword,
        exam_class=raw["exam_class"],
        pos_ids=raw["pos_ids"],
        expect_after_date=raw["expect_after_date"],
        expect_before_date=raw["expect_before_date"],
        expect_time_range=raw["expect_time_range"],
        pref_days_of_week=raw["pref_days_of_week"],
        pref_parts_of_day=raw["pref_parts_of_day"],
    )


def _execute_task(client: APIClient, raw: dict) -> None:
    booking_id = raw["booking_id"]
    logger.info("拿到任务 #%s（user=%s）", booking_id, raw["user_id"])
    try:
        keyword = decrypt_secret(raw["keyword_ciphertext"])
    except Exception as e:  # noqa: BLE001 — 解密失败即任务失败，回报后跳过
        logger.error("任务 #%s 凭据解密失败：%s", booking_id, e)
        client.report(booking_id, "failed", f"凭据解密失败：{e}", None)
        return
    task = build_task(raw, keyword)
    try:
        def should_continue() -> bool:
            try:
                return client.booking_status(booking_id) == "running"
            except Exception as e:  # noqa: BLE001 — 状态检查失败时保守继续，避免误杀任务
                logger.warning("任务 #%s 状态检查失败，继续执行本轮：%s", booking_id, e)
                return True

        def on_progress(message: str) -> None:
            client.report_progress(booking_id, message)

        result: Result = run(task, should_continue=should_continue, on_progress=on_progress)
        if result.success:
            client.report(booking_id, "done", None, {
                "booked_at": result.booked_at,
                "confirmation_no": result.confirmation_no,
                **({"details": result.details} if result.details else {}),
            })
            logger.info("任务 #%s 完成 ✓", booking_id)
        elif result.cancelled:
            logger.info("任务 #%s 已取消，worker 停止执行，不回写结果", booking_id)
        elif result.retryable:
            client.report(booking_id, "pending", result.error or "本轮未抢到号，自动重排", None)
            logger.info("任务 #%s 本轮未抢到号，已重排继续抢：%s", booking_id, result.error)
        else:
            client.report(booking_id, "failed", result.error or "未知失败", None)
            logger.warning("任务 #%s 失败：%s", booking_id, result.error)
    except BookingEngineError as e:
        client.report(booking_id, "failed", str(e), None)
        logger.warning("任务 #%s 失败：%s", booking_id, e)
    except Exception as e:
        logger.exception("任务 #%s 异常", booking_id)
        client.report(booking_id, "failed", f"worker 异常：{e!r}", None)


_shutdown = threading.Event()


def _on_signal(signum, _frame):
    logger.info("收到信号 %s，准备退出…", signum)
    _shutdown.set()


def main() -> None:
    _setup_logging()
    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    client = APIClient()
    logger.info("worker 启动：API=%s，并发=%s，轮询=%ss",
                settings.api_base_url, settings.max_concurrent, settings.poll_interval_seconds)

    with ThreadPoolExecutor(max_workers=settings.max_concurrent) as pool:
        while not _shutdown.is_set():
            try:
                task = client.claim()
            except Exception as e:
                logger.error("claim 失败：%s", e)
                _shutdown.wait(settings.poll_interval_seconds)
                continue
            if task is None:
                _shutdown.wait(settings.poll_interval_seconds)
                continue
            pool.submit(_execute_task, client, task)

    client.close()
    logger.info("worker 退出")


if __name__ == "__main__":
    main()
