"""
AEGIS-Ω Agent Platform — typed dataclass models.

All dataclasses carry a `from_dict` classmethod factory so callers never
have to touch raw dicts.  No external dependencies beyond stdlib.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Revenue
# ---------------------------------------------------------------------------

@dataclass
class RevenueProjection:
    first_year_arr_usd: float
    tier: str
    kan_score: float
    governed_note: str
    assumptions: dict[str, Any]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RevenueProjection":
        return cls(
            first_year_arr_usd=float(d.get("first_year_arr_usd", 0.0)),
            tier=str(d.get("tier", "")),
            kan_score=float(d.get("kan_score", 0.0)),
            governed_note=str(d.get("governed_note", "")),
            assumptions=dict(d.get("assumptions", {})),
        )


# ---------------------------------------------------------------------------
# Collaboration pipeline
# ---------------------------------------------------------------------------

@dataclass
class StageResult:
    stage: int
    role: str
    output: str
    envelope_id: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StageResult":
        return cls(
            stage=int(d.get("stage", 0)),
            role=str(d.get("role", "")),
            output=str(d.get("output", "")),
            envelope_id=str(d.get("envelope_id", "")),
        )


@dataclass
class CollaborateResult:
    mode: str
    cycle_id: str
    objective: str
    departments_collaborated: list[str]
    chain_valid: bool
    projection: Optional[RevenueProjection]
    stages: list[StageResult]
    live: bool

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CollaborateResult":
        raw_proj = d.get("projection")
        projection = RevenueProjection.from_dict(raw_proj) if raw_proj else None

        stages = [StageResult.from_dict(s) for s in d.get("stages", [])]

        return cls(
            mode=str(d.get("mode", "")),
            cycle_id=str(d.get("cycle_id", "")),
            objective=str(d.get("objective", "")),
            departments_collaborated=list(d.get("departments_collaborated", [])),
            chain_valid=bool(d.get("chain_valid", False)),
            projection=projection,
            stages=stages,
            live=bool(d.get("live", False)),
        )


# ---------------------------------------------------------------------------
# Streaming
# ---------------------------------------------------------------------------

@dataclass
class StreamEvent:
    done: bool
    stage: Optional[int] = None
    role: Optional[str] = None
    output: Optional[str] = None
    envelope_id: Optional[str] = None
    projection: Optional[RevenueProjection] = None
    cycle_id: Optional[str] = None
    chain_valid: Optional[bool] = None

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "StreamEvent":
        raw_proj = d.get("projection")
        projection = RevenueProjection.from_dict(raw_proj) if raw_proj else None

        stage_raw = d.get("stage")
        chain_raw = d.get("chain_valid")

        return cls(
            done=bool(d.get("done", False)),
            stage=int(stage_raw) if stage_raw is not None else None,
            role=d.get("role"),
            output=d.get("output"),
            envelope_id=d.get("envelope_id"),
            projection=projection,
            cycle_id=d.get("cycle_id"),
            chain_valid=bool(chain_raw) if chain_raw is not None else None,
        )


# ---------------------------------------------------------------------------
# Agent execution
# ---------------------------------------------------------------------------

@dataclass
class AgentResult:
    task_id: str
    role: str
    output: str
    ralph_cycles: int
    duration_ms: float
    is_valid: bool
    governance: dict[str, Any]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AgentResult":
        return cls(
            task_id=str(d.get("task_id", "")),
            role=str(d.get("role", "")),
            output=str(d.get("output", "")),
            ralph_cycles=int(d.get("ralph_cycles", 0)),
            duration_ms=float(d.get("duration_ms", 0.0)),
            is_valid=bool(d.get("is_valid", False)),
            governance=dict(d.get("governance", {})),
        )


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------

@dataclass
class CatalogResult:
    platform: str
    agent_count: int
    mythos_count: int
    agents: list[dict[str, Any]]
    pricing_tiers: list[dict[str, Any]]

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CatalogResult":
        return cls(
            platform=str(d.get("platform", "")),
            agent_count=int(d.get("agent_count", 0)),
            mythos_count=int(d.get("mythos_count", 0)),
            agents=list(d.get("agents", [])),
            pricing_tiers=list(d.get("pricing_tiers", [])),
        )


# ---------------------------------------------------------------------------
# Audit / certification
# ---------------------------------------------------------------------------

@dataclass
class CertifyResult:
    is_valid: bool
    entry_count: int
    terminal_hash: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "CertifyResult":
        return cls(
            is_valid=bool(d.get("is_valid", False)),
            entry_count=int(d.get("entry_count", 0)),
            terminal_hash=str(d.get("terminal_hash", "")),
        )
