"""Unit tests for the AEGIS-Ω Python SDK — offline, no network required."""
import json
import urllib.error
from unittest.mock import MagicMock, patch
from aegis import AegisClient, AegisError

BASE = "https://aegis-vertex.aegisomega.com"

VALID_ENVELOPE = {
    "contract_version": "1.0.0",
    "execution_id": "exec-test-123",
    "timestamp": "2026-06-13T00:00:00Z",
    "is_replay_reconstructable": True,
    "data": {
        "version": "1.0.0",
        "contract_version": "1.0.0",
        "total_agents": 39,
        "chain_valid": True,
        "audit_chain_hash": "a" * 64,
        "available": True,
    },
}

COLLAB_DATA = {
    "cycle_id": "cyc-1",
    "objective": "Enter EU fintech",
    "mode": "gtm",
    "departments_collaborated": 39,
    "artifacts": [{"role": "Strategy", "output": "Phase 1: design partners..."}],
    "constitutional_audit": {"verdict": "APPROVED", "concerns": []},
    "chain_valid": True,
    "audit_chain_hash": "b" * 64,
    "execution_id": "exec-test-123",
    "projection": {"first_year_arr_usd": 2400000},
}


def _mock_urlopen(body: dict) -> MagicMock:
    m = MagicMock()
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    m.read.return_value = json.dumps(body).encode()
    return m


def test_status_returns_platform_status():
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(VALID_ENVELOPE)):
        status = client.status()
    assert status.total_agents == 39
    assert status.chain_valid is True
    assert status.available is True


def test_collaborate_returns_result():
    envelope = {**VALID_ENVELOPE, "data": COLLAB_DATA}
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(envelope)):
        result = client.collaborate("Enter EU fintech", mode="gtm")
    assert result.departments_collaborated == 39
    assert result.constitutional_audit.verdict == "APPROVED"
    assert result.chain_valid is True
    assert len(result.artifacts) == 1
    assert result.artifacts[0].role == "Strategy"


def test_missing_contract_version_raises():
    bad = {k: v for k, v in VALID_ENVELOPE.items() if k != "contract_version"}
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(bad)):
        try:
            client.status()
            assert False, "should have raised"
        except AegisError as exc:
            assert exc.code == "INTERNAL"


def test_wrong_contract_version_raises():
    bad = {**VALID_ENVELOPE, "contract_version": "2.0.0"}
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(bad)):
        try:
            client.status()
            assert False, "should have raised"
        except AegisError as exc:
            assert exc.code == "INTERNAL"


def test_is_replay_reconstructable_false_raises():
    bad = {**VALID_ENVELOPE, "is_replay_reconstructable": False}
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen", return_value=_mock_urlopen(bad)):
        try:
            client.status()
            assert False, "should have raised"
        except AegisError:
            pass


def test_http_401_raises_unauthorized():
    client = AegisClient("aegis_bad_key", base_url=BASE)
    err_body = json.dumps({"error": "Invalid key", "code": "UNAUTHORIZED"}).encode()
    http_err = urllib.error.HTTPError(url=BASE, code=401, msg="Unauthorized", hdrs=None, fp=None)  # type: ignore[arg-type]
    http_err.read = lambda: err_body  # type: ignore[method-assign]
    with patch("urllib.request.urlopen", side_effect=http_err):
        try:
            client.collaborate("test")
            assert False, "should have raised"
        except AegisError as exc:
            assert exc.code == "UNAUTHORIZED"
            assert exc.status == 401


def test_empty_api_key_raises():
    try:
        AegisClient("")
        assert False, "should have raised"
    except ValueError:
        pass


def test_delete_execution_succeeds():
    resp = MagicMock()
    resp.__enter__ = MagicMock(return_value=resp)
    resp.__exit__ = MagicMock(return_value=False)
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen", return_value=resp):
        client.delete_execution("exec-del-1")
