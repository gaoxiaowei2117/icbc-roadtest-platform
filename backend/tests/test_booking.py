"""建任务的前置校验、列表、取消，以及 claim 原子认领。"""
import pytest
from sqlalchemy.exc import IntegrityError

from app.crud import booking as booking_crud
from app.models.booking import Booking, BookingStatus
from tests.conftest import WORKER_HEADERS


def test_create_requires_full_profile(client, auth_headers):
    """只注册、没填档案 → 400，提示补全。"""
    h = auth_headers()
    r = client.post("/api/bookings", headers=h, json={})
    assert r.status_code == 400
    assert "补全" in r.json()["detail"]


def test_create_and_list(client, ready_user):
    h, *_ = ready_user()
    r = client.post("/api/bookings", headers=h, json={})
    assert r.status_code == 201
    bid = r.json()["id"]
    listing = client.get("/api/bookings", headers=h).json()
    assert any(b["id"] == bid for b in listing)


def test_only_one_active_booking(client, ready_user):
    """同账户同时只能有一个进行中任务（pending/running）。"""
    h, *_ = ready_user()
    assert client.post("/api/bookings", headers=h, json={}).status_code == 201
    r2 = client.post("/api/bookings", headers=h, json={})
    assert r2.status_code == 409
    assert "进行中" in r2.json()["detail"]


def test_can_create_after_cancel(client, ready_user):
    """取消后可以再建新任务。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    client.post(f"/api/bookings/{bid}/cancel", headers=h)
    assert client.post("/api/bookings", headers=h, json={}).status_code == 201


def test_cancel(client, ready_user, db):
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    r = client.post(f"/api/bookings/{bid}/cancel", headers=h)
    assert r.status_code == 200
    db.expire_all()
    assert db.get(Booking, bid).status == BookingStatus.cancelled


def test_user_only_sees_own_bookings(client, ready_user):
    h1, *_ = ready_user(email="u1@gmail.com")
    client.post("/api/bookings", headers=h1, json={})
    h2, *_ = ready_user(email="u2@gmail.com")
    assert client.get("/api/bookings", headers=h2).json() == []


def test_db_unique_index_blocks_second_active(client, ready_user, db):
    """部分唯一索引兜底：绕过 has_active 直接建第二个进行中任务会被 DB 拒绝（防 TOCTOU 竞态）。"""
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={}).json()["id"]
    uid = db.get(Booking, bid).user_id
    with pytest.raises(IntegrityError):
        booking_crud.create(db, uid)  # 第二个 pending 撞 uq_booking_one_active_per_user
    db.rollback()


def test_claim_is_atomic_single_winner(client, ready_user, db):
    """两次 claim：第一次拿到任务，第二次拿到空（任务已被认领）。"""
    h, *_ = ready_user()
    client.post("/api/bookings", headers=h, json={})
    first = client.post("/api/worker/claim", headers=WORKER_HEADERS).json()
    second = client.post("/api/worker/claim", headers=WORKER_HEADERS).json()
    assert first is not None
    assert second is None
