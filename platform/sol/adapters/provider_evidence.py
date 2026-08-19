from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Any, Mapping


PROVIDERS = frozenset({
    "dataverse",
    "figma",
    "github",
    "huggingface",
    "nvidia",
    "sharepoint",
    "wolfram",
})
STATUSES = frozenset({"SUCCEEDED", "FAILED", "DENIED"})
EVIDENCE_TIERS = frozenset({"T0", "T1", "T2", "T3"})
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_OBJECT_RE = re.compile(r"^[0-9a-f]{40,64}$")
CONTAINER_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class ProviderEvidenceError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ExternalReference:
    kind: str
    id: str
    revision: str
    etag: str | None = None
    checksum: str | None = None
    endpoint: str | None = None


@dataclass(frozen=True, slots=True)
class ModelProvenance:
    model_id: str
    revision: str
    runtime: str
    hardware_profile: str | None = None
    container_digest: str | None = None
    dataset_revision: str | None = None


@dataclass(frozen=True, slots=True)
class ProviderEvidence:
    schema_version: str
    provider: str
    capability: str
    observed_at: str
    request_digest: str
    response_digest: str
    status: str
    evidence_tier: str
    grants_authority: bool
    external_reference: ExternalReference
    model_provenance: ModelProvenance | None
    receipt_root: str | None
    evidence_digest: str


def _nonempty(field: str, value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProviderEvidenceError(f"{field} must be a non-empty string")
    return value.strip()


def _sha256(field: str, value: str) -> str:
    value = _nonempty(field, value)
    if not SHA256_RE.fullmatch(value):
        raise ProviderEvidenceError(f"{field} must be lowercase SHA-256 hex")
    return value


def _timestamp(value: str | None) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    normalized = _nonempty("observed_at", value)
    try:
        datetime.fromisoformat(normalized.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProviderEvidenceError("observed_at must be ISO-8601") from exc
    return normalized


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _optional_nonempty(field: str, value: str | None) -> str | None:
    return None if value is None else _nonempty(field, value)


def _validate_external(provider: str, ref: ExternalReference) -> None:
    _nonempty("external_reference.kind", ref.kind)
    _nonempty("external_reference.id", ref.id)
    _nonempty("external_reference.revision", ref.revision)

    if ref.checksum is not None:
        _sha256("external_reference.checksum", ref.checksum)

    if provider == "github":
        if ref.kind not in {"commit", "pull_request", "workflow_run"}:
            raise ProviderEvidenceError("github evidence kind is unsupported")
        if not GIT_OBJECT_RE.fullmatch(ref.revision):
            raise ProviderEvidenceError("github evidence revision must be an immutable Git object id")
    elif provider == "sharepoint":
        if ref.kind != "drive_item" or not ref.etag:
            raise ProviderEvidenceError("sharepoint evidence requires drive_item and etag")
    elif provider == "dataverse":
        if ref.kind != "row" or not ref.etag:
            raise ProviderEvidenceError("dataverse evidence requires row and etag")
    elif provider == "huggingface":
        if ref.kind not in {"model", "dataset", "space", "evaluation"}:
            raise ProviderEvidenceError("huggingface evidence kind is unsupported")
        if not GIT_OBJECT_RE.fullmatch(ref.revision):
            raise ProviderEvidenceError("huggingface revision must be a pinned commit")
    elif provider == "nvidia":
        if ref.kind not in {"nim_inference", "nim_benchmark"} or not ref.endpoint:
            raise ProviderEvidenceError("nvidia evidence requires a NIM kind and endpoint")
        if not ref.endpoint.startswith("https://"):
            raise ProviderEvidenceError("nvidia evidence endpoint must use HTTPS")
    elif provider == "wolfram":
        if ref.kind != "wolfram_result" or ref.checksum is None:
            raise ProviderEvidenceError("wolfram evidence requires a result checksum")
    elif provider == "figma":
        if ref.kind not in {"file_version", "node_snapshot", "prototype"}:
            raise ProviderEvidenceError("figma evidence kind is unsupported")


def _validate_model(provider: str, model: ModelProvenance | None) -> None:
    if provider in {"huggingface", "nvidia"} and model is None:
        raise ProviderEvidenceError(f"{provider} evidence requires model provenance")
    if model is None:
        return
    _nonempty("model_provenance.model_id", model.model_id)
    _nonempty("model_provenance.revision", model.revision)
    _nonempty("model_provenance.runtime", model.runtime)
    if provider == "huggingface":
        if not GIT_OBJECT_RE.fullmatch(model.revision):
            raise ProviderEvidenceError("huggingface model revision must be a pinned commit")
        if model.dataset_revision is not None and not GIT_OBJECT_RE.fullmatch(model.dataset_revision):
            raise ProviderEvidenceError("huggingface dataset revision must be a pinned commit")
    if provider == "nvidia" and model.container_digest is None:
        raise ProviderEvidenceError("nvidia evidence requires a pinned container digest")
    if model.container_digest is not None and not CONTAINER_DIGEST_RE.fullmatch(model.container_digest):
        raise ProviderEvidenceError("model_provenance.container_digest must be sha256:<hex>")


def normalize_provider_evidence(
    *,
    provider: str,
    capability: str,
    request_digest: str,
    response_digest: str,
    status: str,
    evidence_tier: str,
    external_reference: ExternalReference,
    model_provenance: ModelProvenance | None = None,
    receipt_root: str | None = None,
    observed_at: str | None = None,
) -> ProviderEvidence:
    provider = _nonempty("provider", provider)
    if provider not in PROVIDERS:
        raise ProviderEvidenceError("provider is unsupported")
    capability = _nonempty("capability", capability)
    if status not in STATUSES:
        raise ProviderEvidenceError("status is unsupported")
    if evidence_tier not in EVIDENCE_TIERS:
        raise ProviderEvidenceError("evidence_tier is unsupported")

    request_digest = _sha256("request_digest", request_digest)
    response_digest = _sha256("response_digest", response_digest)
    receipt_root = None if receipt_root is None else _sha256("receipt_root", receipt_root)
    observed_at = _timestamp(observed_at)

    external_reference = ExternalReference(
        kind=_nonempty("external_reference.kind", external_reference.kind),
        id=_nonempty("external_reference.id", external_reference.id),
        revision=_nonempty("external_reference.revision", external_reference.revision),
        etag=_optional_nonempty("external_reference.etag", external_reference.etag),
        checksum=_optional_nonempty("external_reference.checksum", external_reference.checksum),
        endpoint=_optional_nonempty("external_reference.endpoint", external_reference.endpoint),
    )
    _validate_external(provider, external_reference)
    _validate_model(provider, model_provenance)

    unsigned = {
        "schema_version": "1.0.0",
        "provider": provider,
        "capability": capability,
        "observed_at": observed_at,
        "request_digest": request_digest,
        "response_digest": response_digest,
        "status": status,
        "evidence_tier": evidence_tier,
        "grants_authority": False,
        "external_reference": asdict(external_reference),
        "model_provenance": asdict(model_provenance) if model_provenance else None,
        "receipt_root": receipt_root,
    }
    evidence_digest = sha256(_canonical(unsigned)).hexdigest()
    return ProviderEvidence(
        schema_version="1.0.0",
        provider=provider,
        capability=capability,
        observed_at=observed_at,
        request_digest=request_digest,
        response_digest=response_digest,
        status=status,
        evidence_tier=evidence_tier,
        grants_authority=False,
        external_reference=external_reference,
        model_provenance=model_provenance,
        receipt_root=receipt_root,
        evidence_digest=evidence_digest,
    )


def to_authority_evidence(evidence: ProviderEvidence) -> dict[str, Any]:
    return {
        "evidence_kind": "SOL_PROVIDER_OBSERVATION_V1",
        "provider": evidence.provider,
        "capability": evidence.capability,
        "status": evidence.status,
        "evidence_tier": evidence.evidence_tier,
        "grants_authority": False,
        "evidence_digest": evidence.evidence_digest,
        "receipt_root": evidence.receipt_root,
    }
