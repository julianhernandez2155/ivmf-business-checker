"""AUTH-04 / D-00-06: audit_log row with before/after diff on admin write.

UPDATE app_config and assert the latest audit_log row has non-null diff jsonb
containing the changed column name as a key.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_app_config_update_writes_diff(conn, _role_guard):
    with conn.cursor() as cur:
        cur.execute(
            """
            update public.app_config
            set description = 'test-update-' || extract(epoch from now())::text
            where key = 'email_domain_allowlist'
            returning updated_at
            """
        )
        conn.commit()
        cur.execute(
            """
            select diff, before, after
            from public.audit_log
            where table_name = 'app_config' and action = 'UPDATE'
            order by created_at desc limit 1
            """
        )
        row = cur.fetchone()
    assert row is not None, "no audit_log row after UPDATE"
    diff, before, after = row
    assert diff is not None, "diff jsonb is null"
    assert "description" in diff, f"diff missing changed key: {diff}"
    assert before is not None
    assert after is not None
