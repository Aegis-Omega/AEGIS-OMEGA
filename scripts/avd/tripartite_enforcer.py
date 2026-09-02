from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .bundle_commitment import canonical_bundle_bytes
from .crypto_util import avd_digest


class TripartiteEnforcementError(RuntimeError):
    pass


@dataclass(frozen=True)
class CommitmentSnapshotV1:
    h_problem: str
    h_verifier: str
    h_oracle: str


class TripartiteRunner:
    """Pre/post commitment guard for the benchmark judge.

    The committed units are complete deterministic directory bundles, not
    individual source files. A trial runner must call verify_commitments()
    before evaluation and again after verifier/oracle execution. Any drift is
    a verifier-compromise condition, not a normal candidate failure.
    """

    def __init__(
        self,
        problem_root: Path,
        verifier_root: Path,
        oracle_root: Path,
        expected: dict[str, str],
    ):
        self.problem_root = problem_root
        self.verifier_root = verifier_root
        self.oracle_root = oracle_root
        self.expected = dict(expected)
        required = {"PROBLEM", "VERIFIER", "ORACLE"}
        if set(self.expected) != required:
            raise TripartiteEnforcementError("EXPECTED_COMMITMENT_SET_INVALID")
        for domain, digest in self.expected.items():
            if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
                raise TripartiteEnforcementError(f"EXPECTED_{domain}_DIGEST_INVALID")

    def current_commitments(self) -> CommitmentSnapshotV1:
        return CommitmentSnapshotV1(
            h_problem=avd_digest("PROBLEM", canonical_bundle_bytes(self.problem_root)),
            h_verifier=avd_digest("VERIFIER", canonical_bundle_bytes(self.verifier_root)),
            h_oracle=avd_digest("ORACLE", canonical_bundle_bytes(self.oracle_root)),
        )

    def verify_commitments(self) -> CommitmentSnapshotV1:
        current = self.current_commitments()
        checks = (
            ("H_P", current.h_problem, self.expected["PROBLEM"]),
            ("H_V", current.h_verifier, self.expected["VERIFIER"]),
            ("H_O", current.h_oracle, self.expected["ORACLE"]),
        )
        for label, actual, expected in checks:
            if actual != expected:
                raise TripartiteEnforcementError(
                    f"{label}_MISMATCH:computed={actual}:expected={expected}"
                )
        return current

    def guarded(self, evaluator):
        """Execute evaluator between two identical commitment checks."""
        before = self.verify_commitments()
        result = evaluator()
        after = self.verify_commitments()
        if after != before:
            raise TripartiteEnforcementError("COMMITMENT_DRIFT_DURING_EVALUATION")
        return result
