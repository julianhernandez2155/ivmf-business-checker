"""CANON-03: normalize helpers for name/domain/phone/address."""
import pytest


@pytest.mark.xfail(strict=False, reason="Wave 1 pending — normalize helpers not yet shipped")
def test_normalize_name_strips_suffix():
    raise NotImplementedError(
        "Wave 1: assert normalize_name('Acme Corp, LLC') == 'acme corp'"
    )


@pytest.mark.xfail(strict=False, reason="Wave 1 pending")
def test_normalize_phone_e164():
    raise NotImplementedError(
        "Wave 1: assert normalize_phone('(315) 443-1234') == '+13154431234'"
    )


@pytest.mark.xfail(strict=False, reason="Wave 1 pending")
def test_normalize_domain_strips_scheme_and_www():
    raise NotImplementedError(
        "Wave 1: assert normalize_domain('https://www.Example.COM/path') == 'example.com'"
    )
