from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from harness.sdk.archive_runtime import ArchiveRuntimeAdapter, ArchiveRuntimeError

BASE = "/platform/archive/runtime"
MAX_GRID_SIDE = 10
MAX_GRID_CELLS = 100
MAX_SWARM_TEXT = 64
MAX_BIOLOGY_TEXT = 256
AUTHORITY_EFFECT = "NONE"

_STATUS_PATHS = {BASE, BASE + "/", BASE + "/status"}
_COMPUTE_PATHS = {
    BASE + "/arc": "arc",
    BASE + "/swarm": "swarm",
    BASE + "/biology": "biology",
}


def _error(code: str, message: str) -> dict[str, Any]:
    return {"error": message, "code": code, "authority_effect": AUTHORITY_EFFECT}


def discover_archive_runtime_root(start: str | Path) -> Path:
    path = Path(start).resolve()
    candidates = [path] if path.is_dir() else []
    candidates.extend(path.parents)
    for candidate in candidates:
        if (
            (candidate / "swarm_os" / "arc" / "dsl" / "vm.py").is_file()
            and (candidate / "harness" / "sdk" / "archive_runtime.py").is_file()
        ):
            return candidate
    raise ArchiveRuntimeError("RECOVERED_RUNTIME_MISSING:repository_root")


def _reject_unknown(payload: Mapping[str, Any], allowed: set[str]) -> None:
    extra = sorted(str(key) for key in set(payload) - allowed)
    if extra:
        raise ValueError("UNKNOWN_BODY_FIELD:" + ",".join(extra))


def _required(payload: Mapping[str, Any], name: str) -> Any:
    if name not in payload:
        raise ValueError(f"MISSING_{name.upper()}")
    return payload[name]


def _bounded_text(value: Any, *, field: str, limit: int) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value) > limit
        or any(ord(ch) < 32 for ch in value)
    ):
        raise ValueError(f"{field.upper()}_INVALID")
    return value


def _parse_grid(grid: Any) -> list[list[int]]:
    if not isinstance(grid, list) or not grid or len(grid) > MAX_GRID_SIDE:
        raise ValueError("GRID_INVALID")
    if not all(isinstance(row, list) and row and len(row) <= MAX_GRID_SIDE for row in grid):
        raise ValueError("GRID_INVALID")
    width = len(grid[0])
    if width > MAX_GRID_SIDE or any(len(row) != width for row in grid):
        raise ValueError("GRID_NON_RECTANGULAR")
    if len(grid) * width > MAX_GRID_CELLS:
        raise ValueError("GRID_TOO_LARGE")
    for row in grid:
        for value in row:
            if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 9:
                raise ValueError("GRID_VALUE_INVALID")
    return grid


def _runtime_status(
    repository_root: str | Path,
    adapter_factory: Callable[[str | Path], ArchiveRuntimeAdapter],
) -> tuple[int, dict[str, Any]]:
    try:
        adapter_factory(repository_root)
        available = True
        state = "READY"
    except ArchiveRuntimeError:
        available = False
        state = "INVALID_OR_STALE"
    return 200 if available else 503, {
        "schema": "AEGIS_ARCHIVE_RUNTIME_STATUS_V1",
        "state": state,
        "available": available,
        "scope": "LOCAL_EPHEMERAL_READ_COMPUTE_ONLY",
        "network_authority": False,
        "persistent_state": False,
        "authority_effect": AUTHORITY_EFFECT,
    }


def dispatch_archive_runtime_get(
    request_target: str,
    *,
    repository_root: str | Path,
    adapter_factory: Callable[[str | Path], ArchiveRuntimeAdapter] = ArchiveRuntimeAdapter,
) -> tuple[int, dict[str, Any]]:
    parsed = urlparse(request_target)
    if parsed.query:
        return 400, _error("INVALID_REQUEST", "QUERY_NOT_ALLOWED")
    if parsed.path in _STATUS_PATHS:
        return _runtime_status(repository_root, adapter_factory)
    if parsed.path in _COMPUTE_PATHS:
        return 405, _error("METHOD_NOT_ALLOWED", "compute requires POST JSON")
    return 404, _error("NOT_FOUND", "archive runtime route not found")


def dispatch_archive_runtime_post(
    request_target: str,
    payload: Mapping[str, Any] | Any,
    *,
    repository_root: str | Path,
    adapter_factory: Callable[[str | Path], ArchiveRuntimeAdapter] = ArchiveRuntimeAdapter,
) -> tuple[int, dict[str, Any]]:
    parsed = urlparse(request_target)
    if parsed.query:
        return 400, _error("INVALID_REQUEST", "QUERY_NOT_ALLOWED")
    if parsed.path in _STATUS_PATHS:
        return 405, _error("METHOD_NOT_ALLOWED", "status requires GET")
    operation = _COMPUTE_PATHS.get(parsed.path)
    if operation is None:
        return 404, _error("NOT_FOUND", "archive runtime route not found")
    if not isinstance(payload, Mapping):
        return 400, _error("INVALID_REQUEST", "BODY_NOT_OBJECT")

    try:
        adapter = adapter_factory(repository_root)

        if operation == "arc":
            _reject_unknown(payload, {"operation_id", "grid"})
            operation_id = _required(payload, "operation_id")
            if isinstance(operation_id, bool) or not isinstance(operation_id, int) or not 0 <= operation_id <= 10:
                raise ValueError("ARC_OPERATION_ID_INVALID")
            grid = _parse_grid(_required(payload, "grid"))
            return 200, adapter.arc_transform(operation_id=operation_id, grid=grid)

        if operation == "swarm":
            _reject_unknown(payload, {"subject", "relation", "object"})
            subject = _bounded_text(_required(payload, "subject"), field="subject", limit=MAX_SWARM_TEXT)
            relation = _bounded_text(_required(payload, "relation"), field="relation", limit=MAX_SWARM_TEXT)
            obj = _bounded_text(_required(payload, "object"), field="object", limit=MAX_SWARM_TEXT)
            return 200, adapter.swarm_observe(subject=subject, relation=relation, obj=obj)

        _reject_unknown(payload, {"stimulus"})
        stimulus = _bounded_text(_required(payload, "stimulus"), field="stimulus", limit=MAX_BIOLOGY_TEXT)
        return 200, adapter.biology_probe(stimulus=stimulus)

    except ValueError as exc:
        return 400, _error("INVALID_REQUEST", str(exc))
    except ArchiveRuntimeError as exc:
        code = str(exc)
        if code.startswith("RECOVERED_RUNTIME_MISSING"):
            return 503, _error("INVALID_OR_STALE", "recovered runtime unavailable")
        return 400, _error("INVALID_REQUEST", code)
    except Exception:
        return 503, _error("INVALID_OR_STALE", "archive runtime unavailable")
