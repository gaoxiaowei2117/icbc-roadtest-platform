"""建任务的前置校验、列表、取消，以及 claim 原子认领。"""
from app.models.booking import Booking, BookingStatus
from tests.conftest import WORKER_HEADERS


def test_create_requires_profile(client, auth_headers):
    """没填驾照/姓氏 → 400。"""
    r = client.post("/api/bookings", headers=auth_headers(), json={"target_date": "2026-07-01"})
    assert r.status_code == 400


def test_create_requires_secret(client, auth_headers):
    """填了资料但没设凭据 → 400。"""
    h = auth_headers()
    client.patch("/api/users/me", headers=h,
                 json={"icbc_license_no": "1234567", "icbc_last_name": "GAO"})
    r = client.post("/api/bookings", headers=h, json={"target_date": "2026-07-01"})
    assert r.status_code == 400


def test_create_and_list(client, ready_user):
    h, *_ = ready_user()
    r = client.post("/api/bookings", headers=h,
                    json={"target_date": "2026-07-01", "pos_code": "VAN"})
    assert r.status_code == 201
    bid = r.json()["id"]
    listing = client.get("/api/bookings", headers=h).json()
    assert any(b["id"] == bid for b in listing)


def test_cancel(client, ready_user, db):
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={"target_date": "2026-07-01"}).json()["id"]
    r = client.post(f"/api/bookings/{bid}/cancel", headers=h)
    assert r.status_code == 200
    db.expire_all()
    assert db.get(Booking, bid).status == BookingStatus.cancelled


def test_user_only_sees_own_bookings(client, ready_user):
    h1, *_ = ready_user(email="u1@gmail.com")
    client.post("/api/bookings", headers=h1, json={"target_date": "2026-07-01"})
    h2, *_ = ready_user(email="u2@gmail.com")
    assert client.get("/api/bookings", headers=h2).json() == []


def test_claim_is_atomic_single_winner(client, ready_user, db):
    """两次 claim：第一次拿到任务，第二次拿到空（任务已被认领）。"""
    h, *_ = ready_user()
    client.post("/api/bookings", headers=h, json={"target_date": "2026-07-01"})
    first = client.post("/api/worker/claim", headers=WORKER_HEADERS).json()
    second = client.post("/api/worker/claim", headers=WORKER_HEADERS).json()
    assert first is not None
    assert second is None
