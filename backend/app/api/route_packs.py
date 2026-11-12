"""/api/route-packs: paid practice-route packs (Google Maps links per test centre)."""
import logging
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_user
from app.core import route_packs as catalog
from app.core.config import get_settings
from app.core.database import get_db
from app.crud import route_pack as route_pack_crud
from app.models.payment import Payment, PaymentKind, PaymentProvider, PaymentRecordStatus
from app.models.route_pack import RoutePackPurchaseSource
from app.models.user import User
from app.schemas.payment import StripeCheckoutOut
from app.schemas.route_pack import (
    RouteLinksOut,
    RoutePackCheckoutIn,
    RoutePackDef,
    RoutePackLinksOut,
    RoutePackOut,
    RouteSegmentOut,
    RouteSegmentSummaryOut,
    RouteSummaryOut,
)

logger = logging.getLogger("icbc.route_packs")
router = APIRouter(prefix="/route-packs", tags=["route-packs"])

ROUTE_PACK_KIND = PaymentKind.route_pack.value
# Stripe Checkout sessions expire after 24 hours; never hand out an older URL.
_CHECKOUT_REUSE_WINDOW = timedelta(hours=23)


def _pack_or_404(slug: str) -> RoutePackDef:
    pack = catalog.get_pack(slug)
    if pack is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "路线包不存在")
    return pack


def _pack_out(pack: RoutePackDef, purchased: bool | None) -> RoutePackOut:
    settings = get_settings()
    return RoutePackOut(
        slug=pack.slug,
        name=pack.name,
        name_zh=pack.name_zh,
        centre=pack.centre,
        price_cents=catalog.price_cents(pack, settings),
        currency=catalog.currency(pack, settings),
        route_count=len(pack.routes),
        routes=[
            RouteSummaryOut(
                title=route.title,
                segment_count=len(route.segments),
                segments=[
                    RouteSegmentSummaryOut(label=seg.label, from_=seg.from_, to=seg.to)
                    for seg in route.segments
                ],
                preview=route.preview,
                note=route.note,
                note_zh=route.note_zh,
            )
            for route in pack.routes
        ],
        checkout_enabled=catalog.checkout_enabled(pack, settings),
        purchased=purchased,
    )


@router.get("", response_model=list[RoutePackOut])
def list_route_packs(
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> list[RoutePackOut]:
    owned = route_pack_crud.purchased_slugs(db, user.id) if user else None
    return [
        _pack_out(pack, None if owned is None else pack.slug in owned)
        for pack in catalog.all_packs()
    ]


@router.get("/{slug}", response_model=RoutePackOut)
def get_route_pack(
    slug: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> RoutePackOut:
    pack = _pack_or_404(slug)
    purchased = route_pack_crud.has_access(db, user.id, slug) if user else None
    return _pack_out(pack, purchased)


@router.get("/{slug}/links", response_model=RoutePackLinksOut)
def get_route_pack_links(
    slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoutePackLinksOut:
    pack = _pack_or_404(slug)
    if not route_pack_crud.has_access(db, user.id, slug):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "尚未购买该路线包")
    return RoutePackLinksOut(
        slug=pack.slug,
        routes=[
            RouteLinksOut(
                title=route.title,
                segments=[RouteSegmentOut(label=s.label, url=s.url) for s in route.segments],
            )
            for route in pack.routes
        ],
    )


@router.post("/{slug}/checkout", response_model=StripeCheckoutOut)
def create_route_pack_checkout(
    slug: str,
    payload: RoutePackCheckoutIn | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StripeCheckoutOut:
    pack = _pack_or_404(slug)
    settings = get_settings()
    if not catalog.checkout_enabled(pack, settings):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "路线包在线付款尚未开放")
    if route_pack_crud.has_access(db, user.id, slug):
        raise HTTPException(status.HTTP_409_CONFLICT, "已购买该路线包")
    stripe.api_key = settings.stripe_secret_key
    site = (payload or RoutePackCheckoutIn()).site

    pack_payments = (
        Payment.user_id == user.id,
        Payment.kind == PaymentKind.route_pack,
        Payment.product_ref == slug,
        Payment.provider == PaymentProvider.stripe,
    )
    open_sessions = db.scalars(
        select(Payment)
        .where(
            *pack_payments,
            Payment.status.in_([PaymentRecordStatus.created, PaymentRecordStatus.pending]),
            Payment.checkout_url.is_not(None),
            Payment.created_at > datetime.now(timezone.utc) - _CHECKOUT_REUSE_WINDOW,
        )
        .order_by(Payment.id.desc())
    ).all()
    # Reuse an open session only if it returns to the same site.
    existing = next(
        (p for p in open_sessions if (p.metadata_json or {}).get("site", "booking") == site), None
    )
    if existing is not None:
        return StripeCheckoutOut(url=existing.checkout_url, session_id=existing.provider_session_id)

    # Concurrent clicks share the attempt number and therefore the Stripe
    # idempotency key (same session); later retries get a fresh key.
    attempt = db.scalar(select(func.count(Payment.id)).where(*pack_payments)) or 0
    return_url = f"{settings.route_pack_return_url(site)}?pack={slug}"
    metadata = {"kind": ROUTE_PACK_KIND, "pack_slug": slug, "user_id": str(user.id)}
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": catalog.stripe_price_id(pack, settings), "quantity": 1}],
            # Same reason as the execution-pass checkout: standard Checkout only.
            managed_payments={"enabled": False},
            customer_email=user.email,
            client_reference_id=f"route_pack:{slug}:{user.id}",
            metadata=metadata,
            payment_intent_data={"metadata": metadata},
            success_url=f"{return_url}&checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{return_url}&checkout=cancelled",
            idempotency_key=f"icbc-route-pack-{slug}-{user.id}-{site}-checkout-{attempt}",
        )
    except stripe.error.StripeError as exc:
        logger.exception("路线包 Stripe Checkout 创建失败 pack=%s user_id=%s", slug, user.id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Stripe 付款页面创建失败") from exc

    payment = Payment(
        user_id=user.id,
        kind=PaymentKind.route_pack,
        product_ref=slug,
        provider=PaymentProvider.stripe,
        status=PaymentRecordStatus.created,
        amount=catalog.price_cents(pack, settings),
        currency=catalog.currency(pack, settings),
        provider_session_id=session.id,
        checkout_url=session.url,
        metadata_json={
            "kind": ROUTE_PACK_KIND, "pack_slug": slug, "user_id": user.id, "site": site,
        },
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(select(Payment).where(Payment.provider_session_id == session.id))
        if existing is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Stripe 付款会话已被其他请求占用")
        return StripeCheckoutOut(url=existing.checkout_url, session_id=existing.provider_session_id)
    return StripeCheckoutOut(url=session.url, session_id=session.id)


def is_route_pack_event(session: dict) -> bool:
    metadata = session.get("metadata") or {}
    return metadata.get("kind") == ROUTE_PACK_KIND


def process_route_pack_checkout_event(db: Session, event: dict, session: dict) -> None:
    """Record a route-pack Checkout event; repeated delivery is harmless.

    Called by the shared Stripe webhook for sessions whose metadata kind is
    ``route_pack``. Raises ValueError for events that cannot be attributed.
    """
    event_type = event.get("type")
    session_id = session.get("id")
    metadata = session.get("metadata") or {}
    pack_slug = metadata.get("pack_slug")
    if not session_id or not pack_slug:
        raise ValueError("Stripe 事件缺少 session_id 或 pack_slug")

    payment = db.scalar(
        select(Payment).where(Payment.provider_session_id == session_id).with_for_update()
    )
    if payment is None:
        try:
            user_id = int(metadata.get("user_id"))
        except (TypeError, ValueError) as exc:
            raise ValueError("Stripe user_id 非法") from exc
        if db.get(User, user_id) is None:
            raise ValueError("Stripe 事件对应的用户不存在")
        payment = Payment(
            user_id=user_id,
            kind=PaymentKind.route_pack,
            product_ref=pack_slug,
            provider=PaymentProvider.stripe,
            status=PaymentRecordStatus.created,
            provider_session_id=session_id,
            metadata_json={"kind": ROUTE_PACK_KIND, "pack_slug": pack_slug, "user_id": user_id},
        )
        db.add(payment)
        db.flush()
    elif payment.kind != PaymentKind.route_pack or payment.product_ref != pack_slug:
        raise ValueError("Stripe 事件与付款记录的商品不一致")

    event_id = event.get("id")
    if event_id and payment.provider_event_id == event_id:
        return
    payment.provider_event_id = event_id
    payment.provider_payment_intent_id = session.get("payment_intent")
    if session.get("amount_total") is not None:
        payment.amount = int(session["amount_total"])
    if session.get("currency"):
        payment.currency = str(session["currency"]).lower()

    if event_type in ("checkout.session.completed", "checkout.session.async_payment_succeeded"):
        if event_type == "checkout.session.completed" and session.get("payment_status") != "paid":
            payment.status = PaymentRecordStatus.pending
        else:
            payment.status = PaymentRecordStatus.paid
            payment.paid_at = payment.paid_at or datetime.now(timezone.utc)
            if catalog.get_pack(pack_slug) is None:
                # Still record it: the customer paid even if the pack was renamed.
                logger.warning("已付款的路线包不在数据文件中 pack=%s", pack_slug)
            route_pack_crud.grant(
                db,
                payment.user_id,
                pack_slug,
                source=RoutePackPurchaseSource.stripe,
                payment_id=payment.id,
            )
    elif event_type == "checkout.session.async_payment_failed":
        payment.status = PaymentRecordStatus.failed
    elif event_type == "checkout.session.expired":
        payment.status = PaymentRecordStatus.expired
    else:
        return
    db.commit()
