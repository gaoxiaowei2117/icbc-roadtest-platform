"""road_adapter 单测：全部 mock vendor.road，不触真实 ICBC。"""
from unittest.mock import patch

import road_adapter
from booking_engine import Task

TASK = Task(
    booking_id=1, user_id=1, target_date="2026-07-01", time_window=None,
    pos_code=None, icbc_username="u", icbc_password="p", max_wait_days=60,
)


def _cfg():
    return {"emailReplace": {"enable": False}}


def test_booking_success_maps_to_result():
    status = {"appointment": {"date": "2026-07-15", "time": "10:30", "dayOfWeek": "Tue"}}
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=status):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert result.booked_at == "2026-07-15 10:30"
    assert result.details["job_status"] == "booking_success"


def test_already_booked_is_success():
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", return_value="already_booked"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert result.booked_at is None


def test_timeout_returns_failure(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 0.2)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.05)
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", return_value="no_appointments"):
        result = road_adapter.run(TASK)
    assert result.success is False
    assert "时限" in result.error


def test_loops_until_success(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    seq = ["no_appointments", "token_failed", "booking_success"]
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", side_effect=seq) as job_mock, \
         patch.object(road_adapter.road, "load_booking_status", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert job_mock.call_count == 3
