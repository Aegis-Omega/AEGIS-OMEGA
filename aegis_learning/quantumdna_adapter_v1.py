"""QuantumDNA adapter for AEGIS Evidence Gradient Compiler v1.

The source witness ledger is snapshotted from exact source head
d766cbf99f0bb1e91300c94bae64c469a5d7d89d where the hosted
`claims-ledger` workflow completed successfully with executed steps.

Declared learning semantics:
- Verified claim -> candidate POSITIVE stream.
- Removed claim -> CONTRASTIVE_ONLY with its correction/removal reason.
- Proposed claim -> QUARANTINE.

The adapter never upgrades the source claim's scientific or operational
authority.  "POSITIVE" means suitable as a positive training target within the
ledger's declared computational/repository scope, not biological truth.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from aegis_learning.evidence_gradient_compiler_v1 import (
    CompilerPolicy,
    FailureKind,
    LearningDisposition,
    Witness,
    WitnessStatus,
    canonical_json_bytes,
    compile_evidence_gradient,
    sha256_hex,
)

SCHEMA = "AEGIS_QUANTUMDNA_EVIDENCE_CURRICULUM_V1"
SOURCE_HEAD = "d766cbf99f0bb1e91300c94bae64c469a5d7d89d"
SOURCE_LEDGER_PATH = "docs/quantum-dna-witness-ledger.json"
SOURCE_LEDGER_GIT_BLOB_SHA = "584230e3b2ab361654f75579ecdaf37392f4a415"
HOSTED_RUN_ID = 34_953_966_856
HOSTED_JOB_ID = 104_332_536_071
HOSTED_WORKFLOW = "claims-ledger"
HOSTED_JOB = "validate-claims"
HOSTED_CONCLUSION = "success"
HOSTED_EXECUTED_STEPS = (
    "Set up job",
    "Run actions/checkout@v4",
    "Run actions/setup-node@v4",
    "Run actions/setup-python@v5",
    "Test QuantumDNA witness and run-contract rejection controls",
    "Validate claims ledger",
    "Complete job",
)
GENESIS = "0" * 64
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class QuantumDnaAdapterError(ValueError):
    pass


def canonical_no_float(value: Any) -> bytes:
    def check(v: Any) -> None:
        if v is None or type(v) in (str, int, bool):
            return
        if type(v) is list:
            for item in v:
                check(item)
            return
        if type(v) is dict and all(type(k) is str for k in v):
            for item in v.values():
                check(item)
            return
        raise QuantumDnaAdapterError(
            "Unsupported value in QuantumDNA hash payload; floats are forbidden"
        )

    check(value)
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def digest_no_float(value: Any) -> str:
    return hashlib.sha256(canonical_no_float(value)).hexdigest()


def validate_ledger_chain(ledger: Mapping[str, Any]) -> str:
    try:
        header = ledger["header"]
        entries = ledger["entries"]
        terminal = ledger["terminal_sha256"]
    except (KeyError, TypeError) as exc:
        raise QuantumDnaAdapterError("MALFORMED_LEDGER") from exc

    if header.get("schema_version") != "AEGIS_QDNA_CLAIMS_CHAIN_V1":
        raise QuantumDnaAdapterError("UNEXPECTED_LEDGER_SCHEMA")
    if header.get("authority_promotion") is not False:
        raise QuantumDnaAdapterError("AUTHORITY_PROMOTION_FORBIDDEN")
    if header.get("serialization") != "SORTED_UTF8_JSON_NO_FLOAT_V1":
        raise QuantumDnaAdapterError("UNEXPECTED_SERIALIZATION")

    source_hashes = header.get("source_sha256")
    if not isinstance(source_hashes, dict) or len(source_hashes) != 10:
        raise QuantumDnaAdapterError("SOURCE_HASH_MANIFEST_INCOMPLETE")
    if any(
        not isinstance(value, str) or _HEX64.fullmatch(value) is None
        for value in source_hashes.values()
    ):
        raise QuantumDnaAdapterError("INVALID_SOURCE_SHA256")

    context = digest_no_float(header)
    previous = GENESIS

    for index, entry in enumerate(entries):
        if entry.get("sequence") != index:
            raise QuantumDnaAdapterError("SEQUENCE_MISMATCH")
        if entry.get("context_sha256") != context:
            raise QuantumDnaAdapterError("CONTEXT_DIGEST_MISMATCH")
        if entry.get("previous_entry_sha256") != previous:
            raise QuantumDnaAdapterError("PREVIOUS_ENTRY_MISMATCH")
        observed = entry.get("entry_sha256")
        if not isinstance(observed, str) or _HEX64.fullmatch(observed) is None:
            raise QuantumDnaAdapterError("INVALID_ENTRY_SHA256")
        payload = dict(entry)
        del payload["entry_sha256"]
        expected = digest_no_float(payload)
        if observed != expected:
            raise QuantumDnaAdapterError("ENTRY_DIGEST_MISMATCH")
        previous = observed

    if terminal != previous:
        raise QuantumDnaAdapterError("TERMINAL_DIGEST_MISMATCH")
    return previous


def hosted_attestation() -> dict[str, Any]:
    return {
        "source_head": SOURCE_HEAD,
        "workflow": HOSTED_WORKFLOW,
        "run_id": HOSTED_RUN_ID,
        "job": HOSTED_JOB,
        "job_id": HOSTED_JOB_ID,
        "conclusion": HOSTED_CONCLUSION,
        "executed_steps": list(HOSTED_EXECUTED_STEPS),
    }


def _verified_witnesses(
    *,
    ledger: Mapping[str, Any],
    terminal_sha256: str,
) -> list[Witness]:
    header = ledger["header"]
    chain_attestation = {
        "header_context_sha256": digest_no_float(header),
        "terminal_sha256": terminal_sha256,
        "entry_count": len(ledger["entries"]),
    }
    manifest_attestation = {
        "source_run_commit": header["source_run_commit"],
        "verified_against": header["verified_against"],
        "source_sha256": header["source_sha256"],
        "evidence_scope": header["evidence_scope"],
    }
    hosted = hosted_attestation()

    return [
        Witness(
            name="quantumdna_ledger_chain",
            status=WitnessStatus.VERIFIED,
            independence_group="ledger_reconstruction",
            source_ref=(
                f"Aegis-Omega/AEGIS-OMEGA@{SOURCE_HEAD}:{SOURCE_LEDGER_PATH}"
            ),
            evidence_sha256=sha256_hex(
                canonical_json_bytes(chain_attestation)
            ),
        ),
        Witness(
            name="quantumdna_source_manifest",
            status=WitnessStatus.VERIFIED,
            independence_group="artifact_manifest",
            source_ref=(
                f"Aegis-Omega/AEGIS-OMEGA@{SOURCE_HEAD}:"
                "genomics/quantum_dna/evidence/"
            ),
            evidence_sha256=sha256_hex(
                canonical_json_bytes(manifest_attestation)
            ),
        ),
        Witness(
            name="quantumdna_hosted_claims_ledger",
            status=WitnessStatus.VERIFIED,
            independence_group="hosted_replay",
            source_ref=(
                f"github-actions://Aegis-Omega/AEGIS-OMEGA/"
                f"runs/{HOSTED_RUN_ID}/jobs/{HOSTED_JOB_ID}@{SOURCE_HEAD}"
            ),
            evidence_sha256=sha256_hex(canonical_json_bytes(hosted)),
            detail=(
                "Hosted exact-head claims-ledger job completed successfully "
                "with nonzero executed validation steps."
            ),
        ),
    ]


def compile_quantumdna_ledger(
    ledger: Mapping[str, Any],
    *,
    target_source_head: str = SOURCE_HEAD,
) -> dict[str, Any]:
    if target_source_head != SOURCE_HEAD:
        raise QuantumDnaAdapterError("SOURCE_HEAD_REBIND_REQUIRED")

    terminal = validate_ledger_chain(ledger)
    base_witnesses = _verified_witnesses(
        ledger=ledger,
        terminal_sha256=terminal,
    )

    records: list[dict[str, Any]] = []
    for entry in ledger["entries"]:
        claim = entry["claim"]
        claim_id = claim["id"]
        tier = claim["tier"]

        representation_payload = {
            "claim": claim,
            "model_scope": entry["model_scope"],
            "limitations": entry["limitations"],
            "entry_sha256": entry["entry_sha256"],
        }
        representation = canonical_no_float(representation_payload)

        witnesses = list(base_witnesses)
        if tier == "Verified":
            pass
        elif tier == "Removed":
            witnesses.append(
                Witness(
                    name=f"{claim_id}_semantic_falsifier",
                    status=WitnessStatus.FAILED,
                    independence_group="semantic_audit",
                    failure_kind=FailureKind.SEMANTIC_DISAGREEMENT,
                    source_ref=(
                        f"Aegis-Omega/AEGIS-OMEGA@{SOURCE_HEAD}:"
                        f"{SOURCE_LEDGER_PATH}#{claim_id}"
                    ),
                    detail=claim["removal_reason"],
                )
            )
        elif tier == "Proposed":
            witnesses.append(
                Witness(
                    name=f"{claim_id}_open_obligation",
                    status=WitnessStatus.UNVERIFIED,
                    independence_group="open_obligation",
                    source_ref=(
                        f"Aegis-Omega/AEGIS-OMEGA@{SOURCE_HEAD}:"
                        f"{SOURCE_LEDGER_PATH}#{claim_id}"
                    ),
                    detail=claim["fails_if"],
                )
            )
        else:
            raise QuantumDnaAdapterError(f"UNSUPPORTED_CLAIM_TIER:{tier}")

        gradient = compile_evidence_gradient(
            example_id=claim_id,
            source_head_sha=SOURCE_HEAD,
            witnesses=witnesses,
            representation=representation,
            policy=CompilerPolicy(
                min_independent_groups=3,
                formal_kernel_required=False,
            ),
            metadata={
                "domain": "QUANTUM_DNA_COMPUTATIONAL_WITNESS",
                "claim_tier": tier,
                "source_ledger_git_blob_sha": SOURCE_LEDGER_GIT_BLOB_SHA,
            },
        )

        target: dict[str, Any]
        if tier == "Removed":
            target = {
                "claim": claim["claim"],
                "correction": claim["removal_reason"],
                "desired_behavior": "REJECT_OR_CORRECT",
            }
        elif tier == "Verified":
            target = {
                "claim": claim["claim"],
                "desired_behavior": "ACCEPT_WITH_DECLARED_SCOPE",
            }
        else:
            target = {
                "claim": claim["claim"],
                "open_condition": claim["fails_if"],
                "desired_behavior": "DEFER_PENDING_EVIDENCE",
            }

        records.append(
            {
                "schema": SCHEMA,
                "claim_id": claim_id,
                "source_tier": tier,
                "target": target,
                "model_scope": entry["model_scope"],
                "limitations": entry["limitations"],
                "entry_sha256": entry["entry_sha256"],
                "learning": gradient,
                "authority_effect": "NONE",
            }
        )

    counts = {
        disposition.value: sum(
            1
            for record in records
            if record["learning"]["disposition"] == disposition.value
        )
        for disposition in LearningDisposition
    }

    receipt = {
        "schema": SCHEMA,
        "source_head": SOURCE_HEAD,
        "source_ledger_path": SOURCE_LEDGER_PATH,
        "source_ledger_git_blob_sha": SOURCE_LEDGER_GIT_BLOB_SHA,
        "terminal_sha256": terminal,
        "record_count": len(records),
        "counts": counts,
        "hosted_attestation": hosted_attestation(),
        "records": records,
        "authority_effect": "NONE",
    }
    receipt["receipt_sha256"] = sha256_hex(canonical_json_bytes(receipt))
    return receipt


def load_snapshot(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))
