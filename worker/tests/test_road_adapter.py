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
