import importlib.util
import io
import json
import sys
import types
from pathlib import Path

PYTHON_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = PYTHON_ROOT / "omega_bridge.py"
sys.path.insert(0, str(PYTHON_ROOT))


class FakeBaseHandler:
    parent_calls = 0

    def do_POST(self):
        type(self).parent_calls += 1

    def _platform_respond(self, status, body):
        self.response = (status, body)


def _load_entrypoint(monkeypatch, verify_api_key):
    fake_bridge = types.ModuleType("bridge")
    fake_bridge.BridgeHandler = FakeBaseHandler
    fake_bridge._platform_verify_api_key = verify_api_key
    fake_bridge.run_bridge = lambda: None
    monkeypatch.setitem(sys.modules, "bridge", fake_bridge)

    spec = importlib.util.spec_from_file_location("omega_bridge_tested", ENTRYPOINT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module, fake_bridge


def _handler(cls, path, payload):
    body = json.dumps(payload).encode()
    h = cls.__new__(cls)
    h.path = path
    h.headers = {"Content-Length": str(len(body)), "x-api-key": "aegis_test"}
    h.rfile = io.BytesIO(body)
    return h


def test_entrypoint_intercepts_omega_route_and_returns_fail_closed_config(monkeypatch):
    module, _ = _load_entrypoint(monkeypatch, lambda _key: ("operator@example.invalid", "operator"))
    monkeypatch.delenv("AEGIS_OPENAI_RUNTIME_ENABLED", raising=False)
    h = _handler(
        module.OmegaBridgeHandler,
        "/v1/omega/run",
        {"input": "x", "allowed_capabilities": ["research-synthesis"]},
    )
    h.do_POST()
    status, response = h.response
    assert status == 503
    assert response["error_code"] == "RUNTIME_DISABLED"


def test_entrypoint_rejects_malformed_json_without_delegating(monkeypatch):
    module, _ = _load_entrypoint(monkeypatch, lambda _key: ("operator@example.invalid", "operator"))
    h = module.OmegaBridgeHandler.__new__(module.OmegaBridgeHandler)
    h.path = "/v1/omega/run"
    h.headers = {"Content-Length": "1", "x-api-key": "aegis_test"}
    h.rfile = io.BytesIO(b"{")
    h.do_POST()
    status, response = h.response
    assert status == 400
    assert response["error_code"] == "INVALID_REQUEST"


def test_entrypoint_delegates_all_existing_routes_unchanged(monkeypatch):
    module, _ = _load_entrypoint(monkeypatch, lambda _key: ("operator@example.invalid", "operator"))
    module.OmegaBridgeHandler.parent_calls = 0
    h = _handler(module.OmegaBridgeHandler, "/platform/collaborate", {"objective": "x"})
    h.do_POST()
    assert module.OmegaBridgeHandler.parent_calls == 1
