# © 2026 Tarik Skalic — Sovereign AGI OS. All rights reserved.
"""
S.W.A.R.M. OS v6.0 — Configuration
All constants in one place. Import from here — never hard-code.
"""

from pathlib import Path

# ── Server ───────────────────────────────────────────────────────────────────
PORT        = 8000
HOST        = "0.0.0.0"
VERSION     = "swarm-6.0.0"
MAX_EVENTS  = 200   # ring buffer cap for in-memory event list

# ── Dream State ──────────────────────────────────────────────────────────────
REM_INTERVAL     = 60.0   # seconds between automatic dream cycles
EPIPHANY_MIN_HOP = 2      # minimum A²[i,j] shared-neighbor count to fire epiphany

# ── Vector space ─────────────────────────────────────────────────────────────
SIMILARITY_THRESHOLD = 0.22   # cosine distance below which concepts are "same"
ETA_DEFAULT          = 0.005  # default phase mutation rate (observer effect)
EMBED_DIM            = 384    # sentence-transformer MiniLM dimension

# ── Identity anchor ──────────────────────────────────────────────────────────
SWARM_SELF_AXIOM = "SWARM_SELF_AXIOM"   # always at z=4, center of visualization

# ── Z-level hierarchy (frequency = continuous HD score per node) ─────────────
#
#   Higher z → lower Hallucination Delta
#   z=4: SOVEREIGN_EGO  — identity anchor, fully verified, HD ≈ 0
#   z=0: INERTIA        — new unverified concept, HD ≈ 1
#
Z_LEVELS = {
    4: {"name": "SOVEREIGN_EGO",      "hz": 523, "color": "#39ff14"},
    3: {"name": "VECTOR_RESOLUTION",  "hz": 415, "color": "#00ffff"},
    2: {"name": "EQUILIBRATION",      "hz": 330, "color": "#8888ff"},
    1: {"name": "RADIATION",          "hz": 294, "color": "#ffaa00"},
    0: {"name": "INERTIA",            "hz": 262, "color": "#555555"},
}

Z_HD_MAP = {
    4: 0.00,   # SOVEREIGN_EGO  — perfect
    3: 0.15,   # VECTOR_RESOLUTION
    2: 0.35,   # EQUILIBRATION
    1: 0.65,   # RADIATION
    0: 0.90,   # INERTIA
}

# ── Paths (relative to swarm_os root) ────────────────────────────────────────
FORGE_DIR   = Path(".forge")
AUDIT_FILE  = FORGE_DIR / "swarm_audit.jsonl"
KG_FILE     = FORGE_DIR / "knowledge_graph.json"
STATE_FILE  = FORGE_DIR / "state.json"

# ── Constitutional law IDs ────────────────────────────────────────────────────
LAW_NO_DIRECT_MUTATION      = "CONST_001"
LAW_NO_GUESSING             = "CONST_002"
LAW_NO_UNAUTHORIZED_CONNECT = "CONST_003"
