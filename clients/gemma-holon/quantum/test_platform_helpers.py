"""Network-free security regressions for the AEGIS Cloudflare Access gateway helper."""
import importlib.util
import http.server
import json
import threading
import os
import pathlib
import subprocess
import sys
import unittest
from unittest.mock import patch

MODULE = pathlib.Path(__file__).resolve().with_name("platform-helpers.py")
spec = importlib.util.spec_from_file_location("aegis_platform_helpers", MODULE)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class FakeResponse:
    status = 200

    def read(self):
        return b'{"ok":true}'


class Recorder:
    calls = []

    def __init__(self, host, timeout):
        self.calls.append(("connect", host))

    def request(self, method, path, body, headers):
        self.calls.append(("request", path, dict(headers)))

    def getresponse(self):
        return FakeResponse()

    def close(self):
        pass


class GatewaySecurityTests(unittest.TestCase):
    def exercise(self, target, approved="gateway.aegisomega.com", credential=True):
        Recorder.calls = []
        environment = {
            "AEGIS_GATEWAY_URL": target,
            "AEGIS_GATEWAY_ALLOWED_HOST": approved,
            "CF_ACCESS_CLIENT_ID": "FAKE_ID" if credential else "",
            "CF_ACCESS_CLIENT_SECRET": "FAKE_SECRET" if credential else "",
        }
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(mod.http.client, "HTTPConnection", Recorder):
                with patch.object(mod.http.client, "HTTPSConnection", Recorder):
                    result = mod.UniversalPlatformHelper().route_payload_to_quantum("hello")
        return result, Recorder.calls

    def test_reject_remote_http_without_network(self):
        result, calls = self.exercise("http://gateway.aegisomega.com/trigger")
        self.assertEqual(result["status_code"], 403)
        self.assertEqual(calls, [])

    def test_reject_unsupported_scheme(self):
        result, calls = self.exercise("ftp://gateway.aegisomega.com/trigger")
        self.assertEqual(result["status_code"], 400)
        self.assertEqual(calls, [])

    def test_reject_https_unapproved_host(self):
        result, calls = self.exercise("https://other.invalid/trigger")
        self.assertEqual(result["status_code"], 403)
        self.assertEqual(calls, [])

    def test_reject_https_without_approval(self):
        result, calls = self.exercise("https://gateway.aegisomega.com/trigger", approved="")
        self.assertEqual(result["status_code"], 403)
        self.assertEqual(calls, [])

    def test_reject_https_without_credentials(self):
        result, calls = self.exercise("https://gateway.aegisomega.com/trigger", credential=False)
        self.assertEqual(result["status_code"], 503)
        self.assertEqual(calls, [])

    def test_reject_userinfo_in_url(self):
        result, calls = self.exercise("https://user:pass@gateway.aegisomega.com/trigger")
        self.assertEqual(result["status_code"], 400)
        self.assertEqual(calls, [])

    def test_https_approved_host_sends_synthetic_access_headers(self):
        result, calls = self.exercise("https://gateway.aegisomega.com/trigger?a=1")
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(calls[1][1], "/trigger?a=1")
        self.assertEqual(calls[1][2]["CF-Access-Client-Secret"], "FAKE_SECRET")

    def test_local_http_never_gets_access_headers(self):
        result, calls = self.exercise("http://127.0.0.1:5000/trigger-quantum")
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(calls[1][1], "/trigger-quantum")
        self.assertNotIn("CF-Access-Client-Secret", calls[1][2])
        self.assertNotIn("CF-Access-Client-Id", calls[1][2])

    def test_reject_malformed_ipv6_url(self):
        result, calls = self.exercise("https://[bad")
        self.assertEqual(result["status_code"], 400)
        self.assertEqual(calls, [])

    def test_reject_https_nondefault_port(self):
        result, calls = self.exercise("https://gateway.aegisomega.com:444/trigger")
        self.assertEqual(result["status_code"], 403)
        self.assertEqual(calls, [])

    def test_reject_control_character_url(self):
        result, calls = self.exercise("https://gateway.aegisomega.com\r\n/trigger")
        self.assertEqual(result["status_code"], 400)
        self.assertEqual(calls, [])

    def test_reject_bad_port(self):
        result, calls = self.exercise("https://gateway.aegisomega.com:abc/trigger")
        self.assertEqual(result["status_code"], 400)
        self.assertEqual(calls, [])

    def test_reject_localhost_hostname_not_literal_loopback(self):
        result, calls = self.exercise("http://localhost:5000/trigger")
        self.assertEqual(result["status_code"], 403)
        self.assertEqual(calls, [])

    def test_cli_exit_status_matches_readiness_without_echoing_secrets(self):
        for url, expected_code in [
            ("https://gateway.aegisomega.com/trigger", 0),
            ("https://attacker.invalid/trigger", 1),
            ("http://127.0.0.1:5000/trigger", 0),
        ]:
            with self.subTest(url=url):
                env = dict(os.environ)
                env.update({
                    "AEGIS_GATEWAY_URL": url,
                    "AEGIS_GATEWAY_ALLOWED_HOST": "gateway.aegisomega.com",
                    "CF_ACCESS_CLIENT_ID": "FAKE_ID",
                    "CF_ACCESS_CLIENT_SECRET": "FAKE_SECRET",
                })
                proc = subprocess.run([sys.executable, str(MODULE)], env=env,
                                      capture_output=True, text=True, timeout=3)
                self.assertEqual(proc.returncode, expected_code)
                self.assertNotIn("FAKE_SECRET", proc.stdout + proc.stderr)
                self.assertNotIn("FAKE_ID", proc.stdout + proc.stderr)

    def test_readiness_never_approves_rejected_transports(self):
        cases = [
            ("ftp://gateway.aegisomega.com/trigger", "gateway.aegisomega.com", True),
            ("http://other.invalid/trigger", "gateway.aegisomega.com", True),
            ("https://other.invalid/trigger", "gateway.aegisomega.com", True),
            ("https://gateway.aegisomega.com:444/trigger", "gateway.aegisomega.com", True),
            ("https://gateway.aegisomega.com/trigger", "", True),
            ("https://gateway.aegisomega.com/trigger", "gateway.aegisomega.com", False),
            ("https://[bad", "gateway.aegisomega.com", True),
        ]
        for target, approved, credentials in cases:
            with self.subTest(target=target, approved=approved, credentials=credentials):
                env = {
                    "AEGIS_GATEWAY_URL": target,
                    "AEGIS_GATEWAY_ALLOWED_HOST": approved,
                    "CF_ACCESS_CLIENT_ID": "FAKE_ID" if credentials else "",
                    "CF_ACCESS_CLIENT_SECRET": "FAKE_SECRET" if credentials else "",
                }
                with patch.dict(os.environ, env, clear=True):
                    self.assertFalse(mod.UniversalPlatformHelper().verify_environment())

    def test_readiness_approves_only_valid_transport(self):
        cases = [
            ("http://127.0.0.1:5000/trigger", False),
            ("http://[::1]:5000/trigger", False),
            ("https://gateway.aegisomega.com/trigger", True),
        ]
        for target, creds in cases:
            with self.subTest(target=target):
                env = {
                    "AEGIS_GATEWAY_URL": target,
                    "AEGIS_GATEWAY_ALLOWED_HOST": "gateway.aegisomega.com",
                    "CF_ACCESS_CLIENT_ID": "FAKE_ID" if creds else "",
                    "CF_ACCESS_CLIENT_SECRET": "FAKE_SECRET" if creds else "",
                }
                with patch.dict(os.environ, env, clear=True):
                    self.assertTrue(mod.UniversalPlatformHelper().verify_environment())

    def test_ipv6_loopback_never_sends_access_headers(self):
        result, calls = self.exercise("http://[::1]:5000/trigger")
        self.assertEqual(result["status_code"], 200)
        self.assertNotIn("CF-Access-Client-Id", calls[1][2])
        self.assertNotIn("CF-Access-Client-Secret", calls[1][2])

    def test_explicit_standard_https_port(self):
        result, calls = self.exercise("https://gateway.aegisomega.com:443/trigger")
        self.assertEqual(result["status_code"], 200)
        self.assertEqual(calls[1][2]["CF-Access-Client-Secret"], "FAKE_SECRET")

    def test_local_loopback_without_credentials(self):
        result, calls = self.exercise("http://127.0.0.1:5000/trigger", credential=False)
        self.assertEqual(result["status_code"], 200)
        self.assertNotIn("CF-Access-Client-Secret", calls[1][2])

    def test_failure_does_not_echo_secret_or_raise(self):
        class Failing:
            def __init__(self, *args, **kwargs):
                pass
            def request(self, *args, **kwargs):
                raise OSError("synthetic FAKE_SECRET transport failure")
            def close(self):
                pass
        environment = {
            "AEGIS_GATEWAY_URL": "https://gateway.aegisomega.com/trigger",
            "AEGIS_GATEWAY_ALLOWED_HOST": "gateway.aegisomega.com",
            "CF_ACCESS_CLIENT_ID": "FAKE_ID",
            "CF_ACCESS_CLIENT_SECRET": "FAKE_SECRET",
        }
        with patch.dict(os.environ, environment, clear=True):
            with patch.object(mod.http.client, "HTTPSConnection", Failing):
                result = mod.UniversalPlatformHelper().route_payload_to_quantum("hello")
        self.assertEqual(result["status_code"], 502)
        self.assertNotIn("FAKE_SECRET", str(result))


    def test_close_failure_cannot_echo_access_secret(self):
        class FailingClose:
            def __init__(self, *args, **kwargs):
                pass
            def request(self, *args, **kwargs):
                pass
            def getresponse(self):
                return FakeResponse()
            def close(self):
                raise OSError("synthetic FAKE_SECRET close failure")

        env = {
            "AEGIS_GATEWAY_URL": "https://gateway.aegisomega.com/trigger",
            "AEGIS_GATEWAY_ALLOWED_HOST": "gateway.aegisomega.com",
            "CF_ACCESS_CLIENT_ID": "FAKE_ID",
            "CF_ACCESS_CLIENT_SECRET": "FAKE_SECRET",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(mod.http.client, "HTTPSConnection", FailingClose):
                result = mod.UniversalPlatformHelper().route_payload_to_quantum("hello")
        self.assertEqual(result, {"status_code": 200, "payload": {"ok": True}})
        self.assertNotIn("FAKE_SECRET", str(result))

    def test_real_loopback_transport_without_access_headers(self):
        received = []

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                payload = self.rfile.read(int(self.headers["Content-Length"]))
                received.append({
                    "path": self.path,
                    "body": json.loads(payload),
                    "header_names": [k.lower() for k in self.headers.keys()],
                })
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"delivered":true}')

            def log_message(self, *_args):
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            environment = {
                "AEGIS_GATEWAY_URL": f"http://127.0.0.1:{server.server_address[1]}/trigger-quantum",
                "CF_ACCESS_CLIENT_ID": "FAKE_ID",
                "CF_ACCESS_CLIENT_SECRET": "FAKE_SECRET",
            }
            with patch.dict(os.environ, environment, clear=True):
                helper = mod.UniversalPlatformHelper()
                self.assertTrue(helper.verify_environment())
                result = helper.route_payload_to_quantum("delivery-check")
            self.assertEqual(result, {"status_code": 200, "payload": {"delivered": True}})
            self.assertEqual(received[0]["path"], "/trigger-quantum")
            self.assertEqual(received[0]["body"], {"prompt": "delivery-check"})
            self.assertNotIn("cf-access-client-secret", received[0]["header_names"])
            self.assertNotIn("cf-access-client-id", received[0]["header_names"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)



    def test_untrusted_error_response_never_echoes_access_secret(self):
        class EchoedErrorResponse:
            status = 401

            def read(self):
                return b"upstream error contained FAKE_SECRET and FAKE_ID"

        class EchoingGateway:
            def __init__(self, *args, **kwargs):
                pass

            def request(self, *args, **kwargs):
                pass

            def getresponse(self):
                return EchoedErrorResponse()

            def close(self):
                pass

        env = {
            "AEGIS_GATEWAY_URL": "https://gateway.aegisomega.com/trigger",
            "AEGIS_GATEWAY_ALLOWED_HOST": "gateway.aegisomega.com",
            "CF_ACCESS_CLIENT_ID": "FAKE_ID",
            "CF_ACCESS_CLIENT_SECRET": "FAKE_SECRET",
        }
        with patch.dict(os.environ, env, clear=True):
            with patch.object(mod.http.client, "HTTPSConnection", EchoingGateway):
                result = mod.UniversalPlatformHelper().route_payload_to_quantum("hello")
        self.assertEqual(result["status_code"], 401)
        self.assertNotIn("FAKE_SECRET", str(result))
        self.assertNotIn("FAKE_ID", str(result))


if __name__ == "__main__":
    unittest.main()
