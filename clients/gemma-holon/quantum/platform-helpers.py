"""
AEGIS Gemma Holon — Cloudflare Zero Trust routing helper.
Routes authenticated mobile client hooks to local quantum execution loop.

Requires env vars:
  CF_ACCESS_CLIENT_ID      — Cloudflare Access service token ID
  CF_ACCESS_CLIENT_SECRET  — Cloudflare Access service token secret
  AEGIS_GATEWAY_URL        — Target URL (default: http://127.0.0.1:5000/trigger-quantum)

Epistemic tier: T2
"""
import os
import sys
import json
import http.client
from urllib.parse import urlparse


class UniversalPlatformHelper:
    def __init__(self):
        self.target_url = os.getenv("AEGIS_GATEWAY_URL", "http://127.0.0.1:5000/trigger-quantum")
        self.cf_client_id = os.getenv("CF_ACCESS_CLIENT_ID", "")
        self.cf_client_secret = os.getenv("CF_ACCESS_CLIENT_SECRET", "")

    def verify_environment(self) -> bool:
        if not self.cf_client_id or not self.cf_client_secret:
            sys.stderr.write("[WARNING]: Missing Cloudflare Access Service Token credentials.\n")
            return False
        return True

    def route_payload_to_quantum(self, prompt_text: str) -> dict:
        parsed = urlparse(self.target_url)
        host = parsed.netloc
        path = parsed.path or "/"
        payload = json.dumps({"prompt": str(prompt_text)})
        headers = {
            "Content-Type": "application/json",
            "CF-Access-Client-Id": self.cf_client_id,
            "CF-Access-Client-Secret": self.cf_client_secret,
        }
        try:
            if parsed.scheme == "https":
                conn = http.client.HTTPSConnection(host, timeout=10)
            else:
                conn = http.client.HTTPConnection(host, timeout=10)
            conn.request("POST", path, body=payload, headers=headers)
            response = conn.getresponse()
            body = response.read().decode("utf-8")
            conn.close()
            return {
                "status_code": response.status,
                "payload": json.loads(body) if response.status == 200 else body,
            }
        except Exception as e:
            return {"status_code": 500, "error": f"Tunnel Execution Failure: {e}"}


if __name__ == "__main__":
    helper = UniversalPlatformHelper()
    helper.verify_environment()
