import json
from pathlib import Path
from urllib.parse import quote

from archive_runtime_api import dispatch_archive_runtime_get, discover_archive_runtime_root

ROOT = Path(__file__).resolve().parents[3]


def call(path: str):
    return dispatch_archive_runtime_get(path, repository_root=ROOT)


def test_root_discovery_from_source_bridge_path():
    found = discover_archive_runtime_root(ROOT / "sovereign-omega-v2" / "python" / "bridge.py")
    assert found == ROOT


def test_status_ready():
    code, payload = call("/platform/archive/runtime/status")
    assert code == 200
    assert payload["available"] is True
    assert payload["authority_effect"] == "NONE"


def test_arc_rot90():
    grid = quote(json.dumps([[1, 2], [3, 4]], separators=(",", ":")))
    code, payload = call(f"/platform/archive/runtime/arc?op=1&grid={grid}")
    assert code == 200
    assert payload["operation"] == "ROT90"
    assert payload["output"] == [[2, 4], [1, 3]]


def test_arc_bounds():
    grid = quote(json.dumps([[1] * 11]))
    code, payload = call(f"/platform/archive/runtime/arc?op=1&grid={grid}")
    assert code == 400
    assert payload["code"] == "INVALID_REQUEST"


def test_swarm_ephemeral():
    code, payload = call(
        "/platform/archive/runtime/swarm?subject=alpha&relation=relates_to&object=beta"
    )
    assert code == 200
    assert payload["persistent_state"] is False
    assert payload["network_access"] is False
    assert payload["audit_entry_count"] >= 3


def test_swarm_rejects_control_chars():
    code, _payload = call(
        "/platform/archive/runtime/swarm?subject=a%0Ab&relation=r&object=o"
    )
    assert code == 400


def test_biology_bounded():
    code, payload = call(
        "/platform/archive/runtime/biology?stimulus=normal%20input"
    )
    assert code == 200
    assert payload["pathogen_detected"] is False
    assert payload["authority_effect"] == "NONE"


def test_unknown_query_rejected():
    code, _payload = call(
        "/platform/archive/runtime/biology?stimulus=x&admin=true"
    )
    assert code == 400


def test_missing_runtime_fails_closed(tmp_path):
    code, payload = dispatch_archive_runtime_get(
        "/platform/archive/runtime/status", repository_root=tmp_path
    )
    assert code == 503
    assert payload["state"] == "INVALID_OR_STALE"
