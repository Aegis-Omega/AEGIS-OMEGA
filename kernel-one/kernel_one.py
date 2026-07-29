from __future__ import annotations

import hashlib
import hmac
import json
import os
import sqlite3
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional

import yaml

from validator import (
    ValidationError,
    calculate_residual_delta,
    sha256_file,
    validate_proposal_schema,
    validate_request_structure,
)

SIGNING_ALGORITHM = "hmac-sha256"
WITNESS_SCHEMA_VERSION = "1.0"
COMPROMISED_KEY_IDS = frozenset({"kernel-hmac-v0-compromised"})
GENESIS_PARENT_RECEIPT = "0" * 64


class KernelConfigurationError(RuntimeError):
    """Raised when required runtime authority configuration is absent or rejected."""


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    """Return deterministic UTF-8 JSON bytes suitable for hashing and signing."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ValidationError(f"NON_CANONICAL_WITNESS:{exc}") from exc


@dataclass(frozen=True)
class WitnessEnvelope:
    schema_version: str
    request_id: str
    artifact_path: str
    artifact_sha256: str
    observed_at: int
    sequence: int
    parent_receipt_hash: str
    key_id: str
    algorithm: str = SIGNING_ALGORITHM

    def canonical_content(self) -> dict[str, Any]:
        return asdict(self)

    def canonical_bytes(self) -> bytes:
        return canonical_json_bytes(self.canonical_content())

    def receipt_hash(self) -> str:
        return hashlib.sha256(self.canonical_bytes()).hexdigest()


class KernelOneEngine:
    def __init__(
        self,
        manifest_path: str = "INDEX.yaml",
        db_path: str = "memory_store.sqlite",
        *,
        signing_key: Optional[bytes] = None,
        signing_key_id: Optional[str] = None,
    ):
        self.manifest_path = Path(manifest_path)
        self.db_path = Path(db_path)
        self.model_version = "Gemma-2B-INT4-Local"
        self.signing_key, self.signing_key_id = self._resolve_signing_config(
            signing_key=signing_key,
            signing_key_id=signing_key_id,
        )

    @staticmethod
    def _resolve_signing_config(
        *,
        signing_key: Optional[bytes],
        signing_key_id: Optional[str],
    ) -> tuple[bytes, str]:
        if signing_key is None:
            raw_key = os.environ.get("AEGIS_KERNEL_SIGNING_KEY")
            if not raw_key:
                raise KernelConfigurationError("AEGIS_KERNEL_SIGNING_KEY is required")
            signing_key = raw_key.encode("utf-8")
        elif not isinstance(signing_key, bytes) or not signing_key:
            raise KernelConfigurationError("AEGIS_KERNEL_SIGNING_KEY must be non-empty bytes")

        key_id = signing_key_id or os.environ.get("AEGIS_KERNEL_SIGNING_KEY_ID")
        if not key_id or not isinstance(key_id, str) or not key_id.strip():
            raise KernelConfigurationError("AEGIS_KERNEL_SIGNING_KEY_ID is required")
        key_id = key_id.strip()
        if key_id in COMPROMISED_KEY_IDS:
            raise KernelConfigurationError(f"COMPROMISED_SIGNING_KEY_ID:{key_id}")

        configured_algorithm = os.environ.get(
            "AEGIS_KERNEL_SIGNING_ALGORITHM", SIGNING_ALGORITHM
        )
        if configured_algorithm != SIGNING_ALGORITHM:
            raise KernelConfigurationError(
                f"UNSUPPORTED_SIGNING_ALGORITHM:{configured_algorithm}"
            )
        return signing_key, key_id

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.is_file():
            raise ValidationError("MISSING_CONSTITUTIONAL_MANIFEST")
        with self.manifest_path.open("r", encoding="utf-8") as handle:
            manifest = yaml.safe_load(handle)
        if not isinstance(manifest, dict):
            raise ValidationError("MALFORMED_CONSTITUTIONAL_MANIFEST")
        safety = manifest.get("safety")
        files = manifest.get("files")
        if not isinstance(safety, dict) or "delta_critical" not in safety:
            raise ValidationError("MISSING_DELTA_CRITICAL")
        if not isinstance(files, dict):
            raise ValidationError("MISSING_FILE_REGISTRY")
        return manifest

    def sign_envelope(self, envelope: WitnessEnvelope) -> str:
        if envelope.key_id in COMPROMISED_KEY_IDS:
            raise ValidationError(f"COMPROMISED_SIGNING_KEY_ID:{envelope.key_id}")
        if envelope.key_id != self.signing_key_id:
            raise ValidationError("SIGNING_KEY_ID_MISMATCH")
        if envelope.algorithm != SIGNING_ALGORITHM:
            raise ValidationError("SIGNING_ALGORITHM_MISMATCH")
        return hmac.new(
            self.signing_key,
            envelope.canonical_bytes(),
            hashlib.sha256,
        ).hexdigest()

    def verify_envelope(
        self,
        envelope: WitnessEnvelope | Mapping[str, Any],
        signature: str,
        *,
        artifact_path: Optional[str | Path] = None,
    ) -> bool:
        try:
            candidate = (
                envelope
                if isinstance(envelope, WitnessEnvelope)
                else WitnessEnvelope(**dict(envelope))
            )
            if candidate.key_id in COMPROMISED_KEY_IDS:
                return False
            if candidate.key_id != self.signing_key_id:
                return False
            if candidate.algorithm != SIGNING_ALGORITHM:
                return False
            if artifact_path is not None:
                current_digest = sha256_file(artifact_path)
                if not hmac.compare_digest(current_digest, candidate.artifact_sha256):
                    return False
            expected = self.sign_envelope(candidate)
            return hmac.compare_digest(expected, signature)
        except (TypeError, ValueError, ValidationError, OSError):
            return False

    def create_file_witness(
        self,
        *,
        request_id: str,
        artifact_path: str | Path,
        observed_at: int,
        sequence: int,
        parent_receipt_hash: str = GENESIS_PARENT_RECEIPT,
    ) -> tuple[WitnessEnvelope, str]:
        normalized_request = validate_request_structure(
            {
                "request_id": request_id,
                "task": "witness-file-integrity",
                "metrics": {
                    "uncertainty": 0.0,
                    "tool_failures": 0.0,
                    "novelty": 0.0,
                    "reviewer_disagreement": 0.0,
                },
            }
        )
        path = Path(artifact_path)
        envelope = WitnessEnvelope(
            schema_version=WITNESS_SCHEMA_VERSION,
            request_id=normalized_request["request_id"],
            artifact_path=str(path),
            artifact_sha256=sha256_file(path),
            observed_at=_require_nonnegative_int(observed_at, "observed_at"),
            sequence=_require_nonnegative_int(sequence, "sequence"),
            parent_receipt_hash=_require_sha256(
                parent_receipt_hash, "parent_receipt_hash"
            ),
            key_id=self.signing_key_id,
        )
        return envelope, self.sign_envelope(envelope)

    @staticmethod
    def _ensure_database_schema(conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            PRAGMA foreign_keys=ON;
            CREATE TABLE IF NOT EXISTS witnesses (
                witness_id TEXT PRIMARY KEY,
                timestamp INTEGER NOT NULL,
                phase TEXT NOT NULL,
                validity TEXT NOT NULL,
                model_version TEXT NOT NULL,
                index_hash TEXT NOT NULL,
                residual_delta REAL NOT NULL,
                plan_hash TEXT NOT NULL,
                output_hash TEXT NOT NULL,
                parent_witness TEXT,
                FOREIGN KEY(parent_witness) REFERENCES witnesses(witness_id)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
                witness_id TEXT PRIMARY KEY,
                plan TEXT,
                output TEXT,
                tool_calls TEXT,
                FOREIGN KEY(witness_id) REFERENCES witnesses(witness_id)
            );
            CREATE TABLE IF NOT EXISTS witness_envelopes (
                witness_id TEXT PRIMARY KEY,
                schema_version TEXT NOT NULL,
                request_id TEXT NOT NULL,
                artifact_path TEXT NOT NULL,
                artifact_sha256 TEXT NOT NULL,
                observed_at INTEGER NOT NULL,
                sequence INTEGER NOT NULL,
                parent_receipt_hash TEXT NOT NULL,
                key_id TEXT NOT NULL,
                algorithm TEXT NOT NULL CHECK (algorithm = 'hmac-sha256'),
                canonical_json TEXT NOT NULL,
                signature TEXT NOT NULL,
                UNIQUE(key_id, sequence),
                FOREIGN KEY(witness_id) REFERENCES witnesses(witness_id)
            );
            """
        )

    def process_transaction(self, request_payload: Any, raw_model_response: str) -> dict:
        request_id = "UNKNOWN"
        try:
            validated_req = validate_request_structure(request_payload)
            request_id = validated_req["request_id"]
            metrics = validated_req["metrics"]
            target_file = request_payload.get("target_file")

            manifest = self._load_manifest()
            delta = calculate_residual_delta(metrics)
            delta_critical = manifest["safety"]["delta_critical"]
            if not isinstance(delta_critical, (int, float)) or isinstance(
                delta_critical, bool
            ):
                raise ValidationError("INVALID_DELTA_CRITICAL")
            if delta >= float(delta_critical):
                raise ValidationError(f"ENTROPY_THRESHOLD_EXCEEDED:{delta:.6f}")

            proposal = validate_proposal_schema(
                raw_model_response,
                str(self.manifest_path),
                target_file,
            )

            plan_hash = hashlib.sha256(proposal["plan"].encode("utf-8")).hexdigest()
            output_hash = hashlib.sha256(
                proposal["output"].encode("utf-8")
            ).hexdigest()
            index_hash = sha256_file(self.manifest_path)
            artifact_content = {
                "plan": proposal["plan"],
                "output": proposal["output"],
                "tool_calls": proposal["tool_calls"],
            }
            artifact_sha256 = hashlib.sha256(
                canonical_json_bytes(artifact_content)
            ).hexdigest()
            artifact_path = target_file or f"kernel-one://artifacts/{request_id}"
            observed_at = int(time.time())

            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("BEGIN IMMEDIATE")
                self._ensure_database_schema(conn)
                latest = conn.execute(
                    """
                    SELECT witness_id, sequence
                    FROM witness_envelopes
                    ORDER BY sequence DESC
                    LIMIT 1
                    """
                ).fetchone()
                parent_receipt_hash = latest[0] if latest else GENESIS_PARENT_RECEIPT
                sequence = (int(latest[1]) + 1) if latest else 0

                envelope = WitnessEnvelope(
                    schema_version=WITNESS_SCHEMA_VERSION,
                    request_id=request_id,
                    artifact_path=artifact_path,
                    artifact_sha256=artifact_sha256,
                    observed_at=observed_at,
                    sequence=sequence,
                    parent_receipt_hash=parent_receipt_hash,
                    key_id=self.signing_key_id,
                )
                witness_id = envelope.receipt_hash()
                signature = self.sign_envelope(envelope)

                conn.execute(
                    """
                    INSERT INTO witnesses (
                        witness_id, timestamp, phase, validity, model_version,
                        index_hash, residual_delta, plan_hash, output_hash,
                        parent_witness
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        witness_id,
                        observed_at,
                        "HARMONIZE",
                        "VERIFIED",
                        self.model_version,
                        index_hash,
                        delta,
                        plan_hash,
                        output_hash,
                        latest[0] if latest else None,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO artifacts (witness_id, plan, output, tool_calls)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        witness_id,
                        proposal["plan"],
                        proposal["output"],
                        json.dumps(
                            proposal["tool_calls"],
                            sort_keys=True,
                            separators=(",", ":"),
                            ensure_ascii=False,
                        ),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO witness_envelopes (
                        witness_id, schema_version, request_id, artifact_path,
                        artifact_sha256, observed_at, sequence,
                        parent_receipt_hash, key_id, algorithm, canonical_json,
                        signature
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        witness_id,
                        envelope.schema_version,
                        envelope.request_id,
                        envelope.artifact_path,
                        envelope.artifact_sha256,
                        envelope.observed_at,
                        envelope.sequence,
                        envelope.parent_receipt_hash,
                        envelope.key_id,
                        envelope.algorithm,
                        envelope.canonical_bytes().decode("utf-8"),
                        signature,
                    ),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.close()

            return {
                "status": "HARMONIZE_SUCCESS",
                "request_id": request_id,
                "witness_id": witness_id,
                "receipt_hash": witness_id,
                "signature": signature,
                "witness_envelope": envelope.canonical_content(),
                "admissible_output": proposal["output"],
            }
        except Exception as exc:
            return {
                "status": "RECONCILED_FALLBACK",
                "request_id": request_id,
                "reason": str(exc),
            }


def _require_nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValidationError(f"INVALID_{field.upper()}")
    return value


def _require_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValidationError(f"INVALID_{field.upper()}")
    return value
