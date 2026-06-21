"""/api/admin/* admin 角色专属：查看所有任务和管理用户。"""
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user
from app.core.database import get_db
from app.crud import booking as booking_crud
from app.crud import user as user_crud
from app.models.booking import BookingStatus
from app.models.user import User
from app.schemas.booking import AdminBookingOut, BookingOut
from app.schemas.user import AdminUserOut, UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/bookings", response_model=list[AdminBookingOut])
def list_all_bookings(
    status_filter: BookingStatus | None = None,
    limit: int = 100,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list:
    bookings = booking_crud.list_all(db, status=status_filter, limit=limit)
    return [
        AdminBookingOut(
            **BookingOut.model_validate(booking).model_dump(),
            user_email=booking.user.email,
        )
        for booking in bookings
    ]


@router.get("/users", response_model=list[AdminUserOut])
def list_all_users(
    limit: int = 200,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list:
    users = user_crud.list_all(db, limit=limit)
    return [
        AdminUserOut(
            **UserPublic.model_validate(user).model_dump(),
            is_active=user.is_active,
            email_verified=user.email_verified,
            has_secret=user.secret is not None,
        )
        for user in users
    ]


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> Response:
    user = user_crud.get_by_id(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    if user.is_admin:
        raise HTTPException(status.HTTP_409_CONFLICT, "不能删除管理员账号")
    user_crud.delete(db, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
