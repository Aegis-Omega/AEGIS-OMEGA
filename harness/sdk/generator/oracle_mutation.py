"""AEGIS evaluator-of-evaluator: adversarial mutation campaign for generated systems.

The nine mutants are FIXED, repo-reviewed transformations of a sealed template;
never run model-supplied arbitrary source in this Docker-only functional runner.

A successful candidate test is insufficient if its oracle cannot detect basic
violations. This campaign quantifies whether contract violations are rejected.
It does not establish microVM sandboxing, supply-chain signatures or admission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Mapping

from harness.sdk.generator.system_foundry import build_readonly_json_api

_KIND = "AEGIS_FOUNDRY_ORACLE_MUTATION_AUDIT_V1"
_MUTATIONS: tuple[tuple[str, str, str], ...] = (
    ("WRONG_ROUTE_BODY", 'status, payload = "200 OK", ROUTES[path]', 'status, payload = "200 OK", {"fake": True}'),
    ("ALLOW_UNSAFE_METHOD", 'if method != "GET":', 'if method == "__not_an_http_method__":'),
    ("UNKNOWN_ROUTE_FALSE_200", '"404 Not Found"', '"200 OK"'),
    ("REJECTED_METHOD_FALSE_200", '"405 Method Not Allowed"', '"200 OK"'),
    ("WRONG_MEDIA_TYPE", '"application/json; charset=utf-8"', '"text/html; charset=utf-8"'),
    ("WRONG_CONTENT_LENGTH", 'str(len(body))', 'str(len(body) + 7)'),
    ("CACHE_DATA_PUBLICLY", '("Cache-Control", "no-store")', '("Cache-Control", "public")'),
    ("DISABLE_NOSNIFF", '("X-Content-Type-Options", "nosniff")', '("X-Content-Type-Options", "off")'),
    ("WRONG_ALLOWED_METHOD", '("Allow", "GET")', '("Allow", "POST")'),
)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), allow_nan=False).encode()


def _run_oracle(source: str, blueprint: Mapping[str, Any], timeout: int) -> dict:
    oracle = Path(__file__).resolve().with_name("independent_oracle.py")
    with tempfile.TemporaryDirectory(prefix="aegis-oracle-falsify-") as tmp:
        root = Path(tmp)
        (root / "service.py").write_text(source, encoding="utf-8")
        (root / "blueprint.json").write_bytes(_canonical(blueprint))
        try:
            run = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(oracle),
                 str(root / "blueprint.json"), str(root / "service.py")],
                cwd=root,
                env={"PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"},
                capture_output=True,
                text=True, encoding="utf-8", errors="replace",
                timeout=timeout, check=False,
            )
        except subprocess.TimeoutExpired:
            return {"outcome": "ORACLE_EXECUTION_TIMEOUT", "exit_code": None}
    try:
        payload = json.loads(run.stdout)
    except ValueError:
        payload = {"outcome": "ORACLE_OUTPUT_INVALID"}
    return {"outcome": payload.get("outcome"), "exit_code": run.returncode,
            "passed": payload.get("passed", 0), "total": payload.get("total", 0)}


def run_mutation_campaign(blueprint: Mapping[str, Any], *, timeout: int = 10) -> dict:
    if not isinstance(timeout, int) or isinstance(timeout, bool) or not 1 <= timeout <= 30:
        raise ValueError("TIMEOUT_INVALID")
    # The compiler, not an agent-supplied arbitrary code path, owns all source.
    candidate = build_readonly_json_api(blueprint)
    source = next(a.content for a in candidate if a.path == "service.py")
    baseline = _run_oracle(source, blueprint, timeout)
    if baseline.get("outcome") != "ORACLE_PASS" or baseline.get("exit_code") != 0:
        raise ValueError("BASELINE_ORACLE_DID_NOT_PASS")

    cases = []
    for mutant_id, needle, replacement in _MUTATIONS:
        if source.count(needle) != 1 or needle == replacement:
            raise ValueError("MUTATION_ANCHOR_INVALID:" + mutant_id)
        modified = source.replace(needle, replacement, 1)
        report = _run_oracle(modified, blueprint, timeout)
        killed = report.get("outcome") == "ORACLE_FAIL" and report.get("exit_code") != 0
        cases.append({
            "mutation": mutant_id,
            "mutant_sha256": hashlib.sha256(modified.encode()).hexdigest(),
            "killed_by_oracle": bool(killed),
            "oracle_outcome": report.get("outcome"),
            "oracle_passed": report.get("passed"),
            "oracle_total": report.get("total"),
        })
    killed = sum(c["killed_by_oracle"] for c in cases)
    body = {
        "schema_version": "1.0.0",
        "kind": _KIND,
        "original_blueprint_sha256": hashlib.sha256(_canonical(blueprint)).hexdigest(),
        "original_source_sha256": hashlib.sha256(source.encode()).hexdigest(),
        "baseline": baseline,
        "mutations": cases,
        "mutant_count": len(cases),
        "mutants_killed": killed,
        "outcome": "ORACLE_SENSITIVITY_PASS" if killed == len(_MUTATIONS) else "ORACLE_SENSITIVITY_FAIL",
        "admission": "NOT_ADMITTED",
        "authority_granted": False,
    }
    body["audit_sha256"] = hashlib.sha256(_canonical({"domain": _KIND, "body": body})).hexdigest()
    return body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blueprint", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        bp = json.loads(Path(args.blueprint).read_text(encoding="utf-8"))
        result = run_mutation_campaign(bp)
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            target = Path(args.output)
            if target.exists() or target.is_symlink():
                raise ValueError("OUTPUT_MUST_NOT_EXIST")
            target.write_text(rendered, encoding="utf-8")
        else:
            print(rendered)
        return 0 if result["outcome"] == "ORACLE_SENSITIVITY_PASS" else 1
    except (OSError, ValueError, TypeError) as exc:
        print("MUTATION_AUDIT_DENIED:" + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
