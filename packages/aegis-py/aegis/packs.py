"""Synthetic, importable offline workflow-pack examples."""
from __future__ import annotations

import copy
import hashlib

SCHEMA_V1 = "aegis.workflow-pack/1"
READ_ONLY = "read_only"


def _pack(pack_id: str, domain: str, objective: str, steps: list[dict[str, str]],
          acceptance: list[dict[str, str]], artifact_id: str, media_type: str,
          content: str) -> dict:
    return {
        "schema": SCHEMA_V1,
        "pack_id": pack_id,
        "domain": domain,
        "permissions": READ_ONLY,
        "objective": objective,
        "steps": steps,
        "acceptance": acceptance,
        "artifacts": [{
            "id": artifact_id,
            "media_type": media_type,
            "content": content,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        }],
    }


PACKS = {
    "code": _pack(
        "sample.code",
        "code",
        "Review a small pure function without executing it.",
        [{"id": "inspect", "description": "Read the embedded function source."}],
        [{"id": "c1", "criterion": "The source contains a pure add function."}],
        "source",
        "text/x-python",
        "def add(left: int, right: int) -> int:\n    return left + right\n",
    ),
    "data": _pack(
        "sample.data",
        "data",
        "Inspect a tiny inline table and identify its declared fields.",
        [{"id": "inspect", "description": "Read the embedded CSV sample."}],
        [{"id": "d1", "criterion": "The header contains id and value."}],
        "table",
        "text/csv",
        "id,value\nsample-1,12\nsample-2,18\n",
    ),
    "science": _pack(
        "sample.science",
        "science",
        "Inspect synthetic observations without making a scientific claim.",
        [{"id": "inspect", "description": "Read the embedded observation note."}],
        [{"id": "s1", "criterion": "The note labels its values synthetic."}],
        "observations",
        "text/plain",
        "Synthetic observations only; no scientific conclusion is asserted.\n",
    ),
}


def get_pack(name: str) -> dict:
    """Return an independent copy of a bundled sample pack."""
    try:
        return copy.deepcopy(PACKS[name])
    except KeyError as exc:
        raise ValueError(f"unknown sample pack {name!r}; choose code, data, or science") from exc
