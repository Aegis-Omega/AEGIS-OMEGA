"""Read-only, fail-closed verification of preregistered AEGIS skill trials.

This is an evidence preflight, never an authority grant or tier mutation.
Keys, expected plan digest, source HEAD and registry root MUST be provided by a
trusted caller outside the candidate bundle. Signatures prove attribution of
claims, not authenticity of the underlying measurements or held-out status.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from hashlib import sha256
from math import comb
import re
from typing import Any, Mapping

from harness.sdk.skill_authority import canonical_bytes

PLAN_SCHEMA = "AEGIS_PROMOTION_PLAN_V1"
EVAL_SCHEMA = "AEGIS_PROMOTION_EVALUATION_V1"
DOMAIN = b"AEGIS_PROMOTION_EVIDENCE_V1\x00"
SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")
COMMIT_RE = re.compile(r"[0-9a-f]{40}\Z")
DECIMAL_RE = re.compile(r"(?:0|1)(?:\.[0-9]{1,9})?\Z")
ROLE_NAMES = ("operator", "evaluator", "reviewer")
SCORE_NAMES = ("candidate", "baseline", "no_change", "external")


class EvidenceDenied(ValueError):
    """The submitted evidence cannot authorize a promotion."""


@dataclass(frozen=True)
class EvidenceVerdict:
    outcome: str  # ELIGIBLE_FOR_REVIEW or DENIED; never a permission grant
    reason: str
    trial_count: int = 0
    comparisons: tuple[tuple[str, str, str, int], ...] = ()


def _need(condition: bool, reason: str) -> None:
    if not condition:
        raise EvidenceDenied(reason)


def _hex(value: Any, pattern: re.Pattern[str], reason: str) -> str:
    _need(isinstance(value, str) and bool(pattern.fullmatch(value)), reason)
    return value


def _score(value: Any) -> Decimal:
    _need(isinstance(value, str) and bool(DECIMAL_RE.fullmatch(value)), "SCORE_FORMAT_INVALID")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise EvidenceDenied("SCORE_FORMAT_INVALID") from exc
    _need(number.is_finite() and 0 <= number <= 1, "SCORE_RANGE_INVALID")
    return number


def _sig_payload(payload: Mapping[str, Any]) -> bytes:
    return sha256(DOMAIN + canonical_bytes(payload)).digest()


def _verify_signature(payload: Mapping[str, Any], signature: Any, role: str,
                      trust: Mapping[str, Any]) -> None:
    _need(isinstance(signature, Mapping), f"{role.upper()}_SIGNATURE_MISSING")
    signer = trust.get(role)
    _need(isinstance(signer, Mapping), f"{role.upper()}_NOT_TRUSTED")
    _need(signature.get("key_id") == signer.get("key_id"), f"{role.upper()}_KEY_ID_MISMATCH")
    key_hex = _hex(signer.get("public_key_hex"), SHA256_RE, f"{role.upper()}_KEY_INVALID")
    sig_hex = signature.get("signature_hex")
    _need(isinstance(sig_hex, str) and bool(re.fullmatch(r"[0-9a-f]{128}", sig_hex)),
          f"{role.upper()}_SIGNATURE_FORMAT_INVALID")
    try:
        # Existing AEGIS CCIL v5 uses Ed25519 over a SHA256 digest of the
        # canonical payload. Here the digest is additionally domain-separated.
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(key_hex)).verify(
            bytes.fromhex(sig_hex), _sig_payload(payload)
        )
    except ImportError as exc:
        raise EvidenceDenied("CRYPTOGRAPHIC_BACKEND_UNAVAILABLE") from exc
    except Exception as exc:
        raise EvidenceDenied(f"{role.upper()}_SIGNATURE_INVALID") from exc


def _trust_check(trust: Any) -> None:
    _need(isinstance(trust, Mapping), "TRUST_ANCHOR_MISSING")
    keys = []
    ids = []
    for role in ROLE_NAMES:
        t = trust.get(role)
        _need(isinstance(t, Mapping), f"{role.upper()}_NOT_TRUSTED")
        ident = t.get("key_id")
        _need(isinstance(ident, str) and bool(ident.strip()), "TRUST_ID_INVALID")
        ids.append(ident)
        keys.append(_hex(t.get("public_key_hex"), SHA256_RE, "TRUST_KEY_INVALID"))
    _need(len(set(keys)) == len(ROLE_NAMES) and len(set(ids)) == len(ROLE_NAMES),
          "SIGNER_ROLES_NOT_INDEPENDENT")


def _plan_check(plan: Any, *, expected_plan_sha256: str, expected_candidate: str,
                expected_registry_root: str) -> dict[str, str]:
    _need(isinstance(plan, Mapping), "PLAN_MISSING")
    _need(plan.get("schema_version") == PLAN_SCHEMA, "PLAN_SCHEMA_INVALID")
    _hex(expected_plan_sha256, SHA256_RE, "EXPECTED_PLAN_HASH_INVALID")
    _hex(expected_candidate, COMMIT_RE, "EXPECTED_HEAD_INVALID")
    _hex(expected_registry_root, SHA256_RE, "EXPECTED_REGISTRY_ROOT_INVALID")
    _need(sha256(canonical_bytes(plan)).hexdigest() == expected_plan_sha256,
          "PLAN_NOT_PREREGISTERED_OR_MODIFIED")
    _need(plan.get("candidate_commit") == expected_candidate, "CANDIDATE_HEAD_MISMATCH")
    _need(plan.get("registry_root") == expected_registry_root, "REGISTRY_ROOT_MISMATCH")
    _hex(plan.get("baseline_commit"), COMMIT_RE, "BASELINE_HEAD_INVALID")
    for label in ("no_change_root", "external_baseline_root"):
        _hex(plan.get(label), SHA256_RE, f"{label.upper()}_INVALID")
    _need(isinstance(plan.get("skill_id"), str) and bool(plan["skill_id"].strip()),
          "SKILL_ID_MISSING")
    _need(plan.get("direction") in ("higher", "lower"), "METRIC_DIRECTION_INVALID")
    alpha = _score(plan.get("alpha"))
    margin = _score(plan.get("minimum_mean_gain"))
    _need(0 < alpha <= Decimal("0.05"), "SIGNIFICANCE_NOT_PREREGISTERED")
    _need(margin > 0, "EFFECT_THRESHOLD_NOT_PREREGISTERED")
    max_regressions = plan.get("maximum_regressions")
    _need(type(max_regressions) is int and 0 <= max_regressions < 30,
          "REGRESSION_BUDGET_INVALID")
    tasks = plan.get("tasks")
    _need(isinstance(tasks, list) and len(tasks) >= 30, "FEWER_THAN_30_PREREGISTERED_TASKS")
    _need(len(tasks) <= 5000, "TASK_LIMIT_EXCEEDED")
    seen = {}
    seen_digests = set()
    for task in tasks:
        _need(isinstance(task, Mapping), "TASK_MALFORMED")
        tid = task.get("id")
        _need(isinstance(tid, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{1,96}", tid),
              "TASK_ID_INVALID")
        _need(tid not in seen, "DUPLICATE_PREREGISTERED_TASK")
        digest = _hex(task.get("task_sha256"), SHA256_RE, "TASK_DIGEST_INVALID")
        _need(digest not in seen_digests, "DUPLICATE_PREREGISTERED_TASK_DIGEST")
        seen_digests.add(digest)
        seen[tid] = digest
    return seen


def _comparison(candidate: list[Decimal], comparator: list[Decimal],
                direction: str, alpha: Decimal, margin: Decimal,
                max_regressions: int, label: str) -> tuple[str, str, str, int]:
    deltas = [a - b if direction == "higher" else b - a
              for a, b in zip(candidate, comparator)]
    gain = sum(deltas, Decimal(0)) / Decimal(len(deltas))
    wins = sum(d > 0 for d in deltas)
    losses = sum(d < 0 for d in deltas)
    n = wins + losses
    _need(n >= 1, f"{label.upper()}_ALL_TIES")
    # Exact one-sided sign test, conservative Bonferroni control for 3 comparators.
    p = Fraction(sum(comb(n, k) for k in range(wins, n + 1)), 2 ** n)
    _need(Decimal(p.numerator) * 3 <= alpha * Decimal(p.denominator),
          f"{label.upper()}_NOT_SIGNIFICANT")
    _need(gain >= margin, f"{label.upper()}_EFFECT_TOO_SMALL")
    _need(losses <= max_regressions, f"{label.upper()}_TOO_MANY_REGRESSIONS")
    return (label, str(gain), f"{p.numerator}/{p.denominator}", losses)


def verify_promotion_evidence(*, plan: Any, plan_signature: Any,
                              evaluation: Any, signatures: Any, trust: Any,
                              expected_plan_sha256: str, expected_candidate: str,
                              expected_registry_root: str) -> EvidenceVerdict:
    """Verify signed, precommitted paired comparisons without changing tiers.

    Trust and expected roots MUST come from an external protected caller. An
    evaluator's signed score is an attributed claim, not independent proof the
    underlying task ran; independent replay remains a separate release gate.
    """
    try:
        _trust_check(trust)
        task_map = _plan_check(plan, expected_plan_sha256=expected_plan_sha256,
                               expected_candidate=expected_candidate,
                               expected_registry_root=expected_registry_root)
        _verify_signature(plan, plan_signature, "operator", trust)
        _need(isinstance(evaluation, Mapping) and isinstance(signatures, Mapping),
              "EVALUATION_OR_SIGNATURES_MISSING")
        _need(evaluation.get("schema_version") == EVAL_SCHEMA, "EVALUATION_SCHEMA_INVALID")
        _need(evaluation.get("plan_sha256") == expected_plan_sha256, "EVALUATION_PLAN_MISMATCH")
        _need(evaluation.get("candidate_commit") == expected_candidate, "EVALUATION_HEAD_MISMATCH")
        _need(evaluation.get("registry_root") == expected_registry_root,
              "EVALUATION_REGISTRY_MISMATCH")
        _need(evaluation.get("baseline_commit") == plan["baseline_commit"],
              "EVALUATION_BASELINE_MISMATCH")
        _need(evaluation.get("no_change_root") == plan["no_change_root"],
              "EVALUATION_NO_CHANGE_MISMATCH")
        _need(evaluation.get("external_baseline_root") == plan["external_baseline_root"],
              "EVALUATION_EXTERNAL_BASELINE_MISMATCH")
        run_id = evaluation.get("run_id")
        _need(isinstance(run_id, str) and re.fullmatch(r"[A-Za-z0-9_.:-]{8,128}", run_id),
              "EVALUATION_RUN_UNIDENTIFIED")
        _verify_signature(evaluation, signatures.get("evaluator"), "evaluator", trust)
        _verify_signature(evaluation, signatures.get("reviewer"), "reviewer", trust)
        trials = evaluation.get("trials")
        _need(isinstance(trials, list) and len(trials) == len(task_map),
              "TRIAL_SET_NOT_PREREGISTERED")
        _need(len(trials) <= 5000, "TASK_LIMIT_EXCEEDED")
        records: dict[str, Mapping[str, Any]] = {}
        for trial in trials:
            _need(isinstance(trial, Mapping), "TRIAL_MALFORMED")
            tid = trial.get("id")
            _need(isinstance(tid, str) and tid in task_map, "UNPLANNED_TASK")
            _need(tid not in records, "DUPLICATE_TRIAL")
            _need(trial.get("task_sha256") == task_map[tid], "TASK_DIGEST_MISMATCH")
            for score in SCORE_NAMES:
                _score(trial.get(f"{score}_score"))
                _hex(trial.get(f"{score}_output_sha256"), SHA256_RE,
                     "OUTPUT_DIGEST_MISSING")
            records[tid] = trial
        _need(set(records) == set(task_map), "MISSING_PREREGISTERED_TRIALS")
        ordered = [records[t["id"]] for t in plan["tasks"]]
        scores = {name: [_score(t[f"{name}_score"]) for t in ordered]
                  for name in SCORE_NAMES}
        comparisons = tuple(_comparison(scores["candidate"], scores[name],
                                        plan["direction"], _score(plan["alpha"]),
                                        _score(plan["minimum_mean_gain"]),
                                        plan["maximum_regressions"], name)
                            for name in ("baseline", "no_change", "external"))
        return EvidenceVerdict("ELIGIBLE_FOR_REVIEW", "SIGNED_STATISTICAL_PREFLIGHT_ONLY",
                               len(ordered), comparisons)
    except EvidenceDenied as exc:
        return EvidenceVerdict("DENIED", str(exc))
    except (TypeError, ValueError, OverflowError, KeyError) as exc:
        # Reject malformed canonical structures, non-JSON objects and overflow.
        return EvidenceVerdict("DENIED", f"MALFORMED_EVIDENCE:{type(exc).__name__}")
