"""AEGIS counterexample memory: discover, shrink, carry and replay failures.

A property probe uses independent source-controlled request expectations rather
than generated self-tests. One subprocess imports compiler-owned Python source;
arbitrary model-supplied code is OUT OF SCOPE without a microVM sandbox.

The portable witness is integrity-addressed but NOT signed, authenticated,
authority-granting, or sufficient to certify a complete program.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import random
import re
import subprocess
import sys
import tempfile
from typing import Any, Mapping

from harness.sdk.generator.system_foundry import build_readonly_json_api

KIND = "AEGIS_REPLAYABLE_COUNTEREXAMPLE_V1"
ALPHABET = "abcdefghjkmnpqrstuvwxyz"
MAX_CASES = 512
MAX_PATH = 96


def canonical(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def digest(obj: Any) -> str:
    return hashlib.sha256(canonical(obj)).hexdigest()


def _validate_blueprint(blueprint: Mapping[str, Any]) -> None:
    build_readonly_json_api(blueprint)


def candidate_paths(blueprint: Mapping[str, Any], *, seed: int, budget: int) -> list[str]:
    """Generate a bounded, deterministic mix of fresh and boundary requests."""
    _validate_blueprint(blueprint)
    if type(seed) is not int or not 0 <= seed <= 2**32 - 1:
        raise ValueError("SEED_INVALID")
    if type(budget) is not int or not 1 <= budget <= MAX_CASES:
        raise ValueError("BUDGET_INVALID")
    routes = set(blueprint["routes"])
    rng = random.Random(seed)
    items: list[str] = []
    for route in sorted(routes):
        items.extend([route, route + "/more", route + "//", route + "-missing"])
    items += ["/", "/favicon.ico", "/__aegis_oracle_no_route__", "/fuzz/zz"]
    # Property space is unbounded; this is a *bounded search*, not complete proof.
    while len(items) < budget * 2:
        middle = "".join(rng.choice(ALPHABET) for _ in range(rng.randrange(1, 17)))
        items += ["/fuzz/" + middle + "zz",
                  "/v1/" + middle, "/" + middle + "/more"]
    result = []
    seen = set()
    for item in items:
        if item not in seen and len(item) <= MAX_PATH:
            seen.add(item)
            result.append(item)
        if len(result) == budget:
            return result
    return result


def _valid_cases(cases: Any) -> list[dict[str, str]]:
    if not isinstance(cases, list) or not 1 <= len(cases) <= MAX_CASES:
        raise ValueError("CASES_INVALID")
    for case in cases:
        if (not isinstance(case, dict)
            or set(case) != {"path", "method"}
            or not isinstance(case["path"], str)
            or len(case["path"]) > MAX_PATH
            or not case["path"].startswith("/")
            or not re.fullmatch(r"[A-Z]{3,8}", case["method"])):
            raise ValueError("CASE_INVALID")
    return cases


def probe_in_subprocess(
    blueprint: Mapping[str, Any],
    service_source: str,
    cases: list[dict[str, str]],
    *, timeout_seconds: int = 12,
) -> dict[str, Any]:
    """Invoke the non-generated oracle logic through a fresh child process."""
    _validate_blueprint(blueprint)
    _valid_cases(cases)
    if type(timeout_seconds) is not int or not 1 <= timeout_seconds <= 30:
        raise ValueError("TIMEOUT_INVALID")
    if not isinstance(service_source, str) or len(service_source) > 100_000:
        raise ValueError("SERVICE_SOURCE_INVALID")
    with tempfile.TemporaryDirectory(prefix="aegis-counterexample-") as tmp:
        root = Path(tmp)
        (root / "blueprint.json").write_bytes(canonical(blueprint))
        (root / "service.py").write_text(service_source, encoding="utf-8")
        (root / "cases.json").write_bytes(canonical(cases))
        try:
            p = subprocess.run(
                [sys.executable, "-I", "-S", "-B", str(Path(__file__).resolve()),
                 "probe", "--blueprint", str(root / "blueprint.json"),
                 "--service", str(root / "service.py"),
                 "--cases", str(root / "cases.json")],
                cwd=root, env={"PYTHONNOUSERSITE": "1", "PYTHONDONTWRITEBYTECODE": "1"},
                text=True, capture_output=True, check=False,
                encoding="utf-8", errors="replace", timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise ValueError("PROBE_TIMEOUT") from exc
    if p.returncode:
        raise ValueError("PROBE_EXECUTION_FAILED")
    try:
        result = json.loads(p.stdout)
    except ValueError as exc:
        raise ValueError("PROBE_REPORT_INVALID") from exc
    if result.get("kind") != "AEGIS_PROPERTY_PROBE_V1" or len(result.get("observations", [])) != len(cases):
        raise ValueError("PROBE_REPORT_INVALID")
    return result


def _probe_mode(blueprint: dict, source: Path, cases: list[dict[str, str]]) -> dict[str, Any]:
    from harness.sdk.generator.independent_oracle import _check_one
    spec = importlib.util.spec_from_file_location("_aegis_probe_candidate", source)
    if spec is None or spec.loader is None:
        raise ValueError("CANDIDATE_IMPORT_DENIED")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = getattr(module, "application", None)
    if not callable(app):
        raise ValueError("APPLICATION_MISSING")
    observations = []
    for case in cases:
        path, method = case["path"], case["method"]
        if method != "GET":
            status, payload = "405 Method Not Allowed", {"error": "method_not_allowed"}
        elif path in blueprint["routes"]:
            status, payload = "200 OK", blueprint["routes"][path]
        else:
            status, payload = "404 Not Found", {"error": "not_found"}
        failures = _check_one(app, path, method, status, payload)
        observations.append({"path": path, "method": method,
                             "failures": failures})
    return {"kind": "AEGIS_PROPERTY_PROBE_V1",
            "service_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "observations": observations,
            "authority_granted": False}


def _source_for_blueprint(blueprint: Mapping[str, Any]) -> str:
    return next(a.content for a in build_readonly_json_api(blueprint)
                if a.path == "service.py")


def discover(
    blueprint: Mapping[str, Any], service_source: str, *,
    seed: int = 20261010, budget: int = 128,
) -> dict[str, Any]:
    """Find and minimize one behavioral violation without approving the program."""
    paths = candidate_paths(blueprint, seed=seed, budget=budget)
    # Methods vary across the same generated paths to reveal asymmetric behavior.
    cases = [{"path": path, "method": ("POST" if i % 7 == 6 else "GET")}
             for i, path in enumerate(paths)]
    report = probe_in_subprocess(blueprint, service_source, cases)
    bad = [entry for entry in report["observations"] if entry["failures"]]
    base = {
        "seed": seed, "probe_budget": len(cases),
        "blueprint_sha256": digest(blueprint),
        "candidate_source_sha256": hashlib.sha256(service_source.encode()).hexdigest(),
        "candidate_report_sha256": digest(report),
        "admission": "NOT_ADMITTED",
        "authority_granted": False,
    }
    if not bad:
        return {**base, "outcome": "NO_COUNTEREXAMPLE_FOUND",
                "coverage_claim": "BOUNDED_PROBE_ONLY"}
    chosen = bad[0]
    path, method = chosen["path"], chosen["method"]
    # One-character deletion reduction, checked against the actual faulty
    # candidate each time. The witness is minimized by tested behavior.
    for _ in range(MAX_PATH):
        edits = []
        for i in range(len(path)):
            reduced = path[:i] + path[i+1:]
            if (reduced and reduced.startswith("/")
                and len(reduced) < len(path)):
                edits.append({"path": reduced, "method": method})
        if not edits:
            break
        reduced_report = probe_in_subprocess(blueprint, service_source, edits)
        candidate = next(
            (x for x in reduced_report["observations"] if x["failures"]), None
        )
        if candidate is None:
            break
        path = candidate["path"]
    verified = probe_in_subprocess(
        blueprint, service_source, [{"path": path, "method": method}]
    )["observations"][0]
    if not verified["failures"]:
        raise ValueError("COUNTEREXAMPLE_NOT_REPRODUCIBLE")
    body = {
        "schema_version": "1.0.0",
        "kind": KIND,
        **base,
        "outcome": "COUNTEREXAMPLE_DISCOVERED",
        "witness": {"path": path, "method": method,
                    "failure_codes": verified["failures"]},
    }
    return {**body, "memory_sha256": digest({"domain": KIND, "body": body})}


def replay(blueprint: Mapping[str, Any], service_source: str,
           memory: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed if recorded counterexample still reproduces on a new build."""
    _validate_blueprint(blueprint)
    if not isinstance(memory, Mapping):
        raise ValueError("MEMORY_INVALID")
    body = {k: v for k, v in memory.items() if k != "memory_sha256"}
    if (body.get("kind") != KIND
        or body.get("outcome") != "COUNTEREXAMPLE_DISCOVERED"
        or body.get("blueprint_sha256") != digest(blueprint)
        or memory.get("memory_sha256") != digest({"domain": KIND, "body": body})):
        raise ValueError("MEMORY_INTEGRITY_OR_SPEC_MISMATCH")
    witness = body.get("witness")
    if not isinstance(witness, Mapping) or set(witness) != {"path", "method", "failure_codes"}:
        raise ValueError("WITNESS_INVALID")
    request = {"path": witness["path"], "method": witness["method"]}
    _valid_cases([request])
    if (not isinstance(witness["failure_codes"], list)
        or not witness["failure_codes"]
        or not all(isinstance(x, str) for x in witness["failure_codes"])):
        raise ValueError("WITNESS_FAILURES_INVALID")
    observed = probe_in_subprocess(blueprint, service_source, [request])["observations"][0]
    if observed["failures"]:
        outcome = "REGRESSION_PRESENT"
    else:
        outcome = "WITNESS_NOW_PASSES"
    return {
        "kind": "AEGIS_COUNTEREXAMPLE_REPLAY_V1",
        "memory_sha256": memory["memory_sha256"],
        "candidate_source_sha256": hashlib.sha256(service_source.encode()).hexdigest(),
        "outcome": outcome,
        "observed_failures": observed["failures"],
        "original_failures": witness["failure_codes"],
        "admission": "NOT_ADMITTED",
        "authority_granted": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["probe", "discover", "replay"])
    parser.add_argument("--blueprint", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--cases")
    parser.add_argument("--memory")
    parser.add_argument("--output")
    parser.add_argument("--seed", type=int, default=20261010)
    parser.add_argument("--budget", type=int, default=128)
    args = parser.parse_args()
    try:
        blueprint = json.loads(Path(args.blueprint).read_text(encoding="utf-8"))
        source_path = Path(args.service)
        if not source_path.is_file() or source_path.is_symlink():
            raise ValueError("SERVICE_FILE_INVALID")
        if args.mode == "probe":
            cases = json.loads(Path(args.cases).read_text(encoding="utf-8"))
            outcome = _probe_mode(blueprint, source_path, _valid_cases(cases))
        elif args.mode == "discover":
            outcome = discover(blueprint, source_path.read_text(encoding="utf-8"),
                               seed=args.seed, budget=args.budget)
        else:
            memory = json.loads(Path(args.memory).read_text(encoding="utf-8"))
            outcome = replay(blueprint, source_path.read_text(encoding="utf-8"), memory)
        result = json.dumps(outcome, sort_keys=True, indent=2) + "\n"
        if args.output:
            target = Path(args.output)
            if target.exists() or target.is_symlink():
                raise ValueError("OUTPUT_ALREADY_EXISTS")
            target.write_text(result, encoding="utf-8")
        else:
            print(result)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print("COUNTEREXAMPLE_DENIED:" + type(exc).__name__, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
