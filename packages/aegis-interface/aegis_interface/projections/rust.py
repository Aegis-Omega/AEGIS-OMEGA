"""Rust projection — RFC 0001 §6.2.

Records become serde-derived structs, variants become serde-derived enums.
No runtime reflection; serialisation is structural via ``serde``.
"""

from __future__ import annotations

import re

from ..ir import IR, IRType
from . import (
    GENERATED_HEADER_LINES,
    pascal_to_snake,
    parse_range_comment,
    range_comment_text,
    snake_to_pascal,
)

_PRIMITIVE = {
    "string": "String",
    "bool": "bool",
    "s32": "i32",
    "s64": "i64",
    "u32": "u32",
    "u64": "u64",
    "f32": "f32",
    "f64": "f64",
}

_DERIVE = "#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]"


def _rust_type(t: IRType) -> str:
    if t.kind == "primitive":
        return _PRIMITIVE[t.name]
    if t.kind == "ref":
        return t.name
    if t.kind == "list":
        return f"Vec<{_rust_type(t.inner)}>"
    if t.kind == "option":
        return f"Option<{_rust_type(t.inner)}>"
    raise ValueError(f"unprojectable type kind {t.kind!r}")


def render(ir: IR) -> str:
    lines: list[str] = []
    for h in GENERATED_HEADER_LINES:
        lines.append(f"// {h}")
    lines.append("")
    lines.append("use serde::{Deserialize, Serialize};")
    lines.append("")

    for var in sorted(ir.variants, key=lambda v: v.name):
        lines.append(_DERIVE)
        lines.append('#[serde(rename_all = "snake_case")]')
        lines.append(f"pub enum {var.name} {{")
        for case in var.cases:
            lines.append(f"    {snake_to_pascal(case)},")
        lines.append("}")
        lines.append("")

    for rec in sorted(ir.records, key=lambda r: r.name):
        lines.append(_DERIVE)
        lines.append(f"pub struct {rec.name} {{")
        for f in rec.fields:
            if f.range is not None:
                lines.append(f"    /// {range_comment_text(f.range.min, f.range.max)}")
            lines.append(f"    pub {f.name}: {_rust_type(f.type)},")
        lines.append("}")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------- #
# Readback
# --------------------------------------------------------------------------- #
def _coarse_from_rust(rust_type: str) -> str:
    rust_type = rust_type.strip()
    m = re.fullmatch(r"Vec<(.+)>", rust_type)
    if m:
        return f"list<{_coarse_from_rust(m.group(1))}>"
    m = re.fullmatch(r"Option<(.+)>", rust_type)
    if m:
        return f"option<{_coarse_from_rust(m.group(1))}>"
    if rust_type == "String":
        return "string"
    if rust_type == "bool":
        return "bool"
    if rust_type in ("i32", "i64", "u32", "u64", "f32", "f64"):
        return "number"
    return rust_type  # reference type


def readback(src: str) -> dict:
    records: dict[str, list] = {}
    variants: dict[str, list] = {}

    for m in re.finditer(r"pub enum (\w+) \{(.*?)\}", src, re.DOTALL):
        name = m.group(1)
        cases = [
            pascal_to_snake(c.strip().rstrip(","))
            for c in m.group(2).splitlines()
            if c.strip() and not c.strip().startswith("//")
        ]
        variants[name] = cases

    for m in re.finditer(r"pub struct (\w+) \{(.*?)\n\}", src, re.DOTALL):
        name = m.group(1)
        fields = []
        pending_range = None
        for raw in m.group(2).splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("///"):
                pending_range = parse_range_comment(line)
                continue
            fm = re.match(r"pub (\w+):\s*(.+?),?$", line)
            if fm:
                fields.append(
                    {
                        "name": fm.group(1),
                        "type": _coarse_from_rust(fm.group(2)),
                        "range": pending_range,
                    }
                )
                pending_range = None
        records[name] = fields

    return {"records": records, "variants": variants}
