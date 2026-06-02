"""抢约引擎。

⚠️ 这是骨架：实际逻辑需要从你原项目的 road.py 抽出来。
接口已经按"可被 worker 调用"的形式定义好：
  - 输入是 dataclass Task
  - 输出是 Result
  - 抛 BookingEngineError 视为失败
"""
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


class BookingEngineError(Exception):
    """抢约过程中可恢复的错误。"""


@dataclass
class Task:
    booking_id: int
    user_id: int
    target_date: str | None
    time_window: dict | None
    pos_code: str | None
    icbc_username: str
    icbc_password: str
    max_wait_days: int


@dataclass
class Result:
    success: bool
    booked_at: str | None = None
    confirmation_no: str | None = None
    details: dict[str, Any] | None = None
    error: str | None = None


def run(task: Task) -> Result:
    """执行一次抢约。

    TODO: 把原 road.py 的核心逻辑搬进来。
    建议的拆分方式：
      1. 登录 ICBC（用 task.icbc_username/password）
      2. 查询可预约时段（按 task.target_date / time_window / pos_code 过滤）
      3. 命中目标就调预约接口
      4. 任何步骤失败抛 BookingEngineError
    """
    logger.warning(
        "booking_engine.run() 还没接入真实逻辑——booking_id=%s", task.booking_id
    )
    raise BookingEngineError("booking_engine 尚未接入 road.py 真实逻辑")
