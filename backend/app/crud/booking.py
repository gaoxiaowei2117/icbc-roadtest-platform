"""抢约任务数据库操作。"""
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus


def list_for_user(db: Session, user_id: int, limit: int = 50) -> Sequence[Booking]:
    stmt = (
        select(Booking)
        .where(Booking.user_id == user_id)
        .order_by(Booking.created_at.desc())
        .limit(limit)
    )
    return db.scalars(stmt).all()


def has_active(db: Session, user_id: int) -> bool:
    """用户是否已有进行中的任务（pending 或 running）。"""
    stmt = (
        select(Booking)
        .where(
            Booking.user_id == user_id,
            Booking.status.in_([BookingStatus.pending, BookingStatus.running]),
        )
        .limit(1)
    )
    return db.scalar(stmt) is not None


def list_all(db: Session, status: BookingStatus | None = None, limit: int = 100) -> Sequence[Booking]:
    stmt = select(Booking).order_by(Booking.created_at.desc()).limit(limit)
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    return db.scalars(stmt).all()


def get(db: Session, booking_id: int) -> Booking | None:
    return db.get(Booking, booking_id)


def create(db: Session, user_id: int, **fields) -> Booking:
    booking = Booking(user_id=user_id, **fields)
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def cancel(db: Session, booking: Booking) -> Booking:
    if booking.status not in (BookingStatus.pending, BookingStatus.running):
        raise ValueError(f"任务状态 {booking.status} 不可取消")
    booking.status = BookingStatus.cancelled
    booking.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(booking)
    return booking


def claim_next_pending(db: Session) -> Booking | None:
    """原子地认领一个 pending 任务。"""
    stmt = (
        select(Booking)
        .where(Booking.status == BookingStatus.pending)
        .order_by(Booking.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    booking = db.scalar(stmt)
    if booking is None:
        return None
    booking.status = BookingStatus.running
    booking.started_at = datetime.now(timezone.utc)
    booking.attempt_count = (booking.attempt_count or 0) + 1
    db.commit()
    db.refresh(booking)
    return booking


def complete(
    db: Session,
    booking: Booking,
    status: BookingStatus,
    last_error: str | None = None,
    result: dict | None = None,
) -> Booking:
    booking.status = status
    booking.last_error = last_error
    booking.result = result
    booking.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(booking)
    return booking


def requeue(db: Session, booking: Booking, last_error: str | None) -> Booking:
    """任务失败但允许重试：回到 pending。"""
    booking.status = BookingStatus.pending
    booking.last_error = last_error
    booking.started_at = None
    db.commit()
    db.refresh(booking)
    return booking


def reset_stale_running(db: Session, timeout_minutes: int) -> int:
    """把卡死的 running 任务重置回 pending（T2 reaper）。

    worker 崩溃 / 网络中断后，任务会一直停在 running 没人收尾。
    凡 started_at 早于 (now - timeout) 的 running 任务，视为卡死，重排重试。
    返回被重置的任务数。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    stmt = select(Booking).where(
        Booking.status == BookingStatus.running,
        Booking.started_at.is_not(None),
        Booking.started_at < cutoff,
    )
    stale = db.scalars(stmt).all()
    for booking in stale:
        booking.status = BookingStatus.pending
        booking.started_at = None
        booking.last_error = f"worker 超时（>{timeout_minutes} 分钟）未完成，自动重置重排"
    if stale:
        db.commit()
    return len(stale)
