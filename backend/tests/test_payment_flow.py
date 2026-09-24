"""付款审核与一次性执行权限的业务不变量。"""
from app.models.booking import Booking, BookingStatus, PaymentStatus
from app.models.execution_pass import ExecutionPass, ExecutionPassStatus
from app.models.user import User
from tests.conftest import WORKER_HEADERS


def _remove_pass(db, email: str) -> int:
    user = db.query(User).filter_by(email=email).one()
    db.query(ExecutionPass).filter_by(user_id=user.id).delete()
    db.commit()
    return user.id


def _make_admin(client, auth_headers, db):
    headers = auth_headers(email="super-admin@gmail.com")
    admin = db.query(User).filter_by(email="super-admin@gmail.com").one()
    admin.is_admin = True
    db.commit()
    return headers


def test_without_pass_task_waits_for_payment(client, ready_user, db):
    user_headers, _, _ = ready_user(email="payer@gmail.com")
    user_id = _remove_pass(db, "payer@gmail.com")

    response = client.post("/api/bookings", headers=user_headers, json={})

    assert response.status_code == 201
    assert response.json()["status"] == BookingStatus.awaiting_payment
    assert response.json()["payment_status"] == PaymentStatus.awaiting_payment
    assert client.get("/api/users/me/credits", headers=user_headers).json() == {"available": 0}
    assert db.query(Booking).filter_by(user_id=user_id).one().status == BookingStatus.awaiting_payment


def test_payment_review_approval_grants_one_execution_pass(client, ready_user, auth_headers, db):
    user_headers, _, _ = ready_user(email="payer@gmail.com")
    _remove_pass(db, "payer@gmail.com")
    admin_headers = _make_admin(client, auth_headers, db)

    booking = client.post("/api/bookings", headers=user_headers, json={}).json()
    bid = booking["id"]
    assert client.post(
        f"/api/bookings/{bid}/payment-submitted",
        headers=user_headers,
        json={"payment_reference": "etransfer-123"},
    ).json()["status"] == BookingStatus.awaiting_review
    assert client.get(
        "/api/admin/bookings?status_filter=awaiting_review", headers=admin_headers
    ).json()[0]["payment_reference"] == "etransfer-123"

    approved = client.post(
        f"/api/admin/bookings/{bid}/approve-payment", headers=admin_headers
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == BookingStatus.pending
    assert approved.json()["payment_status"] == PaymentStatus.approved
    assert client.post("/api/worker/claim", headers=WORKER_HEADERS).json()["booking_id"] == bid


def test_payment_reference_is_required(client, ready_user, db):
    user_headers, _, _ = ready_user(email="payer@gmail.com")
    _remove_pass(db, "payer@gmail.com")
    bid = client.post("/api/bookings", headers=user_headers, json={}).json()["id"]

    assert client.post(
        f"/api/bookings/{bid}/payment-submitted", headers=user_headers, json={}
    ).status_code == 422
    assert client.post(
        f"/api/bookings/{bid}/payment-submitted",
        headers=user_headers,
        json={"payment_reference": "   "},
    ).status_code == 422
    response = client.post(
        f"/api/bookings/{bid}/payment-submitted",
        headers=user_headers,
        json={"payment_reference": "etransfer-456"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == BookingStatus.awaiting_review


def test_awaiting_review_cannot_be_cancelled(client, ready_user, db):
    user_headers, _, _ = ready_user(email="payer@gmail.com")
    _remove_pass(db, "payer@gmail.com")
    bid = client.post("/api/bookings", headers=user_headers, json={}).json()["id"]
    client.post(
        f"/api/bookings/{bid}/payment-submitted",
        headers=user_headers,
        json={"payment_reference": "paid-123"},
    )

    response = client.post(f"/api/bookings/{bid}/cancel", headers=user_headers)

    assert response.status_code == 409
    assert "审核完成后" in response.json()["detail"]
    db.expire_all()
    assert db.get(Booking, bid).status == BookingStatus.awaiting_review


def test_admin_approval_of_legacy_cancelled_payment_grants_available_pass(
    client, ready_user, auth_headers, db
):
    user_headers, _, _ = ready_user(email="payer@gmail.com")
    user_id = _remove_pass(db, "payer@gmail.com")
    admin_headers = _make_admin(client, auth_headers, db)
    bid = client.post("/api/bookings", headers=user_headers, json={}).json()["id"]
    client.post(
        f"/api/bookings/{bid}/payment-submitted",
        headers=user_headers,
        json={"payment_reference": "legacy-paid-123"},
    )
    # Reproduce records created before cancellation of awaiting_review was blocked.
    legacy_booking = db.get(Booking, bid)
    legacy_booking.status = BookingStatus.cancelled
    db.commit()

    response = client.post(
        f"/api/admin/bookings/{bid}/approve-payment", headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == BookingStatus.cancelled
    assert response.json()["payment_status"] == PaymentStatus.approved
    db.expire_all()
    execution_pass = db.query(ExecutionPass).filter_by(user_id=user_id).one()
    assert execution_pass.status == ExecutionPassStatus.available
    assert execution_pass.booking_id is None
    # The next task consumes the user-level pass and does not ask for payment again.
    next_booking = client.post("/api/bookings", headers=user_headers, json={}).json()
    assert next_booking["status"] == BookingStatus.pending
    assert next_booking["payment_status"] == PaymentStatus.approved


def test_cancel_releases_pass_and_success_consumes_it(client, ready_user, db):
    user_headers, _, _ = ready_user(email="payer@gmail.com")
    user_id = db.query(User).filter_by(email="payer@gmail.com").one().id

    first = client.post("/api/bookings", headers=user_headers, json={}).json()
    client.post(f"/api/bookings/{first['id']}/cancel", headers=user_headers)
    assert client.get("/api/users/me/credits", headers=user_headers).json() == {"available": 1}

    second = client.post("/api/bookings", headers=user_headers, json={}).json()
    assert second["status"] == BookingStatus.pending
    claim = client.post("/api/worker/claim", headers=WORKER_HEADERS).json()
    client.post(
        f"/api/worker/bookings/{second['id']}/result",
        headers=WORKER_HEADERS,
        json={"attempt": claim["attempt"], "status": "done", "result": {"ok": True}},
    )
    db.expire_all()
    execution_pass = db.query(ExecutionPass).filter_by(user_id=user_id).one()
    assert execution_pass.status == ExecutionPassStatus.consumed
    assert client.get("/api/users/me/credits", headers=user_headers).json() == {"available": 0}

    third = client.post("/api/bookings", headers=user_headers, json={}).json()
    assert third["status"] == BookingStatus.awaiting_payment


def test_admin_can_reject_payment(client, ready_user, auth_headers, db):
    user_headers, _, _ = ready_user(email="payer@gmail.com")
    _remove_pass(db, "payer@gmail.com")
    admin_headers = _make_admin(client, auth_headers, db)
    bid = client.post("/api/bookings", headers=user_headers, json={}).json()["id"]
    client.post(
        f"/api/bookings/{bid}/payment-submitted",
        headers=user_headers,
        json={"payment_reference": "etransfer-reject"},
    )

    response = client.post(
        f"/api/admin/bookings/{bid}/reject-payment",
        headers=admin_headers,
        json={"reason": "未查到付款记录"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == BookingStatus.payment_rejected
    assert response.json()["review_reason"] == "未查到付款记录"
