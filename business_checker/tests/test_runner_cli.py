"""Tests for the iter-13 CLI contract on run_checker.py and rerun_sample.py.

These tests do not invoke the network or Perplexity — they only check that
argparse enforces `--pipeline` and hard-errors on the removed per-signal
flags. Anything beyond that requires Perplexity calls and lives in the
gate runs themselves.
"""

from __future__ import annotations

import pytest

# rerun_sample's parser builder is exported as a private symbol but is
# stable enough to assert against; if we end up renaming it the tests
# will fail fast.
from eval.rerun_sample import _build_parser as _rerun_parser


class TestRerunSamplePipelineFlag:
    def test_pipeline_is_required(self, capsys):
        parser = _rerun_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([
                "--sample", "x.csv",
                "--input-xlsx", "y.xlsx",
                "--out", "z.csv",
            ])
        err = capsys.readouterr().err
        assert "--pipeline" in err

    def test_pipeline_accepts_valid_choice(self):
        args = _rerun_parser().parse_args([
            "--sample", "x.csv",
            "--input-xlsx", "y.xlsx",
            "--out", "z.csv",
            "--pipeline", "v11",
        ])
        assert args.pipeline == "v11"

    def test_pipeline_rejects_unknown(self, capsys):
        with pytest.raises(SystemExit):
            _rerun_parser().parse_args([
                "--sample", "x.csv",
                "--input-xlsx", "y.xlsx",
                "--out", "z.csv",
                "--pipeline", "v99",
            ])


class TestRerunSampleRemovedFlags:
    """Old per-signal flags must hard-error with a migration message."""

    def test_facebook_recency_flag_errors(self, capsys):
        with pytest.raises(SystemExit):
            _rerun_parser().parse_args([
                "--sample", "x.csv",
                "--input-xlsx", "y.xlsx",
                "--out", "z.csv",
                "--pipeline", "v11",
                "--enable-facebook-recency",
            ])
        err = capsys.readouterr().err
        assert "iter 13" in err
        assert "--pipeline" in err

    def test_instagram_fallback_flag_errors(self, capsys):
        with pytest.raises(SystemExit):
            _rerun_parser().parse_args([
                "--sample", "x.csv",
                "--input-xlsx", "y.xlsx",
                "--out", "z.csv",
                "--pipeline", "v11",
                "--enable-instagram-fallback",
            ])
        err = capsys.readouterr().err
        assert "iter 13" in err


def test_run_checker_pipeline_flag_required(capsys, monkeypatch):
    """run_checker.py's main() must reject invocation without --pipeline."""
    import run_checker
    monkeypatch.setattr("sys.argv", ["run_checker.py", "--input", "fake.xlsx"])
    with pytest.raises(SystemExit):
        run_checker.main()
    err = capsys.readouterr().err
    assert "--pipeline" in err
