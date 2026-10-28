import pytest

import road_adapter


@pytest.fixture(autouse=True)
def _reset_poll_states():
    # road_adapter keeps per-booking poll state across requeues; tests share
    # booking IDs, so clear it to keep tests independent of run order.
    road_adapter._poll_states.clear()
    yield
    road_adapter._poll_states.clear()
