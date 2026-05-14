"""D-00-09: q_verify and q_aggregator queues exist."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending — pgmq queues not yet created")
def test_queues_exist(conn):
    with conn.cursor() as cur:
        cur.execute(
            "select queue_name from pgmq.meta "
            "where queue_name in ('q_verify','q_aggregator')"
        )
        names = {r[0] for r in cur.fetchall()}
        assert names == {"q_verify", "q_aggregator"}
    raise NotImplementedError(
        "Wave 4: verify worker long-poll uses vt=300 at call site"
    )
