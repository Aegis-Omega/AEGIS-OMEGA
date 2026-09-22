"""Offline tests for the recovered archive runtime SDK surface."""
import json
import urllib.parse
from unittest.mock import MagicMock, patch

import pytest

from aegis import AegisClient

BASE = "https://aegis-vertex.aegisomega.com"


def envelope(data):
    return {
        "contract_version": "1.0.0",
        "execution_id": "exec-archive-1",
        "timestamp": "2026-09-22T00:00:00Z",
        "is_replay_reconstructable": True,
        "data": data,
    }


def response(body):
    m = MagicMock()
    m.__enter__ = MagicMock(return_value=m)
    m.__exit__ = MagicMock(return_value=False)
    m.read.return_value = json.dumps(body).encode()
    return m


def test_archive_runtime_status():
    body = envelope({
        "state": "READY",
        "available": True,
        "scope": "LOCAL_EPHEMERAL_READ_COMPUTE_ONLY",
        "network_authority": False,
        "persistent_state": False,
        "authority_effect": "NONE",
    })
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen", return_value=response(body)):
        status = client.archive_runtime_status()
    assert status.available is True
    assert status.network_authority is False
    assert status.persistent_state is False
    assert status.authority_effect == "NONE"


def test_archive_arc_transform_builds_bounded_get():
    body = envelope({
        "schema": "AEGIS_ARCHIVE_ARC_TRANSFORM_V1",
        "operation": "ROT90",
        "output": [[2, 4], [1, 3]],
        "authority_effect": "NONE",
    })
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen", return_value=response(body)) as mocked:
        result = client.archive_arc_transform([[1, 2], [3, 4]], 1)
    request = mocked.call_args.args[0]
    parsed = urllib.parse.urlparse(request.full_url)
    query = urllib.parse.parse_qs(parsed.query)
    assert parsed.path == "/platform/archive/runtime/arc"
    assert query["op"] == ["1"]
    assert json.loads(query["grid"][0]) == [[1, 2], [3, 4]]
    assert result["operation"] == "ROT90"


def test_archive_arc_rejects_oversized_grid_before_network():
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen") as mocked:
        with pytest.raises(ValueError):
            client.archive_arc_transform([[1] * 11], 1)
    mocked.assert_not_called()


def test_archive_swarm_observe_encodes_inputs():
    body = envelope({
        "schema": "AEGIS_ARCHIVE_SWARM_OBSERVATION_V1",
        "persistent_state": False,
        "network_access": False,
        "authority_effect": "NONE",
    })
    client = AegisClient("aegis_test_key", base_url=BASE)
    with patch("urllib.request.urlopen", return_value=response(body)) as mocked:
        result = client.archive_swarm_observe("alpha one", "relates_to", "beta/two")
    request = mocked.call_args.args[0]
    parsed = urllib.parse.urlparse(request.full_url)
    query = urllib.parse.parse_qs(parsed.query)
    assert query["subject"] == ["alpha one"]
    assert query["object"] == ["beta/two"]
    assert result["persistent_state"] is False


def test_archive_biology_probe_is_bounded():
    client = AegisClient("aegis_test_key", base_url=BASE)
    with pytest.raises(ValueError):
        client.archive_biology_probe("x" * 257)
