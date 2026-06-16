"""/api/bookings/* 用户任务管理。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import booking as booking_crud
from app.models.user import User
from app.schemas.booking import BookingCreate, BookingOut

router = APIRouter(prefix="/bookings", tags=["bookings"])


@router.get("", response_model=list[BookingOut])
def list_my_bookings(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list:
    return list(booking_crud.list_for_user(db, user.id))


@router.post("", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    missing = []
    if not user.icbc_license_no or not user.icbc_last_name:
        missing.append("驾照号/姓氏")
    if user.secret is None:
        missing.append("ICBC keyword")
    if not user.exam_class:
        missing.append("考试类型")
    if not user.pos_ids:
        missing.append("考点")
    if not user.expect_after_date or not user.expect_before_date:
        missing.append("日期区间")
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"请先在设置页补全：{'、'.join(missing)}"
        )
    if booking_crud.has_active(db, user.id):
        raise HTTPException(
            status.HTTP_409_CONFLICT, "已有进行中的任务，完成或取消后再新建"
        )
    return booking_crud.create(db, user.id)


@router.get("/{booking_id}", response_model=BookingOut)
def get_booking(
    booking_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = booking_crud.get(db, booking_id)
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    return booking


@router.post("/{booking_id}/cancel", response_model=BookingOut)
def cancel_booking(
    booking_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    booking = booking_crud.get(db, booking_id)
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    try:
        return booking_crud.cancel(db, booking)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
