"""Execute exact PR723 collaboration function with hermetic, no-network fake dependencies.

Uses AST extracted from SHA-bound bridge.py, not a reimplementation.
Validates that corrupted chain does not authorize paid inference or side effects.
"""
import ast
import hashlib
import json
import queue
import threading
import types
import unittest
from pathlib import Path

BRIDGE = Path(__file__).resolve().parents[1] / "bridge.py"
MODULE = ast.parse(BRIDGE.read_text(encoding="utf-8"), filename=str(BRIDGE))
FN = next(n for n in MODULE.body if isinstance(n, ast.FunctionDef) and n.name == "_platform_run_collaboration")
assert FN.lineno > 0
CODE = compile(ast.Module(body=[FN], type_ignores=[]), str(BRIDGE), "exec")


class HermeticRunnerTests(unittest.TestCase):
    def setUp(self):
        self.events = queue.Queue()
        self.calls = []
        self.checks = [True, True]
        self.fitness_corrupts = False
        depts = [
            {"id": "R1", "role": "research", "category": "research"},
            {"id": "G1", "role": "guardian", "category": "governance"},
        ]
        def snapshot():
            self.calls.append("chain_verification")
            valid = self.checks.pop(0) if self.checks else True
            return {"valid": valid, "reason": "CHAIN_RECOMPUTED_IN_PROCESS" if valid else "ENTRY_HASH_MISMATCH:2",
                    "terminal_hash": "a" * 64 if valid else None,
                    "entry_count": 2, "scope": "in_process_sha256_linkage_only"}
        def tracked(name, result):
            def call(*args, **kwargs):
                self.calls.append(name)
                return result(*args, **kwargs) if callable(result) else result
            return call
        def fitness(*args):
            self.calls.append("calculate_fitness")
            if self.fitness_corrupts:
                self.checks = [False]
            return {"fitness_mean": 0.5}
        def model(*args, **kwargs):
            self.calls.append("paid_model_call_mock")
            return {
                "artifacts": [{"output": "governed " + dept["id"]} for dept in depts],
                "constitutional_audit": {"verdict": "APPROVED", "concerns": []},
                "projection": {"first_year_arr_usd": 1000, "tier": "T2"},
            }
        self.stored = {"task-1": {"email": "operator@example.invalid"}}
        globals_dict = {
            "json": json,
            "_exec_queues": {"task-1": self.events},
            "_executions": self.stored,
            "_executions_lock": threading.Lock(),
            "_mc_chain_integrity_snapshot": snapshot,
            "_mc_observe": tracked("observation", "a" * 64),
            "_swarm_live": model,
            "_swarm_autonomous": tracked("autonomous_model_call_mock", None),
            "_make_autonomous_agent_call": lambda: None,
            "_PLATFORM_DEPARTMENTS": depts,
            "_platform_ts": lambda: "2026-10-10T00:00:00Z",
            "_platform_dept_output": lambda objective,mode,dept: "template " + dept["id"],
            "_retrieve_swarm_memory": lambda *args: "",
            "_retrieve_prior_artifacts": lambda *args: [],
            "_eval_fitness": fitness,
            "_store_fitness": tracked("fitness_storage", None),
            "_platform_record_cycle": tracked("cycle_storage", None),
            "_award_graces": tracked("grace_storage", None),
            "_build_live_state_context": lambda: "T2 observation only",
            "_mc_recent_context": lambda *args: "no context",
            "CONSTITUTIONAL_SYSTEM_COMPACT": "SYSTEM",
            "_SWARM_MODEL": "mock-model",
            "_canon_env": types.SimpleNamespace(
                payload_digest=lambda data: hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest(),
                emit_envelope=lambda **kw: {"scope": "TEST_ONLY", "params": kw},
            ),
        }
        exec(CODE, globals_dict)
        self.run_collaboration = globals_dict["_platform_run_collaboration"]

    def execute(self, live):
        self.run_collaboration("task-1", "bounded read-only experiment", "analysis", live=live)
        events = list(self.events.queue)
        self.assertIsNone(events[-1], "SSE must close with sentinel")
        return events

    def test_clean_template_has_linked_evidence_and_receipt(self):
        events = self.execute(live=False)
        self.assertEqual(events[-2]["type"], "completion")
        result = self.stored["task-1"]["result"]
        self.assertIs(result["chain_valid"], True)
        self.assertEqual(result["audit_chain_hash"], "a" * 64)
        self.assertEqual(result["departments_collaborated"], 2)
        self.assertEqual(result["execution_id"], "task-1")
        self.assertEqual(result["chain_verification_scope"], "in_process_sha256_linkage_only")
        self.assertEqual(result["envelope"]["scope"], "TEST_ONLY")
        self.assertEqual(self.calls.count("paid_model_call_mock"), 0)

    def test_corrupt_preflight_blocks_before_mock_inference_and_writes(self):
        self.checks = [False]
        events = self.execute(live=True)
        self.assertEqual(events[-2]["type"], "error")
        self.assertIn("PREFLIGHT_DENIED", self.stored["task-1"]["error"])
        self.assertIsNone(self.stored["task-1"]["result"])
        for forbidden in ("paid_model_call_mock", "fitness_storage", "cycle_storage", "grace_storage"):
            self.assertNotIn(forbidden, self.calls)

    def test_corrupt_preflight_blocks_demo_side_effects(self):
        self.checks = [False]
        events = self.execute(live=False)
        self.assertEqual(events[-2]["type"], "error")
        self.assertNotIn("fitness_storage", self.calls)

    def test_clean_live_mock_records_only_claimed_outputs(self):
        events = self.execute(live=True)
        self.assertEqual(events[-2]["type"], "completion")
        self.assertEqual(self.calls.count("paid_model_call_mock"), 1)
        self.assertEqual([e["type"] for e in events[:-1]].count("agent_event"), 2)
        self.assertEqual(self.stored["task-1"]["result"]["departments_collaborated"], 2)

    def test_midrun_corruption_has_zero_persistent_writes(self):
        self.fitness_corrupts = True
        events = self.execute(live=True)
        self.assertEqual(events[-2]["type"], "error")
        self.assertIn("VALIDATION_FAILED", self.stored["task-1"]["error"])
        self.assertIsNone(self.stored["task-1"]["result"])
        for forbidden in ("fitness_storage", "cycle_storage", "grace_storage"):
            self.assertNotIn(forbidden, self.calls, "Corrupted chain must never commit " + forbidden)

    def test_midrun_corruption_demo_has_zero_persistent_writes(self):
        self.fitness_corrupts = True
        self.execute(live=False)
        self.assertIn("VALIDATION_FAILED", self.stored["task-1"]["error"])
        for forbidden in ("fitness_storage", "cycle_storage", "grace_storage"):
            self.assertNotIn(forbidden, self.calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
