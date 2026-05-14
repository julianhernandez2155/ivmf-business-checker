"""CANON-08: verifications has provenance jsonb, method text NOT NULL, match_signals jsonb."""
import pytest


@pytest.mark.integration
@pytest.mark.xfail(strict=False, reason="Wave 1 pending")
def test_verifications_columns(conn):
    raise NotImplementedError(
        "Wave 1: introspect information_schema.columns for verifications; assert column set"
    )
