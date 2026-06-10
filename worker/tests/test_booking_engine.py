from unittest.mock import patch

import booking_engine
from booking_engine import Result, Task

TASK = Task(
    booking_id=9, user_id=1, target_date=None, time_window=None,
    pos_code=None, icbc_username="u", icbc_password="p", max_wait_days=60,
)


def test_run_delegates_to_adapter():
    fake = Result(success=True, confirmation_no="2026-07-15")
    with patch("road_adapter.run", return_value=fake) as adapter:
        out = booking_engine.run(TASK)
    adapter.assert_called_once_with(TASK)
    assert out is fake
