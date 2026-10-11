"""Diagnostic-only machine checks for AEGIS-OMEGA issue #531.

This test reads the checked-in source AST and preserves regression witnesses
for the legacy M2 address defect, while validating the v2 candidate contract.
It never instantiates the 4 GiB CoreMatrix arena.
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

    def test_legacy_unaligned_offset_witness_is_nine_for_real_profiles(self) -> None:
        # Issue #531's two checked profiles: default 4 GiB arena and checked-in Cloud arena.
        for region_len in (1_288_490_188, 80_530_636):
            offset = _current_offset(sequence=1, verifier_len=1, region_len=region_len)
            self.assertEqual(offset, 9)
            self.assertNotEqual(offset % 8, 0)

    def test_legacy_offset_domain_is_floor_region_len_over_eight(self) -> None:
        for region_len in (1_288_490_188, 80_530_636, 140):
            slot_count = region_len // 8
            self.assertEqual(region_len % 8, 4)
            for sequence in (0, 1, 2, slot_count - 1, slot_count, slot_count + 1):
                offset = _current_offset(sequence, verifier_len=1, region_len=region_len)
                self.assertGreaterEqual(offset, 0)
                self.assertLess(offset, slot_count)
            self.assertLess(slot_count, region_len)

    def test_legacy_phase_wrap_witness_overlaps_eight_byte_windows(self) -> None:
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
        self.assertEqual([(k.arg, getattr(k.value, "value", None)) for k in event_call.keywords],
                         [("source", "event")])
        self.assertEqual([(k.arg, getattr(k.value, "value", None)) for k in gate_call.keywords],
                         [("source", "gate_signal")])

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

    def test_bridge_rejects_invalid_gate_sequence_before_any_gate_mutation(self) -> None:
        handler = next(
            node for node in ast.walk(self.bridge_tree)
            if isinstance(node, ast.ClassDef) and node.name == "BridgeHandler"
        )
        method = next(
            node for node in handler.body
            if isinstance(node, ast.FunctionDef) and node.name == "do_POST"
        )
        gate_branch = next(
            node for node in ast.walk(method)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value == "/gate_signal"
        )
        guard = next(
            node for node in gate_branch.body
            if isinstance(node, ast.If)
            and "type(seq) is not int" in ast.unparse(node.test)
            and "1 << 64" in ast.unparse(node.test)
        )
        ack_writes = [
            node for node in ast.walk(gate_branch)
            if isinstance(node, ast.Assign)
            and any(_is_name(target, "last_ack_sequence") for target in node.targets)
        ]
        gate_calls = [
            node for node in ast.walk(gate_branch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "record_signal"
        ]
        self.assertEqual(len(ack_writes), 1)
        self.assertEqual(len(gate_calls), 1)
        self.assertLess(guard.lineno, ack_writes[0].lineno)
        self.assertLess(guard.lineno, gate_calls[0].lineno)
        self.assertTrue(any(isinstance(child, ast.Return) for child in guard.body))
        self.assertIn("INVALID_SEQUENCE", ast.unparse(guard))

    def test_event_sequence_overflow_guard_precedes_m1_mutation(self) -> None:
        from contextlib import nullcontext
        from types import SimpleNamespace
        from typing import Dict

        core = next(
            node for node in self.core_tree.body
            if isinstance(node, ast.ClassDef) and node.name == "CoreMatrix"
        )
        method = next(
            node for node in core.body
            if isinstance(node, ast.FunctionDef) and node.name == "process_event"
        )
        # Resolve the with self._lock body from the checked-in source.
        with_block = next(
            node for node in method.body if isinstance(node, ast.With)
        )
        candidate_guards = [
            node for node in with_block.body if isinstance(node, ast.If)
            and "SEQUENCE_EXHAUSTED" in ast.unparse(node)
        ]
        self.assertEqual(len(candidate_guards), 1)
        event_guard = candidate_guards[0]
        m1_call = next(
            node for node in ast.walk(with_block)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == "M1"
        )
        self.assertLess(event_guard.lineno, m1_call.lineno)

        # Execute the real source method in isolation: no M1/arena setup.
        module = ast.fix_missing_locations(
            ast.Module(body=[method], type_ignores=[])
        )
        namespace = {"Dict": Dict}
        exec(compile(module, str(CORE_MATRIX_PATH), "exec"), namespace)
        process_event = namespace["process_event"]
        for sequence in (-1, True, (1 << 64) - 1, 1 << 64):
            fake = SimpleNamespace(_lock=nullcontext(), _sequence=sequence)
            output = process_event(fake, b"p", b"\\x01", b"c")
            self.assertEqual(output, {
                "status": "REJECTED",
                "reason": "SEQUENCE_EXHAUSTED",
                "sequence": sequence,
            })

    def test_bridge_ack_sequence_advances_after_both_signal_writes(self) -> None:
        handler = next(
            node for node in ast.walk(self.bridge_tree)
            if isinstance(node, ast.ClassDef) and node.name == "BridgeHandler"
        )
        method = next(
            node for node in handler.body
            if isinstance(node, ast.FunctionDef) and node.name == "do_POST"
        )
        gate_branch = next(
            node for node in ast.walk(method)
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Compare)
            and len(node.test.comparators) == 1
            and isinstance(node.test.comparators[0], ast.Constant)
            and node.test.comparators[0].value == "/gate_signal"
        )
        ack = next(
            node for node in ast.walk(gate_branch)
            if isinstance(node, ast.Assign)
            and any(_is_name(t, "last_ack_sequence") for t in node.targets)
        )
        gate_write = next(
            node for node in ast.walk(gate_branch)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "record_signal"
        )
        m2_write = next(
            node for node in ast.walk(gate_branch)
            if _is_matrix_method_call(node, "receive_gate_signal")
        )
        self.assertLess(gate_write.lineno, m2_write.lineno)
        self.assertLess(m2_write.lineno, ack.lineno)
        locks = [
            node for node in ast.walk(gate_branch)
            if isinstance(node, ast.With) and any(
                isinstance(item.context_expr, ast.Name)
                and item.context_expr.id == "_lock"
                for item in node.items
            )
        ]
        self.assertTrue(any(
            lock.lineno < gate_write.lineno < ack.lineno <= lock.end_lineno
            for lock in locks
        ))

    def test_m2_record_constructed_before_single_buffer_write(self) -> None:
        m2 = _named_function(self.core_tree, "M2")
        writes = [
            node for node in ast.walk(m2)
            if isinstance(node, ast.Assign)
            and any(
                isinstance(t, ast.Subscript) and
                isinstance(t.value, ast.Name) and t.value.id == "state"
                for t in node.targets
            )
        ]
        self.assertEqual(len(writes), 1)
        self.assertTrue(_is_name(writes[0].value, "record"))
        records = [
            node for node in ast.walk(m2)
            if isinstance(node, ast.Assign)
            and any(_is_name(t, "record") for t in node.targets)
        ]
        self.assertEqual(len(records), 1)
        self.assertLess(records[0].lineno, writes[0].lineno)

    def test_unadmitted_policy_cannot_be_promoted_by_contract_toggle(self) -> None:
        self.assertEqual(self.contract["schema"], "aegis.m2.sequence-domain-contract.v2")
        self.assertEqual(self.contract["implementation_status"], "CANDIDATE_NOT_ADMITTED")
        self.assertEqual(self.contract["authority_effect"], "NONE")
        self.assertEqual(self.contract["production_admission"],
                         "BLOCKED_PENDING_REVIEW_AND_EXACT_HEAD_CI")
        self.assertFalse(self.contract["runtime_semantics_change_allowed"])

        policy = self.contract["policy"]
        self.assertEqual(policy["status"], "SELECTED_CANDIDATE")
        self.assertEqual(policy["selected"], "disjoint_source_namespaces")
        self.assertEqual(set(policy["allowed"]), {
            "shared_key", "overwrite_update", "disjoint_source_namespaces",
        })
        self.assertEqual(self.contract["record"]["width_bytes"], 8)

        expected = ast.parse(self.contract["current_offset_formula"], mode="eval").body
        self.assertEqual(_expr_dump(_m2_offset_expr(self.core_tree)), _expr_dump(expected))
        self.assertEqual(
            [item["source_keyword"] for item in self.contract["writers"]],
            ["event", "gate_signal"],
        )


if __name__ == "__main__":
    unittest.main()
