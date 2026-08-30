"""TypeScript projection — RFC 0001 §6.3.

Records become ``interface`` declarations; variants become string-literal
union types (unions are permitted only for enumerations). No ambient mutation,
no runtime inference.
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
    "string": "string",
    "bool": "boolean",
    "s32": "number",
    "s64": "number",
    "u32": "number",
    "u64": "number",
    "f32": "number",
    "f64": "number",
}


def _ts_type(t: IRType) -> str:
    if t.kind == "primitive":
        return _PRIMITIVE[t.name]
    if t.kind == "ref":
        return t.name
    if t.kind == "list":
        inner = _ts_type(t.inner)
        if t.inner.kind == "option":  # parenthesize union element types: (T | null)[]
            inner = f"({inner})"
        return f"{inner}[]"
    if t.kind == "option":
        return f"{_ts_type(t.inner)} | null"
    raise ValueError(f"unprojectable type kind {t.kind!r}")


def render(ir: IR) -> str:
    lines: list[str] = []
    for h in GENERATED_HEADER_LINES:
        lines.append(f"// {h}")
    lines.append("")

    for var in sorted(ir.variants, key=lambda v: v.name):
        union = " | ".join(f'"{c}"' for c in var.cases)
        lines.append(f"export type {var.name} = {union};")
        lines.append("")

    for rec in sorted(ir.records, key=lambda r: r.name):
        lines.append(f"export interface {rec.name} {{")
        for f in rec.fields:
            if f.range is not None:
                lines.append(f"  /** {range_comment_text(f.range.min, f.range.max)} */")
            opt = "?" if f.type.kind == "option" else ""
            lines.append(f"  {f.name}{opt}: {_ts_type(f.type)};")
        lines.append("}")
        lines.append("")

    return "\n".join(lines).rstrip("\n") + "\n"


# --------------------------------------------------------------------------- #
# Readback
# --------------------------------------------------------------------------- #
def _coarse_from_ts(ts_type: str) -> str:
    ts_type = ts_type.strip()
    m = re.fullmatch(r"\((.+)\)", ts_type)  # strip wrapping parens: (T | null)
    if m:
        return _coarse_from_ts(m.group(1))
    m = re.fullmatch(r"(.+) \| null", ts_type)
    if m:
        return f"option<{_coarse_from_ts(m.group(1))}>"
    m = re.fullmatch(r"(.+)\[\]", ts_type)
    if m:
        return f"list<{_coarse_from_ts(m.group(1))}>"
    if ts_type == "string":
        return "string"
    if ts_type == "boolean":
        return "bool"
    if ts_type == "number":
        return "number"
    return ts_type  # reference type


def readback(src: str) -> dict:
    records: dict[str, list] = {}
    variants: dict[str, list] = {}

    for m in re.finditer(r"export type (\w+) = (.+);", src):
        name = m.group(1)
        cases = [c.strip().strip('"') for c in m.group(2).split("|")]
        variants[name] = cases

    for m in re.finditer(r"export interface (\w+) \{(.*?)\n\}", src, re.DOTALL):
        name = m.group(1)
        fields = []
        pending_range = None
        for raw in m.group(2).splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith("/**"):
                pending_range = parse_range_comment(line)
                continue
            fm = re.match(r"(\w+)\??:\s*(.+?);$", line)
            if fm:
                fields.append(
                    {
                        "name": fm.group(1),
                        "type": _coarse_from_ts(fm.group(2)),
                        "range": pending_range,
                    }
                )
                pending_range = None
        records[name] = fields

    return {"records": records, "variants": variants}
