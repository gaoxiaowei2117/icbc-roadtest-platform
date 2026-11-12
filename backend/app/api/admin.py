"""/api/admin/* admin 角色专属：查看所有任务、管理用户和路线包授权。"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_admin_user
from app.core.database import get_db
from app.core import route_packs as route_pack_catalog
from app.crud import booking as booking_crud
from app.crud import route_pack as route_pack_crud
from app.crud import user as user_crud
from app.models.booking import BookingStatus, PaymentStatus
from app.models.execution_pass import ExecutionPass, ExecutionPassStatus
from app.models.user import User
from app.schemas.booking import AdminBookingOut, BookingOut, PaymentReviewIn
from app.models.route_pack import (
    RoutePackOpen, RoutePackPurchase, RoutePackPurchaseSource, RoutePackPurchaseStatus,
)
from app.schemas.route_pack import RoutePackGrantIn, RoutePackOpenOut, RoutePackPurchaseOut
from app.schemas.user import AdminUserOut, UserPublic

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/bookings", response_model=list[AdminBookingOut])
def list_all_bookings(
    status_filter: BookingStatus | None = None,
    payment_status_filter: PaymentStatus | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list:
    bookings = booking_crud.list_all(
        db, status=status_filter, payment_status=payment_status_filter, limit=limit
    )
    return [
        AdminBookingOut(
            **BookingOut.model_validate(booking).model_dump(),
            user_email=booking.user.email,
        )
        for booking in bookings
    ]


@router.post("/bookings/{booking_id}/approve-payment", response_model=AdminBookingOut)
def approve_payment(
    booking_id: int,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    booking = booking_crud.get(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    try:
        approved = booking_crud.approve_payment(db, booking, _admin.id)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    return AdminBookingOut(
        **BookingOut.model_validate(approved).model_dump(),
        user_email=approved.user.email,
    )


@router.post("/bookings/{booking_id}/reject-payment", response_model=AdminBookingOut)
def reject_payment(
    booking_id: int,
    payload: PaymentReviewIn,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    booking = booking_crud.get(db, booking_id)
    if booking is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    try:
        rejected = booking_crud.reject_payment(db, booking, _admin.id, payload.reason)
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    return AdminBookingOut(
        **BookingOut.model_validate(rejected).model_dump(),
        user_email=rejected.user.email,
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_all_users(
    limit: int = Query(default=200, ge=1, le=500),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list:
    users = user_crud.list_all(db, limit=limit)
    user_ids = [user.id for user in users]
    available_passes: dict[int, int] = {}
    if user_ids:
        counts = db.execute(
            select(ExecutionPass.user_id, func.count(ExecutionPass.id))
            .where(
                ExecutionPass.user_id.in_(user_ids),
                ExecutionPass.status == ExecutionPassStatus.available,
            )
            .group_by(ExecutionPass.user_id)
        ).all()
        available_passes = {user_id: count for user_id, count in counts}
    packs_by_user: dict[int, list[str]] = {}
    if user_ids:
        rows = db.execute(
            select(RoutePackPurchase.user_id, RoutePackPurchase.pack_slug)
            .where(RoutePackPurchase.user_id.in_(user_ids), RoutePackPurchase.status == RoutePackPurchaseStatus.active)
            .order_by(RoutePackPurchase.pack_slug)
        ).all()
        for uid, slug in rows:
            packs_by_user.setdefault(uid, []).append(slug)
    opens: dict[int, tuple[int, datetime | None]] = {}
    ips_24h: dict[int, int] = {}
    if user_ids:
        for uid, count, last in db.execute(
            select(RoutePackOpen.user_id, func.count(RoutePackOpen.id), func.max(RoutePackOpen.created_at))
            .where(RoutePackOpen.user_id.in_(user_ids))
            .group_by(RoutePackOpen.user_id)
        ).all():
            opens[uid] = (count, last)
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        for uid, n in db.execute(
            select(RoutePackOpen.user_id, func.count(func.distinct(RoutePackOpen.ip)))
            .where(RoutePackOpen.user_id.in_(user_ids), RoutePackOpen.created_at >= since)
            .group_by(RoutePackOpen.user_id)
        ).all():
            ips_24h[uid] = n
    return [
        AdminUserOut(
            **UserPublic.model_validate(user).model_dump(),
            is_active=user.is_active,
            email_verified=user.email_verified,
            has_secret=user.secret is not None,
            available_execution_passes=available_passes.get(user.id, 0),
            route_packs=packs_by_user.get(user.id, []),
            route_opens=opens.get(user.id, (0, None))[0],
            route_opens_last_at=opens.get(user.id, (0, None))[1],
            route_open_ips_24h=ips_24h.get(user.id, 0),
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


def _purchase_out(purchase: RoutePackPurchase) -> RoutePackPurchaseOut:
    return RoutePackPurchaseOut(
        **RoutePackPurchaseOut.model_validate(purchase).model_dump(exclude={"user_email"}),
        user_email=purchase.user.email if purchase.user else None,
    )


@router.get("/route-packs/purchases", response_model=list[RoutePackPurchaseOut])
def list_route_pack_purchases(
    limit: int = Query(default=200, ge=1, le=500),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list:
    return [_purchase_out(p) for p in route_pack_crud.list_all(db, limit=limit)]


@router.get("/route-packs/opens", response_model=list[RoutePackOpenOut])
def list_route_pack_opens(
    limit: int = Query(default=200, ge=1, le=1000),
    user_id: int | None = Query(default=None),
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
) -> list:
    """最近的"打开导航"记录（谁、哪条路线、什么时候、从哪个 IP）。"""
    stmt = (
        select(RoutePackOpen, User.email)
        .join(User, User.id == RoutePackOpen.user_id)
        .order_by(RoutePackOpen.created_at.desc(), RoutePackOpen.id.desc())
        .limit(limit)
    )
    if user_id is not None:
        stmt = stmt.where(RoutePackOpen.user_id == user_id)
    out = []
    for log, email in db.execute(stmt).all():
        pack = route_pack_catalog.get_pack(log.pack_slug)
        title = (
            pack.routes[log.route_index].title
            if pack is not None and log.route_index < len(pack.routes)
            else None
        )
        out.append(RoutePackOpenOut(
            id=log.id, user_id=log.user_id, user_email=email, pack_slug=log.pack_slug,
            route_index=log.route_index, route_title=title, segment_index=log.segment_index,
            ip=log.ip, user_agent=log.user_agent, created_at=log.created_at,
            redirected_at=log.redirected_at,
        ))
    return out


@router.post("/route-packs/{slug}/grant", response_model=RoutePackPurchaseOut)
def grant_route_pack(
    slug: str,
    payload: RoutePackGrantIn,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """手动开通路线包（线下收款或测试用）；重复开通无副作用。"""
    if route_pack_catalog.get_pack(slug) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "路线包不存在")
    user = user_crud.get_by_email(db, payload.email.lower())
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    purchase = route_pack_crud.grant(
        db, user.id, slug, source=RoutePackPurchaseSource.manual, granted_by=_admin.id
    )
    db.commit()
    db.refresh(purchase)
    return _purchase_out(purchase)


@router.post("/route-packs/{slug}/revoke", response_model=RoutePackPurchaseOut)
def revoke_route_pack(
    slug: str,
    payload: RoutePackGrantIn,
    _admin: User = Depends(get_admin_user),
    db: Session = Depends(get_db),
):
    """收回路线包访问权（例如 Stripe 退款后）。不会自动退款。"""
    user = user_crud.get_by_email(db, payload.email.lower())
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    purchase = route_pack_crud.revoke(db, user.id, slug)
    if purchase is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "该用户没有这个路线包")
    db.commit()
    db.refresh(purchase)
    return _purchase_out(purchase)
