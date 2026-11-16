"""Adversarial tests for MHP-to-morphism evidence binding, read-only.

The finite stores below are deterministic mock trust boundaries only. They are
not evidence of a deployed trusted semantic prover or verified cultural intent.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from harness.sdk.holon_context_morphism_proof import (
    ContextMorphismError,
    ContextReadingMorphismWitnessV1,
    ContextRelationMorphismVerifierV1,
    ContextRelationProofBundleV1,
    ProofBoundIndexedContextVerifierV1,
    pair_proof_convention_root,
    RELATION_PASS,
    JOIN_PASS,
)
from harness.sdk.morphisms import (
    MorphismEnvelopeV1,
    MorphismKind,
    ProofArtifactKind,
    SemanticProofObligationV1,
)
from harness.sdk.meaning_heritage import canonical_hash
from harness.tests.test_holon_meaning_bridge import example as existing_lens_example
from harness.tests.test_holon_indexed_context import case as indexed_case, Store
from harness.tests.test_meaning_heritage_morphisms import (
    ProofStore,
    HeritageStore,
    make_registry,
    proof_receipt,
)


def h(domain, value):
    return canonical_hash(domain, value)


@pytest.fixture
def proof_case(indexed_case):
    indexed = indexed_case
    lens = indexed["lens"]
    meaning_receipt = indexed["receipt"]
    relation = indexed["relation"]
    source, target = lens.readings
    bindings = indexed["verifier"].meaning_verifier.context_bindings
    source_binding = bindings.fetch_verified(source.context_binding_receipt_root)
    target_binding = bindings.fetch_verified(target.context_binding_receipt_root)
    assert source_binding is not None and target_binding is not None

    convention = pair_proof_convention_root(
        meaning_receipt_root=meaning_receipt.root,
        lens=lens,
        relation=relation,
        source_reading_id=source.reading_id,
        target_reading_id=target.reading_id,
        source_binding_root=source_binding.root,
        target_binding_root=target_binding.root,
    )
    subject = h("AEGIS_SEMANTIC_CORRESPONDENCE_SUBJECT_V1", {
        "formal_object_root": source_binding.derived_root,
        "target_semantics_root": target_binding.derived_root,
        "convention_root": convention,
    })
    artifacts = ProofStore()
    soundness = artifacts.put(
        proof_receipt(ProofArtifactKind.SEMANTIC_SOUNDNESS, subject, "holon-pair-soundness")
    )
    correspondence = artifacts.put(
        proof_receipt(ProofArtifactKind.SEMANTIC_CORRESPONDENCE, subject, "holon-pair-correspondence")
    )
    registry = make_registry(artifacts, HeritageStore())
    envelope = MorphismEnvelopeV1(
        morphism_id="holon-pair-bridge-v1",
        kind=MorphismKind.SEMANTIC,
        source_domain_root=source_binding.derived_root,
        target_domain_root=target_binding.derived_root,
        proof_obligation=SemanticProofObligationV1(
            formal_object_root=source_binding.derived_root,
            target_semantics_root=target_binding.derived_root,
            convention_root=convention,
            soundness_receipt_root=soundness,
            correspondence_receipt_root=correspondence,
        ),
    )
    check, morphism = registry.verify_and_issue(envelope)
    assert check.status == "PASS" and morphism is not None

    bundles, relations, receipts, lenses = Store(), indexed["relations"], indexed["receipts"], indexed["lenses"]
    morphisms, envelopes, proof_receipts = Store(), Store(), Store()
    morphisms.put(morphism)
    envelopes.put(envelope)
    witness = ContextReadingMorphismWitnessV1(
        source_reading_id=source.reading_id,
        target_reading_id=target.reading_id,
        morphism_receipt_root=morphism.root,
    )
    bundle = bundles.put(ContextRelationProofBundleV1(
        meaning_receipt_root=meaning_receipt.root,
        relation_receipt_root=relation.root,
        pair_witnesses=(witness,),
    ))
    relation_verifier = ContextRelationMorphismVerifierV1(
        bundles=bundles,
        relations=relations,
        receipts=receipts,
        lenses=lenses,
        context_bindings=bindings,
        morphisms=morphisms,
        morphism_envelopes=envelopes,
        meaning_verifier=indexed["verifier"].meaning_verifier,
        morphism_registry=registry,
    )
    relation_check, relation_proof = relation_verifier.verify(bundle.root)
    assert relation_check.status == RELATION_PASS and relation_proof is not None
    proof_receipts.put(relation_proof)
    strict = ProofBoundIndexedContextVerifierV1(
        indexed=indexed["verifier"],
        relation_verifier=relation_verifier,
        relation_proof_receipts=proof_receipts,
    )
    return {
        "indexed": indexed,
        "relation_verifier": relation_verifier,
        "strict": strict,
        "bundle": bundle,
        "relation_proof": relation_proof,
        "morphism": morphism,
        "envelope": envelope,
        "proof_artifacts": artifacts,
        "soundness_root": soundness,
        "correspondence_root": correspondence,
        "witness": witness,
        "bundles": bundles,
        "morphisms": morphisms,
        "morphism_envelopes": envelopes,
        "relation_proof_receipts": proof_receipts,
        "registry": registry,
    }


def assert_denied(result_and_receipt, code: str):
    result, receipt = result_and_receipt
    assert result.status == "FAIL_CONTEXT_MORPHISM_EVIDENCE_DENIED"
    assert result.error_codes == (code,)
    assert receipt is None and result.verification_root is None


def test_genuine_mhp_lineage_semantic_morphism_pair_replay_passes(proof_case):
    ctx = proof_case
    outcome, receipt = ctx["relation_verifier"].verify(ctx["bundle"].root)
    assert outcome.status == RELATION_PASS
    assert receipt == ctx["relation_proof"]
    assert receipt.authority_class == "NONE"
    assert receipt.verified_morphism_receipt_roots == (ctx["morphism"].root,)
    assert len(receipt.root) == 64


def test_complete_finite_solution_plus_all_pair_proofs_can_join(proof_case):
    ctx = proof_case
    problem = ctx["indexed"]["problem"]
    result, receipt = ctx["strict"].verify(problem.root, (ctx["relation_proof"].root,))
    assert result.status == JOIN_PASS
    assert receipt is not None and receipt.authority_class == "NONE"
    assert len(receipt.root) == 64
    assert receipt.relation_proof_receipt_roots == (ctx["relation_proof"].root,)
    assert (result, receipt) == ctx["strict"].verify(problem.root, (ctx["relation_proof"].root,))


def test_missing_trusted_pair_proof_receipt_denies_strict_join(proof_case):
    ctx = proof_case
    ctx["relation_proof_receipts"].items.clear()
    assert_denied(
        ctx["strict"].verify(ctx["indexed"]["problem"].root, (ctx["relation_proof"].root,)),
        "INDEXED_RELATION_PROOF_UNTRUSTED",
    )


def test_valid_mhp_and_csp_without_relation_pair_proof_denied(proof_case):
    ctx = proof_case
    assert_denied(
        ctx["strict"].verify(ctx["indexed"]["problem"].root, ()),
        "INDEXED_RELATION_PROOFS_INCOMPLETE",
    )


def test_missing_semantic_soundness_artifact_denied_even_with_trusted_morphism_receipt(proof_case):
    ctx = proof_case
    del ctx["proof_artifacts"].data[ctx["soundness_root"]]
    assert_denied(
        ctx["relation_verifier"].verify(ctx["bundle"].root),
        "PAIR_MORPHISM_PROOF_NOT_VERIFIED",
    )


def test_missing_semantic_correspondence_artifact_denied(proof_case):
    ctx = proof_case
    del ctx["proof_artifacts"].data[ctx["correspondence_root"]]
    assert_denied(
        ctx["relation_verifier"].verify(ctx["bundle"].root),
        "PAIR_MORPHISM_PROOF_NOT_VERIFIED",
    )


def test_forged_proof_artifact_content_cannot_reuse_trusted_root(proof_case):
    ctx = proof_case
    old = ctx["proof_artifacts"].data[ctx["soundness_root"]]
    ctx["proof_artifacts"].data[old.root] = replace(old, subject_root=h("ALTERED", "subject"))
    assert_denied(
        ctx["relation_verifier"].verify(ctx["bundle"].root),
        "PAIR_MORPHISM_PROOF_NOT_VERIFIED",
    )


def test_pair_morphism_cannot_be_reused_for_another_context(proof_case):
    ctx = proof_case
    relation = ctx["indexed"]["relation"]
    changed = replace(
        relation,
        source_context_root=relation.target_context_root,
        target_context_root=relation.source_context_root,
    )
    ctx["indexed"]["relations"].put(changed)
    changed_bundle = ctx["bundles"].put(
        replace(ctx["bundle"], relation_receipt_root=changed.root)
    )
    assert_denied(
        ctx["relation_verifier"].verify(changed_bundle.root),
        "RELATION_PAIR_CONTEXT_TRANSPLANT",
    )


def test_pair_morphism_forged_convention_denied(proof_case):
    ctx = proof_case
    original = ctx["envelope"]
    mutated = replace(
        original,
        proof_obligation=replace(
            original.proof_obligation,
            convention_root=h("FORGED", "convention"),
        ),
    )
    ctx["morphism_envelopes"].put(mutated)
    changed_morphism = ctx["morphisms"].put(
        replace(ctx["morphism"], envelope_root=mutated.root)
    )
    changed_witness = replace(ctx["witness"], morphism_receipt_root=changed_morphism.root)
    changed_bundle = ctx["bundles"].put(
        replace(ctx["bundle"], pair_witnesses=(changed_witness,))
    )
    assert_denied(
        ctx["relation_verifier"].verify(changed_bundle.root),
        "PAIR_MORPHISM_CONVENTION_TRANSPLANT",
    )


def test_semantic_pair_proof_is_not_symmetry_or_reverse_equivalence(proof_case):
    ctx = proof_case
    altered = ctx["morphisms"].put(replace(
        ctx["morphism"],
        source_domain_root=ctx["morphism"].target_domain_root,
        target_domain_root=ctx["morphism"].source_domain_root,
    ))
    alternate = ctx["bundles"].put(
        replace(ctx["bundle"], pair_witnesses=(
            replace(ctx["witness"], morphism_receipt_root=altered.root),
        ))
    )
    assert_denied(
        ctx["relation_verifier"].verify(alternate.root),
        "PAIR_MORPHISM_ENDPOINT_OR_KIND_MISMATCH",
    )


def test_nonsemantic_morphism_kind_denied_as_pair_proof(proof_case):
    ctx = proof_case
    altered = ctx["morphisms"].put(replace(
        ctx["morphism"], kind=MorphismKind.CARRIER,
    ))
    alternative = ctx["bundles"].put(replace(
        ctx["bundle"], pair_witnesses=(
            replace(ctx["witness"], morphism_receipt_root=altered.root),
        ),
    ))
    assert_denied(
        ctx["relation_verifier"].verify(alternative.root),
        "PAIR_MORPHISM_ENDPOINT_OR_KIND_MISMATCH",
    )


def test_missing_morphism_envelope_denies_prior_receipt(proof_case):
    ctx = proof_case
    ctx["morphism_envelopes"].items.clear()
    assert_denied(
        ctx["relation_verifier"].verify(ctx["bundle"].root),
        "PAIR_MORPHISM_ENVELOPE_UNTRUSTED",
    )


def test_missing_morphism_receipt_denied(proof_case):
    ctx = proof_case
    ctx["morphisms"].items.clear()
    assert_denied(
        ctx["relation_verifier"].verify(ctx["bundle"].root),
        "PAIR_MORPHISM_RECEIPT_UNTRUSTED",
    )


def test_missing_original_mhp_evidence_denied_even_with_morphism_proof(proof_case):
    ctx = proof_case
    ctx["indexed"]["receipts"].items.clear()
    assert_denied(
        ctx["relation_verifier"].verify(ctx["bundle"].root),
        "MEANING_RECEIPT_UNTRUSTED",
    )


def test_empty_relation_has_no_positive_pair_proof_and_cannot_be_admitted(proof_case):
    ctx = proof_case
    empty_relation = ctx["indexed"]["relations"].put(replace(
        ctx["indexed"]["relation"], allowed_reading_id_pairs=(),
    ))
    changed = ctx["bundles"].put(replace(
        ctx["bundle"], relation_receipt_root=empty_relation.root,
    ))
    assert_denied(
        ctx["relation_verifier"].verify(changed.root),
        "RELATION_PAIR_EVIDENCE_INCOMPLETE",
    )


def test_no_hidden_pair_or_unlisted_borrowed_evidence(proof_case):
    ctx = proof_case
    witness = replace(ctx["witness"], source_reading_id="other-interpretation")
    bundle = ctx["bundles"].put(replace(
        ctx["bundle"], pair_witnesses=(witness,),
    ))
    assert_denied(
        ctx["relation_verifier"].verify(bundle.root),
        "RELATION_PAIR_EVIDENCE_INCOMPLETE",
    )


def test_same_proof_pair_root_from_untrusted_bundle_denied(proof_case):
    ctx = proof_case
    ctx["bundles"].items.clear()
    assert_denied(
        ctx["relation_verifier"].verify(ctx["bundle"].root),
        "RELATION_BUNDLE_UNTRUSTED",
    )


def test_proof_bundle_root_is_order_invariant_only_under_same_pairs(proof_case):
    ctx = proof_case
    # A one-pair proof cannot become a different proof by rearrangement;
    # additional pair proofs must be separately bound to the MHP lens.
    same = replace(ctx["bundle"], pair_witnesses=tuple(reversed(ctx["bundle"].pair_witnesses)))
    assert same.root == ctx["bundle"].root
    with pytest.raises(ContextMorphismError, match="PAIR_WITNESSES_DUPLICATE"):
        replace(ctx["bundle"], pair_witnesses=(ctx["witness"], ctx["witness"]))


def test_claimed_relation_proof_spliced_from_other_meaning_receipt_denied(proof_case):
    ctx = proof_case
    forged = ctx["relation_proof_receipts"].put(replace(
        ctx["relation_proof"], meaning_receipt_root=h("FOREIGN_MHP", "receipt"),
    ))
    assert_denied(
        ctx["strict"].verify(ctx["indexed"]["problem"].root, (forged.root,)),
        "INDEXED_RELATION_PROOF_NOT_REPLAYED",
    )


def test_duplicate_proof_roots_denied_without_overwriting(proof_case):
    ctx = proof_case
    r = ctx["relation_proof"].root
    assert_denied(
        ctx["strict"].verify(ctx["indexed"]["problem"].root, (r, r)),
        "INDEXED_RELATION_PROOF_SET_INVALID",
    )
