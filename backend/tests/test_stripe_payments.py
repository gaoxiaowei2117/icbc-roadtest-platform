"""Stripe configuration and payment entitlement integration tests."""
from types import SimpleNamespace

from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.execution_pass import ExecutionPass, ExecutionPassStatus
from app.models.payment import Payment, PaymentProvider, PaymentRecordStatus
from app.api.payments import _process_checkout_event


def test_stripe_checkout_creates_session_for_awaiting_payment(
    client, ready_user, db, monkeypatch
):
    headers, *_ = ready_user(email="checkout-payer@gmail.com")
    db.query(ExecutionPass).delete()
    db.commit()
    booking = client.post("/api/bookings", headers=headers, json={}).json()
    assert booking["status"] == BookingStatus.awaiting_payment

    settings = SimpleNamespace(
        stripe_enabled=True,
        stripe_secret_key="sk_test_checkout",
        stripe_price_id="price_test_checkout",
        resolved_stripe_success_url="https://example.test/success",
        resolved_stripe_cancel_url="https://example.test/cancel",
    )
    monkeypatch.setattr("app.api.payments._stripe_settings", lambda: settings)

    class FakeSession:
        id = "cs_test_checkout"
        url = "https://checkout.stripe.test/cs_test_checkout"

    def fake_create(**kwargs):
        assert kwargs["line_items"] == [{"price": "price_test_checkout", "quantity": 1}]
        assert kwargs["client_reference_id"] == str(booking["id"])
        return FakeSession()

    monkeypatch.setattr("app.api.payments.stripe.checkout.Session.create", fake_create)
    response = client.post(
        f"/api/payments/stripe/checkout/{booking['id']}", headers=headers
    )

    assert response.status_code == 200
    assert response.json() == {
        "url": "https://checkout.stripe.test/cs_test_checkout",
        "session_id": "cs_test_checkout",
    }


def test_stripe_status_is_disabled_without_production_config(client, ready_user):
    headers, *_ = ready_user()
    response = client.get("/api/payments/stripe/status", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"enabled": False}


def test_stripe_checkout_requires_configuration(client, ready_user, db):
    headers, *_ = ready_user()
    from app.models.execution_pass import ExecutionPass
    db.query(ExecutionPass).delete()
    db.commit()
    booking = client.post("/api/bookings", headers=headers, json={}).json()
    assert booking["status"] == BookingStatus.awaiting_payment

    response = client.post(
        f"/api/payments/stripe/checkout/{booking['id']}", headers=headers
    )
    assert response.status_code == 503


def test_stripe_payment_model_is_registered(db):
    assert db.query(Payment).count() == 0
    payment = Payment(
        user_id=1,
        provider=PaymentProvider.stripe,
        status=PaymentRecordStatus.created,
        amount=100,
        currency="cad",
    )
    # Only verify enum/model construction without committing a foreign-key row.
    assert payment.provider == PaymentProvider.stripe
    assert payment.status == PaymentRecordStatus.created


def test_paid_stripe_webhook_automatically_grants_entitlement(client, ready_user, db):
    headers, *_ = ready_user(email="stripe-payer@gmail.com")
    db.query(ExecutionPass).delete()
    db.commit()
    booking = client.post("/api/bookings", headers=headers, json={}).json()
    assert booking["status"] == BookingStatus.awaiting_payment

    _process_checkout_event(
        db,
        {
            "id": "evt_test_paid_1",
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "id": "cs_test_1",
                    "payment_status": "paid",
                    "payment_intent": "pi_test_1",
                    "amount_total": 1000,
                    "currency": "cad",
                    "metadata": {
                        "booking_id": str(booking["id"]),
                        "user_id": str(booking["user_id"]),
                    },
                }
            },
        },
    )

    db.expire_all()
    updated = db.get(Booking, booking["id"])
    assert updated.status == BookingStatus.pending
    assert updated.payment_status == PaymentStatus.approved
    payment = db.query(Payment).filter_by(provider_session_id="cs_test_1").one()
    assert payment.status == PaymentRecordStatus.paid
    execution_pass = db.query(ExecutionPass).filter_by(user_id=booking["user_id"]).one()
    assert execution_pass.status == ExecutionPassStatus.reserved
    assert execution_pass.booking_id == booking["id"]
