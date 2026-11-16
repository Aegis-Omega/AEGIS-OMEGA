"""Native topology + MHP integration falsifiers for Holon Graph V1.

Reuses the genuine existing MHP-1 test fixture; fabricated in-memory trusted
stores are *fixtures*, never evidence that a production trust store exists.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace

import pytest

from harness.sdk.holon_meaning_bridge import HolonSnapshotV1
from harness.sdk.holon_graph_verifier import (
    HolonGraphError,
    HolonGraphManifestV1,
    HolonGraphNodeRefV1,
    HolonGraphVerifierV1,
    ResearchSourceAttestationV1,
)
from harness.sdk.meaning_heritage import canonical_hash

# Shared fixture issues actual MHP-1 verified ClaimSet, lineage and heritage receipts.
from harness.tests.test_holon_meaning_bridge import example as existing_lens_example


def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def h(domain: str, value: object) -> str:
    return canonical_hash(domain, value)


class VerifiedByRoot:
    def __init__(self):
        self.data = {}

    def put(self, obj):
        self.data[obj.root] = obj
        return obj

    def fetch_verified(self, key):
        return self.data.get(key)


class VerifiedByDocument:
    def __init__(self):
        self.data = {}

    def put(self, obj):
        self.data[obj.document_id] = obj
        return obj

    def fetch_verified(self, document_id):
        return self.data.get(document_id)


@pytest.fixture
def case(existing_lens_example):
    lens, meaning_verifier, artifacts, *_ = existing_lens_example
    meaning_result, meaning_receipt = meaning_verifier.verify(lens)
    assert meaning_result.status == "PASS" and meaning_receipt is not None

    parent = HolonSnapshotV1(
        holon_id="research.holon.symbols",
        scale="molecular",
        tier="T2",
        part_of=(),
        composed_of=(lens.holon.holon_id,),
        invariants=("preserve descendants",),
        interaction_surface=("READ_ONLY",),
        provenance=lens.holon.provenance,
        ontology_term="Holon",
    )
    child = lens.holon
    manifest_store = VerifiedByRoot()
    snapshot_store = VerifiedByRoot()
    source_store = VerifiedByDocument()
    lens_store = VerifiedByRoot()
    meaning_receipt_store = VerifiedByRoot()
    lens_store.put(lens)
    meaning_receipt_store.put(meaning_receipt)

    # A synthetic, exact-byte document used ONLY as a test fixture.
    doc = b"fixture: research on holons; not an authentic Google Drive review"
    doc_root = artifacts.put(doc)
    doc_id = lens.holon.provenance[0]
    source = source_store.put(ResearchSourceAttestationV1(
        document_id=doc_id,
        content_root=doc_root,
        reviewed_tier="T2",
        review_receipt_root=h("FIXTURE_REVIEW", 1),
        verifier_root=h("FIXTURE_REVIEW_VERIFIER", 1),
        policy_root=h("FIXTURE_REVIEW_POLICY", 1),
    ))

    def build(*snapshots: HolonSnapshotV1, include_meaning: bool = True):
        for node in snapshots:
            snapshot_store.put(node)
        nodes = tuple(
            HolonGraphNodeRefV1(
                holon_id=node.holon_id,
                snapshot_root=node.root,
                meaning_receipt_roots=(meaning_receipt.root,)
                if include_meaning and node.holon_id == child.holon_id else (),
            )
            for node in snapshots
        )
        manifest = manifest_store.put(HolonGraphManifestV1(nodes))
        return manifest

    verifier = HolonGraphVerifierV1(
        manifests=manifest_store,
        snapshots=snapshot_store,
        sources=source_store,
        artifacts=artifacts,
        lenses=lens_store,
        meaning_receipts=meaning_receipt_store,
        meaning_verifier=meaning_verifier,
    )
    manifest = build(parent, child)
    return {
        "verifier": verifier,
        "manifest": manifest,
        "parent": parent,
        "child": child,
        "lens": lens,
        "meaning_receipt": meaning_receipt,
        "source": source,
        "document_id": doc_id,
        "docs": source_store,
        "snapshots": snapshot_store,
        "manifests": manifest_store,
        "lenses": lens_store,
        "meaning_receipts": meaning_receipt_store,
        "artifacts": artifacts,
        "build": build,
    }


def error(case, manifest=None):
    selected = manifest or case["manifest"]
    result, receipt = case["verifier"].verify(selected.root)
    assert result.status == "FAIL_HOLON_GRAPH_DENIED"
    assert receipt is None
    return result.error_codes


def test_graph_with_real_mhp_receipts_and_two_possible_meanings_passes(case):
    result, receipt = case["verifier"].verify(case["manifest"].root)
    assert result.status == "PASS_STRUCTURAL_ONLY"
    assert result.error_codes == ()
    assert receipt is not None
    assert receipt.authority_class == "NONE"
    assert receipt.manifest_root == case["manifest"].root
    assert (receipt.node_count, receipt.edge_count, receipt.source_count) == (2, 1, 1)
    assert (receipt.meaning_receipt_count, receipt.contextual_reading_count) == (1, 2)
    assert receipt.competing_reading_count == 1
    assert receipt.root and receipt.verification_root == result.verification_root


def test_manifest_order_is_canonical_and_receipt_replay_is_identical(case):
    first = case["manifest"]
    second = HolonGraphManifestV1(tuple(reversed(first.nodes)))
    assert first.root == second.root
    r1 = case["verifier"].verify(first.root)
    r2 = case["verifier"].verify(second.root)
    assert r1 == r2


def test_mismatched_manifest_root_is_rejected(case):
    result, receipt = case["verifier"].verify(h("UNTRUSTED_MANIFEST", 1))
    assert result.error_codes == ("GRAPH_MANIFEST_UNTRUSTED",)
    assert receipt is None


def test_manifest_root_malformed_fails_closed(case):
    result, receipt = case["verifier"].verify("malformed")
    assert result.error_codes == ("GRAPH_MANIFEST_ROOT_INVALID",)
    assert receipt is None


def test_missing_snapshot_ref_fails_closed(case):
    del case["snapshots"].data[case["child"].root]
    assert error(case) == ("GRAPH_SNAPSHOT_UNTRUSTED",)


def test_relabelled_node_cannot_reuse_snapshot(case):
    refs = list(case["manifest"].nodes)
    i = next(i for i, ref in enumerate(refs) if ref.holon_id == case["child"].holon_id)
    refs[i] = replace(refs[i], holon_id="forged.child.identifier")
    other = case["manifests"].put(HolonGraphManifestV1(tuple(refs)))
    assert error(case, other) == ("GRAPH_SNAPSHOT_UNTRUSTED",)


def test_missing_parent_in_closed_world_fails(case):
    only_child = case["build"](case["child"])
    assert error(case, only_child) == ("GRAPH_PARENT_UNRESOLVED",)


def test_missing_child_in_closed_world_fails(case):
    only_parent = case["build"](case["parent"])
    assert error(case, only_parent) == ("GRAPH_CHILD_UNRESOLVED",)


def test_parent_missing_child_reciprocity_fails(case):
    parent = replace(case["parent"], composed_of=())
    changed = case["build"](parent, case["child"])
    assert error(case, changed) == ("GRAPH_PARENT_RECIPROCITY_MISSING",)


def test_child_missing_parent_reciprocity_fails(case):
    child = replace(case["child"], part_of=())
    changed = case["build"](case["parent"], child)
    assert error(case, changed) == ("GRAPH_CHILD_RECIPROCITY_MISSING",)


def test_two_node_cycle_rejected(case):
    parent = replace(case["parent"], part_of=(case["child"].holon_id,), scale="atomic")
    child = replace(case["child"], composed_of=(case["parent"].holon_id,))
    changed = case["build"](parent, child, include_meaning=False)
    assert error(case, changed) == ("GRAPH_CYCLE_DETECTED",)


def test_subatomic_parent_of_molecular_child_is_scale_inversion(case):
    parent = replace(case["parent"], scale="subatomic")
    changed = case["build"](parent, case["child"])
    assert error(case, changed) == ("GRAPH_SCALE_INVERSION",)


def test_multi_parent_holarchy_is_valid_not_forced_to_tree(case):
    child = replace(case["child"], part_of=("research.parent.one", "research.parent.two"))
    parents = [
        replace(case["parent"], holon_id=pid, composed_of=(child.holon_id,))
        for pid in child.part_of
    ]
    changed = case["build"](*parents, child, include_meaning=False)
    result, receipt = case["verifier"].verify(changed.root)
    assert result.status == "PASS_STRUCTURAL_ONLY"
    assert (receipt.node_count, receipt.edge_count) == (3, 2)
    assert receipt.meaning_receipt_count == 0


def test_high_tier_without_research_attestation_rejected(case):
    del case["docs"].data[case["document_id"]]
    assert error(case) == ("GRAPH_RESEARCH_SOURCE_UNTRUSTED",)


def test_research_attestation_not_equivalent_to_source_bytes(case):
    source = case["source"]
    case["artifacts"].data[source.content_root] = b"tampered"
    assert error(case) == ("GRAPH_RESEARCH_BYTES_UNTRUSTED",)


def test_source_attestation_must_match_declared_document_id(case):
    source = case["source"]
    case["docs"].data[source.document_id] = replace(source, document_id="another-research-source")
    assert error(case) == ("GRAPH_RESEARCH_SOURCE_UNTRUSTED",)


def test_t3_review_cannot_silently_ground_t2_holon(case):
    source = case["source"]
    case["docs"].put(replace(source, reviewed_tier="T3"))
    assert error(case) == ("GRAPH_HIGH_TIER_GROUNDING_ABSENT",)


def test_t3_only_holons_can_be_structurally_attested_with_t3_documents(case):
    source = case["source"]
    case["docs"].put(replace(source, reviewed_tier="T3"))
    node = replace(case["parent"], tier="T3", composed_of=())
    changed = case["build"](node, include_meaning=False)
    result, receipt = case["verifier"].verify(changed.root)
    assert result.status == "PASS_STRUCTURAL_ONLY"
    assert receipt.meaning_receipt_count == 0


def test_missing_lens_denied_even_with_prior_receipt(case):
    del case["lenses"].data[case["lens"].root]
    assert error(case) == ("GRAPH_MEANING_LENS_UNTRUSTED",)


def test_missing_receipt_denied_even_if_lens_still_exists(case):
    del case["meaning_receipts"].data[case["meaning_receipt"].root]
    assert error(case) == ("GRAPH_MEANING_RECEIPT_UNTRUSTED",)


def test_changed_holon_metadata_cannot_reuse_old_semantics_receipt(case):
    child = replace(case["child"], invariants=("altered unreviewed invariant",))
    changed = case["build"](case["parent"], child)
    assert error(case, changed) == ("GRAPH_MEANING_RECEIPT_UNTRUSTED",)


def test_forged_meaning_lens_is_rejected_by_existing_heritage_verifier(case):
    lens = case["lens"]
    # Source carrier remains identical but occurrence is moved to another place.
    relocated = replace(lens.occurrence, start_byte=0, end_byte=1)
    new_lens = replace(lens, occurrence=relocated)
    case["lenses"].data[lens.root] = new_lens
    assert error(case) == ("GRAPH_MEANING_LENS_UNTRUSTED",)


def test_replayed_claimed_receipt_with_valid_root_and_wrong_source_fails(case):
    lens = case["lens"]
    original = case["meaning_receipt"]
    from harness.sdk.holon_meaning_bridge import HolonMeaningReceiptV1
    altered = replace(original, occurrence_root=h("FORGED_ORIGIN", 1))
    case["meaning_receipts"].data[original.root] = altered
    assert isinstance(altered, HolonMeaningReceiptV1)
    assert error(case) == ("GRAPH_MEANING_RECEIPT_UNTRUSTED",)


def test_duplicate_node_ids_are_rejected_on_manifest_construction(case):
    ref = case["manifest"].nodes[0]
    with pytest.raises(HolonGraphError, match="GRAPH_DUPLICATE_HOLON_ID"):
        HolonGraphManifestV1((ref, ref))


def test_bad_research_source_review_tier_rejected(case):
    with pytest.raises(HolonGraphError, match="SOURCE_REVIEW_TIER_INVALID"):
        replace(case["source"], reviewed_tier="T0.5")


def test_graph_ref_hash_and_multiple_receipt_repetition_rejected(case):
    with pytest.raises(HolonGraphError, match="snapshot_root:INVALID_SHA256"):
        HolonGraphNodeRefV1("h", "not-a-hash")
    with pytest.raises(HolonGraphError, match="meaning_receipt_roots:DUPLICATE"):
        HolonGraphNodeRefV1("h", h("S", 1), (h("M", 1), h("M", 1)))


def test_no_readings_is_structural_check_only_not_truth_proof(case):
    changed = case["build"](case["parent"], case["child"], include_meaning=False)
    result, receipt = case["verifier"].verify(changed.root)
    assert result.status == "PASS_STRUCTURAL_ONLY"
    assert receipt.meaning_receipt_count == 0
    assert receipt.authority_class == "NONE"
