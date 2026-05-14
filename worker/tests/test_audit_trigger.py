"""AUTH-04: audit_log row with before/after diff on admin write."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending — audit_log_trigger not yet installed")
def test_app_config_update_writes_diff(conn):
    raise NotImplementedError(
        "Wave 1: update app_config, assert audit_log row with non-null diff jsonb"
    )
