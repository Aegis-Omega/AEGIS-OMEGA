# Relational Gate + Status Journal Foundation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing zero-discretion research gate layer with deterministic late-bound relation binding and append-only claim-status history without introducing collision-specific semantics.

**Architecture:** Reuse `GateReceipt`, canonical hashing, and `AdmissionController` from #320. A relation is a role-bound set of already-hashed participants whose own deterministic digest becomes the `object_digest` for ordinary gate/admission receipts. Status history is a hash-chained immutable journal whose transitions bind previous/next status, evidence digests, criterion epoch, reason, and previous transition digest.

**Tech Stack:** Python 3.11 standard library, `dataclasses`, `enum`, `hashlib`, `unittest`, existing AEGIS canonical JSON/hash helpers.

**Spec:** `docs/superpowers/specs/2026-08-25-cross-domain-collision-v1-design.md`

## Global Constraints

- Parent source semantics are `research/zero-discretion-type-gates-v1@85ceacf48d34dfe3a4dba81f7bb5cb027fb38db3`.
- This layer is generic research governance; it MUST contain no Unicode, NCBI, integer-collision, or null-model business logic.
- All semantic digests are deterministic and exclude wall-clock/performance timing.
- Missing, malformed, stale, role-spliced, or unsupported evidence fails closed.
- Existing #320 tests and admission behavior MUST remain green.
- No merge/deploy/runtime mutation authority is added.

---

### Task 1: Add role-bound relation identity

**Files:**
- Modify: `sovereign-omega-v2/python/research_invariants.py`
- Test: `sovereign-omega-v2/python/tests/test_research_invariants.py`

**Interfaces:**
- Consumes: existing `sha256_hex`, `_check_digest`.
- Produces: `RelationBindingV1`, `bind_relation(relation_id: str, participants: Mapping[str, str]) -> RelationBindingV1`.

- [ ] **Step 1: Write failing relation identity tests**

Append tests equivalent to:

```python
def test_relation_binding_is_order_stable_but_role_sensitive(self):
    a = "a" * 64
    b = "b" * 64
    first = ri.bind_relation("basis-against-gamma-v1", {"basis": a, "gamma": b})
    reordered = ri.bind_relation("basis-against-gamma-v1", {"gamma": b, "basis": a})
    swapped_roles = ri.bind_relation("basis-against-gamma-v1", {"basis": b, "gamma": a})
    self.assertEqual(first.relation_digest, reordered.relation_digest)
    self.assertNotEqual(first.relation_digest, swapped_roles.relation_digest)


def test_relation_binding_rejects_duplicate_or_invalid_roles(self):
    digest = "a" * 64
    with self.assertRaises(ValueError):
        ri.bind_relation("", {"left": digest})
    with self.assertRaises(ValueError):
        ri.bind_relation("x", {})
    with self.assertRaises(ValueError):
        ri.bind_relation("x", {"": digest})
```

- [ ] **Step 2: Run the targeted tests and verify RED**

Run:

```bash
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

Expected: FAIL because `bind_relation`/`RelationBindingV1` do not exist.

- [ ] **Step 3: Implement minimal deterministic relation binding**

Add:

```python
@dataclass(frozen=True)
class RelationBindingV1:
    relation_id: str
    participants: Mapping[str, str]
    relation_digest: str


def bind_relation(relation_id: str, participants: Mapping[str, str]) -> RelationBindingV1:
    if not relation_id:
        raise ValueError("relation_id must be non-empty")
    if not participants:
        raise ValueError("relation requires at least one participant")
    normalized: dict[str, str] = {}
    for role, digest in participants.items():
        if not role:
            raise ValueError("relation participant role must be non-empty")
        if role in normalized:
            raise ValueError(f"duplicate relation role: {role}")
        _check_digest(digest, f"participant[{role}]")
        normalized[str(role)] = digest
    material = {
        "schema": "AEGIS_RELATION_BINDING_V1",
        "relation_id": relation_id,
        "participants": normalized,
    }
    return RelationBindingV1(
        relation_id=relation_id,
        participants=dict(sorted(normalized.items())),
        relation_digest=sha256_hex(material),
    )
```

Do not add timestamps or mutable metadata.

- [ ] **Step 4: Run the entire inherited gate regression suite**

```bash
python -m py_compile sovereign-omega-v2/python/research_invariants.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

Expected: all prior tests plus relation tests PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/python/research_invariants.py sovereign-omega-v2/python/tests/test_research_invariants.py
git commit -m "feat(research): add deterministic relation binding"
```

---

### Task 2: Admit late-bound relational gate receipts without a second receipt system

**Files:**
- Modify: `sovereign-omega-v2/python/research_invariants.py`
- Test: `sovereign-omega-v2/python/tests/test_research_invariants.py`

**Interfaces:**
- Consumes: `RelationBindingV1.relation_digest`, existing `GateReceipt`, existing `AdmissionController.admit`.
- Produces: convention that relational gates bind `GateReceipt.object_digest == relation.relation_digest`; no new authority receipt class.

- [ ] **Step 1: Add RED tests for relation anti-splicing**

```python
def test_admission_accepts_receipt_bound_to_exact_relation(self):
    a = "a" * 64
    b = "b" * 64
    relation = ri.bind_relation("x-against-y-v1", {"x": a, "y": b})
    receipt = ri._receipt(
        gate_id="relation-check",
        type_signature="RelationBindingV1",
        object_digest=relation.relation_digest,
        verdict=ri.GateVerdict.PASS,
        observation={"matched": True},
        started_ns=0,
    )
    ticket = ri.AdmissionController.admit(
        stage_id="relational-stage",
        subject_digest=relation.relation_digest,
        required_gate_ids=["relation-check"],
        receipts=[receipt],
    )
    self.assertEqual(ticket.subject_digest, relation.relation_digest)


def test_admission_rejects_receipt_from_different_counterpart(self):
    a, b, c = "a" * 64, "b" * 64, "c" * 64
    old = ri.bind_relation("x-against-y-v1", {"x": a, "y": b})
    new = ri.bind_relation("x-against-y-v1", {"x": a, "y": c})
    receipt = ri._receipt(
        gate_id="relation-check",
        type_signature="RelationBindingV1",
        object_digest=old.relation_digest,
        verdict=ri.GateVerdict.PASS,
        observation={"matched": True},
        started_ns=0,
    )
    with self.assertRaises(PermissionError):
        ri.AdmissionController.admit(
            stage_id="relational-stage",
            subject_digest=new.relation_digest,
            required_gate_ids=["relation-check"],
            receipts=[receipt],
        )
```

- [ ] **Step 2: Run tests and verify the intended behavior**

Run the suite. If the first test already passes because generic admission is sufficient, keep that as evidence that no implementation change is needed. The second MUST fail closed. Do not add redundant production abstractions merely to make a diff.

- [ ] **Step 3: Add only the minimal public helper needed by downstream code**

If direct use of private `_receipt` is the only gap, expose:

```python
def relation_gate_receipt(
    *,
    gate_id: str,
    relation: RelationBindingV1,
    verdict: GateVerdict,
    observation: Mapping[str, Any],
    started_ns: int,
    gate_version: str = "1",
) -> GateReceipt:
    return _receipt(
        gate_id=gate_id,
        type_signature="RelationBindingV1",
        object_digest=relation.relation_digest,
        verdict=verdict,
        observation=observation,
        started_ns=started_ns,
        gate_version=gate_version,
    )
```

Do not modify `AdmissionController` unless a failing test proves it is necessary.

- [ ] **Step 4: Verify full gate suite**

```bash
python -m py_compile sovereign-omega-v2/python/research_invariants.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/python/research_invariants.py sovereign-omega-v2/python/tests/test_research_invariants.py
git commit -m "feat(research): bind late relational gate receipts"
```

---

### Task 3: Add hash-chained append-only status transitions

**Files:**
- Modify: `sovereign-omega-v2/python/research_invariants.py`
- Test: `sovereign-omega-v2/python/tests/test_research_invariants.py`

**Interfaces:**
- Consumes: `sha256_hex`, `_check_digest`.
- Produces: `StatusTransitionV1`, `StatusJournalV1.append(...)`, `StatusJournalV1.current_status`, immutable `history` tuple.

- [ ] **Step 1: Write RED tests for promotion, demotion, and history integrity**

```python
def test_status_journal_preserves_promotion_and_demotion_history(self):
    evidence_a = "a" * 64
    evidence_b = "b" * 64
    epoch = "c" * 64
    journal = ri.StatusJournalV1("claim-1")
    first = journal.append(
        next_status="CROSS_REGISTRY_COLLISION",
        evidence_receipt_digests=[evidence_a],
        criterion_sha256=epoch,
        reason="exact external mappings",
    )
    second = journal.append(
        next_status="OBSERVED",
        evidence_receipt_digests=[evidence_b],
        criterion_sha256=epoch,
        reason="corrected criterion demotion",
    )
    self.assertEqual(journal.current_status, "OBSERVED")
    self.assertEqual(len(journal.history), 2)
    self.assertEqual(second.previous_transition_sha256, first.transition_sha256)


def test_status_transition_hash_changes_if_reason_or_evidence_changes(self):
    epoch = "c" * 64
    a = ri.StatusJournalV1("claim-1")
    b = ri.StatusJournalV1("claim-1")
    ta = a.append("OBSERVED", ["a" * 64], epoch, "reason-a")
    tb = b.append("OBSERVED", ["a" * 64], epoch, "reason-b")
    self.assertNotEqual(ta.transition_sha256, tb.transition_sha256)
```

- [ ] **Step 2: Run suite and verify RED**

Expected: FAIL because journal classes do not exist.

- [ ] **Step 3: Implement transition and journal**

Use exact semantics:

```python
@dataclass(frozen=True)
class StatusTransitionV1:
    claim_id: str
    previous_status: str | None
    next_status: str
    evidence_receipt_digests: tuple[str, ...]
    criterion_sha256: str | None
    reason: str
    previous_transition_sha256: str | None
    transition_sha256: str


class StatusJournalV1:
    def __init__(self, claim_id: str):
        if not claim_id:
            raise ValueError("claim_id must be non-empty")
        self._claim_id = claim_id
        self._history: list[StatusTransitionV1] = []

    @property
    def history(self) -> tuple[StatusTransitionV1, ...]:
        return tuple(self._history)

    @property
    def current_status(self) -> str | None:
        return self._history[-1].next_status if self._history else None

    def append(
        self,
        next_status: str,
        evidence_receipt_digests: Sequence[str],
        criterion_sha256: str | None,
        reason: str,
    ) -> StatusTransitionV1:
        if not next_status or not reason:
            raise ValueError("next_status and reason must be non-empty")
        evidence = tuple(evidence_receipt_digests)
        for digest in evidence:
            _check_digest(digest, "evidence_receipt_digest")
        if criterion_sha256 is not None:
            _check_digest(criterion_sha256, "criterion_sha256")
        previous = self._history[-1] if self._history else None
        material = {
            "schema": "AEGIS_STATUS_TRANSITION_V1",
            "claim_id": self._claim_id,
            "previous_status": previous.next_status if previous else None,
            "next_status": next_status,
            "evidence_receipt_digests": evidence,
            "criterion_sha256": criterion_sha256,
            "reason": reason,
            "previous_transition_sha256": previous.transition_sha256 if previous else None,
        }
        transition = StatusTransitionV1(
            **material_without_schema,
            transition_sha256=sha256_hex(material),
        )
        self._history.append(transition)
        return transition
```

Implement explicitly rather than literally using undefined `material_without_schema`; construct the dataclass fields from `material`.

- [ ] **Step 4: Add replay verification**

Add `StatusJournalV1.verify(history: Sequence[StatusTransitionV1]) -> bool` or equivalent classmethod that recomputes every hash and previous-link. Add tests that mutating any copied transition field causes verification to return `False` or raise `ValueError`.

- [ ] **Step 5: Run compile + entire inherited test suite**

```bash
python -m py_compile sovereign-omega-v2/python/research_invariants.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add sovereign-omega-v2/python/research_invariants.py sovereign-omega-v2/python/tests/test_research_invariants.py
git commit -m "feat(research): add append-only status journal"
```

---

### Task 4: Wire foundational semantics into CI and document the authority boundary

**Files:**
- Modify: `.github/workflows/zero-discretion-type-gates.yml`
- Modify: `docs/research/zero-discretion-type-gates-v1.md`
- Test: `sovereign-omega-v2/python/tests/test_research_invariants.py`

**Interfaces:**
- Consumes: completed Task 1-3 APIs.
- Produces: exact-head CI coverage and documented relation/journal semantics.

- [ ] **Step 1: Extend the research-gate documentation**

Document these exact points: relation digests are role-bound; relational receipts reuse `GateReceipt`; admission remains generic; status transitions are append-only and may demote; transition history is evidence, not proof of the underlying claim; no wall-clock field is authority-bearing.

- [ ] **Step 2: Keep CI offline and deterministic**

Retain Python 3.11. Ensure workflow path filters include the modified test/module/docs. Add no external network calls. The existing regression command remains:

```bash
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

- [ ] **Step 3: Run local equivalent of workflow**

```bash
python -m py_compile \
  sovereign-omega-v2/python/research_invariants.py \
  sovereign-omega-v2/python/research_preflight.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
python sovereign-omega-v2/python/research_preflight.py --n-f 16 --h 3.5 --target-gamma-max 14.13
```

For the under-resolved case, verify exit code 2:

```bash
python sovereign-omega-v2/python/research_preflight.py --n-f 12 --h 3.5 --target-gamma-max 14.13; test $? -eq 2
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/zero-discretion-type-gates.yml docs/research/zero-discretion-type-gates-v1.md
git commit -m "docs(ci): attest relational research semantics"
```

- [ ] **Step 5: Exact-head verification before calling the foundation complete**

After push, resolve the new head SHA and inspect the workflow run bound to that exact SHA. Ancestor GREEN does not count. If hosted CI fails, classify code/test failure separately from infrastructure failure.
