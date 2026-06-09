"""抢约任务 schema。"""
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict, Field

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    target_date: date | None = None
    time_window: dict | None = None
    pos_code: str | None = Field(default=None, max_length=50)


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    status: BookingStatus
    target_date: date | None
    time_window: dict | None
    pos_code: str | None
    attempt_count: int
    last_error: str | None
    result: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkerClaimOut(BaseModel):
    """worker 拉取到的任务。

    凭据以密文下发（base64 的 SealedBox 密文），明文不经过云端：
    worker 用本地私钥解密。后端没有私钥，全程无法读取明文凭据。
    """
    booking_id: int
    user_id: int
    target_date: date | None
    time_window: dict | None
    pos_code: str | None
    secret_ciphertext: str
    max_wait_days: int


class WorkerResultIn(BaseModel):
    status: BookingStatus
    last_error: str | None = None
    result: dict | None = None
