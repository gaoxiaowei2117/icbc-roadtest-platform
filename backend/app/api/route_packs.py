"""/api/route-packs: paid practice-route packs (Google Maps links per test centre)."""
import logging
from datetime import datetime, timedelta, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_optional_user
from app.core import route_open
from app.core import route_packs as catalog
from app.core.config import get_settings
from app.core.database import get_db
from app.core.ratelimit import limiter
from app.crud import route_pack as route_pack_crud
from app.crud import user as user_crud
from app.models.payment import Payment, PaymentKind, PaymentProvider, PaymentRecordStatus
from app.models.route_pack import RoutePackOpen, RoutePackPurchaseSource
from app.models.user import User
from app.schemas.payment import StripeCheckoutOut
from app.schemas.route_pack import (
    RouteLinksOut,
    RouteOpenIn,
    RouteOpenOut,
    RoutePackCheckoutIn,
    RoutePackDef,
    RoutePackFacetsOut,
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


def _can_open_route(db: Session, user: User, pack: RoutePackDef, route_index: int) -> bool:
    """Free trial routes open for any logged-in user; the rest need the pack (or admin)."""
    if 0 <= route_index < len(pack.routes) and pack.routes[route_index].free:
        return True
    return route_pack_crud.user_can_open(db, user, pack.slug)


def _pack_out(pack: RoutePackDef, purchased: bool | None) -> RoutePackOut:
    settings = get_settings()
    return RoutePackOut(
        slug=pack.slug,
        name=pack.name,
        name_zh=pack.name_zh,
        country=pack.country,
        region=pack.region,
        city=pack.city,
        city_zh=pack.city_zh,
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
                preview_en=route.preview_en,
                note=route.note,
                note_zh=route.note_zh,
                free=route.free,
            )
            for route in pack.routes
        ],
        checkout_enabled=catalog.checkout_enabled(pack, settings),
        purchased=purchased,
    )


@router.get("", response_model=list[RoutePackOut])
def list_route_packs(
    country: str | None = Query(default=None, max_length=2, description="ISO 3166-1 alpha-2, e.g. CA"),
    region: str | None = Query(default=None, max_length=3, description="ISO 3166-2 part, e.g. BC"),
    q: str | None = Query(default=None, max_length=100, description="Search name, address, city, slug"),
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> list[RoutePackOut]:
    if user is None:
        owned = None
    elif user.is_admin:  # admins can open every pack without buying
        owned = {p.slug for p in catalog.all_packs()}
    else:
        owned = route_pack_crud.purchased_slugs(db, user.id)
    packs = catalog.filter_packs(catalog.all_packs(), country=country, region=region, q=q)
    return [_pack_out(pack, None if owned is None else pack.slug in owned) for pack in packs]


# Declared before /{slug} so "facets" isn't taken as a slug.
@router.get("/facets", response_model=RoutePackFacetsOut)
def route_pack_facets() -> RoutePackFacetsOut:
    """Countries and regions that have packs (unfiltered), with counts."""
    return RoutePackFacetsOut.model_validate(catalog.facets(catalog.all_packs()))


_GO_PAGE = """<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>roadtestgo</title>
<style>body{{font-family:system-ui,-apple-system,sans-serif;max-width:480px;margin:15vh auto;padding:0 16px;color:#1e293b}}
a{{color:#2563eb}}</style></head><body><p>{zh}</p><p>{en}</p>
<p><a href="/">roadtestgo.com</a></p></body></html>"""


def _go_error(code: int, zh: str, en: str) -> HTMLResponse:
    return HTMLResponse(_GO_PAGE.format(zh=zh, en=en), status_code=code, headers={"Cache-Control": "no-store"})


# Declared before /{slug} routes. No login header here: the browser (or the phone handing
# the link to Google Maps) just follows it, so the signed token carries who and what.
@router.get("/go/{token}", include_in_schema=False)
def follow_route_link(token: str, db: Session = Depends(get_db)):
    claims = route_open.decode_token(token)
    if claims is None:
        return _go_error(410, "链接已过期，请回到网站重新点「打开导航」。",
                         "This link has expired. Go back to the site and tap “Open navigation” again.")
    pack = catalog.get_pack(claims["slug"])
    user = user_crud.get_by_id(db, claims["user_id"])
    if (
        pack is None or user is None or not user.is_active
        or not _can_open_route(db, user, pack, claims["route_index"])
    ):
        return _go_error(403, "这个账号已经不能打开这条路线。", "This account can no longer open this route.")
    try:
        url = pack.routes[claims["route_index"]].segments[claims["segment_index"]].url
    except IndexError:
        return _go_error(404, "这条路线已经更新，请回到网站重新打开。", "This route has changed. Go back to the site and open it again.")
    log = db.get(RoutePackOpen, claims["open_id"])
    if log is not None and log.redirected_at is None:
        log.redirected_at = datetime.now(timezone.utc)
        db.commit()
    # 302 + no-store: never cached, so a changed link in the data file applies at once.
    return RedirectResponse(url, status_code=302, headers={"Cache-Control": "no-store", "Referrer-Policy": "no-referrer"})


@router.get("/{slug}", response_model=RoutePackOut)
def get_route_pack(
    slug: str,
    user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> RoutePackOut:
    pack = _pack_or_404(slug)
    purchased = route_pack_crud.user_can_open(db, user, slug) if user else None
    return _pack_out(pack, purchased)


@router.get("/{slug}/links", response_model=RoutePackLinksOut)
def get_route_pack_links(
    slug: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RoutePackLinksOut:
    pack = _pack_or_404(slug)
    if not route_pack_crud.user_can_open(db, user, slug):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "尚未购买该路线包")
    return RoutePackLinksOut(
        slug=pack.slug,
        routes=[
            RouteLinksOut(
                title=route.title,
                segments=[RouteSegmentOut(label=s.label) for s in route.segments],
            )
            for route in pack.routes
        ],
    )


@router.post("/{slug}/open", response_model=RouteOpenOut)
@limiter.limit("120/hour")
def open_route(
    request: Request,
    slug: str,
    payload: RouteOpenIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RouteOpenOut:
    """Log a click on "open navigation" and hand back a short-lived redirect URL."""
    pack = _pack_or_404(slug)
    if payload.route >= len(pack.routes) or payload.segment >= len(pack.routes[payload.route].segments):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "路线不存在")
    if not _can_open_route(db, user, pack, payload.route):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "尚未购买该路线包")
    log = RoutePackOpen(
        user_id=user.id,
        pack_slug=slug,
        route_index=payload.route,
        segment_index=payload.segment,
        ip=route_open.client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:300] or None,
    )
    db.add(log)
    db.commit()
    token = route_open.create_token(log.id, user.id, slug, payload.route, payload.segment)
    prefix = get_settings().api_v1_prefix
    return RouteOpenOut(
        url=f"{prefix}/route-packs/go/{token}",
        expires_in=int(route_open.TOKEN_TTL.total_seconds()),
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
    if route_pack_crud.user_can_open(db, user, slug):
        raise HTTPException(status.HTTP_409_CONFLICT, "已购买该路线包（管理员无需购买）" if user.is_admin else "已购买该路线包")
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
