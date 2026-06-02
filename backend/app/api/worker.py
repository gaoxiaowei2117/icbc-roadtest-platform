"""/api/worker/* 仅 worker 共享密钥可访问。"""
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_worker_key
from app.core.database import get_db
from app.crud import booking as booking_crud
from app.crud import secret as secret_crud
from app.schemas.booking import WorkerClaimOut, WorkerResultIn

router = APIRouter(prefix="/worker", tags=["worker"])


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
            db, booking, BookingStatus.failed, last_error="用户未配置 ICBC 凭据"
        )
        return None
    try:
        icbc_username, icbc_password = secret_crud.decrypt_payload(user.secret)
    except ValueError as e:
        booking_crud.complete(db, booking, BookingStatus.failed, last_error=str(e))
        return None
    return WorkerClaimOut(
        booking_id=booking.id,
        user_id=user.id,
        target_date=booking.target_date,
        time_window=booking.time_window,
        pos_code=booking.pos_code,
        icbc_username=icbc_username,
        icbc_password=icbc_password,
        max_wait_days=user.max_wait_days,
    )


@router.post("/bookings/{booking_id}/result", status_code=status.HTTP_204_NO_CONTENT)
def report_result(
    booking_id: int,
    payload: WorkerResultIn,
    db: Session = Depends(get_db),
    x_worker_key: str = Header(..., alias="X-Worker-Key"),
):
    require_worker_key(x_worker_key)
    booking = booking_crud.get(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    if booking.status not in (BookingStatus.running, BookingStatus.pending):
        raise HTTPException(status.HTTP_409_CONFLICT, "任务不在运行中")
    booking_crud.complete(
        db, booking, payload.status, last_error=payload.last_error, result=payload.result
    )
