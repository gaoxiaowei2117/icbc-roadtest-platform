"""抢号任务 schema。"""
from datetime import date, datetime
from pydantic import BaseModel, ConfigDict

from app.models.booking import BookingStatus


class BookingCreate(BaseModel):
    """建任务无参数：抢号参数来自 user 档案。"""
    pass


class BookingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    status: BookingStatus
    attempt_count: int
    progress_rounds: int
    last_progress: str | None
    last_progress_at: datetime | None
    last_error: str | None
    result: dict | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime
    updated_at: datetime


class WorkerClaimOut(BaseModel):
    """worker 拉取到的任务：含完整抢号档案，keyword 为密文（worker 私钥解）。"""
    booking_id: int
    user_id: int
    drvr_last_name: str
    licence_number: str
    keyword_ciphertext: str
    exam_class: str
    pos_ids: list[int]
    expect_after_date: date
    expect_before_date: date
    expect_time_range: str
    pref_days_of_week: list[int]
    pref_parts_of_day: list[int]


class WorkerResultIn(BaseModel):
    status: BookingStatus
    last_error: str | None = None
    result: dict | None = None


class WorkerProgressIn(BaseModel):
    message: str
