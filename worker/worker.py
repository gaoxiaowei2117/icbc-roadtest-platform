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


def _execute_task(client: APIClient, raw: dict) -> None:
    booking_id = raw["booking_id"]
    logger.info("拿到任务 #%s（user=%s）", booking_id, raw["user_id"])
    try:
        icbc_username, icbc_password = decrypt_secret(raw["secret_ciphertext"])
    except Exception as e:  # noqa: BLE001 — 解密失败即任务失败，回报后跳过
        logger.error("任务 #%s 凭据解密失败：%s", booking_id, e)
        client.report(booking_id, "failed", f"凭据解密失败：{e}", None)
        return
    task = Task(
        booking_id=booking_id,
        user_id=raw["user_id"],
        target_date=raw.get("target_date"),
        time_window=raw.get("time_window"),
        pos_code=raw.get("pos_code"),
        icbc_username=icbc_username,
        icbc_password=icbc_password,
        max_wait_days=raw.get("max_wait_days", 60),
    )
    try:
        result: Result = run(task)
        if result.success:
            client.report(booking_id, "done", None, {
                "booked_at": result.booked_at,
                "confirmation_no": result.confirmation_no,
                **({"details": result.details} if result.details else {}),
            })
            logger.info("任务 #%s 完成 ✓", booking_id)
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
