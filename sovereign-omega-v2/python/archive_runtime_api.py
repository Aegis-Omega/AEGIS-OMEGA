from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from urllib.parse import parse_qs, urlparse

from harness.sdk.archive_runtime import ArchiveRuntimeAdapter, ArchiveRuntimeError

BASE = "/platform/archive/runtime"
MAX_GRID_SIDE = 10
MAX_GRID_CELLS = 100
MAX_SWARM_TEXT = 64
MAX_BIOLOGY_TEXT = 256
AUTHORITY_EFFECT = "NONE"


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


def _single(params: dict[str, list[str]], name: str) -> str:
    values = params.get(name)
    if not values:
        raise ValueError(f"MISSING_{name.upper()}")
    if len(values) != 1:
        raise ValueError(f"DUPLICATE_{name.upper()}")
    return values[0]


def _reject_unknown(params: dict[str, list[str]], allowed: set[str]) -> None:
    extra = sorted(set(params) - allowed)
    if extra:
        raise ValueError("UNKNOWN_QUERY_PARAMETER:" + ",".join(extra))


def _bounded_text(value: str, *, field: str, limit: int) -> str:
    if not value or len(value) > limit or any(ord(ch) < 32 for ch in value):
        raise ValueError(f"{field.upper()}_INVALID")
    return value


def _parse_grid(raw: str) -> list[list[int]]:
    try:
        grid = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("GRID_JSON_INVALID") from exc
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


def dispatch_archive_runtime_get(
    request_target: str,
    *,
    repository_root: str | Path,
    adapter_factory: Callable[[str | Path], ArchiveRuntimeAdapter] = ArchiveRuntimeAdapter,
) -> tuple[int, dict[str, Any]]:
    parsed = urlparse(request_target)
    if not parsed.path.startswith(BASE):
        return 404, _error("NOT_FOUND", "archive runtime route not found")

    params = parse_qs(parsed.query, keep_blank_values=True, strict_parsing=False)
    suffix = parsed.path[len(BASE):].strip("/") or "status"

    try:
        if suffix == "status":
            _reject_unknown(params, set())
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

        adapter = adapter_factory(repository_root)

        if suffix == "arc":
            _reject_unknown(params, {"op", "grid"})
            try:
                operation_id = int(_single(params, "op"))
            except (TypeError, ValueError) as exc:
                raise ValueError("ARC_OPERATION_ID_INVALID") from exc
            if not 0 <= operation_id <= 10:
                raise ValueError("ARC_OPERATION_ID_INVALID")
            grid = _parse_grid(_single(params, "grid"))
            return 200, adapter.arc_transform(operation_id=operation_id, grid=grid)

        if suffix == "swarm":
            _reject_unknown(params, {"subject", "relation", "object"})
            subject = _bounded_text(_single(params, "subject"), field="subject", limit=MAX_SWARM_TEXT)
            relation = _bounded_text(_single(params, "relation"), field="relation", limit=MAX_SWARM_TEXT)
            obj = _bounded_text(_single(params, "object"), field="object", limit=MAX_SWARM_TEXT)
            return 200, adapter.swarm_observe(subject=subject, relation=relation, obj=obj)

        if suffix == "biology":
            _reject_unknown(params, {"stimulus"})
            stimulus = _bounded_text(_single(params, "stimulus"), field="stimulus", limit=MAX_BIOLOGY_TEXT)
            return 200, adapter.biology_probe(stimulus=stimulus)

        return 404, _error("NOT_FOUND", "archive runtime operation not found")

    except ValueError as exc:
        return 400, _error("INVALID_REQUEST", str(exc))
    except ArchiveRuntimeError as exc:
        code = str(exc)
        if code.startswith("RECOVERED_RUNTIME_MISSING"):
            return 503, _error("INVALID_OR_STALE", "recovered runtime unavailable")
        return 400, _error("INVALID_REQUEST", code)
    except Exception:
        return 503, _error("INVALID_OR_STALE", "archive runtime unavailable")
