import json
import logging
from datetime import datetime
from unittest.mock import Mock

import pytest
from vendor import road
from worker import VancouverFormatter


@pytest.mark.parametrize('utc_time,local_date,offset', [
    ('2026-09-29T01:00:00+00:00', '2026-09-28', '-07:00'),
    ('2025-12-29T02:00:00+00:00', '2025-12-28', '-08:00'),
    ('2026-12-29T01:00:00+00:00', '2026-12-28', '-07:00'),
])
def test_business_date_and_window_ignore_host_timezone(monkeypatch, utc_time, local_date, offset):
    instant = datetime.fromisoformat(utc_time)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return instant.astimezone(tz) if tz else instant.replace(tzinfo=None)

    monkeypatch.setattr(road, 'datetime', Clock)
    post = Mock(return_value=Mock(status_code=200, json=lambda: []))
    monkeypatch.setattr(road.requests, 'post', post)
    monkeypatch.setattr(road, 'generate_headers', lambda: {})
    config = {'icbc': {'posID': 11, 'examClass': '5', 'prfDaysOfWeek': '[]',
                       'prfPartsOfDay': '[]', 'drvrLastName': 'test', 'licenceNumber': 'test'},
              'autoBooking': {'bookingTimeWindow': '17:00-19:00'}}
    road.get_appointments(config, 'test')
    assert json.loads(post.call_args.kwargs['data'])['examDate'] == local_date
    assert road.is_within_booking_time_window(config)
    record = logging.LogRecord('test', logging.INFO, '', 0, 'test', (), None)
    record.created = instant.timestamp()
    assert VancouverFormatter().formatTime(record) == local_date + 'T18:00:00.000' + offset
