"""Admin stats: who counts, how the funnel and days are worked out."""
from datetime import date, datetime, timezone

from app.core import stats as stats_core
from app.models.payment import Payment, PaymentKind, PaymentProvider, PaymentRecordStatus
from app.models.route_pack import (
    RoutePackOpen, RoutePackPurchase, RoutePackPurchaseSource,
)
from app.models.user import User

SLUG = "burnaby-4399"  # route index 0 is the free route in the shipped catalog


def _admin(client, auth_headers, db, email="admin@gmail.com"):
    headers = auth_headers(email=email)
    admin = db.query(User).filter_by(email=email).one()
    admin.is_admin = True
    db.commit()
    return headers, admin


def _user(db, email, created=None, verified=True, **kw):
    user = User(email=email, password_hash="x", email_verified=verified, **kw)
    if created is not None:
        user.created_at = created
    db.add(user)
    db.commit()
    return user


def _open(db, user, route, at):
    db.add(RoutePackOpen(user_id=user.id, pack_slug=SLUG, route_index=route, created_at=at))
    db.commit()


def _buy(db, user, at, amount=1499):
    payment = Payment(
        user_id=user.id, kind=PaymentKind.route_pack, product_ref=SLUG,
        provider=PaymentProvider.stripe, status=PaymentRecordStatus.paid,
        amount=amount, currency="cad", created_at=at, paid_at=at,
    )
    db.add(payment)
    db.flush()
    db.add(RoutePackPurchase(
        user_id=user.id, pack_slug=SLUG, source=RoutePackPurchaseSource.stripe,
        payment_id=payment.id, created_at=at,
    ))
    db.commit()


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def test_stats_require_admin(client, auth_headers):
    assert client.get("/api/admin/stats").status_code == 401
    assert client.get("/api/admin/stats", headers=auth_headers(email="u@gmail.com")).status_code == 403


def test_funnel_and_daily_counts_leave_out_admins_and_test_accounts(client, auth_headers, db):
    headers, admin = _admin(client, auth_headers, db)
    now = datetime.now(timezone.utc)
    trial = _user(db, "trial@gmail.com")              # tries the free route, doesn't buy
    buyer = _user(db, "buyer@gmail.com")              # tries the free route, then buys
    _user(db, "lurker@gmail.com", verified=False)     # signs up, never verifies
    tester = _user(db, "test@gmail.com", exclude_from_stats=True)

    _open(db, trial, 0, now)
    _open(db, trial, 1, now)        # a paid route (e.g. after an admin grant) is not a trial
    _open(db, buyer, 0, now)
    _buy(db, buyer, now)
    for who in (admin, tester):     # left out entirely
        _open(db, who, 0, now)
        _buy(db, who, now, amount=999)

    body = client.get("/api/admin/stats", params={"days": 7}, headers=headers).json()
    assert body["days"] == 7 and len(body["daily"]) == 7
    assert body["timezone"] == "America/Vancouver"
    assert body["excluded_accounts"] == 2
    assert body["funnel"] == {
        "signed_up": 3, "verified": 2, "tried_free_route": 2, "started_checkout": 1, "purchased": 1,
    }
    t = body["totals"]
    assert (t["signups"], t["trial_users"], t["route_opens"], t["checkouts"], t["purchases"], t["revenue_cents"]) == (
        3, 2, 3, 1, 1, 1499,
    )
    assert (body["trial_users_all_time"], body["trial_then_purchased_all_time"]) == (2, 1)
    assert sum(d["signups"] for d in body["daily"]) == 3


def test_days_are_vancouver_calendar_days(db):
    # 2026-11-14 06:00 UTC is 2026-11-13 22:00 in Vancouver.
    user = _user(db, "late@gmail.com", created=_utc(2026, 11, 14, 6, 0))
    _open(db, user, 0, _utc(2026, 11, 14, 6, 5))
    s = stats_core.compute(db, days=2, today=date(2026, 11, 14))
    by_day = {d.date: d for d in s.daily}
    assert by_day[date(2026, 11, 13)].signups == 1
    assert by_day[date(2026, 11, 13)].trial_users == 1
    assert by_day[date(2026, 11, 14)].signups == 0
    # Older than the range: not counted.
    s = stats_core.compute(db, days=1, today=date(2026, 11, 14))
    assert s.totals.signups == 0 and s.funnel["signed_up"] == 0


def test_purchase_before_any_trial_is_not_a_trial_conversion(db):
    user = _user(db, "direct@gmail.com")
    _buy(db, user, _utc(2026, 11, 10, 12))
    _open(db, user, 0, _utc(2026, 11, 11, 12))
    s = stats_core.compute(db, days=7, today=date(2026, 11, 14))
    assert (s.trial_users_all_time, s.trial_then_purchased_all_time) == (1, 0)


def test_admin_can_mark_test_accounts(client, auth_headers, db):
    headers, admin = _admin(client, auth_headers, db)
    user = _user(db, "mine@gmail.com")
    url = f"/api/admin/users/{user.id}/stats-exclusion"
    assert client.put(url, json={"excluded": True}, headers=auth_headers(email="u@gmail.com")).status_code == 403
    assert client.put(url, json={"excluded": True}, headers=headers).json() == {"excluded": True}
    listed = {u["email"]: u for u in client.get("/api/admin/users", headers=headers).json()}
    assert listed["mine@gmail.com"]["exclude_from_stats"] is True
    assert client.get("/api/admin/stats", headers=headers).json()["funnel"]["signed_up"] == 1  # only u@
    assert client.put(url, json={"excluded": False}, headers=headers).json() == {"excluded": False}
    assert client.put(f"/api/admin/users/{admin.id}/stats-exclusion", json={"excluded": False},
                      headers=headers).status_code == 409
    assert client.put("/api/admin/users/9999/stats-exclusion", json={"excluded": True},
                      headers=headers).status_code == 404
