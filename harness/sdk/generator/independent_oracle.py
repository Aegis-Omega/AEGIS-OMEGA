"""AEGIS System Foundry: external-to-candidate acceptance oracle.

The oracle is source-controlled separately from the generated system and its
self-tests. It reads the typed original blueprint and checks the actual WSGI
callable, without trusting the generated test suite or self-reported success.

This is a functional oracle, NOT a security sandbox for arbitrary untrusted
Python. Always execute candidate code in a dedicated microVM before enabling
user-authored generators. No operational authority is granted here.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
        ensure_ascii=True,
    ).encode("utf-8")


def _check_one(application, path: str, method: str, expected_status: str,
               expected_response: dict) -> list[str]:
    failures = []
    observations = []

    def start_response(status, headers, exc_info=None):
        observations.append((status, dict(headers)))

    try:
        body = application(
            {"PATH_INFO": path, "REQUEST_METHOD": method,
             "SERVER_NAME": "localhost", "SERVER_PORT": "80",
             "wsgi.url_scheme": "http", "wsgi.version": (1, 0),
             "wsgi.input": None, "wsgi.errors": sys.stderr,
             "wsgi.multithread": False, "wsgi.multiprocess": False,
             "wsgi.run_once": False},
            start_response,
        )
        response = b"".join(body)
        if len(observations) != 1:
            return ["START_RESPONSE_INVOCATIONS_INVALID"]
        status, headers = observations[0]
        if status != expected_status:
            failures.append("STATUS_MISMATCH")
        if headers.get("Content-Type") != "application/json; charset=utf-8":
            failures.append("CONTENT_TYPE_INVALID")
        if headers.get("Cache-Control") != "no-store":
            failures.append("CACHE_CONTROL_INVALID")
        if headers.get("X-Content-Type-Options") != "nosniff":
            failures.append("NOSNIFF_MISSING")
        if headers.get("Allow") != "GET":
            failures.append("ALLOW_HEADER_INVALID")
        if headers.get("Content-Length") != str(len(response)):
            failures.append("CONTENT_LENGTH_MISMATCH")
        if len(response) > 131072:
            failures.append("RESPONSE_TOO_LARGE")
        try:
            actual = json.loads(response)
            if actual != expected_response:
                failures.append("BODY_MISMATCH")
        except (ValueError, UnicodeError):
            failures.append("BODY_NOT_JSON")
    except Exception as exc:
        failures.append("APPLICATION_EXCEPTION:" + type(exc).__name__)
    return sorted(set(failures))


def run_oracle(blueprint: dict, service_path: Path) -> dict:
    from importlib.machinery import SourceFileLoader

    # The blueprint is not executable source. Validation is mandatory at the
    # caller boundary; also restrict basic input shapes here.
    if not isinstance(blueprint, dict) or not isinstance(blueprint.get("routes"), dict):
        raise ValueError("BLUEPRINT_INVALID")
    routes = blueprint["routes"]
    if not routes or len(routes) > 16:
        raise ValueError("ROUTES_INVALID")
    if not service_path.is_file() or service_path.is_symlink():
        raise ValueError("CANDIDATE_SOURCE_INVALID")

    spec = importlib.util.spec_from_file_location("_aegis_candidate_under_test", service_path)
    if spec is None or spec.loader is None:
        raise ValueError("CANDIDATE_IMPORT_SPEC_INVALID")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    application = getattr(module, "application", None)
    if not callable(application):
        raise ValueError("WSGI_APPLICATION_MISSING")

    cases = [
        (path, "GET", "200 OK", response)
        for path, response in sorted(routes.items())
    ]
    unknown_path = "/__aegis_oracle_no_route__"
    while unknown_path in routes:
        unknown_path += "_"
    cases.append((unknown_path, "GET", "404 Not Found", {"error": "not_found"}))
    for method in ("POST", "PUT", "PATCH", "DELETE", "OPTIONS"):
        cases.append((sorted(routes)[0], method, "405 Method Not Allowed",
                      {"error": "method_not_allowed"}))
    results = []
    for path, method, status, body in cases:
        failures = _check_one(application, path, method, status, body)
        results.append({
            "case": hashlib.sha256(_canonical({"path": path, "method": method})).hexdigest(),
            "ok": not failures,
            "failures": failures,
        })
    success = all(item["ok"] for item in results)
    return {
        "schema_version": "1.0.0",
        "kind": "AEGIS_FOUNDRY_INDEPENDENT_ACCEPTANCE_ORACLE_V1",
        "blueprint_sha256": hashlib.sha256(_canonical(blueprint)).hexdigest(),
        "service_sha256": hashlib.sha256(service_path.read_bytes()).hexdigest(),
        "total": len(results),
        "passed": sum(item["ok"] for item in results),
        "outcome": "ORACLE_PASS" if success else "ORACLE_FAIL",
        "results": results,
        "admission": "NOT_ADMITTED",
        "authority_granted": False,
    }


def main() -> int:
    if len(sys.argv) != 3:
        print('{"error":"USAGE_INVALID"}')
        return 2
    try:
        blueprint = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        result = run_oracle(blueprint, Path(sys.argv[2]))
    except (OSError, ValueError, TypeError, ImportError) as exc:
        print(json.dumps({"outcome": "ORACLE_FAIL", "error": type(exc).__name__,
                          "admission": "NOT_ADMITTED", "authority_granted": False},
                         sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["outcome"] == "ORACLE_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
