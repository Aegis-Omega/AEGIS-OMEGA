"""Python projection — RFC 0001 §6.4.

Records become ``@dataclass`` declarations; variants become ``Literal`` type
aliases (enum domains). All fields explicitly typed; no dynamic attribute
injection. ``from __future__ import annotations`` makes annotations lazy so
records may reference each other regardless of declaration order.
"""

from __future__ import annotations

import re

from ..ir import IR, IRType
from . import (
    GENERATED_HEADER_LINES,
    parse_range_comment,
    range_comment_text,
)

_PRIMITIVE = {
    "string": "str",
    "bool": "bool",
    "s32": "int",
    "s64": "int",
    "u32": "int",
    "u64": "int",
    "f32": "float",
    "f64": "float",
}


def _py_type(t: IRType) -> str:
    if t.kind == "primitive":
        return _PRIMITIVE[t.name]
    if t.kind == "ref":
        return t.name
    if t.kind == "list":
        return f"list[{_py_type(t.inner)}]"
    if t.kind == "option":
        return f"Optional[{_py_type(t.inner)}]"
    raise ValueError(f"unprojectable type kind {t.kind!r}")


def render(ir: IR) -> str:
    lines: list[str] = []
    for h in GENERATED_HEADER_LINES:
        lines.append(f"# {h}")
    lines.append("")
    lines.append("from __future__ import annotations")
    lines.append("")
    lines.append("from dataclasses import dataclass")
    lines.append("from typing import Literal, Optional")
    lines.append("")

    for var in sorted(ir.variants, key=lambda v: v.name):
        literal = ", ".join(f'"{c}"' for c in var.cases)
        lines.append(f"{var.name} = Literal[{literal}]")
    if ir.variants:
        lines.append("")

    for rec in sorted(ir.records, key=lambda r: r.name):
        lines.append("@dataclass")
        lines.append(f"class {rec.name}:")
        for f in rec.fields:
            suffix = ""
            if f.range is not None:
                suffix = f"  # {range_comment_text(f.range.min, f.range.max)}"
            lines.append(f"    {f.name}: {_py_type(f.type)}{suffix}")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------- #
# Readback
# --------------------------------------------------------------------------- #
def _coarse_from_py(py_type: str) -> str:
    py_type = py_type.strip()
    m = re.fullmatch(r"Optional\[(.+)\]", py_type)
    if m:
        return f"option<{_coarse_from_py(m.group(1))}>"
    m = re.fullmatch(r"list\[(.+)\]", py_type)
    if m:
        return f"list<{_coarse_from_py(m.group(1))}>"
    if py_type == "str":
        return "string"
    if py_type == "bool":
        return "bool"
    if py_type in ("int", "float"):
        return "number"
    return py_type  # reference type


def readback(src: str) -> dict:
    records: dict[str, list] = {}
    variants: dict[str, list] = {}

    for m in re.finditer(r"^(\w+) = Literal\[(.+)\]$", src, re.MULTILINE):
        name = m.group(1)
        cases = [c.strip().strip('"') for c in m.group(2).split(",")]
        variants[name] = cases

    for m in re.finditer(r"@dataclass\nclass (\w+):\n(.*?)(?=\n\n|\Z)", src, re.DOTALL):
        name = m.group(1)
        fields = []
        for raw in m.group(2).splitlines():
            line = raw.strip()
            if not line:
                continue
            body, _, comment = line.partition("#")
            fm = re.match(r"(\w+):\s*(.+?)\s*$", body)
            if fm:
                fields.append(
                    {
                        "name": fm.group(1),
                        "type": _coarse_from_py(fm.group(2)),
                        "range": parse_range_comment(comment) if comment else None,
                    }
                )
        records[name] = fields

    return {"records": records, "variants": variants}
