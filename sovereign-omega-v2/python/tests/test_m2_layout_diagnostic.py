"""Diagnostic-only machine checks for AEGIS-OMEGA issue #531.

This test intentionally does not import or instantiate CoreMatrix. It reads the
checked-in Python source as AST, proves concrete arithmetic witnesses for the
current M2 address formula, and freezes runtime semantics until an explicit
sequence-domain policy is selected.
"""

from __future__ import annotations

import ast
import json
import unittest
from pathlib import Path
from typing import Iterator, Tuple


TEST_DIR = Path(__file__).resolve().parent
PYTHON_DIR = TEST_DIR.parent
CORE_MATRIX_PATH = PYTHON_DIR / "core_matrix.py"
BRIDGE_PATH = PYTHON_DIR / "bridge.py"
CONTRACT_PATH = TEST_DIR / "fixtures" / "m2_sequence_domain_contract.json"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _contract() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def _named_function(tree: ast.AST, name: str) -> ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return node
    raise AssertionError(f"function {name!r} not found")


def _m2_offset_expr(tree: ast.AST) -> ast.AST:
    m2 = _named_function(tree, "M2")
    for node in ast.walk(m2):
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == "offset" for target in node.targets):
                return node.value
    raise AssertionError("M2 offset assignment not found")


def _expr_dump(expr: ast.AST) -> str:
    return ast.dump(expr, annotate_fields=True, include_attributes=False)


def _current_offset(sequence: int, verifier_len: int, region_len: int) -> int:
    slots = region_len // 8
    if slots <= 0:
        raise ValueError("region_len must contain at least one 8-byte slot")
    return (sequence * 8 + verifier_len) % slots


def _window(start: int, width: int = 8) -> set[int]:
    return set(range(start, start + width))


def _core_matrix_m2_writers(tree: ast.Module) -> Iterator[Tuple[str, ast.Call]]:
    for node in tree.body:
        if not isinstance(node, ast.ClassDef) or node.name != "CoreMatrix":
            continue
        for method in node.body:
            if not isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for child in ast.walk(method):
                if isinstance(child, ast.Call) and isinstance(child.func, ast.Name) and child.func.id == "M2":
                    yield method.name, child


def _is_name(node: ast.AST, name: str) -> bool:
    return isinstance(node, ast.Name) and node.id == name


def _is_self_attr(node: ast.AST, attr: str) -> bool:
    return (
        isinstance(node, ast.Attribute)
        and node.attr == attr
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    )


def _is_matrix_method_call(node: ast.AST, method: str) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == method
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "matrix"
    )


class TestM2LayoutDiagnosticGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = _contract()
        cls.core_tree = _tree(CORE_MATRIX_PATH)
        cls.bridge_tree = _tree(BRIDGE_PATH)

    def test_current_source_formula_is_bound_to_diagnostic_contract(self) -> None:
        expected = ast.parse(self.contract["current_offset_formula"], mode="eval").body
        actual = _m2_offset_expr(self.core_tree)
        self.assertEqual(_expr_dump(actual), _expr_dump(expected))

    def test_unaligned_offset_witness_is_nine_for_real_profiles(self) -> None:
        # Issue #531's two checked profiles: default 4 GiB arena and checked-in Cloud arena.
        for region_len in (1_288_490_188, 80_530_636):
            offset = _current_offset(sequence=1, verifier_len=1, region_len=region_len)
            self.assertEqual(offset, 9)
            self.assertNotEqual(offset % 8, 0)

    def test_current_offset_domain_is_floor_region_len_over_eight(self) -> None:
        for region_len in (1_288_490_188, 80_530_636, 140):
            slot_count = region_len // 8
            self.assertEqual(region_len % 8, 4)
            for sequence in (0, 1, 2, slot_count - 1, slot_count, slot_count + 1):
                offset = _current_offset(sequence, verifier_len=1, region_len=region_len)
                self.assertGreaterEqual(offset, 0)
                self.assertLess(offset, slot_count)
            self.assertLess(slot_count, region_len)

    def test_small_phase_wrap_witness_overlaps_eight_byte_windows(self) -> None:
        # Small analogue with the same L mod 8 = 4 shape as both real profiles.
        # floor(140 / 8) = 17, so verifier_len=1 yields:
        # seq 1 -> 9, seq 2 -> 0 (phase wrap), seq 3 -> 8.
        region_len = 140
        before_wrap = _current_offset(1, 1, region_len)
        wrap = _current_offset(2, 1, region_len)
        after_wrap = _current_offset(3, 1, region_len)

        self.assertEqual((before_wrap, wrap, after_wrap), (9, 0, 8))
        self.assertLess(wrap, before_wrap)
        overlap = _window(before_wrap) & _window(after_wrap)
        self.assertEqual(overlap, set(range(9, 16)))
        self.assertEqual(len(overlap), 7)

    def test_both_live_m2_writer_sequence_sources_are_enumerated(self) -> None:
        writers = list(_core_matrix_m2_writers(self.core_tree))
        self.assertEqual([name for name, _ in writers], ["process_event", "receive_gate_signal"])

        event_call = writers[0][1]
        gate_call = writers[1][1]
        self.assertGreaterEqual(len(event_call.args), 4)
        self.assertGreaterEqual(len(gate_call.args), 4)
        self.assertTrue(_is_self_attr(event_call.args[3], "_sequence"))
        self.assertTrue(_is_name(gate_call.args[3], "sequence"))

        declared = {
            item["writer"]: item["sequence_argument"]
            for item in self.contract["writers"]
        }
        self.assertEqual(
            declared,
            {
                "CoreMatrix.process_event": "self._sequence",
                "CoreMatrix.receive_gate_signal": "sequence",
            },
        )

    def test_bridge_discards_event_router_seq_but_forwards_gate_signal_seq(self) -> None:
        register = _named_function(self.bridge_tree, "_register_handlers")
        process_lambdas = []
        for node in ast.walk(register):
            if not isinstance(node, ast.Lambda):
                continue
            if _is_matrix_method_call(node.body, "process_event"):
                process_lambdas.append(node)

        self.assertEqual(len(process_lambdas), 3)
        for lam in process_lambdas:
            self.assertIn("seq", [arg.arg for arg in lam.args.args])
            self.assertEqual(len(lam.body.args), 3)
            self.assertFalse(any(_is_name(arg, "seq") for arg in lam.body.args))

        gate_calls = [
            node for node in ast.walk(self.bridge_tree)
            if _is_matrix_method_call(node, "receive_gate_signal")
        ]
        self.assertEqual(len(gate_calls), 1)
        self.assertGreaterEqual(len(gate_calls[0].args), 3)
        self.assertTrue(_is_name(gate_calls[0].args[2], "seq"))

        seq_from_request = False
        for node in ast.walk(self.bridge_tree):
            if not isinstance(node, ast.Assign):
                continue
            if not any(_is_name(target, "seq") for target in node.targets):
                continue
            value = node.value
            if (
                isinstance(value, ast.Call)
                and isinstance(value.func, ast.Attribute)
                and value.func.attr == "get"
                and isinstance(value.func.value, ast.Name)
                and value.func.value.id == "data"
                and value.args
                and isinstance(value.args[0], ast.Constant)
                and value.args[0].value == "sequence"
            ):
                seq_from_request = True
                break
        self.assertTrue(seq_from_request)
        self.assertEqual(self.contract["event_router_sequence_forwarding"], "DISCARDED")

    def test_runtime_change_remains_fail_closed_until_policy_is_selected(self) -> None:
        policy = self.contract["policy"]
        allowed = {
            "shared_key",
            "overwrite_update",
            "disjoint_source_namespaces",
        }
        self.assertEqual(set(policy["allowed"]), allowed)

        if policy["status"] == "DEFERRED":
            self.assertIsNone(policy["selected"])
            self.assertFalse(self.contract["runtime_semantics_change_allowed"])
            expected = ast.parse(self.contract["current_offset_formula"], mode="eval").body
            self.assertEqual(_expr_dump(_m2_offset_expr(self.core_tree)), _expr_dump(expected))
        else:
            self.assertEqual(policy["status"], "SELECTED")
            self.assertIn(policy["selected"], allowed)
            self.assertTrue(self.contract["runtime_semantics_change_allowed"])


if __name__ == "__main__":
    unittest.main()
