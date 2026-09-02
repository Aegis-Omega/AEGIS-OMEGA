from __future__ import annotations

import hashlib

import pytest

from scripts.avd.frozen_reference import FrozenReferenceError, FrozenReferenceV1
from scripts.avd.mutation_builder import MutationBuilderError, MutationFixtureBuilderV1


TARGET = "sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v"


# Synthetic but structurally representative of the real A1c source.  The
# semantic mutation anchors are intentionally present so build_all() exercises
# every registered mutation without weakening fail-closed source anchoring.
REFERENCE_SOURCE = """\
Definition corn_ir_to_o0_carrier_v1 (x : IR) : O0RealV1 :=
  CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x).

Theorem corn_ir_to_o0_preserves_rat_v1 : forall q : Q, True.
Proof.
  intros q.
  eapply CReq_trans.
  - exact dummy_rat_left.
  - apply CRmorph_rat.
Qed.

Theorem corn_ir_to_o0_strict_v1 : forall x y : IR, x [<] y -> True.
Proof.
  intros x y Hxy.
  exact
    (map_pres_less_unfolded
       IR CRasCReals
       (iso_map_rht CRasCReals IR CRIR_iso)
       x y Hxy).
Qed.
"""

MINIMAL_REFERENCE_SOURCE = """\
Definition corn_ir_to_o0_carrier_v1 (x : IR) : O0RealV1 :=
  CRmorph corn_fast_to_o0_morphism_a1c_v1 (IRasCR x).
"""


def _frozen_reference(source: str = REFERENCE_SOURCE) -> FrozenReferenceV1:
    return FrozenReferenceV1.freeze(
        commit_sha="1" * 40,
        tree_sha="2" * 40,
        source_path=TARGET,
        source_bytes=source.encode("utf-8"),
        dedicated_run_id=101,
        dedicated_conclusion="success",
        formal_attestation_run_id=102,
        formal_attestation_conclusion="success",
        assumptions_closed=True,
    )


def test_reference_freeze_requires_two_green_receipts_and_closed_assumptions() -> None:
    ref = _frozen_reference()
    assert ref.is_frozen is True
    assert ref.source_sha256 == hashlib.sha256(REFERENCE_SOURCE.encode("utf-8")).hexdigest()

    with pytest.raises(FrozenReferenceError, match="DEDICATED_RUN_NOT_GREEN"):
        FrozenReferenceV1.freeze(
            commit_sha="1" * 40,
            tree_sha="2" * 40,
            source_path=TARGET,
            source_bytes=REFERENCE_SOURCE.encode(),
            dedicated_run_id=101,
            dedicated_conclusion="failure",
            formal_attestation_run_id=102,
            formal_attestation_conclusion="success",
            assumptions_closed=True,
        )

    with pytest.raises(FrozenReferenceError, match="FORMAL_ATTESTATION_NOT_GREEN"):
        FrozenReferenceV1.freeze(
            commit_sha="1" * 40,
            tree_sha="2" * 40,
            source_path=TARGET,
            source_bytes=REFERENCE_SOURCE.encode(),
            dedicated_run_id=101,
            dedicated_conclusion="success",
            formal_attestation_run_id=102,
            formal_attestation_conclusion="skipped",
            assumptions_closed=True,
        )

    with pytest.raises(FrozenReferenceError, match="ASSUMPTIONS_NOT_CLOSED"):
        FrozenReferenceV1.freeze(
            commit_sha="1" * 40,
            tree_sha="2" * 40,
            source_path=TARGET,
            source_bytes=REFERENCE_SOURCE.encode(),
            dedicated_run_id=101,
            dedicated_conclusion="success",
            formal_attestation_run_id=102,
            formal_attestation_conclusion="success",
            assumptions_closed=False,
        )


def test_mutation_builder_binds_exact_reference_source_digest() -> None:
    ref = _frozen_reference()
    builder = MutationFixtureBuilderV1(ref, REFERENCE_SOURCE.encode("utf-8"))
    assert builder.reference.commit_sha == "1" * 40

    with pytest.raises(MutationBuilderError, match="REFERENCE_SOURCE_DIGEST_MISMATCH"):
        MutationFixtureBuilderV1(ref, b"different bytes")


def test_mutation_builder_emits_all_manifest_ids_and_keeps_original_exact() -> None:
    ref = _frozen_reference()
    builder = MutationFixtureBuilderV1(ref, REFERENCE_SOURCE.encode("utf-8"))
    fixtures = builder.build_all()

    assert set(fixtures) == {f"MUT_{i:02d}" for i in range(16)}
    assert fixtures["MUT_00"].candidate_source_bytes == REFERENCE_SOURCE.encode("utf-8")
    assert fixtures["MUT_00"].expected_decision == "ACCEPT"
    assert fixtures["MUT_15"].expected_decision == "ACCEPT"


def test_integrity_and_provenance_mutants_are_structurally_explicit() -> None:
    builder = MutationFixtureBuilderV1(_frozen_reference(), REFERENCE_SOURCE.encode("utf-8"))
    fixtures = builder.build_all()

    assert b"Axiom AVD_MUT_07" in fixtures["MUT_07"].candidate_source_bytes
    assert b"Parameter AVD_MUT_08" in fixtures["MUT_08"].candidate_source_bytes
    assert b"Admitted." in fixtures["MUT_09"].candidate_source_bytes
    assert fixtures["MUT_10"].extra_files
    assert fixtures["MUT_11"].extra_files
    assert fixtures["MUT_12"].anchor_override is not None
    assert fixtures["MUT_13"].authority_override == "FORMAL_MATH_EVIDENCE_ONLY"
    assert fixtures["MUT_14"].commitment_override is not None


def test_semantic_mutation_anchors_fail_closed_when_reference_shape_drifts() -> None:
    minimal = MINIMAL_REFERENCE_SOURCE.encode("utf-8")
    builder = MutationFixtureBuilderV1(_frozen_reference(MINIMAL_REFERENCE_SOURCE), minimal)

    with pytest.raises(MutationBuilderError, match="RATIONAL_MUTATION_ANCHOR_NOT_FOUND"):
        builder.build("MUT_05")
    with pytest.raises(MutationBuilderError, match="ORDER_MUTATION_ANCHOR_NOT_FOUND"):
        builder.build("MUT_06")


def test_unknown_mutation_id_fails_closed() -> None:
    builder = MutationFixtureBuilderV1(_frozen_reference(), REFERENCE_SOURCE.encode("utf-8"))
    with pytest.raises(MutationBuilderError, match="UNKNOWN_MUTATION_ID"):
        builder.build("MUT_99")
