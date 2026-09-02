from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Mapping

from .frozen_reference import FrozenReferenceV1
from .mutation_builder import MutationFixtureV1
from .mutation_decision import MutationDecisionV1
from .submission_policy import SubmissionPolicyError, validate_submission_surface


_SHA64 = re.compile(r"^[0-9a-f]{64}$")
Verifier = Callable[[Path], Mapping[str, object]]


class MutationCalibrationError(RuntimeError):
    pass


class MutationCalibrationHarnessV1:
    """Judge-side mutation calibration with targeted rejection classes.

    Every evaluation starts from a fresh copy of the historical RED baseline.
    Provenance/authority/commitment barriers execute before the Coq callback so
    an unrelated later failure cannot satisfy a targeted mutant contract.
    """

    def __init__(
        self,
        *,
        reference: FrozenReferenceV1,
        expected_h_verifier: str,
        expected_h_oracle: str,
    ) -> None:
        if not reference.is_frozen:
            raise MutationCalibrationError("REFERENCE_NOT_FROZEN")
        if _SHA64.fullmatch(expected_h_verifier) is None:
            raise MutationCalibrationError("INVALID_EXPECTED_H_VERIFIER")
        if _SHA64.fullmatch(expected_h_oracle) is None:
            raise MutationCalibrationError("INVALID_EXPECTED_H_ORACLE")
        self.reference = reference
        self.expected_h_verifier = expected_h_verifier
        self.expected_h_oracle = expected_h_oracle

    def evaluate(
        self,
        *,
        baseline_root: Path,
        fixture: MutationFixtureV1,
        verifier: Verifier,
    ) -> MutationDecisionV1:
        baseline_root = baseline_root.resolve()
        if not baseline_root.is_dir():
            raise MutationCalibrationError("BASELINE_ROOT_NOT_DIRECTORY")

        with tempfile.TemporaryDirectory(prefix=f"avd-{fixture.mutation_id.lower()}-") as tmp:
            candidate_root = Path(tmp) / "candidate"
            shutil.copytree(baseline_root, candidate_root, symlinks=True)
            self._materialize_fixture(candidate_root, fixture)

            anchor_failure = self._anchor_failure(fixture)
            if anchor_failure is not None:
                return MutationDecisionV1.validate(
                    mutation_id=fixture.mutation_id,
                    observed_decision="REJECT",
                    observed_reason_class="ANCHOR_BINDING_REJECT",
                    observed_reason=anchor_failure,
                )

            if fixture.authority_override is not None and fixture.authority_override != "NONE":
                return MutationDecisionV1.validate(
                    mutation_id=fixture.mutation_id,
                    observed_decision="REJECT",
                    observed_reason_class="AUTHORITY_REJECT",
                    observed_reason="AUTHORITY_SCOPE_WIDEN",
                )

            commitment_failure = self._commitment_failure(fixture)
            if commitment_failure is not None:
                return MutationDecisionV1.validate(
                    mutation_id=fixture.mutation_id,
                    observed_decision="REJECT",
                    observed_reason_class="COMMITMENT_REJECT",
                    observed_reason=commitment_failure,
                )

            try:
                validate_submission_surface(
                    baseline_root,
                    candidate_root,
                    allowed_path=Path(self.reference.source_path),
                )
            except SubmissionPolicyError as exc:
                return MutationDecisionV1.validate(
                    mutation_id=fixture.mutation_id,
                    observed_decision="REJECT",
                    observed_reason_class="SUBMISSION_SURFACE_REJECT",
                    observed_reason=str(exc),
                )

            result = verifier(candidate_root)
            status = result.get("status")
            reason = result.get("reason")
            if status not in {"PASS", "FAIL"}:
                raise MutationCalibrationError(
                    f"INVALID_VERIFIER_STATUS:{fixture.mutation_id}:{status}"
                )
            if not isinstance(reason, str) or not reason:
                raise MutationCalibrationError(
                    f"INVALID_VERIFIER_REASON:{fixture.mutation_id}"
                )

            if status == "PASS":
                return MutationDecisionV1.validate(
                    mutation_id=fixture.mutation_id,
                    observed_decision="ACCEPT",
                    observed_reason_class="VERIFIER_ACCEPT",
                    observed_reason=reason,
                )

            if reason.startswith("DECLARED_ASSUMPTION_OR_ADMISSION_FOUND"):
                reason_class = "PROOF_INTEGRITY_REJECT"
            else:
                reason_class = "CANDIDATE_SEMANTIC_REJECT"
            return MutationDecisionV1.validate(
                mutation_id=fixture.mutation_id,
                observed_decision="REJECT",
                observed_reason_class=reason_class,
                observed_reason=reason,
            )

    def _materialize_fixture(self, candidate_root: Path, fixture: MutationFixtureV1) -> None:
        target = candidate_root / self.reference.source_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(fixture.candidate_source_bytes)

        for rel, content in fixture.extra_files.items():
            path = Path(rel)
            if path.is_absolute() or ".." in path.parts or ".git" in path.parts:
                raise MutationCalibrationError(
                    f"UNSAFE_MUTATION_EXTRA_PATH:{fixture.mutation_id}:{rel}"
                )
            dst = candidate_root / path
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_bytes(content)

    def _anchor_failure(self, fixture: MutationFixtureV1) -> str | None:
        override = fixture.anchor_override
        if override is None:
            return None
        allowed = {"commit_sha", "tree_sha"}
        if set(override) != allowed:
            return "ANCHOR_OVERRIDE_SURFACE_MISMATCH"
        if override["commit_sha"] != self.reference.commit_sha:
            return "ANCHOR_COMMIT_MISMATCH"
        if override["tree_sha"] != self.reference.tree_sha:
            return "ANCHOR_TREE_MISMATCH"
        return None

    def _commitment_failure(self, fixture: MutationFixtureV1) -> str | None:
        override = fixture.commitment_override
        if override is None:
            return None
        allowed = {"h_verifier", "h_oracle"}
        if not set(override).issubset(allowed):
            return "COMMITMENT_OVERRIDE_SURFACE_MISMATCH"
        if "h_verifier" in override and override["h_verifier"] != self.expected_h_verifier:
            return "H_VERIFIER_MISMATCH"
        if "h_oracle" in override and override["h_oracle"] != self.expected_h_oracle:
            return "H_ORACLE_MISMATCH"
        return None
