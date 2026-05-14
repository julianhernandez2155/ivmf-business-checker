"""AUTH-03: auth.is_allowed_domain RLS function exists and blocks non-allowlisted."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 3 pending — RLS function not yet defined")
def test_is_allowed_domain_function_exists(conn):
    with conn.cursor() as cur:
        cur.execute(
            "select 1 from pg_proc "
            "where proname='is_allowed_domain' and pronamespace='auth'::regnamespace"
        )
        assert cur.fetchone() is not None, "auth.is_allowed_domain missing"
    raise NotImplementedError(
        "Wave 3: assert function returns true for @syr.edu and false for @gmail.com"
    )
