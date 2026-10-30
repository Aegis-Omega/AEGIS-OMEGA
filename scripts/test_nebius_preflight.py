import importlib.util
import io
import json
import pathlib
import unittest
from urllib.error import HTTPError, URLError

spec = importlib.util.spec_from_file_location("nebius_preflight", pathlib.Path(__file__).with_name("nebius_preflight.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class FakeResponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, amount):
        return self.payload[:amount]


class NebiusPreflightTests(unittest.TestCase):
    def test_no_key_never_contacts_network(self):
        def forbidden(*args, **kwargs):
            raise AssertionError("network called without key")
        self.assertEqual(m.probe(token="", model=m.DEFAULT_MODEL, opener=forbidden)["status"], "CREDENTIAL_MISSING")

    def test_valid_get_and_exact_model(self):
        called = []
        def opener(req, timeout):
            called.append((req.full_url, req.get_method(), req.get_header("Authorization"), timeout))
            return FakeResponse({"data": [{"id": m.DEFAULT_MODEL}, {"id": "other/model"}]})
        r = m.probe(token="synthetic-test-token", model=m.DEFAULT_MODEL, opener=opener)
        self.assertEqual(r["status"], "MODEL_AVAILABLE")
        self.assertTrue(r["authenticated"])
        self.assertEqual(called[0][1], "GET")
        self.assertEqual(called[0][0], "https://api.tokenfactory.us-north1.nebius.com/v1/models")
        self.assertEqual(r["paid_inference_calls"], 0)
        self.assertNotIn("synthetic-test-token", json.dumps(r))

    def test_model_not_listed_not_promoted(self):
        r=m.probe(token="test", model=m.DEFAULT_MODEL, opener=lambda *a, **k: FakeResponse({"data": [{"id":"other/model"}]}))
        self.assertEqual(r["status"], "MODEL_NOT_LISTED")
        self.assertTrue(r["authenticated"])
        self.assertFalse(r["model_available"])

    def test_auth_401(self):
        def opener(req, timeout):
            raise HTTPError(req.full_url, 401, "Unauthorized", {}, None)
        r=m.probe(token="serviceaccount-synthetic",model=m.DEFAULT_MODEL,opener=opener)
        self.assertEqual(r["status"], "AUTH_REJECTED")
        self.assertFalse(r["authenticated"])

    def test_auth_403(self):
        def opener(req, timeout):
            raise HTTPError(req.full_url,403,"Forbidden",{},None)
        self.assertEqual(m.probe(token="x",model=m.DEFAULT_MODEL,opener=opener)["status"], "AUTH_FORBIDDEN")

    def test_network_unknown_not_auth_denial(self):
        def opener(req, timeout):
            raise URLError("synthetic DNS failure")
        r=m.probe(token="x",model=m.DEFAULT_MODEL,opener=opener)
        self.assertEqual(r["status"], "NETWORK_UNKNOWN")
        self.assertFalse(r["authenticated"])

    def test_reject_untrusted_endpoints(self):
        for url in ("http://api.tokenfactory.nebius.com/v1", "https://attacker.test/v1", "https://api.tokenfactory.nebius.com/v1?q=1", "https://api.tokenfactory.nebius.com:443/v1", "https://a@api.tokenfactory.nebius.com/v1", "https://api.tokenfactory.nebius.com/v1/chat/completions"):
            with self.subTest(url=url):
                r=m.probe(token="x",model=m.DEFAULT_MODEL,base_url=url,opener=lambda *a,**k: self.fail("network called"))
                self.assertEqual(r["status"], "INVALID_ENDPOINT")

    def test_allow_official_generic_endpoint(self):
        self.assertEqual(m.models_url("https://api.tokenfactory.nebius.com/v1/"),"https://api.tokenfactory.nebius.com/v1/models")

    def test_invalid_model_fails_before_network(self):
        r=m.probe(token="x",model="bad model",opener=lambda *a, **k:self.fail("network called"))
        self.assertEqual(r["status"], "INVALID_MODEL_ID")

    def test_invalid_response(self):
        class Garbled:
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return b'{oops'
        r=m.probe(token="x",model=m.DEFAULT_MODEL,opener=lambda *a,**k:Garbled())
        self.assertEqual(r["status"], "RESPONSE_INVALID")


if __name__ == "__main__":
    unittest.main()
