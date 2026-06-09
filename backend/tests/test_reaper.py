"""T2：卡死任务 reaper —— 超时 running 重置为 pending，新鲜 running 不动。"""
from datetime import datetime, timedelta, timezone

from app.crud import booking as booking_crud
from app.models.booking import Booking, BookingStatus
from tests.conftest import WORKER_HEADERS


def _make_running(client, ready_user, db, started_at):
    h, *_ = ready_user()
    bid = client.post("/api/bookings", headers=h, json={"target_date": "2026-07-01"}).json()["id"]
    client.post("/api/worker/claim", headers=WORKER_HEADERS)  # → running
    booking = db.get(Booking, bid)
    booking.started_at = started_at
    db.commit()
    return bid


def test_stale_running_reset(client, ready_user, db):
    bid = _make_running(client, ready_user, db,
                        datetime.now(timezone.utc) - timedelta(hours=2))
    n = booking_crud.reset_stale_running(db, timeout_minutes=15)
    assert n == 1
    db.expire_all()
    booking = db.get(Booking, bid)
    assert booking.status == BookingStatus.pending
    assert booking.started_at is None
    assert "超时" in booking.last_error


def test_fresh_running_not_reset(client, ready_user, db):
    bid = _make_running(client, ready_user, db, datetime.now(timezone.utc))
    n = booking_crud.reset_stale_running(db, timeout_minutes=15)
    assert n == 0
    db.expire_all()
    assert db.get(Booking, bid).status == BookingStatus.running


def test_reaper_ignores_non_running(client, ready_user, db):
    """pending / done 任务不受 reaper 影响。"""
    h, *_ = ready_user()
    client.post("/api/bookings", headers=h, json={"target_date": "2026-07-01"})  # pending
    n = booking_crud.reset_stale_running(db, timeout_minutes=0)
    assert n == 0
