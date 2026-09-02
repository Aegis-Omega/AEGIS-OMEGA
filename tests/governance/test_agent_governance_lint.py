from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "agent_governance_lint.py"


def _load_lint_module():
    assert SCRIPT_PATH.exists(), "scripts/agent_governance_lint.py must exist"
    spec = importlib.util.spec_from_file_location("agent_governance_lint", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _seed_quarantine(root: Path) -> None:
    _write(
        root,
        "quarantine/legacy-quantum-demonstrator/server.py",
        "# LEGACY DIAGNOSTIC PROTOTYPE ONLY - ZERO RUNTIME OR VERIFICATION AUTHORITY\n"
        "# CONTAINS MOCK/RNG FALLBACKS - PROHIBITED FROM AEGIS KERNEL & ADMISSION PIPELINES\n",
    )


def _git_blob_sha(text: str) -> str:
    data = text.encode("utf-8")
    return hashlib.sha1(f"blob {len(data)}\0".encode("ascii") + data).hexdigest()


def test_clean_repo_shape_passes(tmp_path: Path) -> None:
    lint = _load_lint_module()
    _seed_quarantine(tmp_path)
    _write(tmp_path, "sovereign-omega-v2/src/core/clean.ts", "export const clean = true;\n")

    assert lint.collect_violations(tmp_path) == []


def test_live_legacy_quantum_server_is_rejected(tmp_path: Path) -> None:
    lint = _load_lint_module()
    _seed_quarantine(tmp_path)
    _write(tmp_path, "clients/gemma-holon/quantum/server.py", "print('legacy')\n")

    violations = lint.collect_violations(tmp_path)
    assert any(v.code == "LEGACY_RUNTIME_PATH_PRESENT" for v in violations)


def test_quarantine_requires_zero_authority_markers(tmp_path: Path) -> None:
    lint = _load_lint_module()
    _write(tmp_path, "quarantine/legacy-quantum-demonstrator/server.py", "# missing contract\n")

    violations = lint.collect_violations(tmp_path)
    assert any(v.code == "QUARANTINE_HEADER_MISSING" for v in violations)


def test_quarantine_body_is_bound_to_original_git_blob(tmp_path: Path) -> None:
    lint = _load_lint_module()
    historical = "#!/usr/bin/env python3\nprint('legacy')\n"
    quarantined = (
        "#!/usr/bin/env python3\n"
        "# LEGACY DIAGNOSTIC PROTOTYPE ONLY - ZERO RUNTIME OR VERIFICATION AUTHORITY\n"
        "# CONTAINS MOCK/RNG FALLBACKS - PROHIBITED FROM AEGIS KERNEL & ADMISSION PIPELINES\n"
        "print('legacy')\n"
    )
    path = _write(tmp_path, "quarantine/legacy-quantum-demonstrator/server.py", quarantined)
    expected = _git_blob_sha(historical)

    assert lint.collect_violations(tmp_path, expected_legacy_blob_sha=expected) == []

    path.write_text(quarantined.replace("print('legacy')", "print('rewritten')"), encoding="utf-8")
    violations = lint.collect_violations(tmp_path, expected_legacy_blob_sha=expected)
    assert any(v.code == "QUARANTINE_CONTENT_DRIFT" for v in violations)


@pytest.mark.parametrize(
    "snippet",
    [
        'import { legacy } from "../../../clients/gemma-holon/quantum/server";\n',
        'const legacy = require("../../../clients/gemma-holon/quantum/server");\n',
        'const legacy = await import("../../../clients/gemma-holon/quantum/server");\n',
        'from clients.gemma_holon import quantum\n',
        'import clients.gemma_holon.quantum\n',
    ],
)
def test_sovereign_runtime_imports_from_legacy_holon_are_rejected(
    tmp_path: Path, snippet: str
) -> None:
    lint = _load_lint_module()
    _seed_quarantine(tmp_path)
    suffix = ".py" if "clients.gemma_holon" in snippet else ".ts"
    _write(tmp_path, f"sovereign-omega-v2/src/probe{suffix}", snippet)

    violations = lint.collect_violations(tmp_path)
    assert any(v.code == "FORBIDDEN_LEGACY_IMPORT" for v in violations)


def test_reference_outside_sovereign_src_is_not_blocked(tmp_path: Path) -> None:
    lint = _load_lint_module()
    _seed_quarantine(tmp_path)
    _write(
        tmp_path,
        "sovereign-omega-v2/scripts/mythos-pipeline.ts",
        "const state = 'clients/gemma-holon/state.json';\n",
    )

    assert lint.collect_violations(tmp_path) == []


def test_cli_fails_closed_on_violation(tmp_path: Path) -> None:
    lint = _load_lint_module()
    _seed_quarantine(tmp_path)
    _write(
        tmp_path,
        "sovereign-omega-v2/src/probe.ts",
        'const legacy = require("../../clients/gemma-holon/quantum/server");\n',
    )

    assert lint.main(["--repo-root", str(tmp_path)]) == 1
