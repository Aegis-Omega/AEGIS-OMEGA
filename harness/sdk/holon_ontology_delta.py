"""AEGIS T0 ontology definition drift audit between independently trusted Git blobs.

AEGIS canonical names can remain identical while definitions change. A
membership-only verifier does not establish that a term has unchanged meaning.
This tool compares *exact bytes of every Markdown core-term definition* after
two separately trusted Git-source anchors are validated. It DOES NOT decide
whether differing definitions are equivalent or authorize rebinding a holon
from one ontology version to another.

Each proof-of-source store is external. This implementation validates Git blob
hashes and SHA-256; it cannot independently authenticate Git provider identity,
human semantic interpretation, or policy review.
"""
from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from typing import Protocol

from harness.sdk.holon_ontology_binding import (
    HEX64,
    REPOSITORY,
    ONTOLOGY_PATH,
    HolonOntologyError,
    OntologyGitAnchorV1,
    TrustedOntologyGitAnchorStore,
    TrustedOntologyGitBlobStore,
    parse_core_terms,
)
from harness.sdk.meaning_heritage import NO_AUTHORITY, canonical_hash

DOM_TERM_SOURCE = "AEGIS_HOLON_ONTOLOGY_EXACT_TERM_SOURCE_V1"
DOM_DELTA_CHECK = "AEGIS_HOLON_ONTOLOGY_TERM_DELTA_CHECK_V1"
DOM_DELTA_REPORT = "AEGIS_HOLON_ONTOLOGY_TERM_DELTA_REPORT_V1"
UNCHANGED = "PASS_IDENTICAL_ONTOLOGY_SOURCE_ONLY"
CHANGED = "OPEN_ONTOLOGY_SOURCE_REVIEW_REQUIRED"
DENIED = "FAIL_ONTOLOGY_SOURCE_COMPARISON_DENIED"


@dataclass(frozen=True)
class OntologyTermDeltaVerificationV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class OntologyTermDeltaReportV1:
    prior_anchor_root: str
    candidate_anchor_root: str
    prior_git_blob_sha: str
    candidate_git_blob_sha: str
    entire_document_identical: bool
    unchanged_term_names: tuple[str, ...]
    changed_term_names: tuple[str, ...]
    added_term_names: tuple[str, ...]
    removed_term_names: tuple[str, ...]
    term_source_fingerprints_before: tuple[tuple[str, str], ...]
    term_source_fingerprints_after: tuple[tuple[str, str], ...]
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-ontology-term-delta.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOM_DELTA_REPORT, asdict(self))


def exact_core_term_fingerprints(payload: bytes) -> tuple[tuple[str, str], ...]:
    """Fingerprint each exact core-term definition; NEVER infer equivalence.

    This preserves internal whitespace and Unicode bytes. Formatting changes
    therefore trigger review, even when a human may regard them as cosmetic.
    It is a conservative SOURCE DRIFT detector, not semantic classification.
    """
    names = parse_core_terms(payload)
    content = payload.decode("utf-8")
    in_core = False
    current: str | None = None
    bodies: dict[str, list[str]] = {}
    for line in content.splitlines(keepends=True):
        canonical_line = line.removesuffix("\n")
        if canonical_line.startswith("## "):
            if canonical_line == "## Core Terms":
                in_core = True
            elif in_core:
                in_core = False
            current = None
            continue
        if not in_core:
            continue
        if canonical_line.startswith("### "):
            term = canonical_line[4:]
            if term in names:
                current = term
                bodies[current] = []
                continue
        if current is not None:
            bodies[current].append(line)
    if set(bodies) != set(names):
        raise HolonOntologyError("ONTOLOGY_TERM_BODY_EXTRACTION_INCOMPLETE")
    return tuple(sorted(
        (
            name,
            canonical_hash(DOM_TERM_SOURCE, {
                "term_name": name,
                "exact_definition_sha256": hashlib.sha256(
                    "".join(bodies[name]).encode("utf-8")
                ).hexdigest(),
            }),
        )
        for name in names
    ))


class HolonOntologyTermDeltaVerifierV1:
    def __init__(
        self,
        *,
        anchors: TrustedOntologyGitAnchorStore,
        blobs: TrustedOntologyGitBlobStore,
    ) -> None:
        self.anchors = anchors
        self.blobs = blobs

    def _read(self, root: str) -> tuple[OntologyGitAnchorV1, bytes] | None:
        if not isinstance(root, str) or not HEX64.fullmatch(root):
            return None
        anchor = self.anchors.fetch_verified(root)
        if (not isinstance(anchor, OntologyGitAnchorV1)
                or anchor.root != root
                or anchor.authority_class != NO_AUTHORITY
                or anchor.repository != REPOSITORY
                or anchor.path != ONTOLOGY_PATH):
            return None
        blob = self.blobs.fetch_verified(
            anchor.repository, anchor.commit_sha, anchor.path
        )
        if not isinstance(blob, bytes):
            return None
        if hashlib.sha256(blob).hexdigest() != anchor.content_sha256:
            return None
        git_header = b"blob " + str(len(blob)).encode("ascii") + b"\0"
        if hashlib.sha1(git_header + blob).hexdigest() != anchor.git_blob_sha:
            return None
        return anchor, blob

    def verify(
        self, prior_anchor_root: str, candidate_anchor_root: str
    ) -> tuple[OntologyTermDeltaVerificationV1, OntologyTermDeltaReportV1 | None]:
        def deny(code: str):
            return OntologyTermDeltaVerificationV1(DENIED, (code,), None), None

        prior = self._read(prior_anchor_root)
        if prior is None:
            return deny("PRIOR_ONTOLOGY_SOURCE_UNTRUSTED")
        candidate = self._read(candidate_anchor_root)
        if candidate is None:
            return deny("CANDIDATE_ONTOLOGY_SOURCE_UNTRUSTED")
        try:
            before = exact_core_term_fingerprints(prior[1])
            after = exact_core_term_fingerprints(candidate[1])
        except (HolonOntologyError, UnicodeDecodeError):
            return deny("ONTOLOGY_CORE_TERM_PARSE_FAILED")
        old, new = dict(before), dict(after)
        common = set(old) & set(new)
        changed = tuple(sorted(n for n in common if old[n] != new[n]))
        unchanged = tuple(sorted(n for n in common if old[n] == new[n]))
        added = tuple(sorted(set(new) - set(old)))
        removed = tuple(sorted(set(old) - set(new)))
        # A governance/preamble change outside Core Terms must not silently
        # inherit the old source admission merely because all term headings
        # and bodies compare equal. The complete source is the T0 contract.
        identical = prior[1] == candidate[1]
        status = UNCHANGED if identical else CHANGED
        error = (
            "REVIEW_CHANGED_CORE_TERM_SOURCE" if (changed or added or removed)
            else "REVIEW_CHANGED_NON_CORE_SOURCE"
        )
        root = canonical_hash(DOM_DELTA_CHECK, {
            "prior_anchor_root": prior_anchor_root,
            "candidate_anchor_root": candidate_anchor_root,
            "prior_git_blob_sha": prior[0].git_blob_sha,
            "candidate_git_blob_sha": candidate[0].git_blob_sha,
            "entire_document_identical": identical,
            "unchanged_term_names": unchanged,
            "changed_term_names": changed,
            "added_term_names": added,
            "removed_term_names": removed,
            "term_source_fingerprints_before": before,
            "term_source_fingerprints_after": after,
            "status": status,
        })
        report = OntologyTermDeltaReportV1(
            prior_anchor_root, candidate_anchor_root,
            prior[0].git_blob_sha, candidate[0].git_blob_sha,
            identical, unchanged, changed, added, removed, before, after, root,
        )
        return OntologyTermDeltaVerificationV1(
            status, (error,) if status == CHANGED else (),
            root,
        ), report
