"""AUTH-02: admin can extend allowlist by editing app_config row."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending — app_config seed not yet shipped")
def test_allowlist_extend(conn):
    raise NotImplementedError(
        "Wave 1: update app_config row, assert auth.is_allowed_domain returns true for new domain"
    )
