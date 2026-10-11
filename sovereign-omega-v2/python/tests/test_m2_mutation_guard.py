"""Mutation-negative checks for the source-bound M2 address contract.

Deliberately injure a copy of the checked-in AST and verify that known unsafe
addressing patterns violate invariants. Nothing mutates the repository at run.
"""
from __future__ import annotations

import ast
import copy
import unittest
from pathlib import Path
from typing import Tuple

SOURCE = Path(__file__).resolve().parent.parent / "core_matrix.py"
INT_SCALE = 1 << 16


def _mutant(kind: str):
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("_m2_byte_offset", "M2")
    ]
    if [node.name for node in functions] != ["_m2_byte_offset", "M2"]:
        raise AssertionError("Expected exact, ordered M2 functions")
    helper, m2 = copy.deepcopy(functions)

    if kind == "merge_namespaces":
        guards = [
            node for node in helper.body
            if isinstance(node, ast.If)
            and "source == 'event'" in ast.unparse(node.test)
        ]
        if len(guards) != 1:
            raise AssertionError("M2 namespace branch not found")
        guards[0].test = ast.Constant(value=True)
    elif kind == "byte_unit_modulus":
        assigns = [
            node for node in ast.walk(m2)
            if isinstance(node, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "offset" for t in node.targets)
        ]
        if len(assigns) != 1:
            raise AssertionError("M2 address assignment not unique")
        assigns[0].value = ast.parse(
            "(sequence * 8 + len(verifier_result)) % (len(state) // 8)",
            mode="eval",
        ).body
    elif kind == "unaligned_offset":
        returns = [
            node for node in helper.body
            if isinstance(node, ast.Return)
            and isinstance(node.value, ast.Name)
            and node.value.id == "offset"
        ]
        if len(returns) != 1:
            raise AssertionError("M2 offset return not found")
        returns[0].value = ast.parse("offset + 1", mode="eval").body
    elif kind == "allow_bool_sequence":
        guards = [
            node for node in helper.body
            if isinstance(node, ast.If)
            and "type(sequence) is not int" in ast.unparse(node.test)
        ]
        if len(guards) != 1:
            raise AssertionError("M2 strict sequence guard not found")
        guards[0].test = ast.parse(
            "not 0 <= sequence < (1 << 64)", mode="eval"
        ).body
    else:
        raise ValueError(kind)

    module = ast.fix_missing_locations(
        ast.Module(body=[helper, m2], type_ignores=[])
    )
    namespace = {
        "INT_SCALE": INT_SCALE,
        "Tuple": Tuple,
        "fixed_clamp": lambda x, lo, hi: max(lo, min(hi, x)),
    }
    exec(compile(module, str(SOURCE), "exec"), namespace)
    return namespace["M2"], namespace["_m2_byte_offset"]


class TestM2MutationGuard(unittest.TestCase):
    def test_namespace_merge_mutant_exhibits_cross_source_alias(self):
        _, addr = _mutant("merge_namespaces")
        self.assertEqual(
            addr(140, 1, "event"), addr(140, 1, "gate_signal")
        )

    def test_legacy_byte_modulus_mutant_exhibits_unaligned_write(self):
        write, _ = _mutant("byte_unit_modulus")
        data = bytearray(b"\xa5" * 140)
        write(memoryview(data), b"\x01", INT_SCALE, 1, source="event")
        self.assertEqual(data[8], 0xA5)
        self.assertNotEqual(data[9:17], b"\xa5" * 8)

    def test_unaligned_address_mutant_exhibits_bad_alignment(self):
        _, addr = _mutant("unaligned_offset")
        self.assertNotEqual(addr(140, 1, "event") % 8, 0)

    def test_bool_sequence_mutant_accepts_invalid_input(self):
        _, addr = _mutant("allow_bool_sequence")
        self.assertEqual(
            addr(140, True, "event"), addr(140, 1, "event")
        )


if __name__ == "__main__":
    unittest.main()
