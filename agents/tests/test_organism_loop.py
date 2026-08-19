from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from agents.organism import OrganismStore, OrganizationOrganism, WorkStatus


class FakeDispatcher:
    def __init__(self, *, valid: bool = True, raises: bool = False):
        self.valid = valid
        self.raises = raises
        self.calls: list[tuple[str, dict]] = []

    async def __call__(self, event_type: str, payload: dict):
        self.calls.append((event_type, payload))
        if self.raises:
            raise RuntimeError("dispatcher boom")
        return [SimpleNamespace(is_valid=self.valid, role=SimpleNamespace(value="engineering"))]


class OrganismLoopTests(unittest.TestCase):
    def make_org(self, dispatcher=None):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        path = Path(td.name) / "organism.json"
        store = OrganismStore(path)
        return path, OrganizationOrganism(store, dispatcher=dispatcher or FakeDispatcher())

    def test_submit_persists_and_survives_restart(self):
        path, org = self.make_org()
        org.submit("w1", "github_issue_opened", {"number": 1}, consequence_class="D1")
        restarted = OrganizationOrganism(OrganismStore(path), dispatcher=FakeDispatcher())
        self.assertEqual(restarted.get("w1").status, WorkStatus.QUEUED)

    def test_duplicate_work_id_is_idempotent(self):
        _, org = self.make_org()
        first = org.submit("w1", "market_opportunity", {"x": 1}, consequence_class="D1")
        second = org.submit("w1", "market_opportunity", {"x": 999}, consequence_class="D1")
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(len(org.orders()), 1)

    def test_d1_runs_without_operator_and_records_execution(self):
        dispatcher = FakeDispatcher(valid=True)
        _, org = self.make_org(dispatcher)
        org.submit("w1", "market_opportunity", {"market": "agentic-ai"}, consequence_class="D1")
        result = asyncio.run(org.tick())
        self.assertEqual(result.status, WorkStatus.EXECUTED)
        self.assertEqual(len(dispatcher.calls), 1)
        self.assertEqual(org.operator_inbox(), [])

    def test_d3_waits_for_operator_without_dispatch(self):
        dispatcher = FakeDispatcher()
        _, org = self.make_org(dispatcher)
        order = org.submit("w1", "deployment_event", {"service": "prod"}, consequence_class="D3")
        self.assertEqual(order.status, WorkStatus.WAITING_OPERATOR)
        self.assertIsNone(asyncio.run(org.tick()))
        self.assertEqual(dispatcher.calls, [])
        self.assertEqual([w.work_id for w in org.operator_inbox()], ["w1"])

    def test_d3_approval_requeues_then_executes(self):
        dispatcher = FakeDispatcher(valid=True)
        _, org = self.make_org(dispatcher)
        org.submit("w1", "deployment_event", {"service": "prod"}, consequence_class="D3")
        approved = org.approve("w1", approval_ref="operator:explicit-approval-001")
        self.assertTrue(approved)
        self.assertEqual(org.get("w1").status, WorkStatus.QUEUED)
        result = asyncio.run(org.tick())
        self.assertEqual(result.status, WorkStatus.EXECUTED)
        self.assertEqual(len(dispatcher.calls), 1)

    def test_d4_is_denied_and_cannot_be_approved(self):
        dispatcher = FakeDispatcher()
        _, org = self.make_org(dispatcher)
        order = org.submit("w1", "unknown_high_consequence", {}, consequence_class="D4")
        self.assertEqual(order.status, WorkStatus.DENIED)
        self.assertFalse(org.approve("w1", approval_ref="operator:anything"))
        self.assertEqual(dispatcher.calls, [])

    def test_dispatch_exception_retries_bounded_then_fails(self):
        dispatcher = FakeDispatcher(raises=True)
        _, org = self.make_org(dispatcher)
        org.submit("w1", "github_ci_failure", {"branch": "x"}, consequence_class="D1", max_attempts=2)
        first = asyncio.run(org.tick())
        self.assertEqual(first.status, WorkStatus.QUEUED)
        second = asyncio.run(org.tick())
        self.assertEqual(second.status, WorkStatus.FAILED)
        self.assertEqual(len(dispatcher.calls), 2)

    def test_invalid_agent_result_never_becomes_executed(self):
        dispatcher = FakeDispatcher(valid=False)
        _, org = self.make_org(dispatcher)
        org.submit("w1", "github_pr_opened", {"number": 2}, consequence_class="D1")
        result = asyncio.run(org.tick())
        self.assertEqual(result.status, WorkStatus.FAILED)

    def test_empty_dispatch_is_blocked_authority_not_success(self):
        async def empty_dispatch(_event_type, _payload):
            return []

        _, org = self.make_org(empty_dispatch)
        org.submit("w1", "github_pr_opened", {"number": 3}, consequence_class="D1")
        result = asyncio.run(org.tick())
        self.assertEqual(result.status, WorkStatus.BLOCKED_AUTHORITY)

    def test_hash_chain_tamper_fails_closed(self):
        path, org = self.make_org()
        org.submit("w1", "market_opportunity", {"x": 1}, consequence_class="D1")
        state = json.loads(path.read_text())
        state["journal"][0]["event_type"] = "TAMPERED"
        path.write_text(json.dumps(state))
        with self.assertRaises(ValueError):
            OrganismStore(path)

    def test_run_until_idle_processes_fifo(self):
        dispatcher = FakeDispatcher(valid=True)
        _, org = self.make_org(dispatcher)
        org.submit("w1", "github_issue_opened", {"number": 1}, consequence_class="D1")
        org.submit("w2", "github_issue_opened", {"number": 2}, consequence_class="D1")
        done = asyncio.run(org.run_until_idle(max_ticks=10))
        self.assertEqual([w.work_id for w in done], ["w1", "w2"])
        self.assertEqual([p[1]["number"] for p in dispatcher.calls], [1, 2])


if __name__ == "__main__":
    unittest.main()
