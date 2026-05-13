"""Frozen pipeline configurations for the Business Checker.

A `PipelineConfig` is the single source of truth for which signals,
overrides, and verification steps a run uses. Both `run_checker.py`
(production) and `eval/rerun_sample.py` (eval) consume the same config
objects via the `--pipeline` flag, so eval and prod cannot silently diverge.

Why this exists (iter 13 reproducibility fix): prior to iter 13, the
production runner shipped with metadata-injection and marketplace-residue
overrides silently turned on while the eval rerunner had its own toggles
for FB recency / IG fallback. Different code paths meant the "iter 11
shippable command" in `EVAL_BASELINES.md` could not be reproduced. The
frozen configs below pin every toggle so a single `--pipeline v11` invocation
reproduces the documented iter 11 numbers (within Perplexity-drift band).

Canonical configs:
    v10                  — pre-FB-recency tiered baseline (iter 10).
    v11                  — iter 10 + Facebook recency. The documented shippable.
    v12_current_prod     — what production has been silently doing since iter 12:
                           metadata-on + marketplace-residue-on, FB/IG still off.
                           Named to make the leak visible — this is NOT a
                           recommended config.
    v12_full             — everything on. Reference config for completeness;
                           not for production until iter 14 restructure lands.

Lookup by name with `get_pipeline_config("v11")`. The names are the only
values accepted by the `--pipeline` argparse flag on both runners.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable description of a Business Checker pipeline configuration.

    Every public toggle that materially affects a verdict lives here. New
    signals added in iter 14+ should be added as additional booleans with
    a default that matches current production behavior, and each named
    config should be updated explicitly so the diff is auditable.
    """

    name: str
    use_facebook_recency: bool
    use_instagram_fallback: bool
    use_metadata: bool
    use_marketplace_residue: bool
    use_rule_scorer: bool
    verify_flagged: bool

    def fingerprint(self) -> str:
        """Return a short stable hash of the config payload.

        Used as part of the cache key (so different pipelines never share
        a cache row) and logged at run start so `run.log` records exactly
        which configuration produced the verdicts in that run.

        Excludes `name` from the hashed payload — two configs with the
        same toggles but different names would (rightly) be considered
        cache-compatible, and renaming a config without changing behavior
        should not invalidate cached rows.
        """
        payload = {k: v for k, v in asdict(self).items() if k != "name"}
        encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()[:12]

    def as_log_dict(self) -> dict:
        """Return a dict suitable for logging at run start.

        Includes both the human-readable name and the fingerprint so log
        readers can correlate a run with a config by either handle.
        """
        return {**asdict(self), "fingerprint": self.fingerprint()}


# ── Named, frozen configs ────────────────────────────────────────────────────

V10 = PipelineConfig(
    name="v10",
    use_facebook_recency=False,
    use_instagram_fallback=False,
    use_metadata=False,
    use_marketplace_residue=False,
    use_rule_scorer=True,
    verify_flagged=True,
)

V11 = PipelineConfig(
    name="v11",
    use_facebook_recency=True,
    use_instagram_fallback=False,
    # Metadata and marketplace-residue were NOT part of the documented iter 11
    # shippable. They were silently added to production in iter 12; pinning
    # them off here is what makes "v11 reproduces iter 11" honest.
    use_metadata=False,
    use_marketplace_residue=False,
    use_rule_scorer=True,
    verify_flagged=True,
)

V12_CURRENT_PROD = PipelineConfig(
    name="v12_current_prod",
    # What run_checker.py actually does today (iter 12 leak): metadata is
    # always extracted and passed when columns exist, and the
    # marketplace-residue override fires unconditionally. FB/IG remained
    # off because no flag plumbed them through. Naming this config
    # `v12_current_prod` (not "v12_full") forces the integrity gap into
    # any side-by-side eval.
    use_facebook_recency=False,
    use_instagram_fallback=False,
    use_metadata=True,
    use_marketplace_residue=True,
    use_rule_scorer=True,
    verify_flagged=True,
)

V12_FULL = PipelineConfig(
    name="v12_full",
    use_facebook_recency=True,
    use_instagram_fallback=True,
    use_metadata=True,
    use_marketplace_residue=True,
    use_rule_scorer=True,
    verify_flagged=True,
)


# ── iter-14 spike branches ────────────────────────────────────────────────────
#
# Branch A1: v11 toggles inherited verbatim. The only thing that changes vs.
# v11 is the final verdict source — Sonnet adjudicator instead of Perplexity
# prose + Haiku audit. The toggle table below is identical to V11; the
# adjudicator swap lives in the runner (eval/rerun_sample.py) routing on
# `config.name == "v14_branch_a1"`. See plan §Phase 2.a1.
V14_BRANCH_A1 = PipelineConfig(
    name="v14_branch_a1",
    use_facebook_recency=True,
    use_instagram_fallback=False,
    use_metadata=False,
    use_marketplace_residue=False,  # logic moved into adjudicator prompt
    use_rule_scorer=True,
    verify_flagged=True,
)

# Branch A2: A1 + Firecrawl scrape of top 3 Perplexity citations.
V14_BRANCH_A2 = PipelineConfig(
    name="v14_branch_a2",
    use_facebook_recency=True,
    use_instagram_fallback=False,
    use_metadata=False,
    use_marketplace_residue=False,
    use_rule_scorer=True,
    verify_flagged=True,
)


PIPELINE_REGISTRY: dict[str, PipelineConfig] = {
    V10.name: V10,
    V11.name: V11,
    V12_CURRENT_PROD.name: V12_CURRENT_PROD,
    V12_FULL.name: V12_FULL,
    V14_BRANCH_A1.name: V14_BRANCH_A1,
    V14_BRANCH_A2.name: V14_BRANCH_A2,
}

PIPELINE_NAMES: tuple[str, ...] = tuple(PIPELINE_REGISTRY.keys())


def get_pipeline_config(name: str) -> PipelineConfig:
    """Return the named `PipelineConfig`.

    Raises:
        KeyError: if `name` is not a known pipeline. The error message
            lists the valid choices so the user is not left guessing.
    """
    try:
        return PIPELINE_REGISTRY[name]
    except KeyError as exc:
        valid = ", ".join(PIPELINE_NAMES)
        raise KeyError(
            f"Unknown pipeline '{name}'. Valid choices: {valid}"
        ) from exc
