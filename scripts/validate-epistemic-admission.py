#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.sdk.epistemic_admission import ClaimStatus, FailureLocus, FieldProvenance, Route

SCHEMA = ROOT / "schemas/epistemic-admission-v1.schema.json"
BOOTSTRAP = ROOT / ".claude/epistemic/bootstrap.md"
INTAKE = ROOT / ".claude/hooks/user-prompt-intake.sh"

REQUIRED_BOOTSTRAP_MARKERS = (
    "Epistemic Debugging Bootstrap",
    "No claim may possess greater epistemic authority",
    "search miss ≠ nonexistence",
    "F-18",
    "Verify current repository facts afresh",
)
REQUIRED_INTAKE_MARKERS = (
    "ObservationChain(integrity-only)",
    "Claim-status-required:",
    "chain-integrity≠truth",
    "chain-integrity≠identity",
    "chain-integrity≠consciousness",
    ".claude/epistemic/bootstrap.md",
)
FORBIDDEN_INTAKE_MARKERS = (
    "MetacognitiveLoop(live):",
    "temporal-mass=",
)
TESTS_REQUIRED = (
    "harness.tests.test_epistemic_admission",
    "harness.tests.test_epistemic_bootstrap",
    "harness.tests.test_epistemic_workflow_contract",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    return parser.parse_args()


def validate_schema() -> tuple[bool, list[str]]:
    errors: list[str] = []
    try:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    except Exception as exc:
        return False, [f"SCHEMA_PARSE_FAILED:{type(exc).__name__}"]

    defs = schema.get("$defs", {})
    expected = {
        "ClaimStatus": [x.value for x in ClaimStatus],
        "FieldProvenance": [x.value for x in FieldProvenance],
        "Route": [x.value for x in Route],
        "FailureLocus": [x.value for x in FailureLocus],
    }
    for name, values in expected.items():
        actual = defs.get(name, {}).get("enum")
        if actual != values:
            errors.append(f"SCHEMA_ENUM_MISMATCH:{name}")

    for name in ("EpistemicClaimV1", "AdmissionDecisionV1", "LoadBearingFieldV1", "SourceBindingV1"):
        if name not in defs:
            errors.append(f"SCHEMA_DEF_MISSING:{name}")
    return not errors, errors


def validate_bootstrap() -> tuple[bool, list[str]]:
    errors: list[str] = []
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8") if BOOTSTRAP.is_file() else ""
    intake = INTAKE.read_text(encoding="utf-8") if INTAKE.is_file() else ""

    for marker in REQUIRED_BOOTSTRAP_MARKERS:
        if marker not in bootstrap:
            errors.append(f"BOOTSTRAP_MARKER_MISSING:{marker}")
    for marker in REQUIRED_INTAKE_MARKERS:
        if marker not in intake:
            errors.append(f"INTAKE_MARKER_MISSING:{marker}")
    for marker in FORBIDDEN_INTAKE_MARKERS:
        if marker in intake:
            errors.append(f"INTAKE_FORBIDDEN_MARKER:{marker}")
    return not errors, errors


def main() -> int:
    args = parse_args()
    schema_valid, schema_errors = validate_schema()
    bootstrap_valid, bootstrap_errors = validate_bootstrap()
    violations = schema_errors + bootstrap_errors
    receipt = {
        "authority": "EVIDENCE_ONLY_NOT_ADMISSION_AUTHORITY",
        "bootstrap_valid": bootstrap_valid,
        "candidate_sha": args.candidate_sha,
        "schema_valid": schema_valid,
        "tests_required": list(TESTS_REQUIRED),
        "violations": violations,
    }
    print(json.dumps(receipt, sort_keys=True, separators=(",", ":")))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
