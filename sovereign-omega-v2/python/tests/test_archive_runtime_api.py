from pathlib import Path

from archive_runtime_api import (
    dispatch_archive_runtime_get,
    dispatch_archive_runtime_post,
    discover_archive_runtime_root,
)

ROOT = Path(__file__).resolve().parents[3]


def get(path: str):
    return dispatch_archive_runtime_get(path, repository_root=ROOT)


def post(path: str, payload):
    return dispatch_archive_runtime_post(path, payload, repository_root=ROOT)


def test_root_discovery_from_source_bridge_path():
    found = discover_archive_runtime_root(ROOT / "sovereign-omega-v2" / "python" / "bridge.py")
    assert found == ROOT


def test_status_ready():
    code, payload = get("/platform/archive/runtime/status")
    assert code == 200
    assert payload["available"] is True
    assert payload["authority_effect"] == "NONE"


def test_get_compute_is_method_not_allowed():
    code, payload = get("/platform/archive/runtime/arc")
    assert code == 405
    assert payload["code"] == "METHOD_NOT_ALLOWED"


def test_arc_rot90_post():
    code, payload = post(
        "/platform/archive/runtime/arc",
        {"operation_id": 1, "grid": [[1, 2], [3, 4]]},
    )
    assert code == 200
    assert payload["operation"] == "ROT90"
    assert payload["output"] == [[2, 4], [1, 3]]


def test_arc_bounds():
    code, payload = post(
        "/platform/archive/runtime/arc",
        {"operation_id": 1, "grid": [[1] * 11]},
    )
    assert code == 400
    assert payload["code"] == "INVALID_REQUEST"


def test_swarm_ephemeral_post():
    code, payload = post(
        "/platform/archive/runtime/swarm",
        {"subject": "alpha", "relation": "relates_to", "object": "beta"},
    )
    assert code == 200
    assert payload["persistent_state"] is False
    assert payload["network_access"] is False
    assert payload["audit_entry_count"] >= 3


def test_swarm_rejects_control_chars():
    code, _payload = post(
        "/platform/archive/runtime/swarm",
        {"subject": "a\nb", "relation": "r", "object": "o"},
    )
    assert code == 400


def test_biology_bounded_post():
    code, payload = post(
        "/platform/archive/runtime/biology",
        {"stimulus": "normal input"},
    )
    assert code == 200
    assert payload["pathogen_detected"] is False
    assert payload["authority_effect"] == "NONE"


def test_unknown_body_field_rejected():
    code, payload = post(
        "/platform/archive/runtime/biology",
        {"stimulus": "x", "admin": True},
    )
    assert code == 400
    assert payload["code"] == "INVALID_REQUEST"


def test_query_on_compute_post_rejected():
    code, payload = post(
        "/platform/archive/runtime/arc?op=1",
        {"operation_id": 1, "grid": [[1]]},
    )
    assert code == 400
    assert payload["code"] == "INVALID_REQUEST"


def test_missing_runtime_fails_closed(tmp_path):
    code, payload = dispatch_archive_runtime_get(
        "/platform/archive/runtime/status", repository_root=tmp_path
    )
    assert code == 503
    assert payload["state"] == "INVALID_OR_STALE"
