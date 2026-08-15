"""AEGIS Omega production bridge entrypoint with governed OpenAI runtime v1."""
from __future__ import annotations

import json
import os

import bridge as _bridge
from openai_runtime.bridge_endpoint import handle_omega_run
from openai_runtime.types import RuntimeErrorCode


class OmegaBridgeHandler(_bridge.BridgeHandler):
    """Add /v1/omega/run without changing legacy BridgeHandler routes."""

    def do_POST(self):
        if self.path != "/v1/omega/run":
            return super().do_POST()

        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length)) if length else {}
        except (TypeError, ValueError, json.JSONDecodeError):
            self._platform_respond(400, {
                "status": "FAILED",
                "error_code": RuntimeErrorCode.INVALID_REQUEST.value,
                "is_replay_reconstructable": True,
            })
            return

        status, body = handle_omega_run(
            data=data,
            api_key=self.headers.get("x-api-key", ""),
            verify_api_key=_bridge._platform_verify_api_key,
            env=os.environ,
        )
        self._platform_respond(status, body)


def run_bridge(port=None):
    # bridge.run_bridge resolves BridgeHandler at runtime; replace only the handler
    # class while preserving all matrix/router/checkpoint startup semantics.
    _bridge.BridgeHandler = OmegaBridgeHandler
    return _bridge.run_bridge(port=port)


if __name__ == "__main__":
    run_bridge()
