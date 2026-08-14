from __future__ import annotations

from hashlib import sha256
from pathlib import Path
import sys
import unittest

FRONTIER_DIR = Path(__file__).resolve().parents[1] / "frontier"
sys.path.insert(0, str(FRONTIER_DIR))

from stream_lease import StreamLeaseError, open_stream_lease, verify_stream_event  # noqa: E402
from work_order import ProofCarryingWorkOrder, WorkOrderError, verify_work_order  # noqa: E402


HEX0 = "0" * 64
HEX1 = "1" * 64


def order(**overrides):
    values = dict(
        work_order_id="wo-00000001",
        request_id="req-00000001",
        provider="openai",
        capability="inference.run",
        consequence_class="D3",
        arguments_digest=HEX0,
        expected_parent_state_root=HEX1,
        idempotency_key="idem-00000001",
        max_cost_microusd=250000,
        max_input_tokens=1000,
        max_output_tokens=1000,
        evidence_references=("receipt://evidence/1",),
        operator_approval_reference="approval://operator/1",
        secret_references=("secret://openai/aegisomega",),
        issued_sequence=7,
    )
    values.update(overrides)
    return ProofCarryingWorkOrder(**values)


class WorkOrderTests(unittest.TestCase):
    def test_valid_work_order_is_deterministic(self):
        first = verify_work_order(order())
        second = verify_work_order(order())
        self.assertEqual(first.digest, second.digest)

    def test_d3_requires_operator_approval(self):
        with self.assertRaises(WorkOrderError):
            verify_work_order(order(operator_approval_reference=None))

    def test_d4_is_denied(self):
        with self.assertRaises(WorkOrderError):
            verify_work_order(order(consequence_class="D4"))

    def test_d2_plus_requires_evidence(self):
        with self.assertRaises(WorkOrderError):
            verify_work_order(order(consequence_class="D2", operator_approval_reference=None, evidence_references=()))

    def test_inline_secret_material_is_rejected(self):
        with self.assertRaises(WorkOrderError):
            verify_work_order(order(secret_references=("sk-live-should-not-be-here",)))

    def test_provider_binding_mismatch_is_rejected(self):
        verified = verify_work_order(order())
        with self.assertRaises(WorkOrderError):
            verified.assert_matches(provider="anthropic", capability="inference.run", request_id="req-00000001")


class StreamLeaseTests(unittest.TestCase):
    def test_stream_owner_and_sequence_advance_under_same_fence(self):
        lease = open_stream_lease("exec-1", "operator:tarik", generation=2)
        next_lease = verify_stream_event(
            lease,
            execution_id="exec-1",
            owner_identity="operator:tarik",
            generation=2,
            fencing_token=lease.fencing_token,
            sequence=0,
        )
        self.assertEqual(next_lease.last_sequence, 0)

    def test_wrong_owner_is_rejected(self):
        lease = open_stream_lease("exec-1", "operator:tarik", generation=2)
        with self.assertRaises(StreamLeaseError):
            verify_stream_event(
                lease,
                execution_id="exec-1",
                owner_identity="agent:x",
                generation=2,
                fencing_token=lease.fencing_token,
                sequence=0,
            )

    def test_stale_generation_is_rejected(self):
        lease = open_stream_lease("exec-1", "operator:tarik", generation=3)
        with self.assertRaises(StreamLeaseError):
            verify_stream_event(
                lease,
                execution_id="exec-1",
                owner_identity="operator:tarik",
                generation=2,
                fencing_token=lease.fencing_token,
                sequence=0,
            )

    def test_non_monotone_sequence_is_rejected(self):
        lease = open_stream_lease("exec-1", "operator:tarik", generation=1)
        lease = verify_stream_event(
            lease,
            execution_id="exec-1",
            owner_identity="operator:tarik",
            generation=1,
            fencing_token=lease.fencing_token,
            sequence=0,
        )
        with self.assertRaises(StreamLeaseError):
            verify_stream_event(
                lease,
                execution_id="exec-1",
                owner_identity="operator:tarik",
                generation=1,
                fencing_token=lease.fencing_token,
                sequence=0,
            )


if __name__ == "__main__":
    unittest.main()
