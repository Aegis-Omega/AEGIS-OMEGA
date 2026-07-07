"""
AEGIS-Ω Universal Platform Helpers — EPISTEMIC TIER: T0/T3 BOUNDARY
DETERMINISM CLASS: strict user-space execution

Provides cross-platform routing abstractions, environment sanitization,
and secure ingress/egress mapping across Cloudflare Access Zero Trust Edge 
down to your local CoreMatrix telemetry/execution loop.

Adheres directly to Root Law: AdaptivePower(T) <= ReplayVerifiability(T).
"""

from __future__ import annotations

import os
import sys
import json
import http.client
from urllib.parse import urlparse
from typing import Dict, Any, Optional

# Integrate directly with the repository's native Anthropic client factory
try:
    import anth_client
    _HAS_ANTH_CLIENT = True
except ImportError:
    _HAS_ANTH_CLIENT = False


class UniversalPlatformHelper:
    """
    Orchestrates platform-agnostic environment bindings, securely injecting
    Cloudflare Access Service Tokens into upstream/downstream JSON payloads
    without leaking session entropy or altering execution determinism.
    """
    def __init__(self, target_url: Optional[str] = None):
        # Resolve target endpoint from environment or fall back to native Sovereign Bridge Port
        fallback_port = os.environ.get('SOVEREIGN_BRIDGE_PORT', '7890')
        self.target_url = target_url or os.getenv(
            "AEGIS_GATEWAY_URL", 
            f"http://127.0.0.1:{fallback_port}/gate_signal"
        )
        
        # Pull strict Cloudflare Zero Trust edge headers from host context
        self._cf_client_id = os.getenv("CF_ACCESS_CLIENT_ID", "")
        self._cf_client_secret = os.getenv("CF_ACCESS_CLIENT_SECRET", "")

    def verify_environment(self) -> bool:
        """
        Validates structural token availability before opening network sockets.
        Returns False to prevent silent, unauthenticated bypass failures at the edge.
        """
        if not self._cf_client_id or not self._cf_client_secret:
            sys.stderr.write(
                "[ERROR] T0 Boundary Violation: Cloudflare Access Service Tokens "
                "are completely missing from the current environment variables.\n"
            )
            return False
        return True

    def format_secure_headers(self, base_headers: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        """
        Injects the required Cloudflare Access validation criteria into outbound packets,
        matching your mobile Zero Trust gateway configuration layout.
        """
        headers = base_headers.copy() if base_headers else {}
        headers.update({
            "Content-Type": "application/json",
            "CF-Access-Client-Id": self._cf_client_id,
            "CF-Access-Client-Secret": self._cf_client_secret
        })
        return headers

    def route_signal_to_bridge(self, payload_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dispatches structured telemetry parameters or gate signals down the 
        active cloudflared daemon tunnel directly to the local HTTP server loop.
        """
        if not self.verify_environment():
            return {"status_code": 401, "error": "Missing Zero Trust authentication mapping."}

        parsed_url = urlparse(self.target_url)
        host = parsed_url.netloc
        path = parsed_url.path if parsed_url.path else "/"
        
        # Serialize payload cleanly; maintaining replay-verifiable string properties
        serialized_payload = json.dumps(payload_dict)
        headers = self.format_secure_headers()

        try:
            # Select underlying transport layer based on edge URI scheme
            if parsed_url.scheme == "https":
                conn = http.client.HTTPSConnection(host, timeout=10.0)
            else:
                conn = http.client.HTTPConnection(host, timeout=10.0)
                
            conn.request("POST", path, body=serialized_payload, headers=headers)
            response = conn.getresponse()
            response_data = response.read().decode("utf-8")
            conn.close()

            # Attempt to return clean JSON payload if endpoint replies successfully
            if response.status == 200:
                return {
                    "status_code": response.status,
                    "payload": json.loads(response_data)
                }
            return {
                "status_code": response.status,
                "error_response": response_data
            }

        except Exception as e:
            return {
                "status_code": 500, 
                "error": f"Failed to traverse Zero Trust Edge Architecture: {str(e)}"
            }


# --- SELF-TEST AND EXPORT VALIDATION HOOK ---
if __name__ == "__main__":
    print("[-] Initializing AEGIS-Ω Platform Helper Structural Audits...")
    helper = UniversalPlatformHelper()
    
    # Run sanity checks against runtime environment mappings
    env_ok = helper.verify_environment()
    
    if env_ok:
        print("[+] Environment verified. Compiling validation mock telemetry...")
        # Mirroring a classic gate_signal sequence block to test routing mechanics
        mock_signal = {
            "sequence": 0,
            "epoch": 0,
            "event_type": "TELEMETRY_SAMPLE",
            "meta": {"source": "mobile_edge_gemma", "instruction": "Verify pipeline stability"}
        }
        
        print(f"[-] Dispatching mock payload to target URL: {helper.target_url}")
        result = helper.route_signal_to_bridge(mock_signal)
        print(f"[+] Output telemetry state summary: Status Code -> {result['status_code']}")
    else:
        print("[!] Validation script halted: Export variables before running system binaries.")