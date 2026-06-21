"""/api/worker/* 仅 worker 共享密钥可访问。"""
import base64

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import require_worker_key
from app.core.database import get_db
from app.crud import booking as booking_crud
from app.models.booking import BookingStatus
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
            db, booking, BookingStatus.failed, last_error="用户未配置 ICBC keyword"
        )
        return None
    return WorkerClaimOut(
        booking_id=booking.id,
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
    booking = booking_crud.get(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    if booking.status not in (BookingStatus.running, BookingStatus.pending):
        raise HTTPException(status.HTTP_409_CONFLICT, "任务不在运行中")
    if payload.status == BookingStatus.pending:
        booking_crud.requeue(db, booking, payload.last_error)
        return
    booking_crud.complete(
        db, booking, payload.status, last_error=payload.last_error, result=payload.result
    )


@router.get("/bookings/{booking_id}/status")
def get_booking_status(
    booking_id: int,
    db: Session = Depends(get_db),
    x_worker_key: str = Header(..., alias="X-Worker-Key"),
) -> dict:
    require_worker_key(x_worker_key)
    booking = booking_crud.get(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return {"id": booking.id, "status": booking.status}
