"""AEGIS Ω — source-bound adapters for Prospective Epoch V1.

This module is offline-authoritative.  It consumes immutable raw-byte capture
bundles, validates source-specific semantics, and only then normalizes them to
the generic proof-carrying registry-probe layer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence
from urllib.parse import quote

import cross_domain_collision as cdc
import cross_domain_coverage as cov
import cross_domain_ingest as ingest
import research_invariants as ri


TRANSFORM_ID_V1 = "INTEGER_IDENTITY_EXTERNAL_LOOKUP_KEY_V1"
TRANSFORM_CRITERION_SHA256_V1 = ri.literal_sha256("integer identity external lookup key v1")
UNICODE_SOURCE_LOCATOR_V1 = (
    "https://www.unicode.org/Public/17.0.0/ucd/extracted/DerivedGeneralCategory.txt"
)
NCBI_ESEARCH_LOCATOR_V1 = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
MAX_NCBI_BATCH_V1 = 100


@dataclass(frozen=True)
class SourceContractV1:
    source_id: str
    source_locator: str
    source_version_or_release: str
    contract_sha256: str


@dataclass(frozen=True)
class SourceVerifiedProbeV1:
    probe: cov.VerifiedRegistryProbeV1
    capture: ingest.VerifiedSourceCaptureV1
    requested_subjects: tuple[cdc.IntegerSubjectV1, ...]


def _unicode_source_material() -> Mapping[str, Any]:
    return {
        "schema": "AEGIS_UNICODE_SOURCE_CONTRACT_V1",
        "source_id": "unicode-ucd",
        "release": "17.0.0",
        "source_locator": UNICODE_SOURCE_LOCATOR_V1,
        "parser_version": "1",
        "positive_rule_id": "UNICODE_GENERAL_CATEGORY_NOT_CN_V1",
        "negative_rule_id": "UNICODE_GENERAL_CATEGORY_CN_V1",
        "ambiguous_rule_id": "UNICODE_OUT_OF_RANGE_NOT_ESTABLISHED_V1",
    }


def _ncbi_source_material() -> Mapping[str, Any]:
    return {
        "schema": "AEGIS_NCBI_GENE_SOURCE_CONTRACT_V1",
        "source_id": "ncbi-gene-esearch",
        "database": "gene",
        "endpoint_family": "esearch.fcgi",
        "response_mode": "json",
        "search_field": "UID",
        "parser_version": "1",
        "max_batch_size": 100,
        "batch_rule_id": "SORTED_UNIQUE_UID_OR_QUERY_V1",
        "positive_rule_id": "NCBI_ESEARCH_UID_PRESENT_V1",
        "negative_rule_id": "NCBI_ESEARCH_UID_ABSENT_V1",
        "ambiguous_rule_id": "NCBI_ESEARCH_NOT_ESTABLISHED_V1",
    }


def unicode_source_contract_v1() -> SourceContractV1:
    material = _unicode_source_material()
    return SourceContractV1(
        source_id="unicode-ucd",
        source_locator=UNICODE_SOURCE_LOCATOR_V1,
        source_version_or_release="17.0.0",
        contract_sha256=ri.sha256_hex(material),
    )


def ncbi_gene_source_contract_v1() -> SourceContractV1:
    material = _ncbi_source_material()
    return SourceContractV1(
        source_id="ncbi-gene-esearch",
        source_locator=NCBI_ESEARCH_LOCATOR_V1,
        source_version_or_release="dynamic-observation",
        contract_sha256=ri.sha256_hex(material),
    )


def _adapter_contract(
    registry_id: str,
    positive_rule: str,
    negative_rule: str,
    ambiguous_rule: str,
) -> cov.RegistryAdapterContractV1:
    adapter = cov.RegistryAdapterContractV1(
        registry_id=registry_id,
        adapter_version="PROSPECTIVE_EPOCH_V1",
        query_key_type="integer-decimal",
        transform_id=TRANSFORM_ID_V1,
        transform_criterion_sha256=TRANSFORM_CRITERION_SHA256_V1,
        positive_result_rule_id=positive_rule,
        negative_result_rule_id=negative_rule,
        ambiguous_result_rule_id=ambiguous_rule,
        canonicalization_rule_id="CANONICAL_JSON_V1",
        contract_text=f"prospective epoch v1 {registry_id} source-bound adapter",
    )
    cov.verify_registry_adapter_contract(adapter)
    return adapter


def unicode_adapter_contract_v1() -> cov.RegistryAdapterContractV1:
    return _adapter_contract(
        "unicode",
        "UNICODE_GENERAL_CATEGORY_NOT_CN_V1",
        "UNICODE_GENERAL_CATEGORY_CN_V1",
        "UNICODE_OUT_OF_RANGE_NOT_ESTABLISHED_V1",
    )


def ncbi_gene_adapter_contract_v1() -> cov.RegistryAdapterContractV1:
    return _adapter_contract(
        "ncbi-gene",
        "NCBI_ESEARCH_UID_PRESENT_V1",
        "NCBI_ESEARCH_UID_ABSENT_V1",
        "NCBI_ESEARCH_NOT_ESTABLISHED_V1",
    )


def _validate_common_context(
    subject: cdc.IntegerSubjectV1,
    criterion: cdc.CollisionCriterionV1,
    registry_id: str,
) -> None:
    if not isinstance(subject, cdc.IntegerSubjectV1):
        raise TypeError("expected IntegerSubjectV1")
    if not isinstance(criterion, cdc.CollisionCriterionV1):
        raise TypeError("expected CollisionCriterionV1")
    if cdc.IntegerSubjectV1(subject.value).subject_sha256 != subject.subject_sha256:
        raise ValueError("subject digest mismatch")
    if not criterion.universe_min <= subject.value <= criterion.universe_max:
        raise ValueError("subject outside frozen criterion universe")
    if registry_id not in criterion.registry_set:
        raise ValueError("registry absent from frozen criterion")
    if TRANSFORM_ID_V1 not in criterion.transform_set:
        raise ValueError("identity lookup transform absent from frozen criterion")


def _validate_capture(
    capture: ingest.VerifiedSourceCaptureV1,
    contract: SourceContractV1,
    *,
    exact_release: str | None,
    media_type_prefix: str,
) -> None:
    ingest.verify_source_capture(capture)
    receipt = capture.receipt
    if receipt.source_id != contract.source_id:
        raise ValueError("source capture source-id mismatch")
    if receipt.source_contract_sha256 != contract.contract_sha256:
        raise ValueError("source capture contract mismatch")
    if exact_release is not None and receipt.source_version_or_release != exact_release:
        raise ValueError("source capture release mismatch")
    if receipt.response_status != 200:
        raise ValueError("source capture did not establish HTTP success")
    if not receipt.media_type.lower().startswith(media_type_prefix.lower()):
        raise ValueError("source capture media type mismatch")


def _normalize_probe(
    *,
    subject: cdc.IntegerSubjectV1,
    criterion: cdc.CollisionCriterionV1,
    adapter: cov.RegistryAdapterContractV1,
    capture: ingest.VerifiedSourceCaptureV1,
    matched: bool,
    details: Mapping[str, Any],
) -> cov.VerifiedRegistryProbeV1:
    snapshot = cdc.RegistrySnapshotV1(
        registry_id=adapter.registry_id,
        registry_version_or_release=capture.receipt.source_version_or_release,
        query_key=str(subject.value),
        query_key_type=adapter.query_key_type,
        result_kind="SOURCE_VERIFIED_BOOLEAN_V1",
        canonical_result={
            "match": bool(matched),
            "source_capture_receipt_sha256": capture.receipt.receipt_sha256,
            "source_raw_content_sha256": capture.receipt.raw_content_sha256,
            "details": dict(details),
        },
        source_locator=capture.receipt.request_identity,
        source_observed_at=capture.receipt.observed_at,
        ingestion_producer_id=capture.receipt.producer_id,
    )
    return cov.probe_registry_snapshot(subject, criterion, adapter, snapshot)


def _unicode_ranges(raw: bytes) -> tuple[tuple[int, int, str], ...]:
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Unicode source is not valid UTF-8") from exc
    ranges: list[tuple[int, int, str]] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        pieces = [piece.strip() for piece in line.split(";")]
        if len(pieces) != 2 or not pieces[0] or not pieces[1]:
            raise ValueError(f"malformed Unicode category row at line {line_number}")
        code_spec, category = pieces
        try:
            if ".." in code_spec:
                lo_text, hi_text = code_spec.split("..", 1)
                lo, hi = int(lo_text, 16), int(hi_text, 16)
            else:
                lo = hi = int(code_spec, 16)
        except ValueError as exc:
            raise ValueError(f"invalid Unicode code range at line {line_number}") from exc
        if not 0 <= lo <= hi <= 0x10FFFF:
            raise ValueError(f"Unicode code range outside scalar space at line {line_number}")
        ranges.append((lo, hi, category))
    if not ranges:
        raise ValueError("Unicode category source contains no data rows")
    ranges.sort(key=lambda item: (item[0], item[1], item[2]))
    previous_hi = -1
    for lo, hi, _category in ranges:
        if lo <= previous_hi:
            raise ValueError("Unicode category source contains overlapping ranges")
        previous_hi = hi
    return tuple(ranges)


def _unicode_category(value: int, ranges: Sequence[tuple[int, int, str]]) -> str:
    for lo, hi, category in ranges:
        if lo <= value <= hi:
            return category
        if value < lo:
            break
    raise ValueError("Unicode source does not cover requested code point")


def probe_unicode_general_category(
    subject: cdc.IntegerSubjectV1,
    criterion: cdc.CollisionCriterionV1,
    capture: ingest.VerifiedSourceCaptureV1,
) -> SourceVerifiedProbeV1:
    _validate_common_context(subject, criterion, "unicode")
    if not 0 <= subject.value <= 0x10FFFF:
        raise ValueError("subject outside Unicode scalar range")
    source = unicode_source_contract_v1()
    _validate_capture(capture, source, exact_release="17.0.0", media_type_prefix="text/plain")
    if capture.receipt.request_identity != source.source_locator:
        raise ValueError("Unicode capture request identity mismatch")
    if capture.receipt.request_subject_sha256s:
        raise ValueError("Unicode whole-file capture must not bind per-subject request digests")
    ranges = _unicode_ranges(capture.raw_content)
    category = _unicode_category(subject.value, ranges)
    adapter = unicode_adapter_contract_v1()
    probe = _normalize_probe(
        subject=subject,
        criterion=criterion,
        adapter=adapter,
        capture=capture,
        matched=(category != "Cn"),
        details={"general_category": category, "codepoint": subject.unicode_codepoint_label},
    )
    return SourceVerifiedProbeV1(probe=probe, capture=capture, requested_subjects=(subject,))


def _canonical_ncbi_subjects(
    subjects: Sequence[cdc.IntegerSubjectV1],
) -> tuple[cdc.IntegerSubjectV1, ...]:
    if isinstance(subjects, (str, bytes)):
        raise TypeError("subjects must be a sequence of IntegerSubjectV1")
    by_value: dict[int, cdc.IntegerSubjectV1] = {}
    for subject in subjects:
        if not isinstance(subject, cdc.IntegerSubjectV1):
            raise TypeError("NCBI batch contains non-IntegerSubjectV1 value")
        if cdc.IntegerSubjectV1(subject.value).subject_sha256 != subject.subject_sha256:
            raise ValueError("NCBI batch subject digest mismatch")
        if not 0 <= subject.value <= 100000:
            raise ValueError("NCBI Epoch V1 subject outside frozen universe")
        by_value[subject.value] = subject
    ordered = tuple(by_value[value] for value in sorted(by_value))
    if not ordered:
        raise ValueError("NCBI batch must contain at least one subject")
    if len(ordered) > MAX_NCBI_BATCH_V1:
        raise ValueError("NCBI batch exceeds frozen maximum size")
    return ordered


def make_ncbi_batch_request(
    subjects: Sequence[cdc.IntegerSubjectV1],
) -> tuple[str, tuple[cdc.IntegerSubjectV1, ...]]:
    ordered = _canonical_ncbi_subjects(subjects)
    query = " OR ".join(f"{subject.value}[UID]" for subject in ordered)
    encoded_query = quote(query, safe="")
    identity = (
        f"{NCBI_ESEARCH_LOCATOR_V1}?db=gene&retmode=json&retstart=0"
        f"&retmax={len(ordered)}&term={encoded_query}"
    )
    return identity, ordered


def _ncbi_result(
    ordered: tuple[cdc.IntegerSubjectV1, ...],
    capture: ingest.VerifiedSourceCaptureV1,
) -> tuple[set[int], Mapping[str, Any]]:
    expected_identity, expected_order = make_ncbi_batch_request(ordered)
    if expected_order != ordered:
        raise ValueError("NCBI request subject ordering is not canonical")
    expected_subject_digests = tuple(subject.subject_sha256 for subject in ordered)
    if capture.receipt.request_subject_sha256s != expected_subject_digests:
        raise ValueError("NCBI capture subject binding mismatch")
    if capture.receipt.request_identity != expected_identity:
        raise ValueError("NCBI capture request identity mismatch")
    try:
        payload = json.loads(capture.raw_content.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("NCBI source is not valid UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise ValueError("NCBI response must be a JSON object")
    result = payload.get("esearchresult")
    if not isinstance(result, Mapping):
        raise ValueError("NCBI response missing esearchresult")
    warning = result.get("warninglist")
    if warning:
        raise ValueError("NCBI response contains warning/truncation evidence")
    try:
        retstart = int(result.get("retstart"))
        retmax = int(result.get("retmax"))
        count = int(result.get("count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("NCBI response has invalid count/retmax/retstart") from exc
    if retstart != 0:
        raise ValueError("NCBI response retstart is not zero")
    if retmax < len(ordered):
        raise ValueError("NCBI response retmax cannot establish complete requested batch")
    idlist = result.get("idlist")
    if not isinstance(idlist, list) or any(not isinstance(value, str) for value in idlist):
        raise ValueError("NCBI response idlist is not canonical")
    try:
        returned = [int(value, 10) for value in idlist]
    except ValueError as exc:
        raise ValueError("NCBI response contains a non-integer UID") from exc
    if len(set(returned)) != len(returned):
        raise ValueError("NCBI response contains duplicate UIDs")
    if count != len(returned):
        raise ValueError("NCBI response count does not match complete UID list")
    requested_values = {subject.value for subject in ordered}
    if any(value not in requested_values for value in returned):
        raise ValueError("NCBI response contains an unexpected UID")
    querytranslation = result.get("querytranslation")
    if not isinstance(querytranslation, str) or not querytranslation:
        raise ValueError("NCBI response missing querytranslation")
    for subject in ordered:
        if f"{subject.value}[UID]" not in querytranslation:
            raise ValueError("NCBI querytranslation does not bind every requested UID")
    return set(returned), result


def probe_ncbi_gene_esearch(
    subject: cdc.IntegerSubjectV1,
    criterion: cdc.CollisionCriterionV1,
    ordered_subjects: Sequence[cdc.IntegerSubjectV1],
    capture: ingest.VerifiedSourceCaptureV1,
) -> SourceVerifiedProbeV1:
    _validate_common_context(subject, criterion, "ncbi-gene")
    source = ncbi_gene_source_contract_v1()
    _validate_capture(capture, source, exact_release=None, media_type_prefix="application/json")
    ordered = _canonical_ncbi_subjects(ordered_subjects)
    if subject not in ordered:
        raise ValueError("NCBI probe subject was not part of requested batch")
    returned, _raw_result = _ncbi_result(ordered, capture)
    adapter = ncbi_gene_adapter_contract_v1()
    probe = _normalize_probe(
        subject=subject,
        criterion=criterion,
        adapter=adapter,
        capture=capture,
        matched=(subject.value in returned),
        details={
            "uid": subject.value,
            "requested_subject_sha256s": tuple(item.subject_sha256 for item in ordered),
        },
    )
    return SourceVerifiedProbeV1(probe=probe, capture=capture, requested_subjects=ordered)


def verify_source_verified_probe(bundle: SourceVerifiedProbeV1) -> None:
    if not isinstance(bundle, SourceVerifiedProbeV1):
        raise TypeError("expected SourceVerifiedProbeV1")
    ingest.verify_source_capture(bundle.capture)
    cov.verify_verified_probe(bundle.probe)
    registry_id = bundle.probe.receipt.registry_id
    if registry_id == "unicode":
        replayed = probe_unicode_general_category(
            bundle.probe.subject,
            bundle.probe.criterion,
            bundle.capture,
        )
    elif registry_id == "ncbi-gene":
        replayed = probe_ncbi_gene_esearch(
            bundle.probe.subject,
            bundle.probe.criterion,
            bundle.requested_subjects,
            bundle.capture,
        )
    else:
        raise ValueError("unsupported source-verified registry")
    if replayed.probe != bundle.probe:
        raise ValueError("source-verified probe replay does not reproduce generic probe")
    if replayed.capture != bundle.capture:
        raise ValueError("source-verified probe replay changed source capture")
