from unittest.mock import patch

import booking_engine
from booking_engine import Result, Task

TASK = Task(
    booking_id=9, user_id=1, drvr_last_name="GAO", licence_number="1234567",
    keyword="kw", exam_class="5", pos_ids=[1],
    expect_after_date="2026-07-01", expect_before_date="2026-08-01",
    expect_time_range="10:00-17:00", pref_days_of_week=[0], pref_parts_of_day=[0],
)


def test_run_delegates_to_adapter():
    fake = Result(success=True, confirmation_no="2026-07-15")
    with patch("road_adapter.run", return_value=fake) as adapter:
        out = booking_engine.run(TASK)
    adapter.assert_called_once_with(TASK)
    assert out is fake
