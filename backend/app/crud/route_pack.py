"""Route pack purchase database operations."""
from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.route_pack import (
    RoutePackPurchase,
    RoutePackPurchaseSource,
    RoutePackPurchaseStatus,
)


def has_access(db: Session, user_id: int, pack_slug: str) -> bool:
    stmt = select(RoutePackPurchase.id).where(
        RoutePackPurchase.user_id == user_id,
        RoutePackPurchase.pack_slug == pack_slug,
        RoutePackPurchase.status == RoutePackPurchaseStatus.active,
    )
    return db.scalar(stmt) is not None


def user_can_open(db: Session, user, pack_slug: str) -> bool:
    """Admins open every pack without buying; everyone else needs an active purchase."""
    return bool(getattr(user, "is_admin", False)) or has_access(db, user.id, pack_slug)


def purchased_slugs(db: Session, user_id: int) -> set[str]:
    stmt = select(RoutePackPurchase.pack_slug).where(
        RoutePackPurchase.user_id == user_id,
        RoutePackPurchase.status == RoutePackPurchaseStatus.active,
    )
    return set(db.scalars(stmt).all())


def grant(
    db: Session,
    user_id: int,
    pack_slug: str,
    source: RoutePackPurchaseSource,
    payment_id: int | None = None,
    granted_by: int | None = None,
) -> RoutePackPurchase:
    """Activate (user, pack) without committing; safe to call repeatedly.

    The row is locked so a webhook retry and an admin grant cannot race into a
    unique-constraint error inside the same transaction pattern.
    """
    purchase = db.scalar(
        select(RoutePackPurchase)
        .where(RoutePackPurchase.user_id == user_id, RoutePackPurchase.pack_slug == pack_slug)
        .with_for_update()
    )
    if purchase is None:
        purchase = RoutePackPurchase(
            user_id=user_id,
            pack_slug=pack_slug,
            status=RoutePackPurchaseStatus.active,
            source=source,
            payment_id=payment_id,
            granted_by=granted_by,
        )
        db.add(purchase)
        db.flush()
        return purchase
    if purchase.status == RoutePackPurchaseStatus.active:
        # Already unlocked: keep the original record, but remember a Stripe
        # payment if the earlier grant was manual.
        if payment_id is not None and purchase.payment_id is None:
            purchase.payment_id = payment_id
        return purchase
    purchase.status = RoutePackPurchaseStatus.active
    purchase.source = source
    purchase.revoked_at = None
    purchase.granted_by = granted_by
    if payment_id is not None:
        purchase.payment_id = payment_id
    return purchase


def revoke(db: Session, user_id: int, pack_slug: str) -> RoutePackPurchase | None:
    """Revoke access without committing. Returns None when nothing was granted."""
    purchase = db.scalar(
        select(RoutePackPurchase)
        .where(RoutePackPurchase.user_id == user_id, RoutePackPurchase.pack_slug == pack_slug)
        .with_for_update()
    )
    if purchase is None:
        return None
    if purchase.status != RoutePackPurchaseStatus.revoked:
        purchase.status = RoutePackPurchaseStatus.revoked
        purchase.revoked_at = datetime.now(timezone.utc)
    return purchase


def list_all(db: Session, limit: int = 200) -> Sequence[RoutePackPurchase]:
    stmt = (
        select(RoutePackPurchase)
        .options(joinedload(RoutePackPurchase.user))
        .order_by(RoutePackPurchase.created_at.desc(), RoutePackPurchase.id.desc())
        .limit(limit)
    )
    return db.scalars(stmt).all()
