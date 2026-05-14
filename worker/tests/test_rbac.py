"""AUTH-03: app_metadata.role claims propagate through middleware AND RLS."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 3 pending — RBAC policies not yet shipped")
def test_role_in_jwt():
    raise NotImplementedError(
        "Wave 3: mint a token with app_metadata.role='admin'; assert RLS policy admits"
    )
