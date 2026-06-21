"""aegis-interface — RFC 0001 Stage 1.

Deterministic, contract-first interface compilation: a single WIT source of
truth is lowered to a normalised IR and projected into Rust, TypeScript and
Python, with a CI equivalence gate that rejects cross-runtime schema drift.
"""

from __future__ import annotations

from .compiler import CompileResult, compile_source, compile_sources
from .consensus import ConsensusResult, reach_consensus
from .equivalence import EquivalenceReport, validate
from .evolution import certificate, certificate_json, classify, diff, recommend_version_bump
from .ir import IR, canonical_schema, canonical_schema_json, lower
from .parser import ParseError, parse

__all__ = [
    "CompileResult",
    "compile_source",
    "compile_sources",
    "EquivalenceReport",
    "validate",
    "IR",
    "canonical_schema",
    "canonical_schema_json",
    "lower",
    "ParseError",
    "parse",
    # RFC 0005 — schema evolution & consensus
    "diff",
    "classify",
    "recommend_version_bump",
    "certificate",
    "certificate_json",
    "reach_consensus",
    "ConsensusResult",
]

__version__ = "1.0.0"
