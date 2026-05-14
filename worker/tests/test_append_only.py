"""CANON-06: verifications BEFORE UPDATE/DELETE triggers + UNIQUE constraint."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending — append-only triggers not yet installed")
def test_update_raises_p0001(conn):
    import psycopg

    with conn.cursor() as cur:
        with pytest.raises(psycopg.errors.RaiseException):
            cur.execute(
                "update verifications set status='active' where id = gen_random_uuid()"
            )
    raise NotImplementedError(
        "Wave 1: insert a real verifications row first, then assert UPDATE raises P0001"
    )


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending")
def test_delete_raises_p0001(conn):
    raise NotImplementedError("Wave 1: assert DELETE raises P0001")


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending")
def test_unique_violation_run_row_pass(conn):
    raise NotImplementedError(
        "Wave 1: assert duplicate (run_id, row_index, pass) raises 23505"
    )
