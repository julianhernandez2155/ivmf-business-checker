"""D-00-11 item 5: worker_heartbeats row written by worker."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 4 pending — worker not yet running")
def test_heartbeat_row_within_30s(conn):
    raise NotImplementedError(
        "Wave 4: query worker_heartbeats for row with last_seen_at within 30s of NOW()"
    )
