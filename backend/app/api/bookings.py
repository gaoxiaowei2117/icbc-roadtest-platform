"""/api/bookings/* 用户任务管理。"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.crud import booking as booking_crud
from app.models.booking import BookingStatus
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
    if not user.icbc_license_no or not user.icbc_last_name:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "请先在资料页填写驾照号和姓氏"
        )
    if user.secret is None:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "请先在资料页填写 ICBC 登录凭据"
        )
    return booking_crud.create(
        db, user_id=user.id, **payload.model_dump(exclude_unset=True)
    )


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
