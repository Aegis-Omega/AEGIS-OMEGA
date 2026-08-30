"""Intermediate Representation — RFC 0001 §5.

The IR is the normalised semantic graph that sits between WIT source and the
language projections. Lowering from the AST performs three jobs the RFC
assigns to this layer:

* **Normalisation** — primitive aliases (``float64`` → ``f64``, ``int`` →
  ``s64``, …) collapse to a single canonical primitive set so every
  projection starts from identical ground truth.
* **Resolution** — every type reference must resolve to a canonical
  primitive or a type defined in the same document; dangling references are
  rejected here, not in a projection.
* **Validation** — ``@range`` constraints are only admissible on numeric
  fields.

The IR carries *no runtime execution semantics* (RFC §5.4) — constraints are
recorded data, never evaluated.

:func:`canonical_schema` produces the deterministic, ordering-stable
structure used by the equivalence gate (§8) and the determinism check (§9.2).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field as dc_field
from typing import Optional

from .parser import Document, Range, TypeRef

# Canonical primitive lattice (RFC §5.3). Leaves of the type system.
PRIMITIVES = {
    "string",
    "bool",
    "s32",
    "s64",
    "u32",
    "u64",
    "f32",
    "f64",
}

# Source-level aliases normalised to canonical primitives. Accepting both the
# WIT spelling and the RFC example spelling ("float64") is exactly the
# normalisation the IR exists to perform.
_ALIASES = {
    "float": "f64",
    "float32": "f32",
    "float64": "f64",
    "f32": "f32",
    "f64": "f64",
    "double": "f64",
    "int": "s64",
    "int32": "s32",
    "int64": "s64",
    "uint32": "u32",
    "uint64": "u64",
    "s32": "s32",
    "s64": "s64",
    "u32": "u32",
    "u64": "u64",
    "str": "string",
    "string": "string",
    "bool": "bool",
    "boolean": "bool",
}

_NUMERIC = {"s32", "s64", "u32", "u64", "f32", "f64"}


class IRError(ValueError):
    """Raised when an AST cannot be lowered to a valid IR."""


@dataclass(frozen=True)
class IRType:
    """A resolved type. Exactly one ``kind`` of {primitive, record, variant,
    list, option}. ``name`` holds the canonical primitive or referenced type
    name; ``inner`` is set for list/option."""

    kind: str
    name: str = ""
    inner: Optional["IRType"] = None


@dataclass(frozen=True)
class IRField:
    name: str
    type: IRType
    range: Optional[Range] = None


@dataclass
class IRRecord:
    name: str
    fields: list[IRField] = dc_field(default_factory=list)


@dataclass
class IRVariant:
    name: str
    cases: list[str] = dc_field(default_factory=list)


@dataclass
class IR:
    records: list[IRRecord] = dc_field(default_factory=list)
    variants: list[IRVariant] = dc_field(default_factory=list)

    def type_kind(self, name: str) -> Optional[str]:
        if any(r.name == name for r in self.records):
            return "record"
        if any(v.name == name for v in self.variants):
            return "variant"
        return None


def lower(doc: Document) -> IR:
    """Lower an AST :class:`Document` to a validated, normalised :class:`IR`."""
    record_names = [r.name for r in doc.records]
    variant_names = [v.name for v in doc.variants]
    all_names = record_names + variant_names

    dupes = {n for n in all_names if all_names.count(n) > 1}
    if dupes:
        raise IRError(f"duplicate type name(s): {', '.join(sorted(dupes))}")
    defined = set(all_names)

    ir = IR()

    for var in doc.variants:
        if not var.cases:
            raise IRError(f"variant {var.name!r} has no cases")
        ir.variants.append(IRVariant(name=var.name, cases=list(var.cases)))

    for rec in doc.records:
        if not rec.fields:
            raise IRError(f"record {rec.name!r} has no fields")
        fields: list[IRField] = []
        for f in rec.fields:
            resolved = _resolve(f.type, defined, rec.name, f.name)
            if f.range is not None:
                base = _leaf_primitive(resolved)
                if base not in _NUMERIC:
                    raise IRError(
                        f"@range on {rec.name}.{f.name} requires a numeric type, "
                        f"got {_describe(resolved)}"
                    )
            fields.append(IRField(name=f.name, type=resolved, range=f.range))
        ir.records.append(IRRecord(name=rec.name, fields=fields))

    return ir


def _resolve(t: TypeRef, defined: set[str], rec: str, field: str) -> IRType:
    if t.wrapper in ("list", "option"):
        inner = _resolve(t.inner, defined, rec, field)
        return IRType(kind=t.wrapper, inner=inner)
    canonical = _ALIASES.get(t.name)
    if canonical is not None:
        return IRType(kind="primitive", name=canonical)
    if t.name in defined:
        # kind refined to record/variant by the caller via IR.type_kind; we
        # store "ref" and let projections resolve against the IR.
        return IRType(kind="ref", name=t.name)
    raise IRError(
        f"unknown type {t.name!r} referenced by {rec}.{field} "
        f"(not a primitive and not defined in this document)"
    )


def _leaf_primitive(t: IRType) -> Optional[str]:
    if t.kind == "primitive":
        return t.name
    if t.kind in ("list", "option"):
        return _leaf_primitive(t.inner)
    return None


def _describe(t: IRType) -> str:
    if t.kind == "primitive":
        return t.name
    if t.kind == "ref":
        return t.name
    if t.kind in ("list", "option"):
        return f"{t.kind}<{_describe(t.inner)}>"
    return t.kind


def _type_descriptor(t: IRType) -> str:
    """Stable, language-agnostic string form of a type for the canonical
    schema. This is the cross-language identity key (RFC §7)."""
    if t.kind == "primitive":
        return t.name
    if t.kind == "ref":
        return t.name
    if t.kind in ("list", "option"):
        return f"{t.kind}<{_type_descriptor(t.inner)}>"
    raise IRError(f"un-descriptable type kind {t.kind!r}")


def canonical_schema(ir: IR) -> dict:
    """Deterministic schema descriptor used by the equivalence gate.

    Field and case order is preserved from source (it is semantically
    meaningful and deterministic for identical input); top-level type entries
    are sorted by name so the descriptor is stable regardless of declaration
    order.
    """
    records = {}
    for rec in sorted(ir.records, key=lambda r: r.name):
        records[rec.name] = [
            {
                "name": f.name,
                "type": _type_descriptor(f.type),
                "range": [f.range.min, f.range.max] if f.range else None,
            }
            for f in rec.fields
        ]
    variants = {
        var.name: list(var.cases)
        for var in sorted(ir.variants, key=lambda v: v.name)
    }
    return {"records": records, "variants": variants}


def canonical_schema_json(ir: IR) -> str:
    """Canonical JSON form of the schema descriptor (sorted keys, stable
    separators) — bitwise stable for identical IR (RFC §9.2)."""
    return json.dumps(canonical_schema(ir), sort_keys=True, indent=2) + "\n"
