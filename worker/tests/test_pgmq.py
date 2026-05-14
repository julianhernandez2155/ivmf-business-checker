"""D-00-09: q_verify and q_aggregator queues exist in pgmq.meta."""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_queues_exist(conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            select queue_name from pgmq.meta
            where queue_name in ('q_verify', 'q_aggregator')
            """
        )
        names = {r[0] for r in cur.fetchall()}
    assert names == {"q_verify", "q_aggregator"}, f"queues missing: {names}"
