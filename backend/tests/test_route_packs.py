"""Route pack catalog, purchase gating, Stripe checkout/webhook and admin grants."""
import json
from pathlib import Path

import pytest

from app.api.payments import _process_checkout_event
from app.core import route_packs as catalog
from app.core.config import get_settings
from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.execution_pass import ExecutionPass
from app.models.payment import Payment, PaymentKind, PaymentRecordStatus
from app.models.route_pack import (
    RoutePackPurchase,
    RoutePackPurchaseSource,
    RoutePackPurchaseStatus,
)
from app.models.user import User

SLUG = "burnaby-4399"


def _make_admin(client, auth_headers, db, email="admin@gmail.com"):
    headers = auth_headers(email=email)
    admin = db.query(User).filter_by(email=email).one()
    admin.is_admin = True
    db.commit()
    return headers


def _grant(db, email, slug=SLUG):
    user = db.query(User).filter_by(email=email).one()
    db.add(RoutePackPurchase(user_id=user.id, pack_slug=slug, source=RoutePackPurchaseSource.manual))
    db.commit()
    return user


def _route_pack_event(event_id, session_id, user_id, event_type="checkout.session.completed",
                      payment_status="paid", slug=SLUG):
    return {
        "id": event_id,
        "type": event_type,
        "data": {
            "object": {
                "id": session_id,
                "payment_status": payment_status,
                "payment_intent": "pi_route_pack",
                "amount_total": 1499,
                "currency": "cad",
                "client_reference_id": f"route_pack:{slug}:{user_id}",
                "metadata": {"kind": "route_pack", "pack_slug": slug, "user_id": str(user_id)},
            }
        },
    }


@pytest.fixture
def stripe_configured(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_route_pack")
    monkeypatch.setattr(settings, "stripe_webhook_secret", "whsec_test_route_pack")
    monkeypatch.setattr(settings, "stripe_route_pack_price_id", "price_test_route_pack")
    return settings


# ---- catalog -------------------------------------------------------------------

def test_shipped_catalog_has_burnaby_pack():
    pack = catalog.get_pack(SLUG)
    assert pack is not None
    assert pack.name == "ICBC Burnaby Claim Centre (4399 Wayburne Dr)"
    assert [r.title for r in pack.routes] == ["路线 1", "路线 2", "路线 3", "路线 4 · 上高速线"]
    assert all(1 <= len(r.segments) <= 3 for r in pack.routes)
    assert catalog.price_cents(pack, get_settings()) == 1499
    assert catalog.currency(pack, get_settings()) == "cad"


def test_catalog_requires_valid_location_codes(tmp_path, monkeypatch):
    base = {
        "slug": "x-pack", "name": "X", "city": "Burnaby", "centre": "Somewhere",
        "routes": [{"title": "R", "segments": [{"label": "1", "url": "https://www.google.com/maps/dir/?api=1"}]}],
    }
    for bad in ({}, {"country": "CA"}, {"country": "Canada", "region": "BC"}, {"country": "CA", "region": "CA-BC"}):
        path = tmp_path / "packs.json"
        path.write_text(json.dumps({"packs": [{**base, **bad}]}), encoding="utf-8")
        monkeypatch.setattr(catalog, "_catalog_path", lambda: path)
        with pytest.raises(ValueError):
            catalog.all_packs()


def test_catalog_rejects_more_than_three_segments(tmp_path, monkeypatch):
    bad = {
        "packs": [{
            "slug": "bad-pack", "name": "Bad", "centre": "Somewhere",
            "country": "CA", "region": "BC", "city": "Burnaby",
            "routes": [{"title": "R", "segments": [
                {"label": str(i), "url": "https://www.google.com/maps/dir/?api=1"} for i in range(4)
            ]}],
        }]
    }
    path = tmp_path / "packs.json"
    path.write_text(json.dumps(bad), encoding="utf-8")
    monkeypatch.setattr(catalog, "_catalog_path", lambda: path)
    with pytest.raises(ValueError):
        catalog.all_packs()


# ---- listing ---------------------------------------------------------------------

def test_anonymous_listing_has_no_links_and_no_purchase_flag(client):
    response = client.get("/api/route-packs")
    assert response.status_code == 200
    packs = response.json()
    pack = next(p for p in packs if p["slug"] == SLUG)
    assert pack["purchased"] is None
    assert pack["price_cents"] == 1499
    assert pack["currency"] == "cad"
    assert pack["route_count"] == 4
    assert pack["routes"][0] == {
        "title": "路线 1",
        "segment_count": 2,
        "segments": [
            {"label": "第 1 段", "from": "centre", "to": "Sussex Ave"},
            {"label": "第 2 段", "from": "Sussex Ave", "to": "centre"},
        ],
        "preview": "route-previews/burnaby-4399/route1-v2.jpg",
        "preview_en": "route-previews/burnaby-4399/en/route1.jpg",
        "note": None,
        "note_zh": None,
    }
    assert pack["checkout_enabled"] is False
    assert "google.com/maps" not in response.text


def test_public_listing_includes_segment_ends_and_route_note(client):
    pack = client.get(f"/api/route-packs/{SLUG}").json()
    highway = pack["routes"][3]
    assert [(s["from"], s["to"]) for s in highway["segments"]] == [
        ("centre", "Smith Ave"), ("Smith Ave", "Exit 32 (Laurel St)"), ("Laurel St", "centre"),
    ]
    assert "Carleton Ave" in pack["routes"][2]["note"]
    assert "Carleton Ave" in pack["routes"][2]["note_zh"]
    assert all(r["preview"] for r in pack["routes"])
    assert all(r["preview_en"].startswith("route-previews/burnaby-4399/en/") for r in pack["routes"])


def test_listing_shows_purchased_for_authenticated_user(client, auth_headers, db):
    headers = auth_headers(email="buyer@gmail.com")
    pack = client.get(f"/api/route-packs/{SLUG}", headers=headers).json()
    assert pack["purchased"] is False

    _grant(db, "buyer@gmail.com")
    listed = client.get("/api/route-packs", headers=headers)
    assert next(p for p in listed.json() if p["slug"] == SLUG)["purchased"] is True
    assert "google.com/maps" not in listed.text


def test_listing_rejects_invalid_token(client):
    response = client.get("/api/route-packs", headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401


def test_unknown_pack_is_404(client, auth_headers):
    assert client.get("/api/route-packs/nowhere").status_code == 404
    assert client.get("/api/route-packs/nowhere/links", headers=auth_headers()).status_code == 404


# ---- links -----------------------------------------------------------------------

def test_links_require_login(client):
    assert client.get(f"/api/route-packs/{SLUG}/links").status_code == 401


def test_links_forbidden_before_purchase_and_allowed_after(client, auth_headers, db):
    headers = auth_headers(email="buyer@gmail.com")
    assert client.get(f"/api/route-packs/{SLUG}/links", headers=headers).status_code == 403

    _grant(db, "buyer@gmail.com")
    response = client.get(f"/api/route-packs/{SLUG}/links", headers=headers)
    assert response.status_code == 200
    body = response.json()
    assert body["slug"] == SLUG
    assert [r["title"] for r in body["routes"]] == ["路线 1", "路线 2", "路线 3", "路线 4 · 上高速线"]
    first = body["routes"][0]["segments"][0]
    assert first["label"] == "第 1 段"
    assert first["url"].startswith("https://www.google.com/maps/dir/?api=1&travelmode=driving&origin=")


def test_links_forbidden_for_other_users_and_after_revoke(client, auth_headers, db):
    buyer = auth_headers(email="buyer@gmail.com")
    other = auth_headers(email="other@gmail.com")
    user = _grant(db, "buyer@gmail.com")
    assert client.get(f"/api/route-packs/{SLUG}/links", headers=other).status_code == 403

    purchase = db.query(RoutePackPurchase).filter_by(user_id=user.id).one()
    purchase.status = RoutePackPurchaseStatus.revoked
    db.commit()
    assert client.get(f"/api/route-packs/{SLUG}/links", headers=buyer).status_code == 403


# ---- checkout ----------------------------------------------------------------------

def test_checkout_disabled_without_configuration(client, auth_headers, db):
    headers = auth_headers(email="buyer@gmail.com")
    response = client.post(f"/api/route-packs/{SLUG}/checkout", headers=headers)
    assert response.status_code == 503
    assert db.query(Payment).count() == 0


def test_checkout_disabled_without_price_id(client, auth_headers, stripe_configured, monkeypatch):
    monkeypatch.setattr(stripe_configured, "stripe_route_pack_price_id", "")
    headers = auth_headers(email="buyer@gmail.com")
    assert client.get(f"/api/route-packs/{SLUG}").json()["checkout_enabled"] is False
    assert client.post(f"/api/route-packs/{SLUG}/checkout", headers=headers).status_code == 503


def test_checkout_requires_login(client):
    assert client.post(f"/api/route-packs/{SLUG}/checkout").status_code == 401


def test_checkout_creates_stripe_session(client, auth_headers, db, stripe_configured, monkeypatch):
    headers = auth_headers(email="buyer@gmail.com")
    user = db.query(User).filter_by(email="buyer@gmail.com").one()
    assert client.get(f"/api/route-packs/{SLUG}").json()["checkout_enabled"] is True
    calls = []

    class FakeSession:
        id = "cs_test_route_pack"
        url = "https://checkout.stripe.test/cs_test_route_pack"

    def fake_create(**kwargs):
        calls.append(kwargs)
        return FakeSession()

    monkeypatch.setattr("app.api.route_packs.stripe.checkout.Session.create", fake_create)
    response = client.post(f"/api/route-packs/{SLUG}/checkout", headers=headers)
    assert response.status_code == 200
    assert response.json() == {
        "url": "https://checkout.stripe.test/cs_test_route_pack",
        "session_id": "cs_test_route_pack",
    }
    kwargs = calls[0]
    assert kwargs["mode"] == "payment"
    assert kwargs["line_items"] == [{"price": "price_test_route_pack", "quantity": 1}]
    assert kwargs["metadata"] == {"kind": "route_pack", "pack_slug": SLUG, "user_id": str(user.id)}
    page = f"{stripe_configured.app_base_url}{stripe_configured.frontend_base_path}/routes?pack={SLUG}"
    assert kwargs["success_url"] == f"{page}&checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    assert kwargs["cancel_url"] == f"{page}&checkout=cancelled"
    payment = db.query(Payment).one()
    assert payment.kind == PaymentKind.route_pack
    assert payment.product_ref == SLUG
    assert payment.booking_id is None
    assert payment.amount == 1499

    # A second click reuses the open session instead of creating another one.
    again = client.post(f"/api/route-packs/{SLUG}/checkout", headers=headers)
    assert again.json()["session_id"] == "cs_test_route_pack"
    assert len(calls) == 1


def test_checkout_from_route_site_returns_to_root(
    client, auth_headers, db, stripe_configured, monkeypatch
):
    headers = auth_headers(email="buyer@gmail.com")
    calls = []

    def fake_create(**kwargs):
        calls.append(kwargs)
        n = len(calls)
        return type("S", (), {"id": f"cs_site_{n}", "url": f"https://checkout.stripe.test/{n}"})()

    monkeypatch.setattr("app.api.route_packs.stripe.checkout.Session.create", fake_create)
    root = client.post(f"/api/route-packs/{SLUG}/checkout", headers=headers, json={"site": "routes"})
    assert root.status_code == 200
    base = stripe_configured.app_base_url
    assert calls[0]["success_url"] == (
        f"{base}/?pack={SLUG}&checkout=success&session_id={{CHECKOUT_SESSION_ID}}"
    )
    assert calls[0]["cancel_url"] == f"{base}/?pack={SLUG}&checkout=cancelled"

    # The booking site gets its own session (different return URL) ...
    booking = client.post(f"/api/route-packs/{SLUG}/checkout", headers=headers, json={"site": "booking"})
    assert booking.json()["session_id"] == "cs_site_2"
    assert calls[1]["success_url"].startswith(f"{base}{stripe_configured.frontend_base_path}/routes?")
    # ... and each site reuses its own open session.
    again = client.post(f"/api/route-packs/{SLUG}/checkout", headers=headers, json={"site": "routes"})
    assert again.json()["session_id"] == "cs_site_1"
    assert len(calls) == 2


def test_checkout_rejects_unknown_site(client, auth_headers, stripe_configured):
    headers = auth_headers(email="buyer@gmail.com")
    response = client.post(
        f"/api/route-packs/{SLUG}/checkout", headers=headers,
        json={"site": "https://evil.example"},
    )
    assert response.status_code == 422


def test_checkout_uses_per_pack_price_override(client, auth_headers, stripe_configured, monkeypatch):
    headers = auth_headers(email="buyer@gmail.com")
    pack = catalog.get_pack(SLUG).model_copy(update={"stripe_price_id": "price_pack_override"})
    monkeypatch.setattr(catalog, "get_pack", lambda slug: pack if slug == SLUG else None)
    seen = {}

    class FakeSession:
        id = "cs_test_override"
        url = "https://checkout.stripe.test/cs_test_override"

    def fake_create(**kwargs):
        seen.update(kwargs)
        return FakeSession()

    monkeypatch.setattr("app.api.route_packs.stripe.checkout.Session.create", fake_create)
    assert client.post(f"/api/route-packs/{SLUG}/checkout", headers=headers).status_code == 200
    assert seen["line_items"] == [{"price": "price_pack_override", "quantity": 1}]


def test_checkout_rejected_when_already_purchased(client, auth_headers, db, stripe_configured):
    headers = auth_headers(email="buyer@gmail.com")
    _grant(db, "buyer@gmail.com")
    assert client.post(f"/api/route-packs/{SLUG}/checkout", headers=headers).status_code == 409


# ---- webhook -------------------------------------------------------------------------

def test_webhook_grants_route_pack_idempotently(client, auth_headers, db):
    headers = auth_headers(email="buyer@gmail.com")
    user = db.query(User).filter_by(email="buyer@gmail.com").one()
    event = _route_pack_event("evt_route_pack_1", "cs_route_pack_1", user.id)

    _process_checkout_event(db, event)
    _process_checkout_event(db, event)  # Stripe retries the same event
    # A different event for the same session (e.g. async success) is also harmless.
    _process_checkout_event(
        db,
        _route_pack_event("evt_route_pack_2", "cs_route_pack_1", user.id,
                          event_type="checkout.session.async_payment_succeeded"),
    )

    db.expire_all()
    purchases = db.query(RoutePackPurchase).filter_by(user_id=user.id).all()
    assert len(purchases) == 1
    assert purchases[0].status == RoutePackPurchaseStatus.active
    assert purchases[0].source == RoutePackPurchaseSource.stripe
    payment = db.query(Payment).filter_by(provider_session_id="cs_route_pack_1").one()
    assert payment.status == PaymentRecordStatus.paid
    assert payment.kind == PaymentKind.route_pack
    assert purchases[0].payment_id == payment.id
    assert db.query(Payment).count() == 1
    assert db.query(ExecutionPass).count() == 0
    assert client.get(f"/api/route-packs/{SLUG}/links", headers=headers).status_code == 200


def test_webhook_unpaid_completion_does_not_grant(db, auth_headers):
    auth_headers(email="buyer@gmail.com")
    user = db.query(User).filter_by(email="buyer@gmail.com").one()
    _process_checkout_event(
        db, _route_pack_event("evt_unpaid", "cs_unpaid", user.id, payment_status="unpaid")
    )
    assert db.query(RoutePackPurchase).count() == 0
    assert db.query(Payment).one().status == PaymentRecordStatus.pending


def test_webhook_endpoint_dispatches_route_pack_events(client, auth_headers, db, monkeypatch):
    auth_headers(email="buyer@gmail.com")
    user = db.query(User).filter_by(email="buyer@gmail.com").one()
    monkeypatch.setattr(get_settings(), "stripe_webhook_secret", "whsec_test")
    event = _route_pack_event("evt_endpoint", "cs_endpoint", user.id)
    monkeypatch.setattr(
        "app.api.payments.stripe.Webhook.construct_event", lambda payload, sig, secret: event
    )
    response = client.post(
        "/api/payments/stripe/webhook", content=b"{}", headers={"Stripe-Signature": "t=1,v1=x"}
    )
    assert response.status_code == 204
    assert db.query(RoutePackPurchase).filter_by(user_id=user.id).one().pack_slug == SLUG


def test_execution_pass_webhook_still_works_alongside_route_packs(client, ready_user, db):
    headers, *_ = ready_user(email="pass-payer@gmail.com")
    db.query(ExecutionPass).delete()
    db.commit()
    booking = client.post("/api/bookings", headers=headers, json={}).json()
    _process_checkout_event(db, {
        "id": "evt_pass", "type": "checkout.session.completed",
        "data": {"object": {
            "id": "cs_pass", "payment_status": "paid", "amount_total": 1000, "currency": "cad",
            "metadata": {"booking_id": str(booking["id"]), "user_id": str(booking["user_id"])},
        }},
    })
    db.expire_all()
    updated = db.get(Booking, booking["id"])
    assert updated.status == BookingStatus.pending
    assert updated.payment_status == PaymentStatus.approved
    payment = db.query(Payment).filter_by(provider_session_id="cs_pass").one()
    assert payment.kind == PaymentKind.execution_pass
    assert db.query(RoutePackPurchase).count() == 0


# ---- admin -----------------------------------------------------------------------------

def test_admin_grant_and_revoke(client, auth_headers, db):
    buyer = auth_headers(email="buyer@gmail.com")
    admin = _make_admin(client, auth_headers, db)

    response = client.post(f"/api/admin/route-packs/{SLUG}/grant", headers=admin,
                           json={"email": "Buyer@gmail.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["pack_slug"] == SLUG
    assert body["status"] == "active"
    assert body["source"] == "manual"
    assert body["user_email"] == "buyer@gmail.com"
    # Granting twice is harmless.
    assert client.post(f"/api/admin/route-packs/{SLUG}/grant", headers=admin,
                       json={"email": "buyer@gmail.com"}).status_code == 200
    assert db.query(RoutePackPurchase).count() == 1
    assert client.get(f"/api/route-packs/{SLUG}/links", headers=buyer).status_code == 200

    listed = client.get("/api/admin/route-packs/purchases", headers=admin)
    assert [p["user_email"] for p in listed.json()] == ["buyer@gmail.com"]

    revoked = client.post(f"/api/admin/route-packs/{SLUG}/revoke", headers=admin,
                          json={"email": "buyer@gmail.com"})
    assert revoked.status_code == 200
    assert revoked.json()["status"] == "revoked"
    assert client.get(f"/api/route-packs/{SLUG}/links", headers=buyer).status_code == 403

    # Re-granting reactivates the same row.
    client.post(f"/api/admin/route-packs/{SLUG}/grant", headers=admin, json={"email": "buyer@gmail.com"})
    assert db.query(RoutePackPurchase).count() == 1
    assert client.get(f"/api/route-packs/{SLUG}/links", headers=buyer).status_code == 200


def test_admin_grant_validates_pack_and_user(client, auth_headers, db):
    admin = _make_admin(client, auth_headers, db)
    auth_headers(email="buyer@gmail.com")
    assert client.post("/api/admin/route-packs/nowhere/grant", headers=admin,
                       json={"email": "buyer@gmail.com"}).status_code == 404
    assert client.post(f"/api/admin/route-packs/{SLUG}/grant", headers=admin,
                       json={"email": "missing@gmail.com"}).status_code == 404
    assert client.post(f"/api/admin/route-packs/{SLUG}/revoke", headers=admin,
                       json={"email": "buyer@gmail.com"}).status_code == 404


def test_route_pack_admin_requires_admin(client, auth_headers):
    headers = auth_headers(email="buyer@gmail.com")
    assert client.post(f"/api/admin/route-packs/{SLUG}/grant", headers=headers,
                       json={"email": "buyer@gmail.com"}).status_code == 403
    assert client.get("/api/admin/route-packs/purchases", headers=headers).status_code == 403


# ---- browse: location, filters, search, facets ----------------------------------------

MULTI = Path(__file__).parent / "fixtures" / "route_packs_multi.json"


@pytest.fixture
def multi_catalog(monkeypatch):
    monkeypatch.setattr(catalog, "_catalog_path", lambda: MULTI)


def _slugs(response):
    assert response.status_code == 200
    return [p["slug"] for p in response.json()]


def test_listing_includes_location_fields(client):
    pack = client.get(f"/api/route-packs/{SLUG}").json()
    assert (pack["country"], pack["region"], pack["city"], pack["city_zh"]) == ("CA", "BC", "Burnaby", "本拿比")


def test_listing_filters_by_country_and_region(client, multi_catalog):
    assert len(_slugs(client.get("/api/route-packs"))) == 5
    assert _slugs(client.get("/api/route-packs?country=US")) == ["seattle-downtown"]
    assert _slugs(client.get("/api/route-packs?country=ca&region=bc")) == [
        "burnaby-4399", "richmond-5300", "surrey-newton",
    ]
    assert _slugs(client.get("/api/route-packs?country=CA&region=ON")) == ["toronto-downsview"]
    assert _slugs(client.get("/api/route-packs?country=US&region=BC")) == []
    assert client.get("/api/route-packs?country=CAN").status_code == 422


def test_listing_search_matches_names_city_address_and_slug(client, multi_catalog):
    assert _slugs(client.get("/api/route-packs", params={"q": "richmond"})) == ["richmond-5300"]
    assert _slugs(client.get("/api/route-packs", params={"q": "列治文"})) == ["richmond-5300"]
    assert _slugs(client.get("/api/route-packs", params={"q": "多伦多"})) == ["toronto-downsview"]
    assert _slugs(client.get("/api/route-packs", params={"q": "KING GEORGE"})) == ["surrey-newton"]
    assert _slugs(client.get("/api/route-packs", params={"q": "  burnaby-4399 "})) == ["burnaby-4399"]
    assert _slugs(client.get("/api/route-packs", params={"q": "icbc", "region": "BC"})) == [
        "burnaby-4399", "richmond-5300", "surrey-newton",
    ]
    assert _slugs(client.get("/api/route-packs", params={"q": "vancouver island"})) == []
    # Search never looks inside the links.
    assert _slugs(client.get("/api/route-packs", params={"q": "PLACEHOLDER"})) == []


def test_facets_list_countries_and_regions_with_counts(client, multi_catalog):
    response = client.get("/api/route-packs/facets")
    assert response.status_code == 200
    assert response.json() == {
        "total": 5,
        "countries": [
            {"code": "CA", "count": 4, "regions": [{"code": "BC", "count": 3}, {"code": "ON", "count": 1}]},
            {"code": "US", "count": 1, "regions": [{"code": "WA", "count": 1}]},
        ],
    }


def test_facets_for_shipped_catalog(client):
    assert client.get("/api/route-packs/facets").json() == {
        "total": 1,
        "countries": [{"code": "CA", "count": 1, "regions": [{"code": "BC", "count": 1}]}],
    }


def test_admin_opens_every_pack_without_buying(client, auth_headers, db):
    admin = _make_admin(client, auth_headers, db)
    listed = client.get("/api/route-packs", headers=admin).json()
    assert all(p["purchased"] is True for p in listed)
    assert client.get(f"/api/route-packs/{SLUG}", headers=admin).json()["purchased"] is True
    links = client.get(f"/api/route-packs/{SLUG}/links", headers=admin)
    assert links.status_code == 200
    assert links.json()["routes"][0]["segments"][0]["url"].startswith("https://www.google.com/maps/")
    # No purchase record was created for the admin.
    assert db.query(RoutePackPurchase).count() == 0


def test_admin_user_list_shows_route_packs(client, auth_headers, db):
    auth_headers(email="buyer@gmail.com")
    auth_headers(email="other@gmail.com")
    admin = _make_admin(client, auth_headers, db)
    assert client.post(f"/api/admin/route-packs/{SLUG}/grant", headers=admin,
                       json={"email": "buyer@gmail.com"}).status_code == 200
    users = {u["email"]: u for u in client.get("/api/admin/users", headers=admin).json()}
    assert users["buyer@gmail.com"]["route_packs"] == [SLUG]
    assert users["other@gmail.com"]["route_packs"] == []
