"""Source-bound executed M2 tests for proof-first issue #763.

The AST loader compiles the *checked-in* M2 body and address helper, not an
independent model or a 4 GiB CoreMatrix instance. Legacy witnesses remain in
test_m2_layout_diagnostic; this suite guards the candidate corrected behavior.
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
    tree = ast.parse(CORE_MATRIX.read_text(encoding="utf-8"), filename=str(CORE_MATRIX))
    names = ("_m2_byte_offset", "M2")
    selected = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name in names
    ]
    if [node.name for node in selected] != list(names):
        raise AssertionError("Expected top-level M2 address helper followed by M2")
    if any(node.decorator_list for node in selected):
        raise AssertionError("M2 layout functions must be undecorated")
    # Keep all arithmetic and memory writes from the checked-in source.
    module = ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[]))

    def fixed_clamp(value: int, lower: int, upper: int) -> int:
        return max(lower, min(value, upper))

    namespace = {"INT_SCALE": INT_SCALE, "fixed_clamp": fixed_clamp, "Tuple": Tuple}
    exec(compile(module, str(CORE_MATRIX), "exec"), namespace)
    return namespace["M2"], namespace["_m2_byte_offset"], selected


class TestM2RuntimeReplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        m2, offset, nodes = _source_bound_m2()
        cls.m2 = staticmethod(m2)
        cls.offset = staticmethod(offset)
        cls.nodes = nodes
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_actual_M2_writes_aligned_eight_byte_records(self) -> None:
        for source in ("event", "gate_signal"):
            memory = bytearray(b"\xa5" * 140)
            result = self.m2(memoryview(memory), b"\x01", INT_SCALE // 2,
                             1, source=source)
            offset = self.offset(len(memory), 1, source)
            record = result[0].to_bytes(4, "little") + result[1].to_bytes(4, "little")
            self.assertEqual(result, (INT_SCALE // 2, 0))
            self.assertEqual(offset % 8, 0)
            self.assertEqual(memory[offset:offset + 8], record)
            self.assertEqual(memory[:offset], b"\xa5" * offset)
            self.assertEqual(memory[offset + 8:], b"\xa5" * (len(memory) - offset - 8))

    def test_independent_sources_cannot_alias_on_same_numeric_sequence(self) -> None:
        for length in (16, 17, 23, 140, 256):
            for sequence in (0, 1, 2, 10001, (1 << 64) - 1):
                event = self.offset(length, sequence, "event")
                gate = self.offset(length, sequence, "gate_signal")
                self.assertNotEqual(event, gate)
                self.assertEqual(event % 8, 0)
                self.assertEqual(gate % 8, 0)
                slots = length // 8
                event_slots = (slots + 1) // 2
                self.assertLess(event // 8, event_slots)
                self.assertGreaterEqual(gate // 8, event_slots)

    def test_gate_signal_does_not_overwrite_event_record(self) -> None:
        state = bytearray(140)
        event_offset = self.offset(140, 1, "event")
        gate_offset = self.offset(140, 1, "gate_signal")
        self.m2(memoryview(state), b"\x01", INT_SCALE // 2, 1, source="event")
        previous = bytes(state[event_offset:event_offset + 8])
        self.m2(memoryview(state), b"\x01", INT_SCALE, 1, source="gate_signal")
        self.assertEqual(state[event_offset:event_offset + 8], previous)
        self.assertNotEqual(event_offset, gate_offset)

    def test_circular_wrap_is_confined_to_source_namespace(self) -> None:
        for length in (16, 17, 23, 140, 256):
            slots = length // 8
            event_capacity = (slots + 1) // 2
            gate_capacity = slots - event_capacity
            self.assertEqual(self.offset(length, 0, "event"),
                             self.offset(length, event_capacity, "event"))
            self.assertEqual(self.offset(length, 0, "gate_signal"),
                             self.offset(length, gate_capacity, "gate_signal"))
            self.assertNotEqual(self.offset(length, 0, "event"),
                                self.offset(length, 0, "gate_signal"))

    def test_reject_invalid_address_inputs_before_mutating_state(self) -> None:
        for length, sequence, source in [
            (15, 1, "event"), (0, 1, "gate_signal"),
            (140, -1, "event"), (140, 1 << 64, "gate_signal"),
            (140, True, "event"), (140, 1.0, "event"),
            (140, 1, ""), (140, 1, "unknown"),
        ]:
            memory = bytearray(b"\xa5" * length)
            with self.assertRaises(ValueError):
                self.m2(memoryview(memory), b"\x01", INT_SCALE, sequence,
                        source=source)
            self.assertEqual(memory, bytearray(b"\xa5" * length))

        with self.assertRaises(TypeError):
            self.m2(memoryview(bytearray(140)), b"\x01", INT_SCALE, 1)

    def test_small_region_exhaustive_write_footprint(self) -> None:
        # 241 region sizes * 8 sequences * 5 verifier inputs * 2 sources.
        cases = 0
        for length in range(16, 257):
            for sequence in (0, 1, 2, 3, 17, 64, 1001, 1258291):
                for verifier in (b"", b"\x00", b"\x01", b"\x01\x00", b"\x01" * 9):
                    for source in ("event", "gate_signal"):
                        memory = bytearray(b"\xa5" * length)
                        result = self.m2(memoryview(memory), verifier, INT_SCALE,
                                         sequence, source=source)
                        offset = self.offset(length, sequence, source)
                        record = (result[0].to_bytes(4, "little")
                                  + result[1].to_bytes(4, "little"))
                        expected = bytearray(b"\xa5" * length)
                        expected[offset:offset + 8] = record
                        self.assertEqual(memory, expected)
                        self.assertLessEqual(offset + 8, length)
                        self.assertEqual(offset % 8, 0)
                        cases += 1
        self.assertEqual(cases, 19280)

    def test_q16_16_telemetry_unchanged_by_address_policy(self) -> None:
        for confidence in (-10, 0, 1, INT_SCALE // 2, INT_SCALE, INT_SCALE + 10):
            for verifier in (b"", b"\x00", b"\x01", b"\x01\x00"):
                c = max(0, min(confidence, INT_SCALE))
                err = abs(c - (INT_SCALE if verifier and verifier[0] else 0))
                expected = (err, max(0, c - err))
                for source in ("event", "gate_signal"):
                    result = self.m2(memoryview(bytearray(140)), verifier,
                                     confidence, 1, source=source)
                    self.assertEqual(result, expected)

    def test_default_and_cloud_profiles_without_large_allocation(self) -> None:
        for length in (1_288_490_188, 80_530_636):
            slot_count = length // 8
            event_count = (slot_count + 1) // 2
            self.assertEqual(length % 8, 4)
            self.assertEqual(self.offset(length, 1, "event"), 8)
            self.assertEqual(self.offset(length, 1, "gate_signal"),
                             8 * (event_count + 1))
            self.assertLessEqual(self.offset(length, 1, "gate_signal") + 8, length)

    def test_two_writer_concurrent_interleavings_are_disjoint(self) -> None:
        # Each thread repeatedly updates a distinct namespace at the same
        # numeric sequence. No reliance on the CoreMatrix lock for isolation.
        from concurrent.futures import ThreadPoolExecutor

        state = bytearray(140)

        def write(source: str) -> tuple:
            confidence = INT_SCALE // 2 if source == "event" else INT_SCALE
            result = (0, 0)
            for _ in range(500):
                result = self.m2(memoryview(state), b"\x01", confidence, 1,
                                 source=source)
            return result

        with ThreadPoolExecutor(max_workers=2) as pool:
            event_result, gate_result = list(
                pool.map(write, ("event", "gate_signal"))
            )

        for source, result in (("event", event_result),
                               ("gate_signal", gate_result)):
            offset = self.offset(len(state), 1, source)
            record = (result[0].to_bytes(4, "little")
                      + result[1].to_bytes(4, "little"))
            self.assertEqual(state[offset:offset + 8], record)

    def test_policy_source_bound_and_not_admitted(self) -> None:
        self.assertEqual(self.contract["schema"],
                         "aegis.m2.sequence-domain-contract.v2")
        self.assertEqual(self.contract["policy"]["selected"],
                         "disjoint_source_namespaces")
        self.assertEqual(self.contract["implementation_status"],
                         "CANDIDATE_NOT_ADMITTED")
        self.assertFalse(self.contract["runtime_semantics_change_allowed"])
        m2_node = self.nodes[1]
        offsets = [
            n.value for n in ast.walk(m2_node)
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == "offset" for t in n.targets)
        ]
        self.assertEqual(len(offsets), 1)
        expected = ast.parse(self.contract["current_offset_formula"], mode="eval").body
        self.assertEqual(ast.dump(offsets[0]), ast.dump(expected))


if __name__ == "__main__":
    unittest.main()
