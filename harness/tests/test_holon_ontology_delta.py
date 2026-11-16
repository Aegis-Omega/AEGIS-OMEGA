"""Fail-closed, exact-source ontology drift checks for AEGIS HOLON cross-branch work.

Synthetic changed source bytes are anchored to actual, pinned main ontology
fixture bytes. These tests validate detection, NOT the independent source
identity or admissibility of PR #810/813's changed ontology. That actual blob
was inspected via authenticated GitHub fetch_file and recorded separately.
"""
from __future__ import annotations

import hashlib
from dataclasses import replace
from pathlib import Path

import pytest

from harness.sdk.holon_ontology_binding import (
    ONTOLOGY_PATH,
    OntologyGitAnchorV1,
    parse_core_terms,
)
from harness.sdk.holon_ontology_delta import (
    CHANGED,
    DENIED,
    UNCHANGED,
    HolonOntologyTermDeltaVerifierV1,
    exact_core_term_fingerprints,
)
from harness.tests.test_holon_ontology_binding import (
    AnchorStore,
    BlobStore,
    PINNED_BASE_COMMIT,
    PINNED_GIT_BLOB,
    git_blob_hash,
    sha,
)

SYNTHETIC_COMMIT = "c" * 40
ORIGINAL_LINE = "State management — append-only event log with hash chaining"
REPLACEMENT_LINE = "In-place circular chained digest ring; event payloads are not stored"


@pytest.fixture
def case():
    original = Path(ONTOLOGY_PATH).read_bytes()
    assert git_blob_hash(original) == PINNED_GIT_BLOB
    original_text = original.decode("utf-8")
    assert original_text.count(ORIGINAL_LINE) == 1
    rewritten = original_text.replace(ORIGINAL_LINE, REPLACEMENT_LINE).encode("utf-8")
    old = OntologyGitAnchorV1(
        commit_sha=PINNED_BASE_COMMIT,
        git_blob_sha=git_blob_hash(original),
        content_sha256=sha(original),
    )
    new = OntologyGitAnchorV1(
        commit_sha=SYNTHETIC_COMMIT,
        git_blob_sha=git_blob_hash(rewritten),
        content_sha256=sha(rewritten),
    )
    anchors, blobs = AnchorStore(), BlobStore()
    anchors.put(old)
    anchors.put(new)
    blobs.put(old, original)
    blobs.put(new, rewritten)
    verifier = HolonOntologyTermDeltaVerifierV1(
        anchors=anchors, blobs=blobs,
    )
    return verifier, anchors, blobs, old, new, original, rewritten


def test_names_are_unchanged_but_m123_definition_requires_review(case):
    verifier, _, _, before, after, old_bytes, new_bytes = case
    assert parse_core_terms(old_bytes) == parse_core_terms(new_bytes)
    result, report = verifier.verify(before.root, after.root)
    assert result.status == CHANGED
    assert result.error_codes == ("REVIEW_CHANGED_CORE_TERM_SOURCE",)
    assert report is not None and report.authority_class == "NONE"
    assert report.entire_document_identical is False
    assert report.changed_term_names == ("M1 / M2 / M3",)
    assert report.added_term_names == ()
    assert report.removed_term_names == ()
    assert len(report.unchanged_term_names) == 15
    assert len(report.term_source_fingerprints_before) == 16
    assert len(report.term_source_fingerprints_after) == 16
    assert report.prior_git_blob_sha == before.git_blob_sha
    assert report.candidate_git_blob_sha == after.git_blob_sha
    assert result.verification_root == report.verification_root
    assert len(report.root) == 64
    assert verifier.verify(before.root, after.root) == (result, report)


def test_unmodified_source_can_pass_source_identity_without_inheriting_authority(case):
    verifier, anchors, blobs, before, _, original, _ = case
    identical = OntologyGitAnchorV1(
        commit_sha="d" * 40,
        git_blob_sha=git_blob_hash(original),
        content_sha256=sha(original),
    )
    anchors.put(identical)
    blobs.put(identical, original)
    result, report = verifier.verify(before.root, identical.root)
    assert result.status == UNCHANGED
    assert result.error_codes == ()
    assert report is not None and report.authority_class == "NONE"
    assert report.entire_document_identical is True
    assert report.changed_term_names == ()
    assert report.unchanged_term_names == parse_core_terms(original)
    assert result.verification_root == report.verification_root


def test_only_noncore_governance_drift_also_requires_review(case):
    verifier, anchors, blobs, before, _, original, _ = case
    assert original.count(b"## Epistemic Tier: T0") == 1
    synthetic = original.replace(
        b"## Epistemic Tier: T0", b"## Epistemic Tier: T0\n## Review migration required",
        1,
    )
    # Replacing outside Core Terms leaves ALL 16 term bodies identical.
    new = anchors.put(OntologyGitAnchorV1(
        commit_sha="e" * 40,
        git_blob_sha=git_blob_hash(synthetic),
        content_sha256=sha(synthetic),
    ))
    blobs.put(new, synthetic)
    result, report = verifier.verify(before.root, new.root)
    assert result.status == CHANGED
    assert result.error_codes == ("REVIEW_CHANGED_NON_CORE_SOURCE",)
    assert report is not None and report.entire_document_identical is False
    assert report.changed_term_names == ()
    assert report.added_term_names == ()
    assert report.removed_term_names == ()
    assert report.term_source_fingerprints_before == report.term_source_fingerprints_after


def test_whitespace_only_definition_edit_is_conservative_review(case):
    verifier, anchors, blobs, before, _, original, _ = case
    assert original.count(b"### Holon\n") == 1
    changed = original.replace(b"### Holon\n", b"### Holon\n\n", 1)
    candidate = anchors.put(OntologyGitAnchorV1(
        commit_sha="e" * 40,
        git_blob_sha=git_blob_hash(changed),
        content_sha256=sha(changed),
    ))
    blobs.put(candidate, changed)
    result, report = verifier.verify(before.root, candidate.root)
    assert result.status == CHANGED
    assert report is not None
    assert result.error_codes == ("REVIEW_CHANGED_CORE_TERM_SOURCE",)
    assert report.changed_term_names == ("Holon",)


def test_added_canonical_term_is_not_silently_admitted(case):
    verifier, anchors, blobs, before, _, original, _ = case
    section = b"### Holon\n"
    assert original.count(section) == 1
    changed = original.replace(
        section,
        b"### NewTerm\nNew named definition under review.\n\n" + section,
        1,
    )
    new = anchors.put(OntologyGitAnchorV1(
        commit_sha="e" * 40,
        git_blob_sha=git_blob_hash(changed),
        content_sha256=sha(changed),
    ))
    blobs.put(new, changed)
    result, report = verifier.verify(before.root, new.root)
    assert result.status == CHANGED
    assert report is not None
    assert report.added_term_names == ("NewTerm",)
    assert "Holon" in report.unchanged_term_names


def test_removed_canonical_term_is_not_silently_admitted(case):
    verifier, anchors, blobs, before, _, original, _ = case
    section = b"### Holon\n"
    assert original.count(section) == 1
    changed = original.replace(section, b"### OmittedHolon\n", 1)
    new = anchors.put(OntologyGitAnchorV1(
        commit_sha="e" * 40,
        git_blob_sha=git_blob_hash(changed),
        content_sha256=sha(changed),
    ))
    blobs.put(new, changed)
    result, report = verifier.verify(before.root, new.root)
    assert result.status == CHANGED and report is not None
    assert report.removed_term_names == ("Holon",)
    assert report.added_term_names == ("OmittedHolon",)


def test_reverse_comparison_records_drift_without_invented_migration(case):
    verifier, _, _, before, after, *_ = case
    forward, f_receipt = verifier.verify(before.root, after.root)
    reverse, r_receipt = verifier.verify(after.root, before.root)
    assert forward.status == CHANGED == reverse.status
    assert f_receipt is not None and r_receipt is not None
    assert f_receipt.changed_term_names == r_receipt.changed_term_names
    assert f_receipt.root != r_receipt.root
    assert f_receipt.authority_class == r_receipt.authority_class == "NONE"


def test_missing_prior_authenticated_anchor_denied(case):
    verifier, anchors, _, before, after, *_ = case
    del anchors.records[before.root]
    result, receipt = verifier.verify(before.root, after.root)
    assert result.status == DENIED
    assert result.error_codes == ("PRIOR_ONTOLOGY_SOURCE_UNTRUSTED",)
    assert receipt is None


def test_missing_candidate_anchor_denied(case):
    verifier, anchors, _, before, after, *_ = case
    del anchors.records[after.root]
    result, receipt = verifier.verify(before.root, after.root)
    assert result.status == DENIED
    assert result.error_codes == ("CANDIDATE_ONTOLOGY_SOURCE_UNTRUSTED",)
    assert receipt is None


def test_candidate_source_bytes_missing_denied(case):
    verifier, _, blobs, before, after, *_ = case
    del blobs.data[(after.repository, after.commit_sha, after.path)]
    result, receipt = verifier.verify(before.root, after.root)
    assert result.status == DENIED
    assert result.error_codes == ("CANDIDATE_ONTOLOGY_SOURCE_UNTRUSTED",)
    assert receipt is None


def test_candidate_source_bytes_tampered_denied(case):
    verifier, _, blobs, before, after, *_ = case
    blobs.put(after, b"wrong bytes")
    result, receipt = verifier.verify(before.root, after.root)
    assert result.status == DENIED
    assert result.error_codes == ("CANDIDATE_ONTOLOGY_SOURCE_UNTRUSTED",)
    assert receipt is None


def test_forged_anchor_rejected_even_if_supplied_under_old_root(case):
    verifier, anchors, _, before, after, *_ = case
    anchors.records[after.root] = replace(after, content_sha256="f" * 64)
    result, receipt = verifier.verify(before.root, after.root)
    assert result.status == DENIED
    assert result.error_codes == ("CANDIDATE_ONTOLOGY_SOURCE_UNTRUSTED",)
    assert receipt is None


def test_invalid_or_noncanonical_core_terms_denied(case):
    verifier, anchors, blobs, before, _, original, _ = case
    malformed = original.replace(b"### Holon\n", b"### Holon\nNo.\n### Holon\n", 1)
    updated = anchors.put(OntologyGitAnchorV1(
        commit_sha="f" * 40,
        git_blob_sha=git_blob_hash(malformed),
        content_sha256=sha(malformed),
    ))
    blobs.put(updated, malformed)
    result, receipt = verifier.verify(before.root, updated.root)
    assert result.status == DENIED
    assert result.error_codes == ("ONTOLOGY_CORE_TERM_PARSE_FAILED",)
    assert receipt is None


def test_same_source_with_missing_proof_store_not_accepted(case):
    verifier, _, blobs, before, after, *_ = case
    del blobs.data[(before.repository, before.commit_sha, before.path)]
    result, receipt = verifier.verify(before.root, after.root)
    assert result.status == DENIED
    assert result.error_codes == ("PRIOR_ONTOLOGY_SOURCE_UNTRUSTED",)
    assert receipt is None


def test_fingerprints_have_independent_source_specific_roots(case):
    _, _, _, _, _, old_bytes, new_bytes = case
    left, right = dict(exact_core_term_fingerprints(old_bytes)), dict(
        exact_core_term_fingerprints(new_bytes)
    )
    assert set(left) == set(right)
    assert left["M1 / M2 / M3"] != right["M1 / M2 / M3"]
    assert all(
        left[name] == right[name] for name in left if name != "M1 / M2 / M3"
    )
