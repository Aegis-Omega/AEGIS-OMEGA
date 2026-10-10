"""AEGIS proof-of-learning experiment: discover an evaluator-blind fault.

Unlike nine pre-registered mutations, a hidden path-specific bug survives the
static acceptance oracle. The active probe synthesizes a witness, delta-shrinks
it, persists the replay condition and verifies regression closure.
"""
from __future__ import annotations

import copy
import unittest

from harness.sdk.generator.counterexample_memory import (
    candidate_paths, discover, digest, probe_in_subprocess, replay,
)
from harness.sdk.generator.system_foundry import build_readonly_json_api
from harness.sdk.generator.oracle_mutation import _run_oracle


def blueprint():
    return {"system_id": "self-learning-service", "kind": "readonly-json-api",
            "routes": {"/health": {"alive": True}, "/count": {"n": 4}}}


def service():
    return next(a.content for a in build_readonly_json_api(blueprint())
                if a.path == "service.py")


def hidden_fault():
    original = service()
    target = (
        '    elif path not in ROUTES:\n'
        '        status, payload = "404 Not Found", {"error": "not_found"}'
    )
    mutated = (
        '    elif path not in ROUTES:\n'
        '        if path.startswith("/fuzz/") and path.endswith("zz"):\n'
        '            status, payload = "200 OK", {"error": "silent_contract_failure"}\n'
        '        else:\n'
        '            status, payload = "404 Not Found", {"error": "not_found"}'
    )
    assert original.count(target) == 1
    return original.replace(target, mutated)


class CounterexampleLearningTests(unittest.TestCase):
    def test_static_oracle_misses_hidden_fault(self):
        report = _run_oracle(hidden_fault(), blueprint(), 10)
        self.assertEqual(report["outcome"], "ORACLE_PASS")
        self.assertEqual(report["exit_code"], 0)

    def test_active_probe_finds_and_shrinks_hidden_fault(self):
        bp = blueprint()
        bad = hidden_fault()
        findings = discover(bp, bad, seed=12345, budget=120)
        self.assertEqual(findings["outcome"], "COUNTEREXAMPLE_DISCOVERED")
        self.assertEqual(findings["witness"]["method"], "GET")
        self.assertEqual(findings["witness"]["path"], "/fuzz/zz")
        self.assertTrue(findings["witness"]["failure_codes"])
        self.assertFalse(findings["authority_granted"])
        self.assertEqual(findings["admission"], "NOT_ADMITTED")
        self.assertEqual(findings["memory_sha256"], digest({
            "domain": findings["kind"],
            "body": {k: v for k, v in findings.items() if k != "memory_sha256"},
        }))

    def test_counterexample_replay_blocks_old_and_accepts_repaired_candidate(self):
        bp = blueprint()
        witness = discover(bp, hidden_fault(), seed=12345, budget=120)
        old = replay(bp, hidden_fault(), witness)
        clean = replay(bp, service(), witness)
        self.assertEqual(old["outcome"], "REGRESSION_PRESENT")
        self.assertTrue(old["observed_failures"])
        self.assertEqual(clean["outcome"], "WITNESS_NOW_PASSES")
        self.assertEqual(clean["observed_failures"], [])
        self.assertEqual(clean["memory_sha256"], old["memory_sha256"])
        self.assertFalse(clean["authority_granted"])

    def test_witness_tampering_and_spec_swap_denied(self):
        bp = blueprint()
        witness = discover(bp, hidden_fault(), seed=12345, budget=120)
        forged = copy.deepcopy(witness)
        forged["witness"]["path"] = "/health"
        with self.assertRaisesRegex(ValueError, "MEMORY_INTEGRITY"):
            replay(bp, service(), forged)
        bp["routes"]["/health"]["alive"] = False
        with self.assertRaisesRegex(ValueError, "MEMORY_INTEGRITY"):
            replay(bp, service(), witness)

    def test_clean_candidate_does_not_invent_memory(self):
        finding = discover(blueprint(), service(), seed=12345, budget=90)
        self.assertEqual(finding["outcome"], "NO_COUNTEREXAMPLE_FOUND")
        self.assertEqual(finding["coverage_claim"], "BOUNDED_PROBE_ONLY")
        self.assertNotIn("memory_sha256", finding)

    def test_seed_determinism_and_input_bounds(self):
        a = candidate_paths(blueprint(), seed=99, budget=120)
        b = candidate_paths(blueprint(), seed=99, budget=120)
        self.assertEqual(a, b)
        self.assertEqual(len(a), 120)
        self.assertEqual(len(set(a)), 120)
        for params in ({"seed": -1, "budget": 30},
                       {"seed": 0, "budget": 0},
                       {"seed": 0, "budget": 1000}):
            with self.assertRaises(ValueError):
                candidate_paths(blueprint(), **params)

    def test_requests_do_not_require_generated_self_tests(self):
        r = probe_in_subprocess(
            blueprint(), service(),
            [{"path": "/health", "method": "GET"},
             {"path": "/missing", "method": "GET"},
             {"path": "/health", "method": "POST"}]
        )
        self.assertEqual(r["kind"], "AEGIS_PROPERTY_PROBE_V1")
        self.assertEqual(len(r["observations"]), 3)
        self.assertTrue(all(not o["failures"] for o in r["observations"]))


if __name__ == "__main__":
    unittest.main()
