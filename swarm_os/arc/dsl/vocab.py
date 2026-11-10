"""
ARC v3 — DSL Vocabulary
11 primitive operations (0=NOP, 1–10 transformations).
"""

TOKENS = {
    0:  "NOP",
    1:  "ROT90",
    2:  "ROT180",
    3:  "FLIP_X",    # flip left-right (axis=1)
    4:  "FLIP_Y",    # flip up-down (axis=0)
    5:  "TRANSPOSE",
    6:  "INVERT",    # 9 - x
    7:  "SHIFT_UP",
    8:  "SHIFT_DOWN",
    9:  "SHIFT_LEFT",
    10: "SHIFT_RIGHT",
}

TOKEN_IDS = {v: k for k, v in TOKENS.items()}
N_TOKENS = len(TOKENS)
