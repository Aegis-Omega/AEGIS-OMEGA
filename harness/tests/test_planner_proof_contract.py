"""AEGIS causal system-building contracts: independent falsification tests.

No LLM, no provider, no network, no pre-authorized actions. These assertions
prevent descriptions or planner confidence from being mistaken for execution.
"""
from __future__ import annotations

import copy
import hashlib
import unittest

from harness.sdk.planner import (
    CausalChain, ConstraintType, KhattPhase, Nuqta, Planner, Task,
)


SEAL = "a" * 64


def plan():
    p = Planner(SEAL)
    chain = p.decompose_directive(
        "Build a research-analysis system from a validated specification",
        [ConstraintType.T0_GENESIS_SEAL, ConstraintType.DOMAIN_ISOLATION],
    )
    return p, chain


class PlannerProofContractTests(unittest.TestCase):
    def test_plan_is_digest_bound_but_not_self_authorizing(self):
        p, chain = plan()
        self.assertTrue(p.validate_chain(chain))
        self.assertEqual(chain.confidence, 0.0)
        self.assertEqual(
            chain.nuqta.hash, hashlib.sha256(chain.directive.encode()).hexdigest()
        )
        contract = p.compile_plan_contract(chain)
        self.assertEqual(contract["operational_admission"], "NOT_ADMITTED")
        self.assertFalse(contract["authority_granted"])
        self.assertEqual(contract["verified_constraints"], [])
        self.assertEqual(len(contract["tasks"]), 5)
        self.assertTrue(all(x["execution_state"] == "PENDING_INDEPENDENT_EVIDENCE" for x in contract["tasks"]))
        self.assertTrue(all(x["admission"] == "NOT_ADMITTED" for x in contract["tasks"]))
        self.assertEqual(contract["planner_genesis_reference"], SEAL)

    def test_requirements_are_explicit_and_default_false(self):
        p, chain = plan()
        alif = chain.tasks[1].metadata["alif_results"]
        self.assertEqual(alif["t0_genesis_seal"], False)
        self.assertEqual(alif["domain_isolation"], False)
        self.assertTrue(all(v is False for v in p.raise_alif(list(ConstraintType)).values()))

    def test_invalid_constraints_rejected(self):
        p = Planner(SEAL)
        with self.assertRaises(ValueError):
            p.decompose_directive("spec", ["agpl3_compliance"])
        with self.assertRaises(ValueError):
            p.raise_alif(["agpl3_compliance"])
        with self.assertRaises(ValueError):
            p.decompose_directive("spec", None)
        with self.assertRaises(ValueError):
            p.decompose_directive("", [])

    def test_digest_rejects_directive_tamper(self):
        p, chain = plan()
        chain.directive += " stealth mutation"
        self.assertFalse(chain.nuqta.verify(chain.directive))
        self.assertFalse(p.validate_chain(chain))
        with self.assertRaisesRegex(ValueError, "CAUSAL_CHAIN_INVALID"):
            p.compile_plan_contract(chain)

    def test_duplicate_task_and_dependency_rejected(self):
        p, chain = plan()
        chain.tasks[-1].id = chain.tasks[0].id
        self.assertFalse(p.validate_chain(chain))
        with self.assertRaises(ValueError):
            p.get_execution_plan(chain)
        p, chain = plan()
        chain.tasks[-1].dependencies = ["task_4", "task_4"]
        self.assertFalse(p.validate_chain(chain))

    def test_cycle_rejected_without_infinite_loop(self):
        p, chain = plan()
        chain.tasks[0].dependencies = ["task_5"]
        self.assertFalse(p.validate_chain(chain))
        with self.assertRaises(ValueError):
            p.get_execution_plan(chain)

    def test_future_dependency_invalid(self):
        p, chain = plan()
        chain.tasks[1].dependencies = ["task_4"]
        self.assertFalse(p.validate_chain(chain))

    def test_self_dependency_invalid(self):
        p, chain = plan()
        chain.tasks[2].dependencies = ["task_3"]
        self.assertFalse(p.validate_chain(chain))

    def test_inflated_confidence_is_not_evidence(self):
        p, chain = plan()
        chain.confidence = 0.95
        self.assertFalse(p.validate_chain(chain))

    def test_wrong_genesis_format_denied_not_falsely_verified(self):
        p, chain = plan()
        p.genesis_seal = "not-content-hash"
        self.assertFalse(p.validate_chain(chain))

    def test_plan_independent_of_task_storage_order(self):
        p, chain = plan()
        original = p.compile_plan_contract(chain)
        chain.tasks = list(reversed(chain.tasks))
        self.assertTrue(p.validate_chain(chain))
        self.assertEqual(original, p.compile_plan_contract(chain))

    def test_constraint_order_deterministic(self):
        a = Planner(SEAL).decompose_directive("Build service", [
            ConstraintType.DOMAIN_ISOLATION, ConstraintType.T0_GENESIS_SEAL
        ])
        b = Planner(SEAL).decompose_directive("Build service", [
            ConstraintType.T0_GENESIS_SEAL, ConstraintType.DOMAIN_ISOLATION
        ])
        # Only explicit normalized input order is canonicalized in execution plan.
        self.assertEqual(Planner(SEAL).compile_plan_contract(a)["contract_sha256"],
                         Planner(SEAL).compile_plan_contract(b)["contract_sha256"])

    def test_plan_source_change_changes_contract(self):
        p, chain = plan()
        a = p.compile_plan_contract(chain)
        q = Planner(SEAL)
        other = q.decompose_directive(chain.directive + " v2", chain.tasks[0].constraints)
        b = q.compile_plan_contract(other)
        self.assertNotEqual(a["contract_sha256"], b["contract_sha256"])

    def test_unobserved_registry_cannot_become_authority_from_plan(self):
        p, chain = plan()
        contract = p.compile_plan_contract(chain)
        self.assertNotIn("execution_verified", contract)
        self.assertFalse(contract["authority_granted"])


if __name__ == "__main__":
    unittest.main()
