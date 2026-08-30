"""Pipeline orchestrator — RFC 0001 §2.1.

Drives the deterministic pipeline: WIT source -> AST -> IR -> projections,
then exposes the artefacts and the equivalence report as a single result.
"""

from __future__ import annotations

from dataclasses import dataclass

from . import parser
from .equivalence import EquivalenceReport, validate
from .ir import IR, canonical_schema_json, lower
from .parser import Document
from .projections import python as py_proj
from .projections import rust as rust_proj
from .projections import typescript as ts_proj


@dataclass
class CompileResult:
    ir: IR
    schema_json: str
    rust: str
    typescript: str
    python: str

    def equivalence(self) -> EquivalenceReport:
        return validate(self.ir, self.rust, self.typescript, self.python)


def _merge(documents: list[Document]) -> Document:
    merged = Document()
    for doc in documents:
        merged.records.extend(doc.records)
        merged.variants.extend(doc.variants)
    return merged


def compile_sources(sources: list[str]) -> CompileResult:
    """Compile one or more WIT source strings into a unified set of artefacts.

    Multiple sources are merged into a single contract graph before lowering so
    cross-file type references resolve (RFC §3: a single authoritative graph).
    """
    doc = _merge([parser.parse(src) for src in sources])
    ir = lower(doc)
    return CompileResult(
        ir=ir,
        schema_json=canonical_schema_json(ir),
        rust=rust_proj.render(ir),
        typescript=ts_proj.render(ir),
        python=py_proj.render(ir),
    )


def compile_source(src: str) -> CompileResult:
    return compile_sources([src])
