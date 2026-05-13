"""Tests for the frozen pipeline configurations.

These assertions are intentionally rigid: they exist to detect silent
config drift, not to validate a "reasonable" config. If someone changes
`v11.use_marketplace_residue` to True (re-introducing the iter 12 leak),
the test must fail loudly — that's the whole point of the file.
"""

from __future__ import annotations

import pytest

from tools.pipeline_configs import (
    PIPELINE_NAMES,
    PIPELINE_REGISTRY,
    PipelineConfig,
    V10,
    V11,
    V12_CURRENT_PROD,
    V12_FULL,
    get_pipeline_config,
)


class TestRegistry:
    def test_registry_contains_expected_configs(self):
        # iter 13: v10 / v11 / v12_current_prod / v12_full.
        # iter 14 spike: + v14_branch_a1 / v14_branch_a2.
        # Guard against accidental additions creeping in without an explicit ADR.
        assert set(PIPELINE_NAMES) == {
            "v10",
            "v11",
            "v12_current_prod",
            "v12_full",
            "v14_branch_a1",
            "v14_branch_a2",
        }
        assert len(PIPELINE_REGISTRY) == 6

    def test_lookup_by_name(self):
        assert get_pipeline_config("v11") is V11
        assert get_pipeline_config("v10") is V10

    def test_lookup_unknown_raises(self):
        with pytest.raises(KeyError, match="Unknown pipeline"):
            get_pipeline_config("v99_imaginary")

    def test_configs_are_frozen(self):
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError
            V11.use_facebook_recency = False  # type: ignore[misc]


class TestCanonicalValues:
    """The exact toggle truth for each named pipeline.

    Drifting any of these without a corresponding ADR is exactly the
    iter-12 leak this whole iteration exists to prevent.
    """

    def test_v10_baseline(self):
        assert V10.use_facebook_recency is False
        assert V10.use_instagram_fallback is False
        assert V10.use_metadata is False
        assert V10.use_marketplace_residue is False
        assert V10.use_rule_scorer is True
        assert V10.verify_flagged is True

    def test_v11_documented_shippable(self):
        """v11 = iter 10 + Facebook recency, nothing else.

        Metadata and marketplace-residue MUST be off — otherwise this
        is no longer "v11" but a relabeled iter-12 partial bundle.
        """
        assert V11.use_facebook_recency is True
        assert V11.use_instagram_fallback is False
        assert V11.use_metadata is False
        assert V11.use_marketplace_residue is False
        assert V11.use_rule_scorer is True
        assert V11.verify_flagged is True

    def test_v12_current_prod_exposes_leak(self):
        """v12_current_prod must reflect what production has actually
        been doing since iter 12: metadata + marketplace-residue on,
        FB / IG still off (no flag plumbed those through)."""
        assert V12_CURRENT_PROD.use_facebook_recency is False
        assert V12_CURRENT_PROD.use_instagram_fallback is False
        assert V12_CURRENT_PROD.use_metadata is True
        assert V12_CURRENT_PROD.use_marketplace_residue is True

    def test_v12_full_everything_on(self):
        assert V12_FULL.use_facebook_recency is True
        assert V12_FULL.use_instagram_fallback is True
        assert V12_FULL.use_metadata is True
        assert V12_FULL.use_marketplace_residue is True


class TestFingerprint:
    def test_fingerprint_is_short_and_hex(self):
        fp = V11.fingerprint()
        assert isinstance(fp, str)
        assert len(fp) == 12
        assert all(c in "0123456789abcdef" for c in fp)

    def test_fingerprint_is_stable_across_calls(self):
        assert V11.fingerprint() == V11.fingerprint()

    def test_fingerprint_differs_between_configs(self):
        fps = {c.fingerprint() for c in PIPELINE_REGISTRY.values()}
        # All four configs differ in at least one boolean → all four
        # fingerprints must be unique. If two collide the cache key
        # would namespace them together, defeating Phase A step 2.
        assert len(fps) == 4

    def test_fingerprint_changes_when_a_field_changes(self):
        a = PipelineConfig(
            name="probe",
            use_facebook_recency=False,
            use_instagram_fallback=False,
            use_metadata=False,
            use_marketplace_residue=False,
            use_rule_scorer=True,
            verify_flagged=True,
        )
        b = PipelineConfig(
            name="probe",  # same name — fingerprint ignores name
            use_facebook_recency=True,  # the only difference
            use_instagram_fallback=False,
            use_metadata=False,
            use_marketplace_residue=False,
            use_rule_scorer=True,
            verify_flagged=True,
        )
        assert a.fingerprint() != b.fingerprint()

    def test_fingerprint_ignores_name(self):
        a = PipelineConfig(
            name="alpha",
            use_facebook_recency=True,
            use_instagram_fallback=False,
            use_metadata=False,
            use_marketplace_residue=False,
            use_rule_scorer=True,
            verify_flagged=True,
        )
        b = PipelineConfig(
            name="beta",  # name differs but every toggle matches
            use_facebook_recency=True,
            use_instagram_fallback=False,
            use_metadata=False,
            use_marketplace_residue=False,
            use_rule_scorer=True,
            verify_flagged=True,
        )
        assert a.fingerprint() == b.fingerprint()


class TestLogDict:
    def test_as_log_dict_contains_name_and_fingerprint(self):
        d = V11.as_log_dict()
        assert d["name"] == "v11"
        assert d["fingerprint"] == V11.fingerprint()
        assert d["use_facebook_recency"] is True
        assert d["use_marketplace_residue"] is False
