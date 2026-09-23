"""
ARC v3 — Configuration
Sovereign AGI OS integration: ARC task performance feeds HD measurements.
"""

DEVICE = "cpu"

# Grid encoding — ARC grids are up to 30×30
GRID_MAX = 30
GRID_FLAT = GRID_MAX * GRID_MAX   # 900

# DSL
MAX_PROGRAM_LEN = 8
VOCAB_SIZE = 11   # ops 0–10 (NOP + 10 transforms)

# Model
EMBED_DIM = 128
N_HEAD = 4
N_LAYER = 2

# Training
LR = 3e-4
GAMMA = 0.99
BATCH_SIZE = 32
REPLAY_SIZE = 50000

# Reward shaping
CVS_WEIGHT = 0.2    # causal variance score bonus
MDL_WEIGHT = 0.01   # minimum description length penalty

# ARC data path (relative to this file's parent)
ARC_DATA_PATH = "arc_data"

# HD integration — writes to OS state
STATE_PATH = "../.forge/state.json"
