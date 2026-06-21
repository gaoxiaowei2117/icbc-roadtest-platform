"""road_adapter 单测：全部 mock vendor.road，不触真实 ICBC。"""
from unittest.mock import patch

import road_adapter
from booking_engine import Task

TASK = Task(
    booking_id=1, user_id=1, drvr_last_name="GAO", licence_number="1234567",
    keyword="kw", exam_class="5", pos_ids=[1, 274],
    expect_after_date="2026-07-01", expect_before_date="2026-08-01",
    expect_time_range="10:00-17:00", pref_days_of_week=[0, 1, 2], pref_parts_of_day=[0, 1],
)


def _base():
    return {"gmail": {}, "autoBooking": {}, "emailReplace": {"enable": True}}


def test_build_config_injects_icbc_and_gmail(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "gmail_email", "sys@gmail.com")
    monkeypatch.setattr(road_adapter.settings, "gmail_app_password", "applekey")
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 0.2)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.05)
    captured = {}
    def fake_job(cfg):
        captured["cfg"] = {**cfg, "icbc": dict(cfg["icbc"])}
        return "no_appointments"
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", side_effect=fake_job), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        road_adapter.run(TASK)
    cfg = captured["cfg"]
    assert cfg["gmail"]["email"] == "sys@gmail.com"
    assert cfg["gmail"]["password"] == "applekey"
    assert cfg["autoBooking"]["enable"] is True
    assert cfg["icbc"]["drvrLastName"] == "GAO"
    assert cfg["icbc"]["keyword"] == "kw"
    assert cfg["icbc"]["examClass"] == "5"
    assert cfg["icbc"]["prfDaysOfWeek"] == "[0,1,2]"
    assert cfg["icbc"]["expactTimeRange"] == "10:00-17:00"


def test_dry_run_disables_booking_and_email_replace(monkeypatch):
    """dry_run=True：autoBooking 与 emailReplace 都关，只查号不下单不改邮箱。"""
    monkeypatch.setattr(road_adapter.settings, "dry_run", True)
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 0.2)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.05)
    captured = {}
    def fake_job(cfg):
        captured["cfg"] = {**cfg}
        return "no_appointments"
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", side_effect=fake_job), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        road_adapter.run(TASK)
    assert captured["cfg"]["autoBooking"]["enable"] is False
    assert captured["cfg"]["emailReplace"]["enable"] is False


def test_success_maps_result(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    status = {"appointment": {"date": "2026-07-15", "time": "10:30", "dayOfWeek": "Tue"}}
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=status), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert result.booked_at == "2026-07-15 10:30"


def test_multi_pos_polling(monkeypatch):
    """第一个 posID 没号、第二个成交。"""
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    seen_pos = []
    def fake_job(cfg):
        pos = cfg["icbc"]["posID"]
        seen_pos.append(pos)
        return "booking_success" if pos == 274 else "no_appointments"
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", side_effect=fake_job), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True
    assert seen_pos == [1, 274]


def test_reports_progress_after_each_job(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    messages = []
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        road_adapter.run(TASK, on_progress=messages.append)
    assert messages == ["考点 1 查询结果 booking_success"]


def test_timeout_returns_failure(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 0.2)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.05)
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", return_value="no_appointments"), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is False
    assert "时限" in result.error


def test_job_exception_is_retried(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    seq = [ConnectionError("boom"), "booking_success"]
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", side_effect=seq), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "get_weblogin", return_value=None):
        result = road_adapter.run(TASK)
    assert result.success is True


def test_finally_restores_email_when_enabled(monkeypatch):
    monkeypatch.setattr(road_adapter.settings, "booking_timeout_seconds", 5)
    monkeypatch.setattr(road_adapter.settings, "booking_poll_seconds", 0.01)
    class _Resp:
        headers = {"Authorization": "tok"}
        def json(self):
            return {"email": "replaced@gmail.com"}
    with patch.object(road_adapter.road, "load_config", return_value=_base()), \
         patch.object(road_adapter.road, "job", return_value="booking_success"), \
         patch.object(road_adapter.road, "load_booking_status", return_value=None), \
         patch.object(road_adapter.road, "get_weblogin", return_value=_Resp()), \
         patch.object(road_adapter.road, "restore_original_email") as restore_mock:
        road_adapter.run(TASK)
    restore_mock.assert_called_once()
