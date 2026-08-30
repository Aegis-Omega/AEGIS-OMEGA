"""Equivalence validation — RFC 0001 §8.

Given the IR and the three rendered projections, re-extract each projection's
coarse schema and assert it matches the IR's expected coarse schema. This
enforces §8.1 directly:

* all required fields exist in all targets,
* all enum (variant) constraints are preserved,
* no additional fields are introduced.

A mismatch produces a deterministic diff report and a non-zero result (§8.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from .ir import IR
from .projections import expected_coarse_schema
from .projections import python as py_proj
from .projections import rust as rust_proj
from .projections import typescript as ts_proj


@dataclass
class EquivalenceReport:
    findings: list[str] = dc_field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.findings

    def text(self) -> str:
        if self.ok:
            return "EQUIVALENCE OK — all projections match the IR contract graph."
        lines = ["EQUIVALENCE FAILED — projection drift detected:"]
        lines.extend(f"  - {f}" for f in self.findings)
        return "\n".join(lines)


def _diff_records(expected: dict, actual: dict, lang: str) -> list[str]:
    out: list[str] = []
    exp_names = set(expected)
    act_names = set(actual)
    for name in sorted(exp_names - act_names):
        out.append(f"[{lang}] missing record {name!r}")
    for name in sorted(act_names - exp_names):
        out.append(f"[{lang}] unexpected record {name!r}")
    for name in sorted(exp_names & act_names):
        exp_fields = {f["name"]: f for f in expected[name]}
        act_fields = {f["name"]: f for f in actual[name]}
        for fname in sorted(set(exp_fields) - set(act_fields)):
            out.append(f"[{lang}] {name}: missing field {fname!r}")
        for fname in sorted(set(act_fields) - set(exp_fields)):
            out.append(f"[{lang}] {name}: unexpected field {fname!r}")
        for fname in sorted(set(exp_fields) & set(act_fields)):
            e = exp_fields[fname]
            a = act_fields[fname]
            if e["type"] != a["type"]:
                out.append(
                    f"[{lang}] {name}.{fname}: type {a['type']!r} != expected {e['type']!r}"
                )
            if e["range"] != a["range"]:
                out.append(
                    f"[{lang}] {name}.{fname}: range {a['range']!r} != expected {e['range']!r}"
                )
        # Field ordering is part of identity (RFC §7).
        exp_order = [f["name"] for f in expected[name]]
        act_order = [f["name"] for f in actual[name]]
        if exp_order != act_order and set(exp_order) == set(act_order):
            out.append(f"[{lang}] {name}: field order {act_order} != expected {exp_order}")
    return out


def _diff_variants(expected: dict, actual: dict, lang: str) -> list[str]:
    out: list[str] = []
    exp_names = set(expected)
    act_names = set(actual)
    for name in sorted(exp_names - act_names):
        out.append(f"[{lang}] missing variant {name!r}")
    for name in sorted(act_names - exp_names):
        out.append(f"[{lang}] unexpected variant {name!r}")
    for name in sorted(exp_names & act_names):
        if expected[name] != actual[name]:
            out.append(
                f"[{lang}] variant {name}: cases {actual[name]} != expected {expected[name]}"
            )
    return out


def validate(ir: IR, rust_src: str, ts_src: str, py_src: str) -> EquivalenceReport:
    expected = expected_coarse_schema(ir)
    report = EquivalenceReport()
    for lang, readback in (
        ("rust", rust_proj.readback(rust_src)),
        ("typescript", ts_proj.readback(ts_src)),
        ("python", py_proj.readback(py_src)),
    ):
        report.findings.extend(
            _diff_records(expected["records"], readback["records"], lang)
        )
        report.findings.extend(
            _diff_variants(expected["variants"], readback["variants"], lang)
        )
    return report
