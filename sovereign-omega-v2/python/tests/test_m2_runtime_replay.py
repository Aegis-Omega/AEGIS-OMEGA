"""Execute checked-in M2 without constructing the multi-GB memory arena.

Diagnostic-only issue #531: no bridge imports, subsystem startup, address
repair, gate-policy selection, or runtime authority changes.
"""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path
from typing import Tuple


PYTHON_DIR = Path(__file__).resolve().parent.parent
CORE_MATRIX = PYTHON_DIR / "core_matrix.py"
CONTRACT = Path(__file__).resolve().parent / "fixtures" / "m2_sequence_domain_contract.json"
INT_SCALE = 1 << 16


def _source_bound_m2():
    """Compile only the checked-in M2 function and its pure dependencies."""
    source = ast.parse(CORE_MATRIX.read_text(encoding="utf-8"), filename=str(CORE_MATRIX))
    matches = [
        node for node in source.body
        if isinstance(node, ast.FunctionDef) and node.name == "M2"
    ]
    if len(matches) != 1 or matches[0].decorator_list:
        raise AssertionError("Expected exactly one undecorated top-level M2 function")

    def fixed_clamp(value: int, lower: int, upper: int) -> int:
        return max(lower, min(value, upper))

    namespace = {"INT_SCALE": INT_SCALE, "fixed_clamp": fixed_clamp, "Tuple": Tuple}
    module = ast.fix_missing_locations(ast.Module(body=matches, type_ignores=[]))
    exec(compile(module, str(CORE_MATRIX), "exec"), namespace)
    return namespace["M2"], matches[0]


def _offset(sequence: int, verifier_length: int, region_length: int) -> int:
    return (8 * sequence + verifier_length) % (region_length // 8)


class TestM2RuntimeReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        m2, cls.m2_ast = _source_bound_m2()
        cls.m2 = staticmethod(m2)

    def test_executed_M2_places_record_at_unaligned_byte_nine(self) -> None:
        memory = bytearray(140)
        result = self.m2(memoryview(memory), b"\x01", INT_SCALE // 2, sequence=1)
        self.assertEqual(result, (INT_SCALE // 2, 0))
        record = result[0].to_bytes(4, "little") + result[1].to_bytes(4, "little")
        self.assertEqual(memory[9:17], record)
        self.assertEqual(memory[:9], bytes(9))
        self.assertEqual(memory[17:], bytes(123))
        self.assertEqual(9 % 8, 1)

    def test_executed_M2_phase_wrap_corrupts_previous_record(self) -> None:
        memory = bytearray(140)
        self.m2(memoryview(memory), b"\x01", INT_SCALE // 2, sequence=1)
        original_record = bytes(memory[9:17])
        self.assertEqual(_offset(1, 1, 140), 9)
        self.assertEqual(_offset(2, 1, 140), 0)
        self.assertEqual(_offset(3, 1, 140), 8)
        self.m2(memoryview(memory), b"\x01", INT_SCALE, sequence=3)
        self.assertNotEqual(bytes(memory[9:17]), original_record)
        self.assertEqual(memory[8:16], bytes(4) + INT_SCALE.to_bytes(4, "little"))
        self.assertEqual(len(set(range(9, 17)) & set(range(8, 16))), 7)

    def test_equal_sequences_from_unrelated_sources_have_no_namespace(self) -> None:
        # Potential aliasing counterexample, not a claim that live streams
        # actually emitted equal sequence values.
        memory = bytearray(140)
        first = self.m2(memoryview(memory), b"\x01", INT_SCALE // 2, sequence=1)
        first_record = bytes(memory[9:17])
        second = self.m2(memoryview(memory), b"\x01", INT_SCALE, sequence=1)
        self.assertNotEqual(first, second)
        self.assertNotEqual(bytes(memory[9:17]), first_record)
        expected = second[0].to_bytes(4, "little") + second[1].to_bytes(4, "little")
        self.assertEqual(bytes(memory[9:17]), expected)

    def test_actual_M2_record_writes_are_region_bounded(self) -> None:
        # Exhaustive small-region sweep with isolated real M2 body.
        for length in range(8, 257):
            for sequence in (0, 1, 2, 3, 17, 64, 1001, 1258291):
                for verifier in (b"", b"\x00", b"\x01", b"\x01\x00", b"\x01" * 9):
                    memory = bytearray(b"\xa5" * length)
                    result = self.m2(memoryview(memory), verifier, INT_SCALE, sequence)
                    offset = _offset(sequence, len(verifier), length)
                    expected = bytearray(b"\xa5" * length)
                    record = result[0].to_bytes(4, "little") + result[1].to_bytes(4, "little")
                    self.assertLessEqual(offset + 8, length)
                    expected[offset:offset + 8] = record
                    self.assertEqual(memory, expected)

    def test_contract_cannot_approve_runtime_change_by_json_toggle(self) -> None:
        # Separate proof/review required; fixture alone cannot enable a fix.
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        self.assertEqual(contract["schema"], "aegis.m2.sequence-domain-contract.v1")
        self.assertEqual(contract["policy"]["status"], "DEFERRED")
        self.assertIsNone(contract["policy"]["selected"])
        self.assertIs(contract["runtime_semantics_change_allowed"], False)
        actual_offset = [
            node.value for node in ast.walk(self.m2_ast)
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "offset" for target in node.targets)
        ]
        self.assertEqual(len(actual_offset), 1)
        expected = ast.parse(contract["current_offset_formula"], mode="eval").body
        self.assertEqual(ast.dump(actual_offset[0]), ast.dump(expected))


if __name__ == "__main__":
    unittest.main()
