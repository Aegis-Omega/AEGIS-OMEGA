"""First concrete System Foundry compiler: bounded, dependency-free read-only JSON APIs.

This compiles an explicit typed blueprint into runnable source and tests.
It does NOT execute arbitrary generated code, deploy, imply security approval,
or grant operational authority. Separate CI execution/admission is required.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping

from harness.sdk.generator import CodeArtifact

_ID = re.compile(r"^[a-z][a-z0-9-]{2,31}$")
_ROUTE = re.compile(r"^/(?:[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*)?$")
_MAX_BYTES = 65536
_MAX_ROUTES = 16

# No arbitrary source snippets are interpolated; only JSON-as-a-Python-string.
_SOURCE = '''"""Generated read-only WSGI JSON API. Stdlib-only; no authentication."""
import json
import os
from wsgiref.simple_server import make_server

ROUTES = json.loads(__ROUTES__)

def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "")
    path = environ.get("PATH_INFO", "")
    if method != "GET":
        status, payload = "405 Method Not Allowed", {"error": "method_not_allowed"}
    elif path not in ROUTES:
        status, payload = "404 Not Found", {"error": "not_found"}
    else:
        status, payload = "200 OK", ROUTES[path]
    body = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    start_response(status, [
        ("Content-Type", "application/json; charset=utf-8"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
        ("X-Content-Type-Options", "nosniff"),
        ("Allow", "GET"),
    ])
    return [body]

if __name__ == "__main__":
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8080"))
    with make_server(host, port, application) as server:
        server.serve_forever()
'''

_TEST = '''"""Generated smoke tests: independent CI must execute them to establish results."""
import json
import unittest
from service import application, ROUTES

class ServiceContractTests(unittest.TestCase):
    def call(self, path, method="GET"):
        observed = []
        chunks = application({"PATH_INFO": path, "REQUEST_METHOD": method},
                             lambda status, headers: observed.append((status, dict(headers))))
        return observed[0], json.loads(b"".join(chunks))

    def test_all_declared_routes(self):
        for path, expected in ROUTES.items():
            with self.subTest(path=path):
                (status, headers), payload = self.call(path)
                self.assertEqual(status, "200 OK")
                self.assertEqual(payload, expected)
                self.assertEqual(headers["X-Content-Type-Options"], "nosniff")

    def test_unknown_route_is_404(self):
        (status, _), payload = self.call("/__aegis_nonexistent__")
        self.assertEqual(status, "404 Not Found")
        self.assertEqual(payload["error"], "not_found")

    def test_write_methods_are_rejected(self):
        (status, _), payload = self.call("/", "POST")
        self.assertEqual(status, "405 Method Not Allowed")
        self.assertEqual(payload["error"], "method_not_allowed")

if __name__ == "__main__":
    unittest.main()
'''


class SystemBlueprintError(ValueError):
    pass


def build_readonly_json_api(blueprint: Mapping[str, Any]) -> list[CodeArtifact]:
    """Build a runnable candidate system from a constrained blueprint.

    Supported shape:
      {"system_id":"sample-api", "kind":"readonly-json-api",
       "routes":{"/health":{"status":"ok"}}}
    Acceptance is not inferred from artifact existence.
    """
    if not isinstance(blueprint, Mapping) or set(blueprint) != {"system_id", "kind", "routes"}:
        raise SystemBlueprintError("BLUEPRINT_FIELDS_INVALID")
    if blueprint["kind"] != "readonly-json-api":
        raise SystemBlueprintError("BLUEPRINT_KIND_UNSUPPORTED")
    system_id = blueprint["system_id"]
    if not isinstance(system_id, str) or not _ID.fullmatch(system_id):
        raise SystemBlueprintError("SYSTEM_ID_INVALID")
    routes = blueprint["routes"]
    if not isinstance(routes, dict) or not routes or len(routes) > _MAX_ROUTES:
        raise SystemBlueprintError("ROUTE_COUNT_INVALID")
    for path, response in routes.items():
        if not isinstance(path, str) or not _ROUTE.fullmatch(path):
            raise SystemBlueprintError("ROUTE_PATH_INVALID")
        if not isinstance(response, dict):
            raise SystemBlueprintError("ROUTE_RESPONSE_MUST_BE_OBJECT")
    try:
        encoded = json.dumps(routes, ensure_ascii=True, sort_keys=True, allow_nan=False,
                             separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise SystemBlueprintError("ROUTE_RESPONSE_NOT_JSON") from exc
    if len(encoded.encode("utf-8")) > _MAX_BYTES:
        raise SystemBlueprintError("ROUTE_PAYLOAD_TOO_LARGE")

    source = _SOURCE.replace("__ROUTES__", repr(encoded))
    guide = (
        f"# {system_id}\\n\\n"
        "Generated read-only JSON API candidate. No authentication, data writes, "
        "persistence, or external side effects. Not deployment-approved.\\n\\n"
        "Run: `python service.py`. Tests: `python -m unittest -v test_service.py`.\\n"
    )
    files = [
        ("service.py", source, "python"),
        ("test_service.py", _TEST, "python"),
        ("README.md", guide, "markdown"),
    ]
    return [
        CodeArtifact(
            path=path,
            content=content,
            language=language,
            hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            metadata={"system_id": system_id, "kind": "readonly-json-api",
                      "claim": "CANDIDATE_NOT_TESTED"},
        )
        for path, content, language in files
    ]
