"""Schema evolution & compatibility algebra — RFC 0005 §2, §4.

Evolution between two IR versions is a directed morphism ``L1 -> L2``
decomposed into primitive transformation vectors ``Δ = {δ_1, …, δ_n}``
(field/case/range/type additions, removals and changes). Each vector is
classified for **backward** and **forward** compatibility under the standard
schema-evolution consumer model (unknown fields ignored, absent optional
fields tolerated):

* **backward compatible** — a V1 consumer can ingest data produced by V2
  (``L2 ⊑ L1``, RFC 0005 §2.1).
* **forward compatible** — a V2 consumer can ingest data produced by V1
  (``L1 ⊑ L2``, RFC 0005 §2.2).

The overall verdict aggregates the vectors, and a Proof-Carrying Evolution
Certificate (Γ, §4) records the source/target content hashes, the vectors,
the verdict, and a structural compatibility proof.

Note on the certificate's proof field: RFC 0005 specifies a Lean4 kernel
proof object. That depends on the Stage 4 proof-carrying pipeline (RFC 0004),
which is not implemented. This module emits a *structural* proof — the
enumerated per-vector compatibility derivation — under the engine id
``aegis-structural-v1``. It is independently re-checkable (see
:mod:`aegis_interface.consensus`), which is the property the certificate
needs; it is not a substitute for a kernel-checked proof term.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field as dc_field
from typing import Optional

from .ir import IR, IRField, IRRecord, IRType, canonical_schema_json

CERT_SCHEMA_URL = "https://aegis.dev/schemas/evolution-cert-v5.json"
PROOF_ENGINE = "aegis-structural-v1"

VERDICT_FULL = "FULL"
VERDICT_BACKWARD = "BACKWARD_COMPATIBLE"
VERDICT_FORWARD = "FORWARD_COMPATIBLE"
VERDICT_BREAKING = "BREAKING"


@dataclass(frozen=True)
class EvolutionVector:
    op: str
    path: str  # record / variant name
    name: str  # field / case name ("" for type-level ops)
    backward: bool
    forward: bool
    detail: tuple = ()  # ordered (key, value) pairs for determinism

    def reason(self) -> str:
        if self.backward and self.forward:
            return "fully compatible (safe in both directions)"
        if self.backward:
            return "backward compatible only (old consumers read new data; new consumers cannot read old data)"
        if self.forward:
            return "forward compatible only (new consumers read old data; old consumers cannot read new data)"
        return "breaking (unsafe in both directions)"

    def to_dict(self) -> dict:
        d = {"op": self.op, "path": self.path}
        if self.name:
            d["name"] = self.name
        if self.detail:
            d["detail"] = {k: v for k, v in self.detail}
        d["backward"] = self.backward
        d["forward"] = self.forward
        return d


def _type_desc(t: IRType) -> str:
    if t.kind == "primitive":
        return t.name
    if t.kind == "ref":
        return t.name
    if t.kind in ("list", "option"):
        return f"{t.kind}<{_type_desc(t.inner)}>"
    return t.kind


def _is_optional(f: IRField) -> bool:
    return f.type.kind == "option"


def _range_relation(old: Optional[tuple], new: Optional[tuple]) -> Optional[str]:
    """Classify a range change. Returns one of:
    None (unchanged), 'add', 'remove', 'tighten', 'widen', 'shift'."""
    if old is None and new is None:
        return None
    if old is None:
        return "add"
    if new is None:
        return "remove"
    (a1, b1), (a2, b2) = old, new
    if a1 == a2 and b1 == b2:
        return None
    if a1 <= a2 and b2 <= b1:
        return "tighten"
    if a2 <= a1 and b1 <= b2:
        return "widen"
    return "shift"


def _field_range(f: IRField) -> Optional[tuple]:
    return (f.range.min, f.range.max) if f.range else None


def _diff_record_fields(name: str, old: IRRecord, new: IRRecord) -> list[EvolutionVector]:
    out: list[EvolutionVector] = []
    old_fields = {f.name: f for f in old.fields}
    new_fields = {f.name: f for f in new.fields}

    for fname in sorted(set(new_fields) - set(old_fields)):
        f = new_fields[fname]
        if _is_optional(f):
            out.append(EvolutionVector("AddOptionalField", name, fname, True, True,
                                       (("type", _type_desc(f.type)),)))
        else:
            out.append(EvolutionVector("AddRequiredField", name, fname, True, False,
                                       (("type", _type_desc(f.type)),)))

    for fname in sorted(set(old_fields) - set(new_fields)):
        f = old_fields[fname]
        if _is_optional(f):
            out.append(EvolutionVector("RemoveOptionalField", name, fname, True, True,
                                       (("type", _type_desc(f.type)),)))
        else:
            out.append(EvolutionVector("RemoveRequiredField", name, fname, False, True,
                                       (("type", _type_desc(f.type)),)))

    for fname in sorted(set(old_fields) & set(new_fields)):
        of, nf = old_fields[fname], new_fields[fname]
        ot, nt = _type_desc(of.type), _type_desc(nf.type)
        if ot != nt:
            out.append(EvolutionVector("RetypeField", name, fname, False, False,
                                       (("from", ot), ("to", nt))))
            continue  # a retype subsumes any range change
        rel = _range_relation(_field_range(of), _field_range(nf))
        if rel == "add":
            out.append(EvolutionVector("AddRange", name, fname, True, False,
                                       (("to", list(_field_range(nf))),)))
        elif rel == "remove":
            out.append(EvolutionVector("RemoveRange", name, fname, False, True,
                                       (("from", list(_field_range(of))),)))
        elif rel == "tighten":
            out.append(EvolutionVector("TightenRange", name, fname, True, False,
                                       (("from", list(_field_range(of))), ("to", list(_field_range(nf))))))
        elif rel == "widen":
            out.append(EvolutionVector("WidenRange", name, fname, False, True,
                                       (("from", list(_field_range(of))), ("to", list(_field_range(nf))))))
        elif rel == "shift":
            out.append(EvolutionVector("ShiftRange", name, fname, False, False,
                                       (("from", list(_field_range(of))), ("to", list(_field_range(nf))))))
    return out


def diff(old: IR, new: IR) -> list[EvolutionVector]:
    """Compute the deterministic evolution vector set ``Δ`` from old to new."""
    out: list[EvolutionVector] = []

    old_recs = {r.name: r for r in old.records}
    new_recs = {r.name: r for r in new.records}
    for rname in sorted(set(new_recs) - set(old_recs)):
        out.append(EvolutionVector("AddRecord", rname, "", True, True))
    for rname in sorted(set(old_recs) - set(new_recs)):
        out.append(EvolutionVector("RemoveRecord", rname, "", False, False))
    for rname in sorted(set(old_recs) & set(new_recs)):
        out.extend(_diff_record_fields(rname, old_recs[rname], new_recs[rname]))

    old_vars = {v.name: v for v in old.variants}
    new_vars = {v.name: v for v in new.variants}
    for vname in sorted(set(new_vars) - set(old_vars)):
        out.append(EvolutionVector("AddVariant", vname, "", True, True))
    for vname in sorted(set(old_vars) - set(new_vars)):
        out.append(EvolutionVector("RemoveVariant", vname, "", False, False))
    for vname in sorted(set(old_vars) & set(new_vars)):
        old_cases = set(old_vars[vname].cases)
        new_cases = set(new_vars[vname].cases)
        for c in sorted(new_cases - old_cases):
            out.append(EvolutionVector("AddCase", vname, c, False, True))
        for c in sorted(old_cases - new_cases):
            out.append(EvolutionVector("RemoveCase", vname, c, True, False))

    out.sort(key=lambda v: (v.op, v.path, v.name))
    return out


def classify(vectors: list[EvolutionVector]) -> str:
    if not vectors:
        return VERDICT_FULL
    backward = all(v.backward for v in vectors)
    forward = all(v.forward for v in vectors)
    if backward and forward:
        return VERDICT_FULL
    if backward:
        return VERDICT_BACKWARD
    if forward:
        return VERDICT_FORWARD
    return VERDICT_BREAKING


def recommend_version_bump(vectors: list[EvolutionVector]) -> str:
    """RFC 0001 §10 (as refined): breaking -> major, any other change ->
    minor, no change -> patch."""
    if not vectors:
        return "patch"
    if classify(vectors) == VERDICT_BREAKING:
        return "major"
    return "minor"


def _sha256(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------- #
# Compatibility semiring & evolution composition (categorical core)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CompatClass:
    """A point in the compatibility lattice. ``combine`` is the semiring
    product ``⊗`` over a composed path: a path is safe in a direction only if
    every step is (RFC 0005 §2; the user's C(Δ2∘Δ1)=C(Δ2)⊗C(Δ1))."""

    backward: bool
    forward: bool

    @property
    def verdict(self) -> str:
        if self.backward and self.forward:
            return VERDICT_FULL
        if self.backward:
            return VERDICT_BACKWARD
        if self.forward:
            return VERDICT_FORWARD
        return VERDICT_BREAKING

    def combine(self, other: "CompatClass") -> "CompatClass":
        return CompatClass(self.backward and other.backward, self.forward and other.forward)

    def le(self, other: "CompatClass") -> bool:
        """self ⊑ other — other is at least as compatible as self."""
        return (other.backward or not self.backward) and (other.forward or not self.forward)


def compat_class(vectors: list[EvolutionVector]) -> CompatClass:
    return CompatClass(all(v.backward for v in vectors), all(v.forward for v in vectors))


def compose(*vector_lists: list[EvolutionVector]) -> list[EvolutionVector]:
    """Path composition of evolutions: concatenate the steps' vectors."""
    out: list[EvolutionVector] = []
    for vs in vector_lists:
        out.extend(vs)
    return out


def compose_classes(*classes: CompatClass) -> CompatClass:
    result = CompatClass(True, True)
    for c in classes:
        result = result.combine(c)
    return result


def _vectors_hash(vectors: list[EvolutionVector]) -> str:
    payload = json.dumps([v.to_dict() for v in vectors], sort_keys=True)
    return _sha256(payload)


@dataclass(frozen=True)
class CompositionProof:
    """Witness for the commuting-triangle / confluence law (RFC 0005 §3, the
    user's Δ13 = Δ23 ∘ Δ12). The net (direct) evolution is path-independent —
    it depends only on the endpoints — so any two intermediate paths to the
    same version induce the same net transformation (confluence holds by
    construction). ``conservative`` records that the direct evolution is at
    least as compatible as the composed path (a path may be stricter when
    intermediate steps cancel); ``equivalent`` records exact class equality
    (no cancellation occurred)."""

    path_verdict: str
    direct_verdict: str
    path_hash: str
    direct_hash: str
    conservative: bool
    equivalent: bool


def composition_proof(s1: IR, s2: IR, s3: IR) -> CompositionProof:
    d12, d23, d13 = diff(s1, s2), diff(s2, s3), diff(s1, s3)
    path_class = compose_classes(compat_class(d12), compat_class(d23))
    direct_class = compat_class(d13)
    return CompositionProof(
        path_verdict=path_class.verdict,
        direct_verdict=direct_class.verdict,
        path_hash=_vectors_hash(compose(d12, d23)),
        direct_hash=_vectors_hash(d13),
        conservative=path_class.le(direct_class),
        equivalent=path_class == direct_class,
    )


# --------------------------------------------------------------------------- #
# Proof obligations — RFC 0005 §4 (SMT-verifiable later; structural now)
# --------------------------------------------------------------------------- #
OBLIGATIONS = ("NoFieldLoss", "ConstraintPreserved", "TypeSafetyPreserved", "SerializationInvariant")

_OBLIGATION_VIOLATORS = {
    "NoFieldLoss": {"RemoveRequiredField", "RemoveRecord", "RemoveVariant", "RemoveCase"},
    "ConstraintPreserved": {"TightenRange", "AddRange", "ShiftRange"},
    "TypeSafetyPreserved": {"RetypeField"},
    # SerializationInvariant is handled specially (any both-directions-breaking vector).
}


def obligations(vectors: list[EvolutionVector]) -> dict:
    """Discharge each proof obligation against the evolution vectors."""
    result = {}
    for name in OBLIGATIONS:
        if name == "SerializationInvariant":
            offenders = [v for v in vectors if not v.backward and not v.forward]
        else:
            offenders = [v for v in vectors if v.op in _OBLIGATION_VIOLATORS[name]]
        result[name] = {
            "holds": not offenders,
            "violated_by": sorted(
                f"{v.op}({v.path}{('.' + v.name) if v.name else ''})" for v in offenders
            ),
        }
    return result


def certificate(old: IR, new: IR) -> dict:
    """Build a Proof-Carrying Evolution Certificate (Γ), RFC 0005 §4."""
    vectors = diff(old, new)
    verdict = classify(vectors)
    return {
        "$schema": CERT_SCHEMA_URL,
        "source_hash": _sha256(canonical_schema_json(old)),
        "target_hash": _sha256(canonical_schema_json(new)),
        "evolution_vectors": [v.to_dict() for v in vectors],
        "compatibility": {
            "backward": all(v.backward for v in vectors),
            "forward": all(v.forward for v in vectors),
            "verdict": verdict,
            "recommended_version_bump": recommend_version_bump(vectors),
        },
        "proof_obligations": obligations(vectors),
        "compatibility_proof": {
            "engine": PROOF_ENGINE,
            "checks": [
                {"vector": f"{v.op}({v.path}{('.' + v.name) if v.name else ''})",
                 "backward": v.backward, "forward": v.forward, "reason": v.reason()}
                for v in vectors
            ],
        },
    }


def certificate_json(old: IR, new: IR) -> str:
    return json.dumps(certificate(old, new), sort_keys=True, indent=2) + "\n"
