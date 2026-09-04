import importlib

import pytest


BASELINE = "457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404"
HEAD = "8d46992e93d3f9fa0133b7ce1adba51425f8ca72"
REALITY = "a" * 64
POLICY = "b" * 64


def _bindings():
    return importlib.import_module("agents.quantummanifold.bindings")


def test_valid_coordinate_bindings_are_accepted():
    bindings = _bindings()
    bindings.validate_baseline_digest(BASELINE)
    bindings.validate_source_head(HEAD, ancestor_check=lambda sha: sha == HEAD)
    bindings.validate_reality_snapshot_digest(REALITY, REALITY)
    bindings.validate_scheduler_policy_digest(POLICY, POLICY)


def test_qm_red_002_wrong_baseline_digest_fails_closed():
    with pytest.raises(ValueError, match="^BASELINE_BINDING_MISMATCH$"):
        _bindings().validate_baseline_digest("0" * 64)


def test_qm_red_003_nonancestor_source_head_fails_closed():
    with pytest.raises(ValueError, match="^SOURCE_HEAD_INVALID$"):
        _bindings().validate_source_head(HEAD, ancestor_check=lambda _sha: False)


def test_qm_red_003_malformed_source_head_fails_closed_without_resolver_call():
    called = False

    def resolver(_sha):
        nonlocal called
        called = True
        return True

    with pytest.raises(ValueError, match="^SOURCE_HEAD_INVALID$"):
        _bindings().validate_source_head("not-a-sha", ancestor_check=resolver)
    assert called is False


def test_qm_red_004_reality_snapshot_digest_mismatch_fails_closed():
    with pytest.raises(ValueError, match="^REALITY_DIGEST_MISMATCH$"):
        _bindings().validate_reality_snapshot_digest("a" * 64, "c" * 64)


def test_qm_red_010_scheduler_policy_digest_mismatch_fails_closed():
    with pytest.raises(ValueError, match="^SCHEDULER_POLICY_MISMATCH$"):
        _bindings().validate_scheduler_policy_digest("b" * 64, "d" * 64)
