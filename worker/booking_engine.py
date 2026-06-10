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
    """执行一次抢号（限时循环），委托给 road_adapter。"""
    import road_adapter  # 延迟 import：避免 import 期拉起 vendor.road 依赖链
    return road_adapter.run(task)
