"""Admin stats for the route-pack site: sign-ups, free-route trials, checkouts, sales.

Days are calendar days in Vancouver time. Admins and accounts marked
``exclude_from_stats`` (the owner's test accounts) are left out of every number.

Whether a route counts as the free trial is read from the current catalog, so if
the free route changes later, earlier opens are re-read against the new setting.
Volumes are small (tens of users), so rows are fetched once and counted in Python.
"""
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core import route_packs as catalog
from app.models.payment import Payment, PaymentKind, PaymentRecordStatus
from app.models.route_pack import (
    RoutePackOpen, RoutePackPurchase, RoutePackPurchaseSource, RoutePackPurchaseStatus,
)
from app.models.user import User

TZ = ZoneInfo("America/Vancouver")


@dataclass
class Day:
    date: date
    signups: int = 0
    verified: int = 0          # of that day's sign-ups, how many have verified by now
    trial_users: int = 0       # users whose first free-route open was that day
    route_opens: int = 0       # every "open navigation" click
    checkouts: int = 0         # users who started a route-pack checkout that day
    purchases: int = 0         # paid route-pack purchases (Stripe), not manual grants
    revenue_cents: int = 0


@dataclass
class Stats:
    days: int
    start: date
    end: date
    timezone: str
    currency: str
    excluded_accounts: int
    daily: list[Day]
    totals: Day
    # Users who signed up in the range, and how far each got.
    funnel: dict[str, int] = field(default_factory=dict)
    # All time: users who opened a free route, and how many of them bought afterwards.
    trial_users_all_time: int = 0
    trial_then_purchased_all_time: int = 0


def _local_day(ts: datetime) -> date:
    return ts.astimezone(TZ).date()


def _is_free(slug: str, route_index: int) -> bool:
    pack = catalog.get_pack(slug)
    return pack is not None and 0 <= route_index < len(pack.routes) and pack.routes[route_index].free


def compute(db: Session, days: int, today: date | None = None) -> Stats:
    today = today or datetime.now(TZ).date()
    start = today - timedelta(days=days - 1)
    since = datetime.combine(start, time.min, tzinfo=TZ).astimezone(timezone.utc)

    counted = and_(User.is_admin.is_(False), User.exclude_from_stats.is_(False))
    excluded = db.scalar(
        select(func.count()).select_from(User)
        .where(or_(User.is_admin.is_(True), User.exclude_from_stats.is_(True)))
    ) or 0

    users = db.execute(select(User.id, User.created_at, User.email_verified).where(counted)).all()
    signed_up_in_range = {uid: (_local_day(ts), verified) for uid, ts, verified in users if ts >= since}

    # Opens: all time for counted users (first free open decides the trial day).
    opens = db.execute(
        select(RoutePackOpen.user_id, RoutePackOpen.pack_slug, RoutePackOpen.route_index, RoutePackOpen.created_at)
        .join(User, User.id == RoutePackOpen.user_id).where(counted)
        .order_by(RoutePackOpen.created_at)
    ).all()
    first_free: dict[int, datetime] = {}
    for uid, slug, idx, ts in opens:
        if uid not in first_free and _is_free(slug, idx):
            first_free[uid] = ts

    checkouts = db.execute(
        select(Payment.user_id, Payment.created_at, Payment.status, Payment.amount, Payment.currency, Payment.paid_at)
        .join(User, User.id == Payment.user_id)
        .where(counted, Payment.kind == PaymentKind.route_pack)
    ).all()

    purchases = db.execute(
        select(RoutePackPurchase.user_id, RoutePackPurchase.created_at)
        .join(User, User.id == RoutePackPurchase.user_id)
        .where(
            counted,
            RoutePackPurchase.status == RoutePackPurchaseStatus.active,
            RoutePackPurchase.source == RoutePackPurchaseSource.stripe,
        )
    ).all()
    first_purchase: dict[int, datetime] = {}
    for uid, ts in purchases:
        if uid not in first_purchase or ts < first_purchase[uid]:
            first_purchase[uid] = ts

    by_day = {start + timedelta(days=i): Day(date=start + timedelta(days=i)) for i in range(days)}

    for d, verified in signed_up_in_range.values():
        if d in by_day:
            by_day[d].signups += 1
            by_day[d].verified += int(verified)
    for ts in first_free.values():
        d = _local_day(ts)
        if d in by_day:
            by_day[d].trial_users += 1
    for _uid, _slug, _idx, ts in opens:
        d = _local_day(ts)
        if d in by_day:
            by_day[d].route_opens += 1
    checkout_users_by_day: dict[date, set[int]] = defaultdict(set)
    currency = "cad"
    for uid, created, status_, amount, cur, paid_at in checkouts:
        d = _local_day(created)
        if d in by_day:
            checkout_users_by_day[d].add(uid)
        if status_ == PaymentRecordStatus.paid and paid_at is not None:
            pd = _local_day(paid_at)
            if pd in by_day:
                by_day[pd].revenue_cents += amount or 0
                currency = cur or currency
    for d, uids in checkout_users_by_day.items():
        by_day[d].checkouts = len(uids)
    for _uid, ts in purchases:
        d = _local_day(ts)
        if d in by_day:
            by_day[d].purchases += 1

    daily = [by_day[d] for d in sorted(by_day)]
    totals = Day(date=today)
    for row in daily:
        for name in ("signups", "verified", "trial_users", "route_opens", "checkouts", "purchases", "revenue_cents"):
            setattr(totals, name, getattr(totals, name) + getattr(row, name))
    # A user who started checkout on two days counts once in the total.
    totals.checkouts = len({uid for uids in checkout_users_by_day.values() for uid in uids})

    cohort = set(signed_up_in_range)
    checkout_users = {uid for uid, *_ in checkouts}
    funnel = {
        "signed_up": len(cohort),
        "verified": sum(1 for uid in cohort if signed_up_in_range[uid][1]),
        "tried_free_route": len(cohort & set(first_free)),
        "started_checkout": len(cohort & checkout_users),
        "purchased": len(cohort & set(first_purchase)),
    }

    trial_then_purchased = sum(
        1 for uid, ts in first_free.items() if uid in first_purchase and first_purchase[uid] >= ts
    )

    return Stats(
        days=days, start=start, end=today, timezone=str(TZ), currency=currency,
        excluded_accounts=excluded, daily=daily, totals=totals, funnel=funnel,
        trial_users_all_time=len(first_free), trial_then_purchased_all_time=trial_then_purchased,
    )
