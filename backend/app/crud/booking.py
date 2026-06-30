"""抢约任务数据库操作。"""
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

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
    stmt = (
        select(Booking)
        .options(joinedload(Booking.user))
        .order_by(Booking.created_at.desc())
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    return db.scalars(stmt).all()


def get(db: Session, booking_id: int) -> Booking | None:
    return db.get(Booking, booking_id)


def get_for_update(db: Session, booking_id: int) -> Booking | None:
    """加行锁读取，供需要"读-改-写"原子性的路径使用（取消 / worker 回报）。"""
    return db.get(Booking, booking_id, with_for_update=True)


def create(db: Session, user_id: int, **fields) -> Booking:
    booking = Booking(user_id=user_id, **fields)
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


def cancel(db: Session, booking: Booking) -> Booking:
    # 加行锁后重新校验状态，避免与 worker 的 complete 并发时"后写者覆盖"（done 被改成 cancelled）
    locked = db.get(Booking, booking.id, with_for_update=True)
    if locked is None:
        raise ValueError("任务不存在")
    if locked.status not in (BookingStatus.pending, BookingStatus.running):
        raise ValueError(f"任务状态 {locked.status} 不可取消")
    locked.status = BookingStatus.cancelled
    locked.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(locked)
    return locked


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
    booking.finished_at = None
    booking.result = None
    db.commit()
    db.refresh(booking)
    return booking


def record_progress(db: Session, booking: Booking, message: str) -> Booking:
    booking.progress_rounds = (booking.progress_rounds or 0) + 1
    booking.last_progress = message[:500]
    booking.last_progress_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(booking)
    return booking


def reset_stale_running(db: Session, timeout_minutes: int) -> int:
    """把卡死的 running 任务重置回 pending（T2 reaper）。

    worker 崩溃 / 网络中断后，任务会一直停在 running 没人收尾。
    凡最近活动时间早于 (now - timeout) 的 running 任务，视为卡死，重排重试。
    最近活动时间优先用 worker 进度心跳 last_progress_at，没有进度时回退到 started_at。
    返回被重置的任务数。
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)
    stmt = select(Booking).where(
        Booking.status == BookingStatus.running,
        Booking.started_at.is_not(None),
        Booking.started_at < cutoff,
    )
    candidates = db.scalars(stmt).all()
    stale_ids = []
    for booking in candidates:
        active_at = booking.last_progress_at or booking.started_at
        if active_at is not None and active_at >= cutoff:
            continue
        stale_ids.append(booking.id)
    if not stale_ids:
        return 0
    # 守卫：UPDATE 必须带 status='running'，避免覆盖在"读取候选"与"提交"之间
    # 已由 worker 完成（done/failed）或被用户取消（cancelled）的任务。
    result = db.execute(
        update(Booking)
        .where(
            Booking.id.in_(stale_ids),
            Booking.status == BookingStatus.running,
        )
        .values(
            status=BookingStatus.pending,
            started_at=None,
            last_error=f"worker 超时（>{timeout_minutes} 分钟）未完成，自动重置重排",
        )
        .execution_options(synchronize_session=False),
    )
    db.commit()
    return result.rowcount
