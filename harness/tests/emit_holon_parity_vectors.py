"""Deterministic Python side of AEGIS holon Python/TypeScript canonical parity.

This is a *narrow interchange profile*, NOT a replacement for the repository's
Python canonical_hash or a general proof that Python JSON equals RFC 8785 JCS.
It binds actual holon dataclasses, roots, and receipts to executable TS vectors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from harness.sdk.sovereign_execution import canonical_bytes, canonical_hash
from harness.sdk.holon_meaning_bridge import (
    DOM_CONTEXT_BINDING_RECEIPT,
    DOM_HOLON_MEANING_LENS,
    DOM_HOLON_MEANING_RECEIPT,
    DOM_HOLON_SNAPSHOT,
    DOM_SOURCE_OCCURRENCE,
    ContextBindingReceiptV1,
    ContextualReadingV1,
    HolonMeaningLensV1,
    HolonMeaningReceiptV1,
    HolonSnapshotV1,
    SourceOccurrenceV1,
)
from harness.sdk.holon_graph_verifier import (
    DOM_GRAPH_MANIFEST,
    DOM_GRAPH_RECEIPT,
    DOM_GRAPH_VERIFICATION,
    DOM_RESEARCH_SOURCE,
    HolonGraphManifestV1,
    HolonGraphNodeRefV1,
    HolonGraphReceiptV1,
    ResearchSourceAttestationV1,
)

# Integers larger than this are not exact as JavaScript Number values.
MAX_EXACT_INTEGER = (1 << 53) - 1


class HolonParityProfileError(ValueError):
    pass


def check_interchange_value(value: Any, *, path: str = "$") -> None:
    """Reject all values outside the tested Python/TS holon serialization subset.

    ASCII JSON object *keys* are necessary for this profile's sorting guarantee.
    Unicode *values* are preserved byte-for-byte, without normalization.
    Floats, surrogate code points, non-string keys, and unsafe integers fail.
    """
    if value is None or type(value) is bool:
        return
    if type(value) is int:
        if abs(value) > MAX_EXACT_INTEGER:
            raise HolonParityProfileError(f"{path}:UNSAFE_INTEGER")
        return
    if type(value) is str:
        if any(0xD800 <= ord(ch) <= 0xDFFF for ch in value):
            raise HolonParityProfileError(f"{path}:SURROGATE")
        return
    if type(value) in (tuple, list):
        for index, element in enumerate(value):
            check_interchange_value(element, path=f"{path}[{index}]")
        return
    if type(value) is dict:
        for key, element in value.items():
            if type(key) is not str or not key.isascii():
                raise HolonParityProfileError(f"{path}:KEY_NOT_ASCII")
            check_interchange_value(key, path=f"{path}.key")
            check_interchange_value(element, path=f"{path}.{key}")
        return
    raise HolonParityProfileError(f"{path}:UNSUPPORTED_TYPE:{type(value).__name__}")


def _sha(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def generate_vectors() -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []

    def add(label: str, domain: str, value: Any, expected_root: str | None = None) -> None:
        check_interchange_value({"domain": domain, "value": value})
        bytes_value = canonical_bytes({"domain": domain, "value": value})
        digest = canonical_hash(domain, value)
        if hashlib.sha256(bytes_value).hexdigest() != digest:
            raise AssertionError("Python canonical_hash primitive changed")
        if expected_root is not None and digest != expected_root:
            raise AssertionError(f"{label}: source object root diverges from vector")
        result.append({
            "label": label,
            "domain": domain,
            "value": value,
            "expected_root": digest,
            "expected_canonical_hex": bytes_value.hex(),
        })

    document_id = "1BsjFB_9_nmTp3_VzscrSuUO-yFGWVOFp"  # source ID, NOT a fetched document
    parent = HolonSnapshotV1(
        holon_id="research.holon.semantic_context",
        scale="molecular",
        tier="T2",
        part_of=(),
        composed_of=("research.holon.symbol_A",),
        invariants=("source bytes are immutable", "riječi imaju porijeklo"),
        interaction_surface=("READ_ONLY",),
        provenance=(document_id,),
        ontology_term="Holon",
    )
    child = HolonSnapshotV1(
        holon_id="research.holon.symbol_A",
        scale="atomic",
        tier="T2",
        part_of=(parent.holon_id,),
        composed_of=(),
        invariants=("A is not its interpretation", 'context: "a/b"\nwith\\escapes'),
        interaction_surface=("SEMANTIC_READ_ONLY",),
        provenance=(document_id,),
        ontology_term="Holon",
    )
    for name, holon in (("parent_snapshot", parent), ("child_snapshot", child)):
        add(name, DOM_HOLON_SNAPSHOT, asdict(holon), holon.root)

    origin = b"document: A (not a universal meaning)"
    occurrence = SourceOccurrenceV1(
        artifact_root=hashlib.sha256(origin).hexdigest(),
        start_byte=origin.index(b"A"),
        end_byte=origin.index(b"A") + 1,
        carrier_root=hashlib.sha256(b"A").hexdigest(),
    )
    add("source_occurrence", DOM_SOURCE_OCCURRENCE, asdict(occurrence), occurrence.root)

    readings = tuple(
        ContextualReadingV1(
            reading_id=reading_id,
            context_root=_sha(f"context:{reading_id}"),
            envelope_root=_sha(f"envelope:{reading_id}"),
            heritage_receipt_root=_sha(f"heritage:{reading_id}"),
            context_binding_receipt_root=_sha(f"binding:{reading_id}"),
        )
        for reading_id in ("latin_letter", "dna_base")
    )
    lens = HolonMeaningLensV1(child, occurrence, readings)
    add("meaning_lens", DOM_HOLON_MEANING_LENS, {
        "schema_version": lens.schema_version,
        "holon_root": lens.holon.root,
        "occurrence_root": lens.occurrence.root,
        "readings": sorted((asdict(r) for r in lens.readings), key=lambda r: r["reading_id"]),
    }, lens.root)

    binding = ContextBindingReceiptV1(
        reading_id="latin_letter",
        holon_root=child.root,
        occurrence_root=occurrence.root,
        context_root=readings[0].context_root,
        envelope_root=readings[0].envelope_root,
        transform_root=_sha("transform:latin"),
        derived_root=_sha("derived:latin"),
        verifier_root=_sha("verifier:latin"),
        policy_root=_sha("policy:latin"),
    )
    add("context_binding_receipt", DOM_CONTEXT_BINDING_RECEIPT, asdict(binding), binding.root)

    meaning_receipt = HolonMeaningReceiptV1(
        lens_root=lens.root,
        occurrence_root=occurrence.root,
        holon_root=child.root,
        heritage_receipt_roots=tuple(sorted(r.heritage_receipt_root for r in readings)),
        context_binding_receipt_roots=tuple(sorted(r.context_binding_receipt_root for r in readings)),
        verification_root=_sha("meaning:verification"),
    )
    add("meaning_receipt", DOM_HOLON_MEANING_RECEIPT, asdict(meaning_receipt), meaning_receipt.root)

    manifest = HolonGraphManifestV1((
        HolonGraphNodeRefV1(parent.holon_id, parent.root),
        HolonGraphNodeRefV1(child.holon_id, child.root, (meaning_receipt.root,)),
    ))
    value = {
        "schema_version": manifest.schema_version,
        "nodes": [{
            "holon_id": n.holon_id,
            "snapshot_root": n.snapshot_root,
            "meaning_receipt_roots": sorted(n.meaning_receipt_roots),
        } for n in sorted(manifest.nodes, key=lambda n: n.holon_id)],
    }
    add("graph_manifest", DOM_GRAPH_MANIFEST, value, manifest.root)

    research = ResearchSourceAttestationV1(
        document_id=document_id,
        content_root=_sha("example bytes, NOT actual Drive document"),
        reviewed_tier="T2",
        review_receipt_root=_sha("synthetic review"),
        verifier_root=_sha("synthetic verifier"),
        policy_root=_sha("synthetic policy"),
    )
    add("research_source_attestation_shape_only", DOM_RESEARCH_SOURCE, asdict(research), research.root)

    graph_verification_root = canonical_hash(DOM_GRAPH_VERIFICATION, {
        "manifest_root": manifest.root,
        "verified_snapshot_roots": tuple(sorted((child.root, parent.root))),
        "verified_source_attestation_roots": (research.root,),
        "verified_meaning_receipt_roots": (meaning_receipt.root,),
        "node_count": 2,
        "edge_count": 1,
        "source_count": 1,
        "meaning_receipt_count": 1,
        "contextual_reading_count": 2,
        "competing_reading_count": 1,
        "status": "PASS_STRUCTURAL_ONLY",
    })
    receipt = HolonGraphReceiptV1(
        manifest.root, tuple(sorted((child.root, parent.root))),
        (research.root,), (meaning_receipt.root,),
        2, 1, 1, 1, 2, 1, graph_verification_root,
    )
    add("graph_receipt_shape_only", DOM_GRAPH_RECEIPT, asdict(receipt), receipt.root)

    unicode_samples = (
        "život", "e\u0301", "\u00e9", "العلم", "漢字", "🤖", "\u2028",
        "line\nbreak", "tab\tvalue", "back\\slash", 'quote"mark',
        "slash/forward", "\x00", "\x1f", "Caffè",
    )
    for index, value in enumerate(unicode_samples):
        add(f"text_value_{index}", "AEGIS_HOLON_PARITY_TEXT_V1", {
            "symbol": value,
            "meaning": f"example:{index}",
            "context": {"origin": "research", "admitted": False, "span": [1, 2]},
        })

    for n in range(32):
        add(f"integer_and_nested_{n}", "AEGIS_HOLON_PARITY_NESTED_V1", {
            "counter": n,
            "negative": -n,
            "limit": MAX_EXACT_INTEGER - n,
            "readings": [{"id": f"r{n}", "accept": n % 2 == 0, "note": None}],
            "metadata": {"a": {"z": n + 1, "b": [False, True, None]}, "z": n},
        })
    add("last_safe_negative_integer", "AEGIS_HOLON_PARITY_BOUNDS_V1", {
        "limit": -MAX_EXACT_INTEGER,
    })
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    records = generate_vectors()
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    raw = "".join(
        json.dumps(row, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in records
    ).encode("utf-8")
    out.write_bytes(raw)
    print(f"HOLON_PYTHON_VECTORS={len(records)}")
    print(f"HOLON_PYTHON_VECTORS_SHA256={hashlib.sha256(raw).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
