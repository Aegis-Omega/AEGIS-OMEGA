"""Exact Git-blob ontology membership tests for holon canonical names.

Only GitHub-returned source bytes under an independently accepted commit/blob
anchor can be trusted by a real adapter. These finite readback fixtures do not
constitute a deployed trusted Git endpoint or an ontology truth proof.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from harness.sdk.holon_meaning_bridge import HolonSnapshotV1
from harness.sdk.holon_ontology_binding import (
    HolonOntologyBindingVerifierV1,
    HolonOntologyError,
    OntologyGitAnchorV1,
    REPOSITORY,
    ONTOLOGY_PATH,
    parse_core_terms,
)


# Main Git SHA is the verified ancestor of the PR at this checkpoint.
PINNED_BASE_COMMIT = "ec5fea38b9abee0bf850a1d39b52bdd3fb7197ed"
# GitHub blob SHA returned by authenticated fetch_file at this commit.
PINNED_GIT_BLOB = "6b91f34a778b20b95f6d55820e2c26f91e54ce5c"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob_hash(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


class AnchorStore:
    def __init__(self):
        self.records = {}

    def put(self, anchor):
        self.records[anchor.root] = anchor
        return anchor

    def fetch_verified(self, root):
        return self.records.get(root)


class BlobStore:
    def __init__(self):
        self.data = {}

    def put(self, anchor, payload):
        self.data[(anchor.repository, anchor.commit_sha, anchor.path)] = payload

    def fetch_verified(self, repository, commit_sha, path):
        return self.data.get((repository, commit_sha, path))


def holon(holon_id="research.holon.alpha", term="Holon"):
    return HolonSnapshotV1(
        holon_id=holon_id,
        scale="atomic",
        tier="T2",
        part_of=(),
        composed_of=(),
        invariants=("keep context",),
        interaction_surface=("READ_ONLY",),
        provenance=("research-doc-id",),
        ontology_term=term,
    )


@pytest.fixture
def case():
    # This is a repository copy at checkout, not an authenticated HTTPS fetch.
    payload = Path(ONTOLOGY_PATH).read_bytes()
    assert git_blob_hash(payload) == PINNED_GIT_BLOB, "ontology source drift from pinned main"
    anchor = OntologyGitAnchorV1(
        commit_sha=PINNED_BASE_COMMIT,
        git_blob_sha=PINNED_GIT_BLOB,
        content_sha256=sha(payload),
    )
    anchors, blobs = AnchorStore(), BlobStore()
    anchors.put(anchor)
    blobs.put(anchor, payload)
    verifier = HolonOntologyBindingVerifierV1(anchors=anchors, blobs=blobs)
    return verifier, anchors, blobs, anchor, payload


def test_real_repo_ontology_membership_and_root_is_verified(case):
    verifier, _, _, anchor, payload = case
    assert b"## Core Terms\n" in payload
    result, receipt = verifier.verify(anchor.root, (holon(), holon("research.holon.beta"),))
    assert result.status == "PASS_ONTOLOGY_MEMBERSHIP_ONLY"
    assert receipt is not None and receipt.authority_class == "NONE"
    assert "Holon" in receipt.canonical_term_names
    assert "Provenance" in receipt.canonical_term_names
    assert receipt.ontology_content_sha256 == sha(payload)
    assert result.verification_root == receipt.verification_root
    assert receipt.root and len(receipt.root) == 64


def test_reordering_holons_preserves_ontology_binding(case):
    verifier, _, _, anchor, _ = case
    a, b = holon("unit.a"), holon("unit.b")
    first = verifier.verify(anchor.root, (a, b))[1]
    second = verifier.verify(anchor.root, (b, a))[1]
    assert first is not None and first == second


def test_unknown_ontology_term_fails_closed(case):
    verifier, _, _, anchor, _ = case
    result, receipt = verifier.verify(anchor.root, (holon(term="Meaning invented here"),))
    assert receipt is None
    assert result.error_codes == ("ONTOLOGY_TERM_UNDECLARED",)


def test_contextual_meaning_is_not_canonical_term(case):
    verifier, _, _, anchor, _ = case
    result, receipt = verifier.verify(anchor.root, (holon(term="latin-letter-A"),))
    assert receipt is None
    assert result.error_codes == ("ONTOLOGY_TERM_UNDECLARED",)


def test_reused_id_for_distinct_holons_denied(case):
    verifier, _, _, anchor, _ = case
    result, receipt = verifier.verify(anchor.root, (holon(), holon()))
    assert receipt is None
    assert result.error_codes == ("ONTOLOGY_HOLON_ID_DUPLICATE",)


def test_missing_authenticated_anchor_denied(case):
    verifier, anchors, _, anchor, _ = case
    del anchors.records[anchor.root]
    result, receipt = verifier.verify(anchor.root, (holon(),))
    assert receipt is None
    assert result.error_codes == ("ONTOLOGY_ANCHOR_UNTRUSTED",)


def test_anchor_hash_mismatch_denied(case):
    verifier, anchors, _, anchor, _ = case
    anchors.records[anchor.root] = replace(anchor, content_sha256=sha(b"not the original"))
    result, receipt = verifier.verify(anchor.root, (holon(),))
    assert receipt is None
    assert result.error_codes == ("ONTOLOGY_ANCHOR_UNTRUSTED",)


def test_missing_git_blob_denied(case):
    verifier, _, blobs, anchor, _ = case
    del blobs.data[(REPOSITORY, PINNED_BASE_COMMIT, ONTOLOGY_PATH)]
    result, receipt = verifier.verify(anchor.root, (holon(),))
    assert receipt is None
    assert result.error_codes == ("ONTOLOGY_GIT_BLOB_UNTRUSTED",)


def test_mutated_git_blob_bytes_denied(case):
    verifier, _, blobs, anchor, payload = case
    blobs.put(anchor, payload.replace(b"### Holon", b"### Contradiction", 1))
    result, receipt = verifier.verify(anchor.root, (holon(),))
    assert receipt is None
    assert result.error_codes == ("ONTOLOGY_CONTENT_SHA256_MISMATCH",)


def test_relabelled_git_blob_with_updated_content_sha_but_stale_blob_id_denied(case):
    verifier, anchors, blobs, anchor, payload = case
    mutated = payload + b"\n"
    forged = replace(anchor, content_sha256=sha(mutated))
    anchors.put(forged)
    blobs.put(forged, mutated)
    result, receipt = verifier.verify(forged.root, (holon(),))
    assert receipt is None
    assert result.error_codes == ("ONTOLOGY_GIT_BLOB_SHA_MISMATCH",)


def test_parser_duplicate_terms_denied(case):
    _, _, _, _, payload = case
    text = payload.decode("utf-8")
    duplicated = text.replace("### Holon\n", "### Holon\nNew description\n### Holon\n", 1)
    with pytest.raises(HolonOntologyError, match="ONTOLOGY_DUPLICATE_OR_INVALID_TERM"):
        parse_core_terms(duplicated.encode("utf-8"))


def test_parser_missing_core_section_denied(case):
    _, _, _, _, payload = case
    with pytest.raises(HolonOntologyError, match="ONTOLOGY_CORE_TERMS_MISSING"):
        parse_core_terms(payload.replace(b"## Core Terms", b"## Terms Not Verified"))


def test_parser_blank_term_denied(case):
    _, _, _, _, payload = case
    with pytest.raises(HolonOntologyError, match="ONTOLOGY_DUPLICATE_OR_INVALID_TERM"):
        parse_core_terms(payload.replace(b"### Holon\n", b"###  \n", 1))


def test_parser_undecodable_source_denied():
    with pytest.raises(HolonOntologyError, match="ONTOLOGY_NOT_UTF8"):
        parse_core_terms(b"\xff \xfe")


def test_anchor_fields_fixed_to_git_repo_and_source_path():
    anchor = OntologyGitAnchorV1(
        commit_sha=PINNED_BASE_COMMIT,
        git_blob_sha=PINNED_GIT_BLOB,
        content_sha256=sha(b"synthetic"),
    )
    assert anchor.repository == REPOSITORY and anchor.path == ONTOLOGY_PATH
    with pytest.raises(ValueError, match="init=False"):
        replace(anchor, repository="somewhere.else")


def test_empty_holon_set_rejected(case):
    verifier, _, _, anchor, _ = case
    assert verifier.verify(anchor.root, ())[0].error_codes == ("ONTOLOGY_HOLONS_INVALID",)


def test_unknown_ontology_on_different_holon_still_rejected(case):
    verifier, _, _, anchor, _ = case
    a, b = holon("known", "Holon"), holon("unknown", "NotInOntology")
    assert verifier.verify(anchor.root, (a, b))[0].error_codes == ("ONTOLOGY_TERM_UNDECLARED",)
