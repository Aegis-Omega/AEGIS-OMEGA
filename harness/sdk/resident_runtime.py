"""Resident-runtime facade with closed-loop epistemic actuation.

The large production implementation remains byte-identical in
``resident_runtime_impl``.  This facade adds the bounded sensing/evidence
contract required by the resident path without rewriting unrelated execution,
effect-verification, admission, replay, or memory logic.

Core invariant:

    compute/capability != observation != evidence != learning != authority.

A successful knowledge-verification path is therefore never used as a proxy for
measured information gain.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import os
from pathlib import Path
from typing import Any

from harness.sdk import resident_runtime_impl as _impl
from harness.sdk.resident_runtime_impl import *  # noqa: F401,F403
from harness.sdk.closed_loop_epistemic_actuation import (
    ObservationEvidenceV1,
    ObservationTransformV1,
    verify_observation_effect,
)
from harness.sdk.sovereign_execution import canonical_hash


@dataclass(frozen=True)
class AnalysisPacketV1(_impl.AnalysisPacketV1):
    """Resident analysis packet with explicit sensing/evidence bindings.

    Zero/None means the corresponding epistemic effect has not been established.
    In particular, ``observed_information_gain_bps is None`` is deliberately
    distinct from an observed gain of zero.
    """

    observation_transform_root: str = _impl.ZERO_HASH
    observation_receipt_root: str = _impl.ZERO_HASH
    observed_information_gain_bps: int | None = None


# Functions defined in the implementation module resolve this global at call
# time. Rebinding preserves the mature implementation while extending packets.
_impl.AnalysisPacketV1 = AnalysisPacketV1


class ResidentRuntime(_impl.ResidentRuntime):
    """Production resident runtime with action-conditioned observation receipts."""

    def _persist_observation_receipt(
        self,
        *,
        transform: ObservationTransformV1,
        evidence: ObservationEvidenceV1,
        receipt: Any,
    ) -> None:
        observations = self.state_root / "observations"
        observations.mkdir(parents=True, exist_ok=True)
        path = observations / f"{receipt.root}.json"
        payload = {
            "schema_version": "1.0.0",
            "transform": asdict(transform),
            "evidence": asdict(evidence),
            "receipt": asdict(receipt),
            "authority": _impl.EVIDENCE_ONLY,
            "non_claims": [
                "NO_INFORMATION_GAIN_WITHOUT_CALIBRATED_MEASUREMENT",
                "NO_LEARNING_FROM_OBSERVATION_RECEIPT",
                "NO_EXECUTION_OR_ADMISSION_AUTHORITY",
            ],
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        if path.exists():
            if path.read_text(encoding="utf-8") != encoded:
                raise _impl.ResidentRuntimeError("OBSERVATION_RECEIPT_COLLISION")
            return
        temporary = observations / f".{receipt.root}.tmp"
        temporary.write_text(encoded, encoding="utf-8")
        os.replace(temporary, path)

    def _observe_repository(
        self,
        event: _impl.RepositoryEventV1,
    ) -> tuple[AnalysisPacketV1 | None, str | None]:
        packet, failure = super()._observe_repository(event)
        if packet is None:
            return None, failure

        transform = ObservationTransformV1(
            action_id=f"observe:{packet.run_id}:{packet.task_id}",
            action_kind="REPOSITORY_FILE_READ",
            target_scope=f"{packet.repository_head}:{packet.changed_path}",
            predicted_transform="GIT_SHOW_AND_WORKTREE_BYTE_EXACT_VIEW",
            budget_units=1,
        )
        evidence = ObservationEvidenceV1(
            action_id=transform.action_id,
            observed_transform=transform.predicted_transform,
            observation_root=packet.observation_root,
            # The existing resident path has no calibrated belief distribution
            # or critical-feature oracle.  Missing measurements remain missing;
            # a successful file verification is not converted into fake IG.
            prior_entropy_bits=None,
            posterior_entropy_bits=None,
            calibration_before_bps=None,
            calibration_after_bps=None,
            missed_critical_feature=None,
        )
        observation_receipt = verify_observation_effect(transform, evidence)
        self._persist_observation_receipt(
            transform=transform,
            evidence=evidence,
            receipt=observation_receipt,
        )
        extended = replace(
            packet,
            observation_transform_root=transform.root,
            observation_receipt_root=observation_receipt.root,
            observed_information_gain_bps=None,
        )
        return extended, None

    def _finalize(
        self,
        *,
        event: _impl.RepositoryEventV1,
        run_id: str,
        task_id: str,
        decision: str,
        reasons: tuple[str, ...],
        warnings: tuple[str, ...],
        packet: AnalysisPacketV1 | None,
        candidate_claim: _impl.KnowledgeClaimV1 | None,
        admitted_claim: _impl.KnowledgeClaimV1 | None,
        experiment_id: str | None,
        verification_root: str | None,
        admission_root: str | None,
        evidence_roots: tuple[str, ...],
        local_calls: int,
        frontier_calls: int,
        independent_model_confirmations: int,
        artifact_digest: str | None = None,
    ) -> _impl.ResidentRunReceiptV1:
        """Finalize a run without conflating VERIFIED with information gain."""
        if decision not in _impl.KNOWLEDGE_DECISIONS:
            decision = _impl.UNKNOWN
            reasons = reasons + ("UNKNOWN_KNOWLEDGE_DECISION",)
        _, event_log_root = self.store.append(
            event_id=run_id,
            event_kind="KNOWLEDGE_DECISION",
            payload={
                "run_id": run_id,
                "task_id": task_id,
                "claim_id": candidate_claim.claim_id if candidate_claim else None,
                "experiment_id": experiment_id,
                "knowledge_decision": decision,
                "reason_codes": reasons,
                "authority_before": self.authority_ceiling,
                "authority_after": self.authority_ceiling,
                "verification_receipt_root": verification_root,
                "admission_receipt_root": admission_root,
                "observation_transform_root": (
                    packet.observation_transform_root if packet is not None else _impl.ZERO_HASH
                ),
                "observation_receipt_root": (
                    packet.observation_receipt_root if packet is not None else _impl.ZERO_HASH
                ),
            },
        )
        projection = self.store.update_self_model(
            decision,
            authority_denied="AUTHORITY_ESCALATION_DENIED" in reasons,
        )
        runs = projection.get("runs", 0)
        verified = projection.get("verified", 0)
        information_gain_established = bool(
            packet is not None and packet.observed_information_gain_bps is not None
        )
        self_model: dict[str, Any] = {
            **projection,
            "verification_rate_bps": 0 if runs == 0 else (verified * 10_000) // runs,
            "unique_provenance_roots": len(set(evidence_roots)),
            "independent_model_confirmations": independent_model_confirmations,
            "expected_information_gain_bps": (
                packet.expected_information_gain_bps if packet is not None else 0
            ),
            "observed_information_gain_bps": (
                packet.observed_information_gain_bps
                if information_gain_established
                else 0
            ),
            "information_gain_established": information_gain_established,
            "observation_transform_root": (
                packet.observation_transform_root if packet is not None else _impl.ZERO_HASH
            ),
            "observation_receipt_root": (
                packet.observation_receipt_root if packet is not None else _impl.ZERO_HASH
            ),
            "epistemic_debt": projection.get("quarantined", 0) + projection.get("unknown", 0),
            "verification_debt": projection.get("unknown", 0),
        }
        event_digest = self._event_digest(event)
        receipt_without_bundle = _impl.ResidentRunReceiptV1(
            schema_version="1.0.0",
            run_id=run_id,
            event_id=event.event_id,
            event_digest=event_digest,
            task_id=task_id,
            claim_id=candidate_claim.claim_id if candidate_claim else None,
            experiment_id=experiment_id,
            repository_head=event.repository_head,
            changed_path=event.changed_path,
            knowledge_decision=decision,
            reason_codes=reasons,
            warnings=warnings,
            candidate_claim_kind=candidate_claim.claim_kind if candidate_claim else None,
            candidate_epistemic_tier=candidate_claim.epistemic_tier if candidate_claim else None,
            admitted_claim_kind=admitted_claim.claim_kind if admitted_claim else None,
            verification_receipt_root=verification_root,
            admission_receipt_root=admission_root,
            evidence_roots=tuple(dict.fromkeys(evidence_roots)),
            event_log_root=event_log_root,
            authority_before=self.authority_ceiling,
            authority_after=self.authority_ceiling,
            local_calls=local_calls,
            frontier_calls=frontier_calls,
            avoided_frontier_calls=int(frontier_calls == 0),
            self_model=self_model,
            bundle_digest=_impl.ZERO_HASH,
            requester_root=event.requester_root,
            admitted_claim_id=admitted_claim.claim_id if admitted_claim else None,
        )
        receipt_body = asdict(receipt_without_bundle)
        receipt_body.pop("bundle_digest")
        bundle_body = {
            "schema_version": "1.0.0",
            "receipt": receipt_body,
            "candidate_claim": asdict(candidate_claim) if candidate_claim else None,
            "admitted_claim": asdict(admitted_claim) if admitted_claim else None,
            "artifact_digest": artifact_digest,
            "integrity_scope": "REPLAY_INTEGRITY_AND_LINEAGE_NOT_SEMANTIC_TRUTH",
        }
        bundle_digest = canonical_hash("AEGIS_RESIDENT_RUN_BUNDLE_V1", bundle_body)
        receipt = replace(receipt_without_bundle, bundle_digest=bundle_digest)
        runs_dir = self.state_root / "runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        path = runs_dir / f"{run_id}.json"
        payload = {
            "bundle_body": bundle_body,
            "bundle_digest": bundle_digest,
            "receipt": asdict(receipt),
        }
        temporary = runs_dir / f".{run_id}.tmp"
        temporary.write_text(
            json.dumps(payload, sort_keys=True, separators=(",", ":")),
            encoding="utf-8",
        )
        os.replace(temporary, path)
        self.store.put_run(receipt, self._idempotency_scope(event))
        return receipt


# Ensure methods in the implementation module that instantiate the runtime by
# explicit global name can resolve the upgraded facade when imported after us.
_impl.AnalysisPacketV1 = AnalysisPacketV1
