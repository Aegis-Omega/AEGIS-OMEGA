"""Fail-closed interchange profile tests for native holon Python/TS parity."""
from __future__ import annotations

from dataclasses import asdict

import pytest

from harness.sdk.holon_meaning_bridge import HolonSnapshotV1
from harness.sdk.meaning_heritage import canonical_hash
from harness.tests.emit_holon_parity_vectors import (
    HolonParityProfileError,
    MAX_EXACT_INTEGER,
    check_interchange_value,
    generate_vectors,
)


def test_vectors_cover_real_holon_contract_roots():
    vectors = generate_vectors()
    labels = {v["label"] for v in vectors}
    assert len(labels) == len(vectors) >= 45
    assert {
        "parent_snapshot", "child_snapshot", "source_occurrence",
        "meaning_lens", "context_binding_receipt", "meaning_receipt",
        "graph_manifest", "research_source_attestation_shape_only",
        "graph_receipt_shape_only",
    } <= labels
    for vec in vectors:
        assert len(vec["expected_root"]) == 64
        assert canonical_hash(vec["domain"], vec["value"]) == vec["expected_root"]
        check_interchange_value({"domain": vec["domain"], "value": vec["value"]})


def test_parity_vectors_are_replay_deterministic():
    assert generate_vectors() == generate_vectors()


@pytest.mark.parametrize(
    ("bad", "reason"),
    [
        ({"n": 1.25}, "UNSUPPORTED_TYPE"),
        ({"n": 1e20}, "UNSUPPORTED_TYPE"),
        ({"n": MAX_EXACT_INTEGER + 1}, "UNSAFE_INTEGER"),
        ({"n": -(MAX_EXACT_INTEGER + 1)}, "UNSAFE_INTEGER"),
        ({"é": "value"}, "KEY_NOT_ASCII"),
        ({"n": "\ud800"}, "SURROGATE"),
        ({"n": "\udc00"}, "SURROGATE"),
        ({"n": object()}, "UNSUPPORTED_TYPE"),
        ({42: "int key"}, "KEY_NOT_ASCII"),
    ],
)
def test_unrepresentable_interchange_values_are_rejected(bad, reason):
    with pytest.raises(HolonParityProfileError, match=reason):
        check_interchange_value(bad)


def test_interchange_preserves_unicode_text_without_normalization():
    # These are distinct payloads. Unicode compatibility/cultural equivalence
    # is not conferred by JSON byte agreement.
    composed = {"label": "é"}
    decomposed = {"label": "e\u0301"}
    check_interchange_value(composed)
    check_interchange_value(decomposed)
    assert canonical_hash("HOLON_CONTEXT", composed) != canonical_hash(
        "HOLON_CONTEXT", decomposed
    )


def test_shared_ontology_term_does_not_merge_distinct_holon_id():
    base = {
        "holon_id": "scope.alpha",
        "scale": "atomic",
        "tier": "T2",
        "part_of": [],
        "composed_of": [],
        "invariants": ["preserve origin"],
        "interaction_surface": ["READ_ONLY"],
        "provenance": ["research-source-id"],
        "ontology_term": "Holon",
    }
    first = HolonSnapshotV1.from_typescript_record(base)
    second = HolonSnapshotV1.from_typescript_record(
        {**base, "holon_id": "scope.beta"}
    )
    check_interchange_value(asdict(first))
    check_interchange_value(asdict(second))
    assert first.root != second.root


def test_interchange_profile_rejects_boolean_subclasses_from_container_types():
    # "bool" and "int" are separate canonical JSON atoms in both runtimes.
    check_interchange_value({"valid": True, "count": 1, "empty": None})
    assert canonical_hash("HOLON_BOOL_INT", {"valid": True}) != canonical_hash(
        "HOLON_BOOL_INT", {"valid": 1}
    )
