"""Native integration falsifiers: HolonMetadata -> occurrence -> MHP-1 readings."""
from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from harness.sdk.holon_meaning_bridge import (
    ContextBindingReceiptV1,
    ContextualReadingV1,
    HolonMeaningError,
    HolonMeaningLensV1,
    HolonMeaningVerifierV1,
    HolonSnapshotV1,
    SourceOccurrenceV1,
)
from harness.sdk.meaning_heritage import (
    ClaimRef,
    ClaimSetEnvelopeV1,
    ClaimSetVerifierV13,
    DeclaredAdditionEdge,
    DerivationProofReceiptV1,
    HeritageVerifierV13,
    LossType,
    SemanticLineageEnvelopeV1,
    TransformRelation,
    canonical_hash,
)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def h(domain: str, value: object) -> str:
    return canonical_hash(domain, value)


class VerifiedStore:
    def __init__(self):
        self.data = {}

    def put(self, obj):
        self.data[obj.root] = obj
        return obj

    def fetch_verified(self, root: str):
        return self.data.get(root)


class ArtifactStore:
    def __init__(self):
        self.data: dict[str, bytes] = {}

    def put(self, value: bytes):
        root = sha(value)
        self.data[root] = value
        return root

    def fetch_verified(self, root: str):
        return self.data.get(root)


class ProofStore:
    def __init__(self):
        self.derivations = {}

    def fetch_derivation(self, root):
        return self.derivations.get(root)

    def fetch_preservation(self, root):
        return None


class FixedExtractor:
    def __init__(self, name: str, claims):
        self.extractor_root = h("BRIDGE_EXTRACTOR", name)
        self.policy_root = h("BRIDGE_EXTRACTOR_POLICY", name)
        self.claims = claims

    def extract(self, payload: bytes):
        return self.claims


def issue(payload: bytes, claims: tuple[ClaimRef, ...], name: str):
    extractor = FixedExtractor(name, claims)
    env = ClaimSetEnvelopeV1(
        lineage_id=name,
        payload_root=sha(payload),
        raw_claims=claims,
        extractor_root=extractor.extractor_root,
        extractor_policy_root=extractor.policy_root,
    )
    return ClaimSetVerifierV13.verify_and_issue(env, payload, extractor)


def holon() -> HolonSnapshotV1:
    # Exact public HolonMetadata field/enum shape from sovereign-omega-v2/src/core/types.ts.
    return HolonSnapshotV1.from_typescript_record({
        "holon_id": "research.holon.symbol.A",
        "scale": "atomic",
        "tier": "T2",
        "part_of": ["research.holon.symbols"],
        "composed_of": [],
        "invariants": ["preserve origin and all plausible readings"],
        "interaction_surface": ["READ_ONLY"],
        "provenance": ["1PdmRTqAxd61sXoqcITPKu1AqBjDkwWSu"],
        "ontology_term": "Holon",
    })


@pytest.fixture
def example():
    # No model may infer that the carrier 'A' is the same *occurrence* in every source.
    original = b"note/alpha: A /tail"
    start = original.index(b"A")
    artifacts = ArtifactStore()
    artifact_root = artifacts.put(original)
    occurrence = SourceOccurrenceV1(artifact_root, start, start + 1, sha(b"A"))
    source_claim = ClaimRef("carrier:A", h("TEST_CARRIER_CLAIM", "A"), "fp:carrier:A")
    source_claimset = issue(b"A", (source_claim,), "bridge-source")
    claimsets, envelopes, heritage, bindings = VerifiedStore(), VerifiedStore(), VerifiedStore(), VerifiedStore()
    claimsets.put(source_claimset)
    proofs = ProofStore()
    readings = []

    for name, context, output, uncertainty in (
        ("latin-letter", b"codebook:latin", b"candidate:Latin capital letter A", 800),
        ("bio-base", b"codebook:DNA", b"candidate:adenine symbol A", 2000),
    ):
        target_claim = ClaimRef(name, h("TEST_READING_CLAIM", name), f"fp:reading:{name}")
        target = issue(output, (target_claim,), f"bridge-derived-{name}")
        claimsets.put(target)
        artifacts.put(output)
        context_root = artifacts.put(context)
        transform_root = h("BRIDGE_CONTEXT_TRANSFORM", name)
        proof = DerivationProofReceiptV1(
            derived_claim_digest=target_claim.claim_digest,
            source_claim_digests=(source_claim.claim_digest,),
            source_semantic_fingerprints=(source_claim.semantic_fingerprint,),
            derived_semantic_fingerprint=target_claim.semantic_fingerprint,
            transform_root=transform_root,
            verifier_root=h("BRIDGE_PROOF_VERIFIER", name),
            policy_root=h("BRIDGE_PROOF_POLICY", name),
        )
        proofs.derivations[proof.root] = proof
        env = SemanticLineageEnvelopeV1(
            lineage_id=f"reading-{name}",
            source_root=source_claimset.payload_root,
            source_claimset_receipt_root=source_claimset.root,
            derived_root=target.payload_root,
            derived_claimset_receipt_root=target.root,
            transform_root=transform_root,
            transform_relation=TransformRelation.LOSSY_TRANSFORM,
            loss_type=LossType.HEURISTIC_ABSTRACTION,
            preservation_edges=(),
            declared_omission_digests=(source_claim.claim_digest,),
            declared_additions=(DeclaredAdditionEdge(target_claim.claim_digest, proof.root),),
            uncertainty_bps=uncertainty,
        )
        result, receipt = HeritageVerifierV13(
            verifier_root=h("BRIDGE_HERITAGE_VERIFIER", name),
            policy_root=h("BRIDGE_HERITAGE_POLICY", name),
            proof_store=proofs,
            claimset_store=claimsets,
        ).verify(env, source_claimset, target)
        assert result.status == "PASS"
        assert receipt is not None and receipt.authority_class == "NONE"
        envelopes.put(env)
        heritage.put(receipt)
        binding = ContextBindingReceiptV1(
            reading_id=name,
            holon_root=holon().root,
            occurrence_root=occurrence.root,
            context_root=context_root,
            envelope_root=env.root,
            transform_root=env.transform_root,
            derived_root=env.derived_root,
            verifier_root=h("BRIDGE_CONTEXT_BIND_VERIFIER", name),
            policy_root=h("BRIDGE_CONTEXT_BIND_POLICY", name),
        )
        bindings.put(binding)
        readings.append(ContextualReadingV1(name, context_root, env.root, receipt.root, binding.root))

    lens = HolonMeaningLensV1(holon(), occurrence, tuple(readings))
    verifier = HolonMeaningVerifierV1(artifacts=artifacts, heritage=heritage,
                                      envelopes=envelopes, claimsets=claimsets, context_bindings=bindings)
    return lens, verifier, artifacts, heritage, envelopes, claimsets, bindings


def test_two_contextual_readings_are_both_preserved_without_selection(example):
    lens, verifier, *_ = example
    result, receipt = verifier.verify(lens)
    assert result.status == "PASS"
    assert receipt is not None and receipt.authority_class == "NONE"
    assert len(receipt.heritage_receipt_roots) == 2
    assert len(receipt.context_binding_receipt_roots) == 2
    assert receipt.occurrence_root == lens.occurrence.root
    assert result.verification_root == receipt.verification_root


def test_same_carrier_from_distinct_origins_is_not_same_occurrence(example):
    lens, verifier, artifacts, heritage, envelopes, claimsets, bindings = example
    new_parent = b"record/beta: A /tail"
    idx = new_parent.index(b"A")
    other_occurrence = SourceOccurrenceV1(artifacts.put(new_parent), idx, idx + 1, sha(b"A"))
    second = replace(lens, occurrence=other_occurrence)
    assert second.occurrence.carrier_root == lens.occurrence.carrier_root
    assert second.occurrence.root != lens.occurrence.root
    assert second.root != lens.root
    # An old attestation cannot be silently reused for the new origin.
    assert verifier.verify(second)[0].error_codes == ("READING_CONTEXT_TRANSPLANT",)

    new_readings = []
    for reading in lens.readings:
        previous = bindings.fetch_verified(reading.context_binding_receipt_root)
        fresh = replace(previous, occurrence_root=other_occurrence.root)
        bindings.put(fresh)
        new_readings.append(replace(reading, context_binding_receipt_root=fresh.root))
    second = replace(second, readings=tuple(new_readings))
    result, issued = verifier.verify(second)
    assert result.status == "PASS" and issued is not None
    assert issued.occurrence_root != lens.occurrence.root


def test_readings_order_does_not_change_root(example):
    lens, verifier, *_ = example
    swapped = replace(lens, readings=tuple(reversed(lens.readings)))
    assert swapped.root == lens.root
    assert verifier.verify(swapped)[1].root == verifier.verify(lens)[1].root


def test_wrong_source_span_fails_closed(example):
    lens, verifier, *_ = example
    bad = replace(lens, occurrence=replace(lens.occurrence, start_byte=0, end_byte=1))
    result, receipt = verifier.verify(bad)
    assert receipt is None and result.error_codes == ("SOURCE_SPAN_CARRIER_MISMATCH",)


def test_source_overflow_fails_closed(example):
    lens, verifier, *_ = example
    bad = replace(lens, occurrence=replace(lens.occurrence, end_byte=1000))
    assert verifier.verify(bad)[0].error_codes == ("SOURCE_SPAN_OUT_OF_BOUNDS",)


def test_context_substitution_with_valid_context_bytes_is_rejected(example):
    lens, verifier, *_ = example
    other_context = lens.readings[1].context_root
    bad = replace(lens, readings=(replace(lens.readings[0], context_root=other_context), lens.readings[1]))
    assert verifier.verify(bad)[0].error_codes == ("READING_CONTEXT_TRANSPLANT",)


def test_holon_metadata_splice_fails_without_new_binding(example):
    lens, verifier, *_ = example
    renamed = replace(lens.holon, holon_id="research.holon.symbol.A.forged")
    assert verifier.verify(replace(lens, holon=renamed))[0].error_codes == ("READING_CONTEXT_TRANSPLANT",)


def test_missing_context_binding_is_denied(example):
    lens, verifier, artifacts, heritage, envelopes, claimsets, bindings = example
    bindings.data.pop(lens.readings[0].context_binding_receipt_root)
    assert verifier.verify(lens)[0].error_codes == ("READING_CONTEXT_BINDING_UNTRUSTED",)


def test_untrusted_parent_fails_closed(example):
    lens, verifier, artifacts, *_ = example
    artifacts.data.pop(lens.occurrence.artifact_root)
    assert verifier.verify(lens)[0].error_codes == ("SOURCE_ARTIFACT_UNTRUSTED",)


def test_untrusted_context_fails_closed(example):
    lens, verifier, artifacts, *_ = example
    artifacts.data.pop(lens.readings[0].context_root)
    assert verifier.verify(lens)[0].error_codes == ("READING_CONTEXT_UNTRUSTED",)


def test_unknown_receipt_fails_closed(example):
    lens, verifier, artifacts, heritage, *_ = example
    heritage.data.pop(lens.readings[0].heritage_receipt_root)
    assert verifier.verify(lens)[0].error_codes == ("READING_HERITAGE_UNTRUSTED",)


def test_swapped_receipt_is_not_authorized_by_another_context(example):
    lens, verifier, *_ = example
    tampered = replace(lens.readings[0], heritage_receipt_root=lens.readings[1].heritage_receipt_root)
    bad = replace(lens, readings=(tampered, lens.readings[1]))
    assert verifier.verify(bad)[0].error_codes == ("READING_MHP_BINDING_MISMATCH",)


def test_missing_derived_payload_fails_closed(example):
    lens, verifier, artifacts, _, envelopes, _, _ = example
    env = envelopes.fetch_verified(lens.readings[0].envelope_root)
    artifacts.data.pop(env.derived_root)
    assert verifier.verify(lens)[0].error_codes == ("READING_DERIVED_ARTIFACT_UNTRUSTED",)


def test_missing_claimset_fails_closed(example):
    lens, verifier, artifacts, heritage, envelopes, claimsets, _ = example
    env = envelopes.fetch_verified(lens.readings[0].envelope_root)
    claimsets.data.pop(env.derived_claimset_receipt_root)
    assert verifier.verify(lens)[0].error_codes == ("READING_CLAIMSET_UNTRUSTED",)


def test_unverified_holon_topology_is_not_self_certified(example):
    lens, verifier, *_ = example
    result, receipt = verifier.verify(lens)
    assert result.status == "PASS" and receipt.authority_class == "NONE"
    assert lens.holon.part_of == ("research.holon.symbols",)
    # Receipt reports only structural, byte, and trusted-MHP bindings.
    assert not hasattr(receipt, "ontology_truth_verified")
    assert not hasattr(receipt, "meaning_is_true")


def test_reject_unbounded_holon_shape_and_unbacked_high_tier():
    d = {
        "holon_id": "a", "scale": "atomic", "tier": "T0",
        "part_of": [], "composed_of": [], "invariants": [],
        "interaction_surface": [], "provenance": [], "ontology_term": "Holon",
    }
    with pytest.raises(HolonMeaningError, match="HOLON_PROVENANCE_REQUIRED"):
        HolonSnapshotV1.from_typescript_record(d)
    d["provenance"] = ["drive-source"]
    d["mutation_authority"] = "ANY"
    with pytest.raises(HolonMeaningError, match="HOLON_METADATA_SHAPE_INVALID"):
        HolonSnapshotV1.from_typescript_record(d)


def test_reject_self_edges_and_duplicate_reading_ids(example):
    lens, *_ = example
    with pytest.raises(HolonMeaningError, match="HOLON_SELF_EDGE"):
        replace(lens.holon, part_of=(lens.holon.holon_id,))
    with pytest.raises(HolonMeaningError, match="HOLON_READING_ID_DUPLICATE"):
        HolonMeaningLensV1(lens.holon, lens.occurrence, (lens.readings[0], lens.readings[0]))


def test_invalid_span_and_unknown_scale_rejected(example):
    lens, *_ = example
    with pytest.raises(HolonMeaningError, match="SOURCE_SPAN_INVALID"):
        replace(lens.occurrence, end_byte=lens.occurrence.start_byte)
    with pytest.raises(HolonMeaningError, match="HOLON_SCALE_UNKNOWN"):
        replace(lens.holon, scale="FIELD")
