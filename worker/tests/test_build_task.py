from worker import build_task

RAW = {
    "booking_id": 7, "user_id": 3,
    "drvr_last_name": "GAO", "licence_number": "1234567",
    "keyword_ciphertext": "ignored-here",
    "exam_class": "5", "pos_ids": [1, 274],
    "expect_after_date": "2026-07-01", "expect_before_date": "2026-08-01",
    "expect_time_range": "10:00-17:00",
    "pref_days_of_week": [0, 1, 2], "pref_parts_of_day": [0, 1],
}


def test_build_task_maps_fields():
    task = build_task(RAW, keyword="my-keyword")
    assert task.booking_id == 7
    assert task.drvr_last_name == "GAO"
    assert task.licence_number == "1234567"
    assert task.keyword == "my-keyword"
    assert task.exam_class == "5"
    assert task.pos_ids == [1, 274]
    assert task.expect_after_date == "2026-07-01"
    assert task.pref_days_of_week == [0, 1, 2]
