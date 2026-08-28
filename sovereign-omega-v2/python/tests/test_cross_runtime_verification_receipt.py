"""
AEGIS Ω — Cross-runtime verification receipt preregistration.

TDD contract: committed before harness/sdk/cross_runtime_verification.py exists.
The aggregate must fail closed when any required runtime lacks an exact source
and execution binding. Local PASS counts are evidence, never remote authority.
"""

from harness.sdk.cross_runtime_verification import (
    RuntimeEvidenceV1,
    build_cross_runtime_receipt,
)


def _bound(name: str, sha: str, passes: int) -> RuntimeEvidenceV1:
    return RuntimeEvidenceV1(
        component=name,
        required=True,
        source_repo="Aegis-Omega/AEGIS-OMEGA",
        source_commit=sha,
        execution_commit=sha,
        execution_status="PASS",
        observed_passes=passes,
        observed_failures=0,
        evidence_origin="REMOTE_EXACT_HEAD_REPLAY",
    )


def test_all_required_exact_head_replays_establish_aggregate():
    sha = "a" * 40
    receipt = build_cross_runtime_receipt([
        _bound("hardware_config_t0", sha, 159),
        _bound("qform_canonical", sha, 12),
    ]).to_dict()

    assert receipt["overall_status"] == "ESTABLISHED"
    assert receipt["all_required_components_exact_head_bound"] is True
    assert receipt["rh_proven"] is False


def test_local_verified_component_blocks_aggregate_authority():
    sha = "b" * 40
    local = RuntimeEvidenceV1(
        component="sovereign_guard_64_suite",
        required=True,
        source_repo="Aegis-Omega/sovereign-guard",
        source_commit=None,
        execution_commit=None,
        execution_status="PASS",
        observed_passes=64,
        observed_failures=0,
        evidence_origin="LOCAL_WORKING_ENVIRONMENT_UNBOUND",
    )
    receipt = build_cross_runtime_receipt([
        _bound("hardware_config_t0", sha, 159),
        local,
    ]).to_dict()

    component = next(x for x in receipt["components"] if x["component"] == "sovereign_guard_64_suite")
    assert component["binding_status"] == "LOCAL_VERIFIED_UNBOUND"
    assert receipt["overall_status"] == "BLOCKED_UNBOUND_COMPONENT"
    assert receipt["all_required_components_exact_head_bound"] is False


def test_exact_public_guard_replay_does_not_launder_unbound_64_suite():
    guard_sha = "1" * 40
    public_package = RuntimeEvidenceV1(
        component="sovereign_guard_public_package_v1",
        required=True,
        source_repo="Aegis-Omega/sovereign-guard",
        source_commit=guard_sha,
        execution_commit=guard_sha,
        execution_status="PASS",
        observed_passes=None,
        observed_failures=0,
        evidence_origin="REMOTE_EXACT_HEAD_REPLAY",
    )
    local_64 = RuntimeEvidenceV1(
        component="sovereign_guard_64_suite",
        required=True,
        source_repo="Aegis-Omega/sovereign-guard",
        source_commit=None,
        execution_commit=None,
        execution_status="PASS",
        observed_passes=64,
        observed_failures=0,
        evidence_origin="OPERATOR_REPORTED_LOCAL_WORKING_ENVIRONMENT_UNBOUND",
        remote_reference_commit=guard_sha,
    )

    receipt = build_cross_runtime_receipt([public_package, local_64]).to_dict()
    components = {item["component"]: item for item in receipt["components"]}

    assert components["sovereign_guard_public_package_v1"]["binding_status"] == "REMOTE_EXACT_HEAD_VERIFIED"
    assert components["sovereign_guard_64_suite"]["binding_status"] == "LOCAL_VERIFIED_UNBOUND"
    assert components["sovereign_guard_64_suite"]["remote_reference_grants_authority"] is False
    assert receipt["overall_status"] == "BLOCKED_UNBOUND_COMPONENT"
    assert receipt["all_required_components_exact_head_bound"] is False


def test_remote_source_without_execution_replay_is_not_established():
    remote_only = RuntimeEvidenceV1(
        component="sovereign_guard_remote_v1",
        required=True,
        source_repo="Aegis-Omega/sovereign-guard",
        source_commit="3c6568684fc58bbab015f0ea34a87f9df4cfe1aa",
        execution_commit=None,
        execution_status="NOT_RUN",
        observed_passes=None,
        observed_failures=None,
        evidence_origin="REMOTE_SOURCE_ONLY",
    )
    receipt = build_cross_runtime_receipt([remote_only]).to_dict()

    assert receipt["components"][0]["binding_status"] == "REMOTE_SOURCE_UNREPLAYED"
    assert receipt["overall_status"] == "BLOCKED_UNBOUND_COMPONENT"


def test_execution_must_match_source_commit():
    mismatched = RuntimeEvidenceV1(
        component="mismatch",
        required=True,
        source_repo="Aegis-Omega/AEGIS-OMEGA",
        source_commit="c" * 40,
        execution_commit="d" * 40,
        execution_status="PASS",
        observed_passes=1,
        observed_failures=0,
        evidence_origin="REMOTE_EXACT_HEAD_REPLAY",
    )
    receipt = build_cross_runtime_receipt([mismatched]).to_dict()

    assert receipt["components"][0]["binding_status"] == "SOURCE_EXECUTION_MISMATCH"
    assert receipt["overall_status"] == "BLOCKED_UNBOUND_COMPONENT"


def test_receipt_digest_changes_with_source_identity():
    r1 = build_cross_runtime_receipt([_bound("hardware_config_t0", "e" * 40, 159)]).to_dict()
    r2 = build_cross_runtime_receipt([_bound("hardware_config_t0", "f" * 40, 159)]).to_dict()

    assert len(r1["receipt_sha256"]) == 64
    assert len(r2["receipt_sha256"]) == 64
    assert r1["receipt_sha256"] != r2["receipt_sha256"]
