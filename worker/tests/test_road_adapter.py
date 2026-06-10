"""road_adapter 单测：全部 mock vendor.road，不触真实 ICBC。"""
from unittest.mock import patch

import pytest

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


class _Resp:
    headers = {"Authorization": "tok"}
    def json(self):
        return {"email": "replaced@gmail.com"}


def test_finally_restores_email_when_enabled():
    cfg = {"emailReplace": {"enable": True}}
    with patch.object(road_adapter.road, "load_config", return_value=cfg), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "get_weblogin", return_value=_Resp()), \
         patch.object(road_adapter.road, "restore_original_email") as restore_mock:
        road_adapter.run(TASK)
    restore_mock.assert_called_once()


def test_no_restore_when_disabled():
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "restore_original_email") as restore_mock:
        road_adapter.run(TASK)
    restore_mock.assert_not_called()


def test_config_load_failure_propagates():
    """config 加载失败时清晰报错（异常上传给 worker 上报 failed）。"""
    with patch.object(road_adapter.road, "load_config",
                      side_effect=FileNotFoundError("config.yml 不存在")):
        with pytest.raises(FileNotFoundError):
            road_adapter.run(TASK)


def test_job_exception_is_retried(monkeypatch):
    """单轮 job() 抛异常不应中断循环，下一轮成功仍能成交。"""
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    seq = [ConnectionError("boom"), "booking_success"]
    with patch.object(road_adapter.road, "load_config", return_value=_cfg()), \
         patch.object(road_adapter.road, "job", side_effect=seq) as job_mock, \
         patch.object(road_adapter.road, "load_booking_status", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert job_mock.call_count == 2
