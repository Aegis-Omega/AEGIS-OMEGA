"""AEGIS HolonMetadata canonical-term binding to an independently retrieved Git blob.

This module does not attest that a Git commit exists or that a Git server is
trusted. Those are external trusted-store obligations. It validates exact
source bytes, their Git blob identity, canonical term definitions, and concrete
holon terms without promoting contextual readings to canonical terminology.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from typing import Protocol

from harness.sdk.holon_meaning_bridge import HolonSnapshotV1
from harness.sdk.meaning_heritage import NO_AUTHORITY, canonical_hash

DOM_ANCHOR = "AEGIS_HOLON_ONTOLOGY_GIT_ANCHOR_V1"
DOM_CHECK = "AEGIS_HOLON_ONTOLOGY_BINDING_CHECK_V1"
DOM_RECEIPT = "AEGIS_HOLON_ONTOLOGY_BINDING_RECEIPT_V1"
REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
ONTOLOGY_PATH = "docs/ONTOLOGY.md"
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEADER = re.compile(r"^### ([^\r\n]+)$")
MAX_ONTOLOGY_BYTES = 1_000_000
MAX_HOLONS = 4096
MAX_TERMS = 512

PASS = "PASS_ONTOLOGY_MEMBERSHIP_ONLY"
DENIED = "FAIL_ONTOLOGY_BINDING_DENIED"


class HolonOntologyError(ValueError):
    pass


def _require(value: object, pattern: re.Pattern[str], name: str) -> str:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise HolonOntologyError(f"{name}:INVALID")
    return value


@dataclass(frozen=True)
class OntologyGitAnchorV1:
    """A provenance claim, NOT a self-authenticating authorization.

    A separately trusted anchor store must bind this to the intended repository
    commit. A separately trusted Git blob store must resolve and authenticate
    exact bytes at (repository, commit_sha, path).
    """

    commit_sha: str
    git_blob_sha: str
    content_sha256: str
    repository: str = field(default=REPOSITORY, init=False)
    path: str = field(default=ONTOLOGY_PATH, init=False)
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-ontology-git-anchor.v1", init=False)

    def __post_init__(self) -> None:
        _require(self.commit_sha, HEX40, "commit_sha")
        _require(self.git_blob_sha, HEX40, "git_blob_sha")
        _require(self.content_sha256, HEX64, "content_sha256")

    @property
    def root(self) -> str:
        return canonical_hash(DOM_ANCHOR, asdict(self))


class TrustedOntologyGitAnchorStore(Protocol):
    def fetch_verified(self, root: str) -> OntologyGitAnchorV1 | None: ...


class TrustedOntologyGitBlobStore(Protocol):
    def fetch_verified(self, repository: str, commit_sha: str, path: str) -> bytes | None: ...


@dataclass(frozen=True)
class OntologyBindingVerificationV1:
    status: str
    error_codes: tuple[str, ...]
    verification_root: str | None


@dataclass(frozen=True)
class OntologyBindingReceiptV1:
    anchor_root: str
    ontology_content_sha256: str
    canonical_term_names: tuple[str, ...]
    holon_snapshot_roots: tuple[str, ...]
    verification_root: str
    authority_class: str = field(default=NO_AUTHORITY, init=False)
    schema_version: str = field(default="aegis.holon-ontology-binding-receipt.v1", init=False)

    @property
    def root(self) -> str:
        return canonical_hash(DOM_RECEIPT, asdict(self))


def parse_core_terms(source_bytes: bytes) -> tuple[str, ...]:
    """Parse only exact ### definitions inside ## Core Terms.

    The parser intentionally does not infer synonyms or semantic equivalence.
    It requires the named section to exist exactly once, its headings to have
    unique spellings, and an actual definition body under each heading.
    """
    if not isinstance(source_bytes, bytes) or not source_bytes or len(source_bytes) > MAX_ONTOLOGY_BYTES:
        raise HolonOntologyError("ONTOLOGY_BYTES_INVALID")
    try:
        content = source_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HolonOntologyError("ONTOLOGY_NOT_UTF8") from exc
    if content.startswith("\ufeff") or "\x00" in content or "\r" in content:
        raise HolonOntologyError("ONTOLOGY_BYTES_NONCANONICAL")
    section_found = False
    in_terms = False
    names: list[str] = []
    body: dict[str, int] = {}
    current: str | None = None
    for line in content.split("\n"):
        if line.startswith("## "):
            heading = line[3:]
            if heading == "Core Terms":
                if section_found:
                    raise HolonOntologyError("ONTOLOGY_DUPLICATE_CORE_TERMS_SECTION")
                section_found = True
                in_terms = True
                current = None
                continue
            if in_terms:
                in_terms = False
                current = None
        if not in_terms:
            continue
        hit = HEADER.fullmatch(line)
        if hit:
            name = hit.group(1)
            if (not name.strip() or name != name.strip()
                    or name in body or len(name) > 128):
                raise HolonOntologyError("ONTOLOGY_DUPLICATE_OR_INVALID_TERM")
            names.append(name)
            body[name] = 0
            current = name
            if len(names) > MAX_TERMS:
                raise HolonOntologyError("ONTOLOGY_TOO_MANY_TERMS")
        elif current is not None and line.strip() and not line.startswith("#"):
            body[current] += 1
    if not section_found or not names:
        raise HolonOntologyError("ONTOLOGY_CORE_TERMS_MISSING")
    if any(count == 0 for count in body.values()):
        raise HolonOntologyError("ONTOLOGY_TERM_WITHOUT_DEFINITION")
    return tuple(sorted(names))


class HolonOntologyBindingVerifierV1:
    def __init__(
        self,
        *,
        anchors: TrustedOntologyGitAnchorStore,
        blobs: TrustedOntologyGitBlobStore,
    ):
        self.anchors = anchors
        self.blobs = blobs

    def verify(
        self, anchor_root: str, holons: tuple[HolonSnapshotV1, ...]
    ) -> tuple[OntologyBindingVerificationV1, OntologyBindingReceiptV1 | None]:
        def deny(reason: str):
            return OntologyBindingVerificationV1(DENIED, (reason,), None), None

        if not isinstance(anchor_root, str) or not HEX64.fullmatch(anchor_root):
            return deny("ONTOLOGY_ANCHOR_ROOT_INVALID")
        anchor = self.anchors.fetch_verified(anchor_root)
        if (not isinstance(anchor, OntologyGitAnchorV1)
                or anchor.root != anchor_root or anchor.authority_class != NO_AUTHORITY):
            return deny("ONTOLOGY_ANCHOR_UNTRUSTED")
        source_bytes = self.blobs.fetch_verified(
            anchor.repository, anchor.commit_sha, anchor.path
        )
        if not isinstance(source_bytes, bytes):
            return deny("ONTOLOGY_GIT_BLOB_UNTRUSTED")
        if hashlib.sha256(source_bytes).hexdigest() != anchor.content_sha256:
            return deny("ONTOLOGY_CONTENT_SHA256_MISMATCH")
        prefix = b"blob " + str(len(source_bytes)).encode("ascii") + b"\0"
        if hashlib.sha1(prefix + source_bytes).hexdigest() != anchor.git_blob_sha:
            return deny("ONTOLOGY_GIT_BLOB_SHA_MISMATCH")
        try:
            terms = parse_core_terms(source_bytes)
        except HolonOntologyError as exc:
            return deny(str(exc))
        if (not isinstance(holons, tuple) or not holons
                or len(holons) > MAX_HOLONS or any(not isinstance(h, HolonSnapshotV1) for h in holons)):
            return deny("ONTOLOGY_HOLONS_INVALID")
        if len({h.holon_id for h in holons}) != len(holons):
            return deny("ONTOLOGY_HOLON_ID_DUPLICATE")
        if any(h.ontology_term not in terms for h in holons):
            return deny("ONTOLOGY_TERM_UNDECLARED")
        holon_roots = tuple(sorted(h.root for h in holons))
        verification_root = canonical_hash(DOM_CHECK, {
            "anchor_root": anchor_root,
            "ontology_content_sha256": anchor.content_sha256,
            "canonical_term_names": terms,
            "holon_snapshot_roots": holon_roots,
            "status": PASS,
        })
        receipt = OntologyBindingReceiptV1(
            anchor_root, anchor.content_sha256, terms, holon_roots, verification_root
        )
        return OntologyBindingVerificationV1(PASS, (), verification_root), receipt
