from __future__ import annotations

from harness.sdk.fiber_refinement_authority import (
    FiberRefinementSpec,
    FiberRefinementVerdict,
    evaluate_fiber_refinement,
)


def _digest(ch: str = "a") -> str:
    return "sha256:" + ch * 64


def _spec(
    *,
    base_cells: tuple[str, ...] = ("base:a", "base:b"),
    refined_parent: tuple[tuple[str, str], ...] = (
        ("refined:a1", "base:a"),
        ("refined:b1", "base:b"),
    ),
    base_effect_scope: frozenset[str] = frozenset(
        {"repo:read", "evidence:record"}
    ),
    refined_effect_scope: frozenset[str] = frozenset({"repo:read"}),
    context_digest: str = _digest(),
) -> FiberRefinementSpec:
    return FiberRefinementSpec(
        base_cells=base_cells,
        refined_parent=refined_parent,
        base_effect_scope=base_effect_scope,
        refined_effect_scope=refined_effect_scope,
        context_digest=context_digest,
    )


def _assert_never_mints_authority(receipt: object) -> None:
    assert receipt.grants_execution_authority is False
    assert receipt.grants_effect_authority is False
    assert receipt.grants_atomic_admission_authority is False
    assert receipt.requires_external_authorization is True


def test_valid_refinement_certifies_non_expansion_but_never_authority() -> None:
    receipt = evaluate_fiber_refinement(_spec())

    assert receipt.verdict == FiberRefinementVerdict.VALID
    assert receipt.reason_codes == ()
    assert receipt.certifies_non_expansion is True
    assert receipt.spec_digest.startswith("sha256:")
    assert receipt.receipt_sha256.startswith("sha256:")
    _assert_never_mints_authority(receipt)


def test_effect_scope_expansion_fails_closed() -> None:
    receipt = evaluate_fiber_refinement(
        _spec(refined_effect_scope=frozenset({"repo:read", "repo:write"}))
    )

    assert receipt.verdict == FiberRefinementVerdict.INVALID
    assert "EFFECT_SCOPE_EXPANSION" in receipt.reason_codes
    assert receipt.certifies_non_expansion is False
    _assert_never_mints_authority(receipt)


def test_unknown_parent_and_orphaned_base_cell_fail_closed() -> None:
    unknown = evaluate_fiber_refinement(
        _spec(
            refined_parent=(
                ("refined:a1", "base:a"),
                ("refined:x1", "base:unknown"),
            )
        )
    )
    orphaned = evaluate_fiber_refinement(
        _spec(refined_parent=(("refined:a1", "base:a"),))
    )

    assert unknown.verdict == FiberRefinementVerdict.INVALID
    assert "UNKNOWN_PARENT_CELL" in unknown.reason_codes
    assert orphaned.verdict == FiberRefinementVerdict.INVALID
    assert "BASE_CELL_WITHOUT_REFINED_CHILD" in orphaned.reason_codes
    _assert_never_mints_authority(unknown)
    _assert_never_mints_authority(orphaned)


def test_duplicate_or_conflicting_child_mapping_is_not_normalized_away() -> None:
    receipt = evaluate_fiber_refinement(
        _spec(
            refined_parent=(
                ("refined:a1", "base:a"),
                ("refined:a1", "base:b"),
            )
        )
    )

    assert receipt.verdict == FiberRefinementVerdict.INVALID
    assert "DUPLICATE_REFINED_CELL" in receipt.reason_codes
    _assert_never_mints_authority(receipt)


def test_duplicate_base_cells_and_malformed_context_fail_closed() -> None:
    duplicate_base = evaluate_fiber_refinement(
        _spec(base_cells=("base:a", "base:a"), refined_parent=(("r1", "base:a"),))
    )
    bad_context = evaluate_fiber_refinement(_spec(context_digest="not-a-sha256"))

    assert duplicate_base.verdict == FiberRefinementVerdict.INVALID
    assert "DUPLICATE_BASE_CELL" in duplicate_base.reason_codes
    assert bad_context.verdict == FiberRefinementVerdict.INVALID
    assert "MALFORMED_CONTEXT_DIGEST" in bad_context.reason_codes
    _assert_never_mints_authority(duplicate_base)
    _assert_never_mints_authority(bad_context)


def test_semantically_identical_input_order_has_identical_receipt() -> None:
    first = evaluate_fiber_refinement(_spec())
    second = evaluate_fiber_refinement(
        _spec(
            base_cells=("base:b", "base:a"),
            refined_parent=(
                ("refined:b1", "base:b"),
                ("refined:a1", "base:a"),
            ),
            base_effect_scope=frozenset({"evidence:record", "repo:read"}),
        )
    )

    assert first.verdict == FiberRefinementVerdict.VALID
    assert second.verdict == FiberRefinementVerdict.VALID
    assert first.spec_digest == second.spec_digest
    assert first.receipt_sha256 == second.receipt_sha256


def _deductive_closure_fixture() -> FiberRefinementSpec:
    return _spec(
        base_cells=("claim:undecided", "claim:established"),
        refined_parent=(
            ("claim:undecided:open", "claim:undecided"),
            ("claim:established:derived", "claim:established"),
        ),
        context_digest=_digest("b"),
    )


def _phi_spectral_cluster_fixture() -> FiberRefinementSpec:
    return _spec(
        base_cells=("spectrum:cluster-0", "spectrum:cluster-1"),
        refined_parent=(
            ("spectrum:phi-low", "spectrum:cluster-0"),
            ("spectrum:phi-high", "spectrum:cluster-1"),
        ),
        context_digest=_digest("c"),
    )


def _subcritical_observer_fixture() -> FiberRefinementSpec:
    return _spec(
        base_cells=("observer:seen", "observer:unseen"),
        refined_parent=(
            ("observer:seen:resolved", "observer:seen"),
            ("observer:unseen:bounded", "observer:unseen"),
        ),
        context_digest=_digest("d"),
    )


def test_three_independent_fixture_families_share_the_same_non_escalation_law() -> None:
    for fixture in (
        _deductive_closure_fixture(),
        _phi_spectral_cluster_fixture(),
        _subcritical_observer_fixture(),
    ):
        receipt = evaluate_fiber_refinement(fixture)
        assert receipt.verdict == FiberRefinementVerdict.VALID
        assert receipt.certifies_non_expansion is True
        _assert_never_mints_authority(receipt)


def test_three_fixture_families_all_reject_scope_smuggling() -> None:
    for fixture in (
        _deductive_closure_fixture(),
        _phi_spectral_cluster_fixture(),
        _subcritical_observer_fixture(),
    ):
        attacked = FiberRefinementSpec(
            base_cells=fixture.base_cells,
            refined_parent=fixture.refined_parent,
            base_effect_scope=fixture.base_effect_scope,
            refined_effect_scope=frozenset(set(fixture.refined_effect_scope) | {"repo:write"}),
            context_digest=fixture.context_digest,
        )
        receipt = evaluate_fiber_refinement(attacked)
        assert receipt.verdict == FiberRefinementVerdict.INVALID
        assert "EFFECT_SCOPE_EXPANSION" in receipt.reason_codes
        _assert_never_mints_authority(receipt)
