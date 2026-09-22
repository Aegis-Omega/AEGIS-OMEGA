"""
ARC v3 — Grammar-Extended VM
Executes programs whose tokens are rule IDs from MacroLibrary,
not just primitive op ints.

A program in grammar space is a sequence of rule IDs:
  ["ROT90", "MACRO_000_FLIP_X_FLIP_Y", "NOP", "MACRO_001_ROT90_TRANSPOSE"]

Execution: expand each rule to its primitive op_sequence, then run DSLVM.

This turns macro application into transparent, verifiable execution —
no black-box transformation, always reducible to the primitive DSL.
"""

import numpy as np
from dsl.vm import DSLVM
from .macro_library import MacroLibrary


class GrammarVM:
    def __init__(self, library: MacroLibrary):
        self.library = library
        self._vm     = DSLVM()

    def expand(self, rule_ids: list[str]) -> list[int]:
        """
        Expand a grammar program (rule ID sequence) into primitive ops.
        Unknown rule IDs → NOP (op 0).
        """
        primitive_ops = []
        for rid in rule_ids:
            rule = self.library.get(rid)
            if rule is None:
                primitive_ops.append(0)   # NOP fallback
            else:
                primitive_ops.extend(rule.op_sequence)
        return primitive_ops

    def run(self, rule_ids: list[str], grid: np.ndarray) -> np.ndarray:
        """
        Expand rule_ids to primitives and execute on grid.
        Returns transformed grid.
        """
        ops = self.expand(rule_ids)
        return self._vm.run(ops, grid)

    def run_ops(self, ops: list[int], grid: np.ndarray) -> np.ndarray:
        """Direct primitive execution (bypass grammar layer)."""
        return self._vm.run(ops, grid)
