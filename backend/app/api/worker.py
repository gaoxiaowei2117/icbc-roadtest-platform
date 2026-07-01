"""/api/worker/* 仅 worker 共享密钥可访问。"""
import base64

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_worker_key
from app.core.database import get_db
from app.crud import booking as booking_crud
from app.crud import user as user_crud
from app.models.booking import BookingStatus
from app.schemas.booking import WorkerClaimOut, WorkerProgressIn, WorkerResultIn

router = APIRouter(prefix="/worker", tags=["worker"])


def _check_fencing(booking, attempt: int) -> None:
    """拒绝过期认领的回写（fencing token）。

    任务被 reaper 重排并被另一个 worker 重新认领后，attempt_count 会自增。
    旧 worker 携带的 attempt 与当前不一致，说明它的认领已失效，必须拒绝，
    否则慢 worker 的迟到回报会覆盖新 worker 正在进行的那次运行。
    """
    if attempt != booking.attempt_count:
        raise HTTPException(status.HTTP_409_CONFLICT, "认领已过期（任务已被重排并重新认领）")


@router.post("/claim", response_model=WorkerClaimOut | None)
def claim_task(
    db: Session = Depends(get_db),
    x_worker_key: str = Header(..., alias="X-Worker-Key"),
):
    require_worker_key(x_worker_key)
    booking = booking_crud.claim_next_pending(db)
    if booking is None:
        return None
    user = booking.user
    if user.secret is None:
        booking_crud.complete(
            db, booking, BookingStatus.failed, last_error="用户未配置 ICBC keyword"
        )
        return None
    # 兜底：claim_next_pending 已提交 running，此处必须在组装 WorkerClaimOut 前
    # 校验必填档案齐全。否则缺字段（如日期被清成 NULL）会让 schema 非空约束抛 500，
    # 任务卡 running 被 reaper 无限重排。缺字段则直接判失败，给出清晰错误、只失败一次。
    missing = user_crud.missing_booking_fields(user)
    if missing:
        booking_crud.complete(
            db, booking, BookingStatus.failed,
            last_error=f"档案不完整，缺少：{'、'.join(missing)}",
        )
        return None
    return WorkerClaimOut(
        booking_id=booking.id,
        attempt=booking.attempt_count,
        user_id=user.id,
        drvr_last_name=user.icbc_last_name or "",
        licence_number=user.icbc_license_no or "",
        keyword_ciphertext=base64.b64encode(user.secret.ciphertext).decode(),
        exam_class=user.exam_class or "",
        pos_ids=user.pos_ids or [],
        expect_after_date=user.expect_after_date,
        expect_before_date=user.expect_before_date,
        expect_time_range=user.expect_time_range or "",
        pref_days_of_week=user.pref_days_of_week or [],
        pref_parts_of_day=user.pref_parts_of_day or [],
    )


@router.post("/bookings/{booking_id}/result", status_code=status.HTTP_204_NO_CONTENT)
def report_result(
    booking_id: int,
    payload: WorkerResultIn,
    db: Session = Depends(get_db),
    x_worker_key: str = Header(..., alias="X-Worker-Key"),
):
    require_worker_key(x_worker_key)
    # 加行锁读取，使 fencing 校验 + 状态校验 + 写终态成为原子操作，
    # 避免与用户取消（cancel 同样加行锁）并发时互相覆盖。
    booking = booking_crud.get_for_update(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    _check_fencing(booking, payload.attempt)
    if booking.status not in (BookingStatus.running, BookingStatus.pending):
        raise HTTPException(status.HTTP_409_CONFLICT, "任务不在运行中")
    if payload.status == BookingStatus.pending:
        booking_crud.requeue(db, booking, payload.last_error)
        return
    booking_crud.complete(
        db, booking, payload.status, last_error=payload.last_error, result=payload.result
    )


@router.post("/bookings/{booking_id}/progress", status_code=status.HTTP_204_NO_CONTENT)
def report_progress(
    booking_id: int,
    payload: WorkerProgressIn,
    db: Session = Depends(get_db),
    x_worker_key: str = Header(..., alias="X-Worker-Key"),
):
    require_worker_key(x_worker_key)
    booking = booking_crud.get(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    _check_fencing(booking, payload.attempt)
    if booking.status != BookingStatus.running:
        raise HTTPException(status.HTTP_409_CONFLICT, "任务不在运行中")
    booking_crud.record_progress(db, booking, payload.message)


@router.get("/bookings/{booking_id}/status")
def get_booking_status(
    booking_id: int,
    attempt: int,
    db: Session = Depends(get_db),
    x_worker_key: str = Header(..., alias="X-Worker-Key"),
) -> dict:
    require_worker_key(x_worker_key)
    booking = booking_crud.get(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    # 认领已过期时返回 409，worker 据此停止本轮执行，避免与新 worker 并行抢同一任务
    _check_fencing(booking, attempt)
    return {"id": booking.id, "status": booking.status, "attempt": booking.attempt_count}
