"""
ARC v3 — Grammar Rule
A grammar rule is a conditional graph rewrite:

  IF  trigger_pattern matches subgraph of input G
  THEN apply op_sequence (macro body) to G

The "graph grammar" property: macros compose.
A program P is a sequence of grammar productions r_1, r_2, ..., r_k
where each r_i is either a primitive DSL op or a learned macro.

Rule hierarchy:
  Level 0 — primitives: single DSL ops (NOP, ROT90, ..., SHIFT_RIGHT)
  Level 1 — macros: sequences of primitives discovered by GrammarInducer
  Level 2 — meta-macros: sequences of Level-1 macros (automatic via induction)
"""

from dataclasses import dataclass, field
from typing import Optional
import numpy as np


@dataclass
class TriggerPattern:
    """
    A structural pattern over graph node features that activates a macro.
    Matching is fuzzy: pattern fires when cosine_sim(graph_signature, pattern_vector) > threshold.
    """
    vector:    np.ndarray   # d_model-dim signature of graphs this macro is useful on
    threshold: float = 0.7  # minimum similarity to trigger
    name:      str   = ""

    def matches(self, graph_signature: np.ndarray) -> bool:
        norm = np.linalg.norm(self.vector) * np.linalg.norm(graph_signature)
        if norm < 1e-8:
            return False
        sim = float(np.dot(self.vector, graph_signature) / norm)
        return sim >= self.threshold


@dataclass
class GrammarRule:
    """
    A single grammar rule (macro or primitive).

    id:           unique string, e.g. "MACRO_003" or "ROT90"
    op_sequence:  list of primitive op ints (len=1 for primitives)
    level:        0 = primitive, 1 = macro, 2 = meta-macro
    trigger:      optional TriggerPattern (None = always applicable)
    count:        times this rule was used during training (for MDL)
    mdl_saving:   MDL compression: count*(len-1) - (len+1)  [>0 = worth keeping]
    """
    id:          str
    op_sequence: list[int]
    level:       int = 0
    trigger:     Optional[TriggerPattern] = None
    count:       int = 0
    mdl_saving:  float = 0.0
    description: str = ""

    @property
    def length(self) -> int:
        return len(self.op_sequence)

    @property
    def is_primitive(self) -> bool:
        return self.level == 0

    def expected_mdl_saving(self, corpus_count: int) -> float:
        """
        MDL saving if this rule appears corpus_count times.
        savings = count * (len - 1)     -- each use compresses by (len-1) symbols
        cost    = len + 1               -- storing the rule costs (len+1) symbols
        net     = savings - cost
        """
        savings = corpus_count * (self.length - 1)
        cost    = self.length + 1
        return float(savings - cost)
