"""抢约任务和一次性执行权限的数据库操作。"""
from datetime import datetime, timedelta, timezone
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session, joinedload

from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.execution_pass import ExecutionPass, ExecutionPassStatus


ACTIVE_STATUSES = (
    BookingStatus.awaiting_payment,
    BookingStatus.awaiting_review,
    BookingStatus.pending,
    BookingStatus.running,
)


def list_for_user(db: Session, user_id: int, limit: int = 50) -> Sequence[Booking]:
    stmt = (
        select(Booking)
        .where(Booking.user_id == user_id)
        .order_by(Booking.created_at.desc())
        .limit(limit)
    )
    return db.scalars(stmt).all()


def has_active(db: Session, user_id: int) -> bool:
    """用户是否已有未结束任务（付款、审核、pending 或 running）。"""
    stmt = (
        select(Booking.id)
        .where(Booking.user_id == user_id, Booking.status.in_(ACTIVE_STATUSES))
        .limit(1)
    )
    return db.scalar(stmt) is not None


def list_all(
    db: Session,
    status: BookingStatus | None = None,
    payment_status: PaymentStatus | None = None,
    limit: int = 100,
) -> Sequence[Booking]:
    stmt = (
        select(Booking)
        .options(joinedload(Booking.user))
        .order_by(Booking.created_at.desc())
        .limit(limit)
    )
    if status is not None:
        stmt = stmt.where(Booking.status == status)
    if payment_status is not None:
        stmt = stmt.where(Booking.payment_status == payment_status)
    return db.scalars(stmt).all()


def get(db: Session, booking_id: int) -> Booking | None:
    return db.get(Booking, booking_id)


def get_for_update(db: Session, booking_id: int) -> Booking | None:
    """加行锁读取，供需要“读-改-写”原子性的路径使用。"""
    return db.get(Booking, booking_id, with_for_update=True)


def _reserve_available_pass(
    db: Session,
    user_id: int,
    booking_id: int,
    approved_by: int | None = None,
) -> ExecutionPass | None:
    """锁住并占用一个可用次数；调用方必须在同一事务中提交。"""
    stmt = (
        select(ExecutionPass)
        .where(
            ExecutionPass.user_id == user_id,
            ExecutionPass.status == ExecutionPassStatus.available,
        )
        .order_by(ExecutionPass.id.asc())
        .limit(1)
        .with_for_update()
    )
    execution_pass = db.scalar(stmt)
    if execution_pass is None:
        return None
    execution_pass.status = ExecutionPassStatus.reserved
    execution_pass.booking_id = booking_id
    execution_pass.approved_by = approved_by
    execution_pass.approved_at = datetime.now(timezone.utc)
    execution_pass.released_at = None
    return execution_pass


def create(db: Session, user_id: int, **fields) -> Booking:
    """创建任务，并在同一事务中预留已有的一次性执行权限（如果有）。"""
    # 先 flush 取得 booking id，再把 pass 指向该任务，整个过程由事务保护。
    booking = Booking(
        user_id=user_id,
        status=BookingStatus.awaiting_payment,
        payment_status=PaymentStatus.awaiting_payment,
        **fields,
    )
    db.add(booking)
    db.flush()
    execution_pass = _reserve_available_pass(db, user_id, booking.id)
    if execution_pass is not None:
        booking.status = BookingStatus.pending
        booking.payment_status = PaymentStatus.approved
    db.commit()
    db.refresh(booking)
    return booking


def submit_payment(
    db: Session, booking: Booking, payment_reference: str | None = None
) -> Booking:
    locked = db.get(Booking, booking.id, with_for_update=True)
    if locked is None:
        raise ValueError("任务不存在")
    if locked.status != BookingStatus.awaiting_payment:
        raise ValueError(f"任务状态 {locked.status} 不需要提交付款")
    locked.status = BookingStatus.awaiting_review
    locked.payment_status = PaymentStatus.awaiting_review
    locked.payment_reference = payment_reference
    locked.payment_submitted_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(locked)
    return locked


def approve_payment(db: Session, booking: Booking, admin_id: int) -> Booking:
    locked = db.get(Booking, booking.id, with_for_update=True)
    if locked is None:
        raise ValueError("任务不存在")
    if (
        locked.payment_status != PaymentStatus.awaiting_review
        or locked.status not in (BookingStatus.awaiting_review, BookingStatus.cancelled)
    ):
        raise ValueError(f"任务状态 {locked.status} 不在待审核队列")
    was_cancelled = locked.status == BookingStatus.cancelled
    # 每一笔确认到账的付款都发放一个新权限。若原任务已取消，权限先保持
    # available；否则直接预留给当前任务并进入 worker 队列。
    db.add(ExecutionPass(
        user_id=locked.user_id,
        booking_id=None if was_cancelled else locked.id,
        status=(
            ExecutionPassStatus.available
            if was_cancelled
            else ExecutionPassStatus.reserved
        ),
        approved_by=admin_id,
        approved_at=datetime.now(timezone.utc),
    ))
    if not was_cancelled:
        locked.status = BookingStatus.pending
    locked.payment_status = PaymentStatus.approved
    locked.reviewed_by = admin_id
    locked.reviewed_at = datetime.now(timezone.utc)
    locked.review_reason = None
    db.commit()
    db.refresh(locked)
    return locked


def reject_payment(
    db: Session, booking: Booking, admin_id: int, reason: str | None = None
) -> Booking:
    locked = db.get(Booking, booking.id, with_for_update=True)
    if locked is None:
        raise ValueError("任务不存在")
    if (
        locked.payment_status != PaymentStatus.awaiting_review
        or locked.status not in (BookingStatus.awaiting_review, BookingStatus.cancelled)
    ):
        raise ValueError(f"任务状态 {locked.status} 不在待审核队列")
    if locked.status != BookingStatus.cancelled:
        locked.status = BookingStatus.payment_rejected
    locked.payment_status = PaymentStatus.rejected
    locked.reviewed_by = admin_id
    locked.reviewed_at = datetime.now(timezone.utc)
    locked.review_reason = reason
    db.commit()
    db.refresh(locked)
    return locked


def available_pass_count(db: Session, user_id: int) -> int:
    stmt = select(ExecutionPass.id).where(
        ExecutionPass.user_id == user_id,
        ExecutionPass.status == ExecutionPassStatus.available,
    )
    return len(db.scalars(stmt).all())


def _release_reserved_pass(db: Session, booking_id: int) -> None:
    execution_pass = db.scalar(
        select(ExecutionPass)
        .where(
            ExecutionPass.booking_id == booking_id,
            ExecutionPass.status == ExecutionPassStatus.reserved,
        )
        .with_for_update()
    )
    if execution_pass is None:
        return
    execution_pass.status = ExecutionPassStatus.available
    execution_pass.booking_id = None
    execution_pass.released_at = datetime.now(timezone.utc)


def _finish_reserved_pass(
    db: Session, booking_id: int, status: BookingStatus
) -> None:
    execution_pass = db.scalar(
        select(ExecutionPass)
        .where(
            ExecutionPass.booking_id == booking_id,
            ExecutionPass.status == ExecutionPassStatus.reserved,
        )
        .with_for_update()
    )
    if execution_pass is None:
        return
    if status == BookingStatus.done:
        execution_pass.status = ExecutionPassStatus.consumed
        execution_pass.consumed_at = datetime.now(timezone.utc)
    elif status == BookingStatus.failed:
        execution_pass.status = ExecutionPassStatus.available
        execution_pass.booking_id = None
        execution_pass.released_at = datetime.now(timezone.utc)


def cancel(db: Session, booking: Booking) -> Booking:
    # 加行锁后重新校验状态，避免与 worker 的 complete 并发时后写者覆盖 done。
    locked = db.get(Booking, booking.id, with_for_update=True)
    if locked is None:
        raise ValueError("任务不存在")
    if locked.status == BookingStatus.awaiting_review:
        raise ValueError("付款已提交并正在审核，审核完成后才能取消任务")
    if locked.status not in (
        BookingStatus.awaiting_payment,
        BookingStatus.pending,
        BookingStatus.running,
        BookingStatus.payment_rejected,
    ):
        raise ValueError(f"任务状态 {locked.status} 不可取消")
    _release_reserved_pass(db, locked.id)
    locked.status = BookingStatus.cancelled
    locked.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(locked)
    return locked


def claim_next_pending(db: Session) -> Booking | None:
    """原子地认领一个已经获得执行权限的 pending 任务。"""
    stmt = (
        select(Booking)
        .where(
            Booking.status == BookingStatus.pending,
            Booking.payment_status.in_([PaymentStatus.approved, PaymentStatus.not_required]),
        )
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
    if status not in (BookingStatus.done, BookingStatus.failed):
        raise ValueError("只能用 complete 写入 done 或 failed")
    _finish_reserved_pass(db, booking.id, status)
    booking.status = status
    booking.last_error = last_error
    booking.result = result
    booking.finished_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(booking)
    return booking


def requeue(db: Session, booking: Booking, last_error: str | None) -> Booking:
    """任务失败但允许重试：回到 pending，继续占用本次执行权限。"""
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
    """把卡死的 running 任务重置回 pending，保留已预留的执行权限。"""
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
    result = db.execute(
        update(Booking)
        .where(Booking.id.in_(stale_ids), Booking.status == BookingStatus.running)
        .values(
            status=BookingStatus.pending,
            started_at=None,
            last_error=f"worker 超时（>{timeout_minutes} 分钟）未完成，自动重置重排",
        )
        .execution_options(synchronize_session=False),
    )
    db.commit()
    return result.rowcount
