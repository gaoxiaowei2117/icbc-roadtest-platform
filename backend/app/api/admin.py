"""/api/admin/* admin 角色专属：看所有任务、查任意用户。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user
from app.core.database import get_db
from app.crud import booking as booking_crud
from app.models.booking import BookingStatus
from app.models.user import User
from app.schemas.booking import BookingOut

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/bookings", response_model=list[BookingOut])
def list_all_bookings(
    status_filter: BookingStatus | None = None,
    limit: int = 100,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list:
    return list(booking_crud.list_all(db, status=status_filter, limit=limit))
