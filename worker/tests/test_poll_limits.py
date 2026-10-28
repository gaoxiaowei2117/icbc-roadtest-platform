from dataclasses import replace
from unittest.mock import Mock

import pytest
import road_adapter as adapter
from vendor import road
from tests.test_road_adapter import TASK


def test_three_consecutive_403_and_single_success_recovery():
    state = adapter._PollState()
    for _ in range(2):
        state.observe('access_limited', False)
    assert not state.limited
    state.observe('query_failed', False)
    assert state.consecutive_403 == 0
    for _ in range(3):
        state.observe('access_limited', False)
    assert state.limited
    state.observe('token_failed', False)
    assert state.limited
    state.observe('no_appointments', True)
    assert not state.limited


def test_intervals_survive_requeue_and_recover(monkeypatch):
    now = [0.0]
    monkeypatch.setattr(adapter.time, 'monotonic', lambda: now[0])
    monkeypatch.setattr(adapter.time, 'sleep', lambda seconds: now.__setitem__(0, now[0] + seconds))
    monkeypatch.setattr(adapter.random, 'uniform', lambda low, high: (low + high) / 2)
    monkeypatch.setattr(adapter.settings, 'booking_poll_min_seconds', 12)
    monkeypatch.setattr(adapter.settings, 'booking_poll_max_seconds', 20)
    monkeypatch.setattr(adapter.settings, 'booking_timeout_seconds', 100)
    monkeypatch.setattr(adapter, '_poll_states', {})
    monkeypatch.setattr(adapter, '_build_config', lambda task: {})
    monkeypatch.setattr(adapter, '_best_effort_restore', lambda config: None)
    calls = []
    outcomes = iter(['access_limited'] * 3 + ['query_failed', 'no_appointments', 'booking_success'])

    def job(config):
        calls.append(now[0])
        status = next(outcomes)
        config['_query_http_status'] = 200 if status in ('no_appointments', 'booking_success') else None
        return status

    monkeypatch.setattr(road, 'job', job)
    monkeypatch.setattr(road, 'load_booking_status', lambda config: None)
    task = replace(TASK, pos_ids=[1])
    assert adapter.run(task).retryable
    assert calls == [0, 16, 32]
    assert adapter.run(task).retryable
    assert calls == [0, 16, 32, 148]
    assert adapter.run(task).success
    assert calls == [0, 16, 32, 148, 264, 280]
    assert not adapter._poll_states


@pytest.mark.parametrize('login_code,query_code,expected', [
    (403, None, 'access_limited'),
    (200, 403, 'access_limited'),
    (200, 500, 'query_failed'),
    (200, 200, 'no_appointments'),
])
def test_real_job_classifies_http_outcomes(monkeypatch, login_code, query_code, expected):
    config = {'icbc': adapter._icbc_from_task(TASK, 1), 'autoBooking': {'enable': False}}
    monkeypatch.setattr(road, 'check_if_already_booked', lambda config: False)
    monkeypatch.setattr(road, 'generate_headers', lambda: {})
    monkeypatch.setattr(road, 'ensure_email_synced', lambda *args: None)
    monkeypatch.setattr(road, 'check_existing_appointments', lambda data: [])
    monkeypatch.setattr(road.requests, 'put', Mock(return_value=Mock(
        status_code=login_code, headers={'Authorization': 'test'}, json=lambda: {})))
    monkeypatch.setattr(road.requests, 'post', Mock(return_value=Mock(
        status_code=query_code, json=lambda: [])))
    assert road.job(config) == expected
    assert (config['_query_http_status'] == 200) == (query_code == 200)
