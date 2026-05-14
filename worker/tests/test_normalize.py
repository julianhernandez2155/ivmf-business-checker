"""CANON-03 unit tests for normalize helpers."""
from __future__ import annotations

import pytest

from workers.lib.normalize import (
    normalize_address,
    normalize_domain,
    normalize_name,
    normalize_phone,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Acme Corp, LLC", "acme corp"),
        ("Acme Corp.", "acme corp"),
        ("ACME CORPORATION", "acme"),
        ("  Café  Resto  ", "café resto"),
        ("", ""),
    ],
)
def test_normalize_name(raw: str, expected: str) -> None:
    assert normalize_name(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("https://www.example.com/path", "example.com"),
        ("HTTP://Sub.Example.COM", "sub.example.com"),
        ("example.com/foo", "example.com"),
        ("", ""),
    ],
)
def test_normalize_domain(raw: str, expected: str) -> None:
    assert normalize_domain(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("(315) 443-1234", "+13154431234"),
        ("315.443.1234", "+13154431234"),
        ("1-315-443-1234", "+13154431234"),
        ("+13154431234", "+13154431234"),
    ],
)
def test_normalize_phone_e164(raw: str, expected: str) -> None:
    assert normalize_phone(raw) == expected


def test_normalize_phone_invalid_returns_none() -> None:
    assert normalize_phone("invalid") is None
    assert normalize_phone("") is None


def test_normalize_address_basic() -> None:
    result = normalize_address("123 Main St, Syracuse, NY 13210")
    assert result["street_address"] == "123 Main St"
    assert result["city"] == "Syracuse"
    assert result["state"] == "NY"
    assert result["zip"] == "13210"


def test_normalize_address_empty() -> None:
    assert normalize_address("") == {}
