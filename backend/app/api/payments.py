"""Stripe Checkout and webhook endpoints."""
import logging
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.crud import booking as booking_crud
from app.models.booking import BookingStatus, PaymentStatus
from app.models.payment import Payment, PaymentProvider, PaymentRecordStatus
from app.models.user import User
from app.schemas.payment import StripeCheckoutOut, StripeStatusOut

logger = logging.getLogger("icbc.stripe")
router = APIRouter(prefix="/payments", tags=["payments"])


def _stripe_settings():
    settings = get_settings()
    if not settings.stripe_enabled:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Stripe 付款尚未配置")
    stripe.api_key = settings.stripe_secret_key
    return settings


@router.get("/stripe/status", response_model=StripeStatusOut)
def stripe_status(user: User = Depends(get_current_user)) -> StripeStatusOut:
    del user
    return StripeStatusOut(enabled=get_settings().stripe_enabled)


@router.post("/stripe/checkout/{booking_id}", response_model=StripeCheckoutOut)
def create_stripe_checkout(
    booking_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> StripeCheckoutOut:
    settings = _stripe_settings()
    booking = db.get(booking_id)
    if booking is None or booking.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "任务不存在")
    if booking.status != BookingStatus.awaiting_payment or booking.payment_status != PaymentStatus.awaiting_payment:
        raise HTTPException(status.HTTP_409_CONFLICT, "当前任务不需要 Stripe 付款")

    existing = db.scalar(
        select(Payment)
        .where(
            Payment.booking_id == booking.id,
            Payment.provider == PaymentProvider.stripe,
            Payment.status.in_([PaymentRecordStatus.created, PaymentRecordStatus.pending]),
            Payment.checkout_url.is_not(None),
        )
        .order_by(Payment.id.desc())
    )
    if existing is not None:
        return StripeCheckoutOut(url=existing.checkout_url, session_id=existing.provider_session_id)

    success_url = settings.resolved_stripe_success_url
    separator = "&" if "?" in success_url else "?"
    success_url = f"{success_url}{separator}session_id={{CHECKOUT_SESSION_ID}}"
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": settings.stripe_price_id, "quantity": 1}],
            customer_email=user.email,
            client_reference_id=str(booking.id),
            metadata={"booking_id": str(booking.id), "user_id": str(user.id)},
            success_url=success_url,
            cancel_url=settings.resolved_stripe_cancel_url,
            idempotency_key=f"icbc-booking-{booking.id}",
        )
    except stripe.error.StripeError as exc:
        logger.exception("Stripe Checkout 创建失败 booking_id=%s", booking.id)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Stripe 付款页面创建失败") from exc

    payment = Payment(
        user_id=user.id,
        booking_id=booking.id,
        provider=PaymentProvider.stripe,
        status=PaymentRecordStatus.created,
        provider_session_id=session.id,
        checkout_url=session.url,
        metadata_json={"booking_id": booking.id, "user_id": user.id},
    )
    db.add(payment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.scalar(
            select(Payment).where(Payment.provider_session_id == session.id)
        )
        if existing is None:
            raise HTTPException(status.HTTP_409_CONFLICT, "Stripe 付款会话已被其他请求占用")
        return StripeCheckoutOut(url=existing.checkout_url, session_id=existing.provider_session_id)
    return StripeCheckoutOut(url=session.url, session_id=session.id)


def _event_object(event):
    data = event.get("data") or {}
    return data.get("object") or {}


def _process_checkout_event(db: Session, event: dict) -> None:
    event_type = event.get("type")
    session = _event_object(event)
    session_id = session.get("id")
    metadata = session.get("metadata") or {}
    booking_id_raw = metadata.get("booking_id") or session.get("client_reference_id")
    if not session_id or not booking_id_raw:
        raise ValueError("Stripe 事件缺少 session_id 或 booking_id")
    try:
        booking_id = int(booking_id_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("Stripe booking_id 非法") from exc

    payment = db.scalar(
        select(Payment).where(Payment.provider_session_id == session_id).with_for_update()
    )
    from app.models.booking import Booking

    booking = db.get(Booking, booking_id, with_for_update=True)
    if booking is None:
        raise ValueError("Stripe 事件对应的任务不存在")
    if payment is None:
        payment = Payment(
            user_id=booking.user_id,
            booking_id=booking.id,
            provider=PaymentProvider.stripe,
            status=PaymentRecordStatus.created,
            provider_session_id=session_id,
        )
        db.add(payment)
        db.flush()

    previous_event_id = payment.provider_event_id
    event_id = event.get("id")
    if previous_event_id == event_id and event_id:
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
            payment.paid_at = datetime.now(timezone.utc)
            booking_crud.grant_paid_entitlement(db, booking, source="stripe")
    elif event_type == "checkout.session.async_payment_failed":
        payment.status = PaymentRecordStatus.failed
    elif event_type == "checkout.session.expired":
        payment.status = PaymentRecordStatus.expired
    else:
        return
    db.commit()


@router.post("/stripe/webhook", status_code=status.HTTP_204_NO_CONTENT)
async def stripe_webhook(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    if not settings.stripe_webhook_secret:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Stripe Webhook 尚未配置")
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "缺少 Stripe-Signature")
    try:
        event = stripe.Webhook.construct_event(payload, stripe_signature, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Stripe Webhook 签名无效") from exc
    try:
        _process_checkout_event(db, event)
    except ValueError as exc:
        db.rollback()
        logger.warning("Stripe 事件无法处理：%s", exc)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
