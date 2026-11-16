"""Independently sourced graph+ontology receipt join falsifiers.

These suites exercise full native graph + existing MHP lineage + the exact
pinned Git ontology bytes. In-memory stores are fixtures only; they do not
turn source, meaning or ontological labels into execution authority.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from harness.sdk.holon_ontology_binding import (
    HolonGraphOntologyJoinVerifierV1,
    OntologyBindingReceiptV1,
)
from harness.tests.test_holon_graph_verifier import case as graph_case
from harness.tests.test_holon_ontology_binding import case as ontology_case


class Verified:
    def __init__(self):
        self.values = {}

    def put(self, receipt):
        self.values[receipt.root] = receipt
        return receipt

    def fetch_verified(self, root):
        return self.values.get(root)


@pytest.fixture
def integrated(graph_case, ontology_case):
    graph_result, graph_receipt = graph_case["verifier"].verify(
        graph_case["manifest"].root
    )
    assert graph_result.status == "PASS_STRUCTURAL_ONLY" and graph_receipt is not None
    ontology_verifier, _, _, anchor, _ = ontology_case
    expected_holons = (graph_case["child"], graph_case["parent"])
    ontology_result, ontology_receipt = ontology_verifier.verify(
        anchor.root, expected_holons
    )
    assert ontology_result.status == "PASS_ONTOLOGY_MEMBERSHIP_ONLY"
    assert ontology_receipt is not None
    graph_store, ontology_store = Verified(), Verified()
    graph_store.put(graph_receipt)
    ontology_store.put(ontology_receipt)
    verifier = HolonGraphOntologyJoinVerifierV1(
        graphs=graph_store, ontologies=ontology_store
    )
    return {
        "verifier": verifier,
        "graph": graph_receipt,
        "ontology": ontology_receipt,
        "graphs": graph_store,
        "ontologies": ontology_store,
        "graph_case": graph_case,
        "ontology_case": ontology_case,
    }


def _deny(ctx, graph_root=None, ontology_root=None):
    gr = ctx["graph"].root if graph_root is None else graph_root
    ont = ctx["ontology"].root if ontology_root is None else ontology_root
    result, receipt = ctx["verifier"].verify(gr, ont)
    assert receipt is None
    assert result.verification_root is None
    assert result.status == "FAIL_GRAPH_ONTOLOGY_JOIN_DENIED"
    return result.error_codes


def test_two_independently_verified_proofs_join_on_exact_holon_set(integrated):
    r = integrated["verifier"].verify(
        integrated["graph"].root, integrated["ontology"].root
    )
    result, receipt = r
    assert result.status == "PASS_GRAPH_ONTOLOGY_JOIN_ONLY"
    assert receipt is not None and receipt.authority_class == "NONE"
    assert receipt.graph_receipt_root == integrated["graph"].root
    assert receipt.ontology_receipt_root == integrated["ontology"].root
    assert receipt.holon_snapshot_roots == integrated["graph"].verified_snapshot_roots
    assert len(receipt.holon_snapshot_roots) == 2
    assert result.verification_root == receipt.verification_root
    assert r == integrated["verifier"].verify(
        integrated["graph"].root, integrated["ontology"].root
    )


def test_receipts_are_order_invariant_but_identity_bound(integrated):
    verifier, _, _, anchor, _ = integrated["ontology_case"]
    child = integrated["graph_case"]["child"]
    parent = integrated["graph_case"]["parent"]
    result, fresh = verifier.verify(anchor.root, (parent, child))
    assert result.status == "PASS_ONTOLOGY_MEMBERSHIP_ONLY"
    assert fresh == integrated["ontology"]


def test_ontology_subset_cannot_represent_whole_graph(integrated):
    verifier, _, _, anchor, _ = integrated["ontology_case"]
    result, subset = verifier.verify(anchor.root, (integrated["graph_case"]["parent"],))
    assert result.status == "PASS_ONTOLOGY_MEMBERSHIP_ONLY"
    integrated["ontologies"].put(subset)
    assert _deny(integrated, ontology_root=subset.root) == (
        "GRAPH_ONTOLOGY_SNAPSHOT_SET_MISMATCH",
    )


def test_extra_ontology_holon_cannot_be_ghost_graph_node(integrated):
    verifier, _, _, anchor, _ = integrated["ontology_case"]
    parent = integrated["graph_case"]["parent"]
    child = integrated["graph_case"]["child"]
    extra = replace(child, holon_id="research.holon.ghost")
    result, overfull = verifier.verify(anchor.root, (parent, child, extra))
    assert result.status == "PASS_ONTOLOGY_MEMBERSHIP_ONLY"
    integrated["ontologies"].put(overfull)
    assert _deny(integrated, ontology_root=overfull.root) == (
        "GRAPH_ONTOLOGY_SNAPSHOT_SET_MISMATCH",
    )


def test_same_holon_id_with_different_metadata_cannot_be_transplanted(integrated):
    verifier, _, _, anchor, _ = integrated["ontology_case"]
    parent = integrated["graph_case"]["parent"]
    child = replace(
        integrated["graph_case"]["child"],
        invariants=("not the verified original invariant",),
    )
    result, mismatched = verifier.verify(anchor.root, (parent, child))
    assert result.status == "PASS_ONTOLOGY_MEMBERSHIP_ONLY"
    integrated["ontologies"].put(mismatched)
    assert _deny(integrated, ontology_root=mismatched.root) == (
        "GRAPH_ONTOLOGY_SNAPSHOT_SET_MISMATCH",
    )


def test_missing_graph_receipt_cannot_be_self_certified(integrated):
    del integrated["graphs"].values[integrated["graph"].root]
    assert _deny(integrated) == ("GRAPH_RECEIPT_UNTRUSTED",)


def test_missing_ontology_receipt_cannot_be_self_certified(integrated):
    del integrated["ontologies"].values[integrated["ontology"].root]
    assert _deny(integrated) == ("ONTOLOGY_RECEIPT_UNTRUSTED",)


def test_valid_hex_hash_but_missing_store_denied(integrated):
    root = "0" * 64
    assert _deny(integrated, graph_root=root) == ("GRAPH_RECEIPT_UNTRUSTED",)
    assert _deny(integrated, ontology_root=root) == ("ONTOLOGY_RECEIPT_UNTRUSTED",)


@pytest.mark.parametrize("bad", ("", "abc", "f" * 63, "Z" * 64))
def test_malformed_receipt_root_denied(integrated, bad):
    assert _deny(integrated, graph_root=bad) == (
        "GRAPH_ONTOLOGY_RECEIPT_ROOT_INVALID",
    )
    assert _deny(integrated, ontology_root=bad) == (
        "GRAPH_ONTOLOGY_RECEIPT_ROOT_INVALID",
    )


def test_swapped_ontology_root_in_trusted_store_denied(integrated):
    genuine = integrated["ontology"]
    impostor = replace(genuine, verification_root="e" * 64)
    integrated["ontologies"].values[genuine.root] = impostor
    assert _deny(integrated) == ("ONTOLOGY_RECEIPT_UNTRUSTED",)


def test_swapped_graph_root_in_trusted_store_denied(integrated):
    original = integrated["graph"]
    forged = replace(original, edge_count=23)
    integrated["graphs"].values[original.root] = forged
    assert _deny(integrated) == ("GRAPH_RECEIPT_UNTRUSTED",)


def test_duplicate_snapshots_cannot_falsely_pass_full_graph(integrated):
    original = integrated["graph"]
    forged = replace(
        original,
        verified_snapshot_roots=(
            original.verified_snapshot_roots[0],
            original.verified_snapshot_roots[0],
        ),
    )
    integrated["graphs"].put(forged)
    assert _deny(integrated, graph_root=forged.root) == (
        "GRAPH_ONTOLOGY_SNAPSHOT_SET_MISMATCH",
    )


def test_valid_but_independent_proofs_are_not_composable_without_join(integrated):
    # Both of the source proofs pass in isolation. Joining tests exact common
    # identity and scope; mere "PASS" labels are insufficient.
    v = integrated["ontology_case"][0]
    _, independent = v.verify(
        integrated["ontology_case"][3].root,
        (integrated["graph_case"]["parent"],),
    )
    assert independent is not None and independent.authority_class == "NONE"
    assert integrated["graph"].authority_class == "NONE"
    integrated["ontologies"].put(independent)
    assert _deny(integrated, ontology_root=independent.root) == (
        "GRAPH_ONTOLOGY_SNAPSHOT_SET_MISMATCH",
    )
