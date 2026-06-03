#!/usr/bin/env python3
"""
AEGIS-Ω Harness SDK — Docs Harness

Ingests repository documentation and produces Phase 1 static skill trees
per SKILL_HARNESS_SPECIFICATION.md §24 (Phase 1: static, human-authored baseline).

Evidence refs in this module point to .md source files, not runtime events —
Phase 2 will wire live telemetry as the primary evidence stream.

Epistemic Tier: T2 (engineering hypothesis — Phase 1 implementation)
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


DOCS_VERSION = "1.0.0"
PHASE = 1
GENESIS_SEAL = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

# Tier weights for initial confidence seeding (T0 = strongest evidence)
TIER_CONFIDENCE: dict[str, float] = {
    "T0": 0.95,
    "T1": 0.80,
    "T2": 0.65,
    "T3": 0.40,
}

EXCLUDED_DIRS = {"node_modules", "target", ".git", "__pycache__", ".venv"}


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class SkillObject:
    """Probabilistic competency object per SKILL_HARNESS_SPECIFICATION §4."""
    skill_id: str
    label: str
    domain: str
    tier: str                          # T0-T3
    confidence: float                  # 0.0–1.0
    validated_runs: int                # 0 in Phase 1
    failure_rate: float
    recency_score: float
    domain_affinity: list[str]
    dependencies: list[str]
    evidence_refs: list[str]           # source .md file paths
    last_validated: str                # ISO 8601
    description: str = ""


@dataclass
class SkillTree:
    """Phase 1 static skill tree output."""
    version: str
    phase: int
    generated_at: str
    genesis_seal: str
    doc_count: int
    skills: list[SkillObject] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["skills"] = [asdict(s) for s in self.skills]
        return d

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)


@dataclass
class DocRecord:
    """Parsed documentation file."""
    path: str
    rel_path: str
    sha256: str
    headings: list[str]
    tiers: list[str]
    gates: list[str]
    domains: list[str]
    line_count: int


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class DocParser:
    """Minimal regex-based extractor for AEGIS .md files."""

    _HEADING_RE = re.compile(r"^#{1,4}\s+(.+)$", re.MULTILINE)
    _TIER_RE    = re.compile(r"\b(T0|T1|T2|T3|T4|T5)\b")
    _GATE_RE    = re.compile(r"\bGate\s+(\d{3})\b", re.IGNORECASE)
    _DOMAIN_RE  = re.compile(
        r"\b(Rust|TypeScript|Python|Constitutional|Governance|Telemetry|"
        r"Consensus|Martingale|Deployment|Replay|Audit|Hash|Cryptograph\w+|"
        r"Agent|Skill|Harness|Orchestrat\w+|Khatt|GCCE|RALPH|BFT|ECCF|"
        r"Sovereign|Commercial|Supabase|Vercel|Gumroad)\b",
        re.IGNORECASE,
    )

    def parse(self, path: Path, repo_root: Path) -> DocRecord:
        text = path.read_text(encoding="utf-8", errors="replace")
        sha = hashlib.sha256(text.encode()).hexdigest()
        lines = text.splitlines()

        headings = [m.group(1).strip() for m in self._HEADING_RE.finditer(text)]
        tiers    = sorted(set(self._TIER_RE.findall(text)))
        gates    = sorted(set(self._GATE_RE.findall(text)))
        domains  = sorted({d.lower() for d in self._DOMAIN_RE.findall(text)})

        return DocRecord(
            path=str(path),
            rel_path=str(path.relative_to(repo_root)),
            sha256=sha,
            headings=headings,
            tiers=tiers,
            gates=gates,
            domains=domains,
            line_count=len(lines),
        )


# ---------------------------------------------------------------------------
# Hand-authored Phase 1 skill definitions
# ---------------------------------------------------------------------------
# Each entry: (skill_id, label, domain, tier, confidence, domain_affinity,
#              dependencies, evidence_docs, description)

_SKILL_DEFINITIONS: list[tuple] = [
    # ── Constitutional Governance ────────────────────────────────────────
    (
        "constitutional_law_enforcement",
        "Constitutional Law Enforcement",
        "constitutional_governance",
        "T0", 0.95,
        ["governance", "constitutional", "replay"],
        [],
        ["sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md",
         "CONSTITUTIONAL_DECLARATION.md"],
        "Enforce Root Constitutional Law: AdaptivePower(T) ≤ ReplayVerifiability(T). "
        "Covers constitutional boundary checks, T0_ABORT conditions, and replay sovereignty.",
    ),
    (
        "martingale_gating",
        "Martingale Gate Enforcement",
        "constitutional_governance",
        "T1", 0.85,
        ["governance", "martingale", "typescript"],
        ["constitutional_law_enforcement"],
        ["sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md",
         "sovereign-omega-v2/docs/CONSTITUTIONAL_GOVERNANCE_SURFACE.md"],
        "certifyMartingale() + assertMartingaleAnchored() — suspends mutation authority "
        "when drift_bounded, is_anchored, or entropy_bounded constraints fail.",
    ),
    (
        "epistemic_tier_classification",
        "Epistemic Tier Classification",
        "constitutional_governance",
        "T0", 0.95,
        ["governance", "audit", "constitutional"],
        [],
        ["CLAUDE.md", ".sovereign_context/SYSTEM_DIRECTIVES.md"],
        "Tag every module T0-T5. T0=mechanically proven; T4/T5 confined to docs/. "
        "A file's tier is determined by mechanism, not framing.",
    ),
    (
        "ontology_admission",
        "Ontology Admission Enforcement",
        "constitutional_governance",
        "T1", 0.80,
        ["governance", "typescript", "constitutional"],
        ["epistemic_tier_classification"],
        ["sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md",
         "sovereign-omega-v2/docs/ONTOLOGY.md" if False else "docs/ONTOLOGY.md"],
        "admitAbstraction() blocks T4/T5 constructs. Every abstraction must reduce "
        "to six canonical primitives: Event, Transition, Ownership, Entropy, Transport, Verification.",
    ),
    # ── Cryptographic Infrastructure ─────────────────────────────────────
    (
        "jcs_canonicalization",
        "JCS RFC 8785 Canonicalization",
        "cryptographic_infrastructure",
        "T0", 0.95,
        ["cryptograph", "hash", "typescript"],
        [],
        ["sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md", "CLAUDE.md"],
        "canonicalizeJCS() in src/core/canonicalize.ts — RFC 8785 → SHA-256. "
        "Only permitted hash path. Never JSON.stringify for integrity.",
    ),
    (
        "hash_chain_construction",
        "Hash Chain Construction",
        "cryptographic_infrastructure",
        "T0", 0.95,
        ["cryptograph", "hash", "rust", "replay"],
        ["jcs_canonicalization"],
        ["sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md",
         "docs/GATE_201_REFACTORING.md"],
        "Every Rust gate module implements verify_chain() → (bool, Option<usize>). "
        "All hash inputs use to_be_bytes(). f64 hashed as value.to_bits().to_be_bytes(). "
        "Chain starts from *_GENESIS_HASH = [0u8; 32].",
    ),
    (
        "genesis_seal_verification",
        "Genesis Seal Verification",
        "cryptographic_infrastructure",
        "T0", 0.95,
        ["cryptograph", "constitutional", "rust"],
        ["hash_chain_construction"],
        ["docs/GATE_201_REFACTORING.md", "docs/GATE_202_HARNESS_SDK.md"],
        "Verify T0 genesis seals in Planner and Evaluator. "
        "SHA-256 of empty payload = e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855.",
    ),
    # ── Rust Systems ─────────────────────────────────────────────────────
    (
        "rust_gate_module_development",
        "Rust Gate Module Development",
        "rust_systems",
        "T0", 0.90,
        ["rust", "hash", "audit"],
        ["hash_chain_construction", "deterministic_data_structures"],
        ["CLAUDE.md", "sovereign-omega-v2/docs/CL_PSI_SPECIFICATION.md"],
        "Implement aegis-cl-psi gate modules: public struct with verify_chain(), "
        "BTreeMap/BTreeSet only, saturating arithmetic, to_be_bytes() big-endian.",
    ),
    (
        "deterministic_data_structures",
        "Deterministic Data Structures (Rust)",
        "rust_systems",
        "T0", 0.95,
        ["rust", "replay", "constitutional"],
        [],
        ["CLAUDE.md", ".sovereign_context/SYSTEM_DIRECTIVES.md"],
        "BTreeMap / BTreeSet only — never HashMap/HashSet in Rust. "
        "Iteration order must be deterministic for cross-platform replay.",
    ),
    (
        "safe_arithmetic",
        "Safe Arithmetic (Rust)",
        "rust_systems",
        "T0", 0.95,
        ["rust", "constitutional"],
        [],
        ["CLAUDE.md"],
        "saturating_add / saturating_mul — no silent overflow. "
        "No f64 in consensus/threshold logic — use integer arithmetic.",
    ),
    (
        "cargo_build_and_test",
        "Cargo Build & Test Lifecycle",
        "rust_systems",
        "T1", 0.85,
        ["rust", "deployment"],
        ["rust_gate_module_development"],
        ["CLAUDE.md"],
        "cargo test (plain, never --all-features — hip/rocblas require ROCm hardware). "
        "cargo build --release for native. 5114 tests in aegis-cl-psi; 96 in aegis-runtime.",
    ),
    # ── TypeScript Governance Runtime ────────────────────────────────────
    (
        "typescript_event_ledger",
        "TypeScript Event Ledger",
        "typescript_governance",
        "T0", 0.90,
        ["typescript", "replay", "constitutional"],
        ["jcs_canonicalization"],
        ["sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md", "CLAUDE.md"],
        "Append-only canonical event log. No Date.now() except src/event/uuid.ts. "
        "No array.length for sequence numbers — use IndexedDBSequenceAllocator. "
        "deepFreeze every state object after construction.",
    ),
    (
        "bft_swarm_consensus",
        "BFT Swarm Consensus",
        "typescript_governance",
        "T2", 0.70,
        ["consensus", "bft", "typescript", "governance"],
        ["typescript_event_ledger", "constitutional_law_enforcement"],
        ["sovereign-omega-v2/docs/AGENT_COORDINATION_MODEL.md", "CLAUDE.md"],
        "tallyVotes() → SwarmConvergenceRecord at 1/φ ≈ 0.618 quorum. "
        "Bernstein bounds (not Hoeffding). src/consensus/swarm.ts.",
    ),
    (
        "ralph_loop_execution",
        "RALPH Loop Execution",
        "typescript_governance",
        "T1", 0.80,
        ["agent", "typescript", "orchestrat"],
        ["typescript_event_ledger"],
        ["sovereign-omega-v2/handoff/RALPH_LOOP_OMEGA2_INTEGRATION_AUDIT.md",
         "sovereign-omega-v2/handoff/RALPH_LOOP_OMEGA_EXECUTION_SYNTHESIS.md",
         "CLAUDE.md"],
        "Fibonacci-paced R→A→L→P→H loops. src/agents/executor/loop.ts. "
        "Corpus knowledge enters through 5-phase loop only — no raw narrative propagation.",
    ),
    (
        "adaptive_lineage_tracking",
        "Adaptive Lineage Tracking",
        "typescript_governance",
        "T1", 0.75,
        ["typescript", "hash", "governance"],
        ["hash_chain_construction", "typescript_event_ledger"],
        ["CLAUDE.md"],
        "Hash-chained capability evolution events. src/frame/adaptive-lineage.ts.",
    ),
    (
        "gate8_deployment_gate",
        "Gate 8 — Pre-Commit Deployment Gate",
        "typescript_governance",
        "T0", 0.95,
        ["deployment", "typescript", "governance"],
        ["typescript_event_ledger"],
        ["CLAUDE.md"],
        "npm run test && npm run typecheck && npm run build must pass in "
        "sovereign-omega-v2 before any commit. Mandatory — no exceptions.",
    ),
    # ── Python Bridge ────────────────────────────────────────────────────
    (
        "python_bridge_development",
        "Python Bridge Development",
        "python_bridge",
        "T1", 0.80,
        ["python", "telemetry", "governance"],
        ["constitutional_law_enforcement"],
        ["CLAUDE.md", "sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md"],
        "HTTP server on port 7890 exposing /telemetry /event /gate_signal /health /claude /node. "
        "No time.time() in determinism-critical paths. PGCS must pass before TGCS is valid.",
    ),
    (
        "frozen_file_protection",
        "Frozen Constitutional File Protection",
        "python_bridge",
        "T0", 0.95,
        ["constitutional", "cryptograph", "audit"],
        ["genesis_seal_verification"],
        ["CLAUDE.md"],
        "gate.py / dna.py / router.py are FROZEN. Verify SHA-256 before every session via "
        "node scripts/verify-hashes.mjs. Never modify without /guardian APPROVED verdict.",
    ),
    (
        "telemetry_streaming",
        "Telemetry Streaming (Python)",
        "python_bridge",
        "T2", 0.70,
        ["telemetry", "python", "governance"],
        ["python_bridge_development"],
        ["CLAUDE.md", "docs/TELEMETRY_SPEC.md"],
        "5-second poll from cockpit + sovereign-omega-v2 dashboard to /telemetry. "
        "corruption_count must equal 0. bit-shifted integer arithmetic throughout.",
    ),
    # ── Planner-Generator-Evaluator (Harness SDK) ─────────────────────────
    (
        "khatt_loop_execution",
        "Khatt Loop Execution",
        "harness_sdk",
        "T2", 0.70,
        ["khatt", "gcce", "harness", "orchestrat"],
        ["planner_module", "generator_module", "evaluator_module"],
        ["docs/GATE_202_HARNESS_SDK.md", "docs/GCCE_ARCHITECTURE.md"],
        "5-phase loop: Nuqta (inscribe truth) → Alif (hard constraints) → "
        "Rasm (continuous flow) → Tashkeel (uncertainty metadata) → Tanasub (fractal scaling).",
    ),
    (
        "planner_module",
        "Planner Module (Node α)",
        "harness_sdk",
        "T2", 0.70,
        ["harness", "orchestrat", "python"],
        ["hash_chain_construction", "genesis_seal_verification"],
        ["docs/GATE_202_HARNESS_SDK.md"],
        "Receives directives, decomposes into CausalChain with Nuqta/Alif constraints. "
        "harness/sdk/planner/__init__.py — Node α (Architect) in Fractal Sovereign Mesh.",
    ),
    (
        "generator_module",
        "Generator Module (Node β)",
        "harness_sdk",
        "T2", 0.65,
        ["harness", "python"],
        ["planner_module"],
        ["docs/GATE_202_HARNESS_SDK.md"],
        "Executes sprint work maintaining Rasm continuity. "
        "harness/sdk/generator/__init__.py — Node β (Artisan) in Fractal Sovereign Mesh.",
    ),
    (
        "evaluator_module",
        "Evaluator Module (Node γ)",
        "harness_sdk",
        "T2", 0.70,
        ["harness", "audit", "python"],
        ["generator_module"],
        ["docs/GATE_202_HARNESS_SDK.md"],
        "QA via Playwright, Tashkeel confidence validation, Tanasub fractal scaling check. "
        "Verdicts: PASS / PASS_WITH_WARNINGS / FAIL / REJECT_REROLL.",
    ),
    # ── Skill Harness Architecture ────────────────────────────────────────
    (
        "skill_tree_construction",
        "Skill Tree Construction (Phase 1)",
        "skill_harness",
        "T2", 0.65,
        ["skill", "harness"],
        ["epistemic_tier_classification"],
        ["sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md"],
        "Phase 1: static, human-authored, inspectable skill trees. "
        "Each skill is a probabilistic competency object with confidence, "
        "validated_runs, failure_rate, recency_score, domain_affinity, dependencies.",
    ),
    (
        "probabilistic_competency_modeling",
        "Probabilistic Competency Modeling",
        "skill_harness",
        "T2", 0.65,
        ["skill", "harness", "governance"],
        ["skill_tree_construction"],
        ["sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md"],
        "Skills are NOT booleans. Required attributes: skill_id, confidence, "
        "validated_runs, failure_rate, recency_score, domain_affinity, dependencies, evidence_refs.",
    ),
    (
        "skill_event_sourcing",
        "Skill Event Sourcing",
        "skill_harness",
        "T2", 0.60,
        ["skill", "harness", "replay"],
        ["probabilistic_competency_modeling", "typescript_event_ledger"],
        ["sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md"],
        "Store evolution history, not snapshots. Events: SKILL_VALIDATED, SKILL_DEGRADED, "
        "SKILL_DECAYED, SKILL_SPECIALIZED, SKILL_REJECTED, SKILL_REINFORCED, "
        "SKILL_TRANSFERRED, SKILL_MERGED, SKILL_SPLIT.",
    ),
    (
        "orchestration_routing",
        "Orchestration Routing via Skills",
        "skill_harness",
        "T2", 0.60,
        ["skill", "orchestrat", "agent"],
        ["probabilistic_competency_modeling", "bft_swarm_consensus"],
        ["sovereign-omega-v2/docs/SKILL_HARNESS_SPECIFICATION.md"],
        "Route tasks to best-qualified agent using: competency confidence, "
        "specialization domain, failure history, domain affinity, recency score.",
    ),
    # ── Agent Operations ─────────────────────────────────────────────────
    (
        "agent_role_governance",
        "Agent Role Governance",
        "agent_operations",
        "T1", 0.80,
        ["agent", "governance"],
        [],
        [".agent/rules.md"],
        "ORCHESTRATOR / ARCHITECT / BUILDER / RESEARCHER / QA / DEBUG / REVIEWER / PRE-SHIP roles. "
        "Each role has constrained tool access. Builder: no web_search. Researcher: authorized web_search.",
    ),
    (
        "agent_handoff_protocol",
        "Agent Handoff Protocol",
        "agent_operations",
        "T1", 0.80,
        ["agent", "governance"],
        ["agent_role_governance"],
        [".agent/rules.md"],
        "Mandatory format: [FROM]/[TO]/[TYPE: HANDOFF|REQUEST|BLOCKER|UPDATE]/CONTEXT/MESSAGE/EXPECTED RESPONSE.",
    ),
    (
        "cognitive_event_logging",
        "Cognitive Event Logging",
        "agent_operations",
        "T1", 0.80,
        ["agent", "audit"],
        ["agent_handoff_protocol"],
        [".agent/rules.md"],
        "Log via tools/log-action.js: SKILL_CHECK, PLAN_CREATED, PLAN_MUTATED, "
        "CONTEXT_ROT, FATAL_BLOCKER, LANE_VIOLATION, MISSING_CAPABILITY, MISSION_REPORT.",
    ),
    (
        "three_strike_failsafe",
        "3-Strike Failsafe Protocol",
        "agent_operations",
        "T1", 0.85,
        ["agent", "constitutional"],
        ["agent_role_governance"],
        [".agent/rules.md"],
        "If VERIFY fails 3× on same approach: STOP, output FATAL_BLOCKER, log to log-action.js, "
        "do NOT retry same approach.",
    ),
    # ── Commercial Products ───────────────────────────────────────────────
    (
        "shared_component_library",
        "Shared Component Library (@shared)",
        "commercial_products",
        "T1", 0.80,
        ["typescript", "commercial"],
        [],
        ["CLAUDE.md", "packages/shared"],
        "@shared alias → packages/shared. DashScope caller, useAsyncForm, ErrorAlert, "
        "LoadingSpinner, ScoreBar, ToolkitFooter. All 3 products import from here.",
    ),
    (
        "dashscope_qwen_integration",
        "DashScope / Qwen API Integration",
        "commercial_products",
        "T2", 0.70,
        ["commercial", "typescript"],
        ["shared_component_library"],
        ["CLAUDE.md"],
        "VITE_DASHSCOPE_API_KEY + VITE_DASHSCOPE_MODEL env vars. "
        "@shared/lib/dashscope generic caller. Default model: qwen-plus.",
    ),
    (
        "vercel_deployment",
        "Vercel Deployment Pipeline",
        "commercial_products",
        "T1", 0.80,
        ["deployment", "commercial"],
        ["gate8_deployment_gate"],
        ["DEPLOY.md", "CLAUDE.md"],
        "One Vercel project per product (Root Directory set per product). "
        "Gate 8 must pass before any deployment. vercel --prod from product directory.",
    ),
    (
        "gumroad_product_pricing",
        "Gumroad Product Pricing",
        "commercial_products",
        "T1", 0.75,
        ["commercial"],
        ["vercel_deployment"],
        ["docs/GUMROAD_LISTINGS.md", "CLAUDE.md"],
        "$19/product, $29 any 2, $39 all 3 (Full Creator AI Toolkit). "
        "platform-picker + hook-generator + content-calendar.",
    ),
    # ── Security & Audit ─────────────────────────────────────────────────
    (
        "audit_trail_management",
        "Audit Trail Management",
        "security_audit",
        "T1", 0.80,
        ["audit", "replay", "constitutional"],
        ["hash_chain_construction"],
        ["docs/AUDIT_FINDINGS.md", "docs/TRACEABILITY.md",
         "sovereign-omega-v2/docs/TRACEABILITY.md"],
        "Immutable audit logs, full evolution traceability, is_replay_reconstructable: true "
        "on every record. directive_hash on all outputs.",
    ),
    (
        "eccf_security_alignment",
        "ECCF Security Alignment",
        "security_audit",
        "T2", 0.65,
        ["eccf", "audit", "governance"],
        ["constitutional_law_enforcement"],
        ["docs/GATE_204_ECCF_SECURITY_ALIGNMENT.md"],
        "Gate 204 security model. EU AI Act compliance audit chain. "
        "385-gate Rust inference crate (aegis-cl-psi) tagged T2.",
    ),
    (
        "replay_sovereignty",
        "Replay Sovereignty",
        "security_audit",
        "T0", 0.95,
        ["replay", "constitutional", "cryptograph"],
        ["hash_chain_construction", "constitutional_law_enforcement"],
        ["sovereign-omega-v2/docs/SOVEREIGN_RUNTIME_HANDOFF_v1.0.md"],
        "replay(genesis, events) → identical topology hash across Linux/macOS/Docker/WASM/ARM/x86. "
        "Replay determinism supersedes runtime convenience, orchestration flexibility, adaptive velocity.",
    ),
    # ── Gate Progression ─────────────────────────────────────────────────
    (
        "gate_progression_system",
        "Gate Progression System",
        "gate_progression",
        "T1", 0.80,
        ["governance", "audit"],
        ["constitutional_law_enforcement"],
        ["docs/GATE_201_REFACTORING.md", "docs/GATE_202_HARNESS_SDK.md",
         "docs/GATE_203_SOVEREIGN_AUTOMATON.md", "docs/GATE_204_ECCF_SECURITY_ALIGNMENT.md",
         "docs/GATE_205_MESH_DEPLOYMENT.md"],
        "Gate 201 (refactoring) → 202 (harness SDK) → 203 (sovereign automaton) → "
        "204 (ECCF security) → 205 (mesh deployment) → 210 (evaluator verdict correction). "
        "Each gate: complete → status COMPLETE + epistemic tier declaration.",
    ),
    (
        "sovereign_mesh_deployment",
        "Sovereign Mesh Deployment",
        "gate_progression",
        "T2", 0.65,
        ["deployment", "governance", "orchestrat"],
        ["vercel_deployment", "gate_progression_system"],
        ["docs/GATE_205_MESH_DEPLOYMENT.md",
         "sovereign-omega-v2/docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md"],
        "Fractal Sovereign Mesh: Node α (Architect/Planner), Node β (Artisan/Generator), "
        "Node γ (Auditor/Evaluator). Alibaba Cloud FC / ACK targets.",
    ),
]


# ---------------------------------------------------------------------------
# Docs scanner
# ---------------------------------------------------------------------------

class DocsScanner:
    """Walks the repository and returns parsed DocRecord objects."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.parser = DocParser()

    def scan(self) -> list[DocRecord]:
        records: list[DocRecord] = []
        for md_path in self.repo_root.rglob("*.md"):
            # Skip node_modules, target, etc.
            parts = set(md_path.parts)
            if parts & EXCLUDED_DIRS:
                continue
            try:
                records.append(self.parser.parse(md_path, self.repo_root))
            except Exception:
                pass
        return records


# ---------------------------------------------------------------------------
# Skill tree builder
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_skill_tree(repo_root: Path) -> SkillTree:
    """
    Phase 1: construct static skill tree from hand-authored definitions,
    enriched with doc-scan evidence refs.
    """
    scanner = DocsScanner(repo_root)
    doc_records = scanner.scan()
    known_paths = {r.rel_path for r in doc_records}

    now = _now_iso()

    skills: list[SkillObject] = []
    for defn in _SKILL_DEFINITIONS:
        (skill_id, label, domain, tier, base_confidence,
         domain_affinity, dependencies, raw_refs, description) = defn

        # Filter evidence_refs to those actually present on disk
        evidence_refs = [r for r in raw_refs if r in known_paths or
                         any(k.endswith(r) or r.endswith(k) for k in known_paths)]
        if not evidence_refs:
            evidence_refs = raw_refs  # keep spec refs even if files moved

        confidence = TIER_CONFIDENCE.get(tier, base_confidence)

        skills.append(SkillObject(
            skill_id=skill_id,
            label=label,
            domain=domain,
            tier=tier,
            confidence=confidence,
            validated_runs=0,            # Phase 1 — no telemetry yet
            failure_rate=0.0,
            recency_score=1.0,           # freshly documented
            domain_affinity=domain_affinity,
            dependencies=dependencies,
            evidence_refs=evidence_refs,
            last_validated=now,
            description=description,
        ))

    return SkillTree(
        version=DOCS_VERSION,
        phase=PHASE,
        generated_at=now,
        genesis_seal=GENESIS_SEAL,
        doc_count=len(doc_records),
        skills=skills,
    )


# ---------------------------------------------------------------------------
# Markdown renderer (for .agent/skills.md)
# ---------------------------------------------------------------------------

def render_skills_md(tree: SkillTree) -> str:
    """Render skill tree as the .agent/skills.md registry format."""
    lines = [
        "# SOVEREIGN AGI OS — SKILLS REGISTRY",
        "",
        f"**Phase:** {tree.phase} (static, human-authored baseline)  ",
        f"**Generated:** {tree.generated_at}  ",
        f"**Docs scanned:** {tree.doc_count}  ",
        f"**Skills:** {len(tree.skills)}",
        "",
        "---",
        "",
    ]

    # Group by domain
    by_domain: dict[str, list[SkillObject]] = {}
    for s in tree.skills:
        by_domain.setdefault(s.domain, []).append(s)

    for domain, skills in sorted(by_domain.items()):
        lines.append(f"## Domain: `{domain}`")
        lines.append("")
        for s in skills:
            lines += [
                f"### SKILL: {s.skill_id}",
                f"- **Label:** {s.label}",
                f"- **Tier:** {s.tier}",
                f"- **Confidence:** {s.confidence:.2f}",
                f"- **Validated runs:** {s.validated_runs}",
                f"- **Failure rate:** {s.failure_rate:.2f}",
                f"- **Recency score:** {s.recency_score:.2f}",
                f"- **Domain affinity:** {', '.join(s.domain_affinity)}",
                f"- **Dependencies:** {', '.join(s.dependencies) if s.dependencies else 'none'}",
                f"- **Evidence refs:** {', '.join(s.evidence_refs)}",
                f"- **Last validated:** {s.last_validated}",
                f"- **Description:** {s.description}",
                "",
            ]

    lines += [
        "---",
        "",
        "## Format",
        "",
        "```",
        "### SKILL: <skill_id>",
        "- **Tier:** T0-T3",
        "- **Confidence:** 0.0–1.0 (T0=0.95 seed, T1=0.80, T2=0.65, T3=0.40)",
        "- **Validated runs:** incremented by telemetry in Phase 2",
        "- **Failure rate:** 0.0 in Phase 1 (no telemetry yet)",
        "```",
        "",
        "_Skills evolve via SKILL_VALIDATED / SKILL_DEGRADED / SKILL_DECAYED events in Phase 2._",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ingest(repo_root: str | Path = ".") -> SkillTree:
    """Entry point: scan docs, build and return SkillTree."""
    return build_skill_tree(Path(repo_root).resolve())


if __name__ == "__main__":
    import sys
    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parents[3]
    tree = ingest(root)
    print(tree.to_json())
