"""
ARC v3 — DSL Virtual Machine
Executes programs (sequences of op codes) on ARC grids.
"""

import numpy as np


class DSLVM:
    def run(self, program, grid: np.ndarray) -> np.ndarray:
        """
        Execute a program on a grid, returning the transformed grid.
        Program is a list/array of integer op codes.
        Grid shape is preserved (not padded).
        """
        x = np.array(grid, dtype=np.int64)

        for op in program:
            op = int(op)
            if op == 0:   # NOP
                pass
            elif op == 1:  # ROT90
                x = np.rot90(x)
            elif op == 2:  # ROT180
                x = np.rot90(x, 2)
            elif op == 3:  # FLIP_X (left-right)
                x = np.flip(x, axis=1)
            elif op == 4:  # FLIP_Y (up-down)
                x = np.flip(x, axis=0)
            elif op == 5:  # TRANSPOSE
                x = x.T
            elif op == 6:  # INVERT
                x = 9 - x
            elif op == 7:  # SHIFT_UP
                x = np.roll(x, -1, axis=0)
            elif op == 8:  # SHIFT_DOWN
                x = np.roll(x, 1, axis=0)
            elif op == 9:  # SHIFT_LEFT
                x = np.roll(x, -1, axis=1)
            elif op == 10: # SHIFT_RIGHT
                x = np.roll(x, 1, axis=1)

        return x
