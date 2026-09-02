from __future__ import annotations

import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .coq_signature_contract import build_signature_contract


REQUIRED_THEOREMS = (
    "corn_ir_to_o0_preserves_rat_v1",
    "corn_ir_to_o0_strict_v1",
    "corn_ir_to_o0_preserves_zero_v1",
    "corn_ir_to_o0_preserves_one_v1",
    "corn_ir_to_o0_preserves_plus_v1",
    "corn_ir_to_o0_preserves_mult_v1",
    "corn_ir_to_o0_preserves_le_v1",
)

_TARGET_REL = Path("sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v")
_SPEC_REL = Path("sovereign-omega-v2/formal/tests/Weil/CornO0MorphismBridgeSpec.v")
_FORBIDDEN_DECLARATION = re.compile(
    r"^[\t ]*(?:Axiom|Axioms|Parameter|Parameters|Admitted)\b|\badmit\s*\.",
    re.MULTILINE,
)


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def verify_coq_candidate(workspace_root: Path) -> dict[str, Any]:
    workspace_root = workspace_root.resolve()
    target = workspace_root / _TARGET_REL
    spec = workspace_root / _SPEC_REL
    weil_dir = workspace_root / "sovereign-omega-v2/formal/theories/Weil"
    test_dir = workspace_root / "sovereign-omega-v2/formal/tests/Weil"

    if not target.is_file():
        return {"status": "FAIL", "reason": "EXPECTED_RED_MISSING_PRODUCTION_MODULE"}
    if not spec.is_file():
        return {"status": "FAIL", "reason": "FROZEN_SPEC_MISSING"}

    source_text = target.read_text(encoding="utf-8")
    if _FORBIDDEN_DECLARATION.search(source_text):
        return {"status": "FAIL", "reason": "DECLARED_ASSUMPTION_OR_ADMISSION_FOUND"}

    compile_source = _run(["coqc", "-Q", str(weil_dir), "", str(target)], cwd=workspace_root)
    if compile_source.returncode != 0:
        return {
            "status": "FAIL",
            "reason": "COMPILATION_ERROR",
            "stdout": compile_source.stdout,
            "stderr": compile_source.stderr,
        }

    # The historical RED spec checks public names, but name existence alone is
    # insufficient: a captured candidate could keep the names and weaken their
    # propositions. A verifier-owned exact-type assignment closes that gap.
    with tempfile.TemporaryDirectory(prefix="avd-a1c-signature-") as tmp:
        signature_path = Path(tmp) / "AVDA1cSignatureContract.v"
        signature_path.write_text(build_signature_contract(), encoding="utf-8")
        compile_signature = _run(
            ["coqc", "-Q", str(weil_dir), "", str(signature_path)],
            cwd=workspace_root,
        )
    if compile_signature.returncode != 0:
        return {
            "status": "FAIL",
            "reason": "SIGNATURE_CONTRACT_FAILURE",
            "stdout": compile_signature.stdout,
            "stderr": compile_signature.stderr,
        }

    compile_spec = _run(
        ["coqc", "-Q", str(weil_dir), "", "-Q", str(test_dir), "", str(spec)],
        cwd=workspace_root,
    )
    if compile_spec.returncode != 0:
        return {
            "status": "FAIL",
            "reason": "SPEC_CONTRACT_FAILURE",
            "stdout": compile_spec.stdout,
            "stderr": compile_spec.stderr,
        }

    for theorem in REQUIRED_THEOREMS:
        script = (
            "Set Coqtop Exit On Error.\n"
            "Require Import CornO0MorphismBridge.\n"
            f"Print Assumptions {theorem}.\n"
        )
        with tempfile.NamedTemporaryFile("w", suffix=".v", encoding="utf-8", delete=False) as handle:
            handle.write(script)
            query_path = Path(handle.name)
        try:
            check = _run(
                ["coqtop", "-quiet", "-batch", "-Q", str(weil_dir), "", "-l", str(query_path)],
                cwd=workspace_root,
            )
        finally:
            query_path.unlink(missing_ok=True)

        combined = check.stdout + "\n" + check.stderr
        if check.returncode != 0:
            return {"status": "FAIL", "reason": f"THEOREM_NOT_FOUND:{theorem}", "output": combined}
        if "Closed under the global context" not in combined or re.search(r"^Axioms:", combined, re.MULTILINE):
            return {"status": "FAIL", "reason": f"UNVETTED_AXIOMS_IN_THEOREM:{theorem}", "output": combined}

    return {"status": "PASS", "reason": "ALL_THEOREMS_CLOSED_AND_SIGNATURE_LOCKED"}
