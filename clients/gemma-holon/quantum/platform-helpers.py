"""
AEGIS Gemma Holon — Cloudflare Zero Trust routing helper.
Routes authenticated mobile client hooks to local quantum execution loop.

Requires env vars:
  CF_ACCESS_CLIENT_ID      — Cloudflare Access service token ID
  CF_ACCESS_CLIENT_SECRET  — Cloudflare Access service token secret
  AEGIS_GATEWAY_URL        — Target URL (default: http://127.0.0.1:5000/trigger-quantum)
  AEGIS_GATEWAY_ALLOWED_HOST — Exact approved hostname for HTTPS Access requests

Epistemic tier: T2
"""
import os
import sys
import json
import http.client
from urllib.parse import urlsplit


class UniversalPlatformHelper:
    def __init__(self):
        self.target_url = os.getenv("AEGIS_GATEWAY_URL", "http://127.0.0.1:5000/trigger-quantum")
        self.cf_client_id = os.getenv("CF_ACCESS_CLIENT_ID", "")
        self.cf_client_secret = os.getenv("CF_ACCESS_CLIENT_SECRET", "")

    def _validated_gateway(self):
        """Share the same transport admission decision with readiness and execution."""
        # urlsplit strips CR/LF/TAB. Check the original string first.
        if any(ord(c) < 32 or ord(c) == 127 for c in self.target_url):
            return None, None, {"status_code": 400, "error": "Invalid gateway URL"}
        try:
            parsed = urlsplit(self.target_url)
            host = parsed.hostname
            port = parsed.port  # Fail closed on invalid or out-of-range ports.
        except ValueError:
            return None, None, {"status_code": 400, "error": "Invalid gateway URL"}
        if not host or parsed.username is not None or parsed.password is not None or parsed.fragment:
            return None, None, {"status_code": 400, "error": "Invalid gateway URL"}

        if parsed.scheme == "http":
            # DNS names (including localhost) can resolve to a non-loopback IP.
            if host not in {"127.0.0.1", "::1"}:
                return None, None, {"status_code": 403, "error": "Plain HTTP is limited to loopback"}
            return parsed, "loopback", None
        if parsed.scheme == "https":
            if port not in {None, 443}:
                return None, None, {"status_code": 403, "error": "Gateway HTTPS port is not approved"}
            allowed_host = os.getenv("AEGIS_GATEWAY_ALLOWED_HOST", "").lower().rstrip(".")
            if not allowed_host or host.lower().rstrip(".") != allowed_host:
                return None, None, {"status_code": 403, "error": "Gateway host is not approved"}
            if not self.cf_client_id or not self.cf_client_secret:
                return None, None, {"status_code": 503, "error": "Access credentials unavailable"}
            return parsed, "access", None
        return None, None, {"status_code": 400, "error": "Gateway requires HTTPS or loopback HTTP"}

    def verify_environment(self) -> bool:
        _, _, error = self._validated_gateway()
        if error is not None:
            sys.stderr.write("[WARNING]: Gateway configuration not approved.\n")
            return False
        return True

    def route_payload_to_quantum(self, prompt_text: str) -> dict:
        parsed, transport, error = self._validated_gateway()
        if error is not None:
            return error

        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        payload = json.dumps({"prompt": str(prompt_text)})
        headers = {"Content-Type": "application/json"}
        if transport == "access":
            headers["CF-Access-Client-Id"] = self.cf_client_id
            headers["CF-Access-Client-Secret"] = self.cf_client_secret

        conn = None
        try:
            if parsed.scheme == "https":
                conn = http.client.HTTPSConnection(parsed.netloc, timeout=10)
            else:
                conn = http.client.HTTPConnection(parsed.netloc, timeout=10)
            conn.request("POST", path, body=payload, headers=headers)
            response = conn.getresponse()
            if response.status != 200:
                # The upstream error body is untrusted and may reflect Access headers.
                # Preserve HTTP status for callers, but never return raw error content.
                return {"status_code": response.status, "error": "Gateway request rejected"}
            body = response.read().decode("utf-8")
            return {"status_code": response.status, "payload": json.loads(body)}
        except (OSError, ValueError, json.JSONDecodeError, http.client.HTTPException):
            # Exception strings may contain URL or request details; never echo secrets.
            return {"status_code": 502, "error": "Gateway request failed"}
        finally:
            if conn is not None:
                try:
                    conn.close()
                except OSError:
                    # Cleanup failure must never expose credential-bearing exception text.
                    pass


if __name__ == "__main__":
    helper = UniversalPlatformHelper()
    raise SystemExit(0 if helper.verify_environment() else 1)
