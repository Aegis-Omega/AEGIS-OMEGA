# Relational Gate + Status Journal Foundation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the existing zero-discretion research gate layer with deterministic late-bound relation binding and append-only claim-status history without introducing collision-specific semantics.

**Architecture:** Reuse `GateReceipt`, canonical hashing, and `AdmissionController` from #320. A relation is a role-bound set of already-hashed participants whose deterministic digest becomes the `object_digest` for ordinary gate/admission receipts. Status history is a hash-chained immutable journal whose transitions bind previous/next status, evidence digests, criterion epoch, reason, and previous transition digest.

**Tech Stack:** Python 3.11 standard library, `dataclasses`, `hashlib`, `unittest`, existing AEGIS canonical JSON/hash helpers.

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

Append:

```python
def test_relation_binding_is_order_stable_but_role_sensitive(self):
    a = "a" * 64
    b = "b" * 64
    first = ri.bind_relation("basis-against-gamma-v1", {"basis": a, "gamma": b})
    reordered = ri.bind_relation("basis-against-gamma-v1", {"gamma": b, "basis": a})
    swapped_roles = ri.bind_relation("basis-against-gamma-v1", {"basis": b, "gamma": a})
    self.assertEqual(first.relation_digest, reordered.relation_digest)
    self.assertNotEqual(first.relation_digest, swapped_roles.relation_digest)


def test_relation_binding_rejects_invalid_material(self):
    digest = "a" * 64
    with self.assertRaises(ValueError):
        ri.bind_relation("", {"left": digest})
    with self.assertRaises(ValueError):
        ri.bind_relation("x", {})
    with self.assertRaises(ValueError):
        ri.bind_relation("x", {"": digest})
    with self.assertRaises(ValueError):
        ri.bind_relation("x", {"left": "not-a-digest"})
```

- [ ] **Step 2: Run and verify RED**

```bash
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

Expected: FAIL because `bind_relation`/`RelationBindingV1` do not exist.

- [ ] **Step 3: Implement deterministic relation binding**

Add:

```python
@dataclass(frozen=True)
class RelationBindingV1:
    relation_id: str
    participants: Mapping[str, str]
    relation_digest: str


def bind_relation(
    relation_id: str,
    participants: Mapping[str, str],
) -> RelationBindingV1:
    if not relation_id:
        raise ValueError("relation_id must be non-empty")
    if not participants:
        raise ValueError("relation requires at least one participant")
    normalized: dict[str, str] = {}
    for role, digest in participants.items():
        role = str(role)
        if not role:
            raise ValueError("relation participant role must be non-empty")
        _check_digest(digest, f"participant[{role}]")
        normalized[role] = digest
    ordered = dict(sorted(normalized.items()))
    material = {
        "schema": "AEGIS_RELATION_BINDING_V1",
        "relation_id": relation_id,
        "participants": ordered,
    }
    return RelationBindingV1(
        relation_id=relation_id,
        participants=ordered,
        relation_digest=sha256_hex(material),
    )
```

- [ ] **Step 4: Verify GREEN**

```bash
python -m py_compile sovereign-omega-v2/python/research_invariants.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

- [ ] **Step 5: Commit**

```bash
git add sovereign-omega-v2/python/research_invariants.py sovereign-omega-v2/python/tests/test_research_invariants.py
git commit -m "feat(research): add deterministic relation binding"
```

---

### Task 2: Bind late relational checks to ordinary GateReceipts

**Files:**
- Modify: `sovereign-omega-v2/python/research_invariants.py`
- Test: `sovereign-omega-v2/python/tests/test_research_invariants.py`

**Interfaces:**
- Consumes: `RelationBindingV1.relation_digest`, existing `GateReceipt`, `_receipt`, `AdmissionController.admit`.
- Produces: `relation_gate_receipt(...) -> GateReceipt`.

- [ ] **Step 1: Write RED test for the public helper and anti-splicing**

```python
def test_relation_gate_receipt_admits_only_exact_relation(self):
    a, b, c = "a" * 64, "b" * 64, "c" * 64
    exact = ri.bind_relation("x-against-y-v1", {"x": a, "y": b})
    changed = ri.bind_relation("x-against-y-v1", {"x": a, "y": c})
    receipt = ri.relation_gate_receipt(
        gate_id="relation-check",
        relation=exact,
        verdict=ri.GateVerdict.PASS,
        observation={"matched": True},
    )
    ticket = ri.AdmissionController.admit(
        stage_id="relational-stage",
        subject_digest=exact.relation_digest,
        required_gate_ids=["relation-check"],
        receipts=[receipt],
    )
    self.assertEqual(ticket.subject_digest, exact.relation_digest)
    with self.assertRaises(PermissionError):
        ri.AdmissionController.admit(
            stage_id="relational-stage",
            subject_digest=changed.relation_digest,
            required_gate_ids=["relation-check"],
            receipts=[receipt],
        )
```

- [ ] **Step 2: Run and verify RED**

Expected: FAIL because `relation_gate_receipt` does not exist.

- [ ] **Step 3: Implement public relational receipt helper**

```python
def relation_gate_receipt(
    *,
    gate_id: str,
    relation: RelationBindingV1,
    verdict: GateVerdict,
    observation: Mapping[str, Any],
    gate_version: str = "1",
) -> GateReceipt:
    started_ns = time.perf_counter_ns()
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

Do not modify `AdmissionController`; its existing exact-subject anti-splicing rule is the authority boundary.

- [ ] **Step 4: Run inherited tests**

```bash
python -m py_compile sovereign-omega-v2/python/research_invariants.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

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
- Produces: `StatusTransitionV1`, `StatusJournalV1.append(...)`, `StatusJournalV1.verify(...)`, `StatusJournalV1.current_status`, immutable `history` tuple.

- [ ] **Step 1: Write RED promotion/demotion tests**

```python
def test_status_journal_preserves_promotion_and_demotion_history(self):
    journal = ri.StatusJournalV1("claim-1")
    first = journal.append(
        next_status="CROSS_REGISTRY_COLLISION",
        evidence_receipt_digests=["a" * 64],
        criterion_sha256="c" * 64,
        reason="exact external mappings",
    )
    second = journal.append(
        next_status="OBSERVED",
        evidence_receipt_digests=["b" * 64],
        criterion_sha256="c" * 64,
        reason="corrected criterion demotion",
    )
    self.assertEqual(journal.current_status, "OBSERVED")
    self.assertEqual(len(journal.history), 2)
    self.assertEqual(second.previous_transition_sha256, first.transition_sha256)
    self.assertTrue(ri.StatusJournalV1.verify(journal.history))
```

- [ ] **Step 2: Write RED tamper test**

```python
def test_status_journal_replay_detects_tampering(self):
    from dataclasses import replace
    journal = ri.StatusJournalV1("claim-1")
    transition = journal.append(
        next_status="OBSERVED",
        evidence_receipt_digests=["a" * 64],
        criterion_sha256="c" * 64,
        reason="initial observation",
    )
    tampered = replace(transition, reason="rewritten history")
    self.assertFalse(ri.StatusJournalV1.verify([tampered]))
```

- [ ] **Step 3: Implement exact transition object and journal**

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
        if not next_status:
            raise ValueError("next_status must be non-empty")
        if not reason:
            raise ValueError("reason must be non-empty")
        evidence = tuple(evidence_receipt_digests)
        for digest in evidence:
            _check_digest(digest, "evidence_receipt_digest")
        if criterion_sha256 is not None:
            _check_digest(criterion_sha256, "criterion_sha256")
        previous = self._history[-1] if self._history else None
        previous_status = previous.next_status if previous else None
        previous_sha = previous.transition_sha256 if previous else None
        material = {
            "schema": "AEGIS_STATUS_TRANSITION_V1",
            "claim_id": self._claim_id,
            "previous_status": previous_status,
            "next_status": next_status,
            "evidence_receipt_digests": evidence,
            "criterion_sha256": criterion_sha256,
            "reason": reason,
            "previous_transition_sha256": previous_sha,
        }
        transition = StatusTransitionV1(
            claim_id=self._claim_id,
            previous_status=previous_status,
            next_status=next_status,
            evidence_receipt_digests=evidence,
            criterion_sha256=criterion_sha256,
            reason=reason,
            previous_transition_sha256=previous_sha,
            transition_sha256=sha256_hex(material),
        )
        self._history.append(transition)
        return transition

    @staticmethod
    def verify(history: Sequence[StatusTransitionV1]) -> bool:
        previous: StatusTransitionV1 | None = None
        for transition in history:
            if previous is None:
                if transition.previous_status is not None or transition.previous_transition_sha256 is not None:
                    return False
            else:
                if transition.claim_id != previous.claim_id:
                    return False
                if transition.previous_status != previous.next_status:
                    return False
                if transition.previous_transition_sha256 != previous.transition_sha256:
                    return False
            material = {
                "schema": "AEGIS_STATUS_TRANSITION_V1",
                "claim_id": transition.claim_id,
                "previous_status": transition.previous_status,
                "next_status": transition.next_status,
                "evidence_receipt_digests": transition.evidence_receipt_digests,
                "criterion_sha256": transition.criterion_sha256,
                "reason": transition.reason,
                "previous_transition_sha256": transition.previous_transition_sha256,
            }
            if sha256_hex(material) != transition.transition_sha256:
                return False
            previous = transition
        return True
```

- [ ] **Step 4: Add validation tests**

Assert empty `claim_id`, empty `next_status`, empty `reason`, malformed evidence digest, and malformed criterion digest all raise `ValueError`.

- [ ] **Step 5: Run compile + inherited suite**

```bash
python -m py_compile sovereign-omega-v2/python/research_invariants.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
```

- [ ] **Step 6: Commit**

```bash
git add sovereign-omega-v2/python/research_invariants.py sovereign-omega-v2/python/tests/test_research_invariants.py
git commit -m "feat(research): add append-only status journal"
```

---

### Task 4: Wire foundation into CI/docs and exact-head verification

**Files:**
- Modify: `.github/workflows/zero-discretion-type-gates.yml`
- Modify: `docs/research/zero-discretion-type-gates-v1.md`

**Interfaces:**
- Consumes: Tasks 1-3.
- Produces: offline CI coverage and documented authority boundary.

- [ ] **Step 1: Extend the research-gate document**

Add these exact semantics: relation digests are role-bound; relational receipts reuse `GateReceipt`; `AdmissionController` remains the anti-splicing authority; status history is append-only and can contain demotions; a transition receipt proves only that a transition was recorded under the bound evidence, not the underlying scientific claim; execution timing is non-authoritative.

- [ ] **Step 2: Keep CI deterministic**

No network calls. Preserve Python 3.11 and the existing commands. The workflow path filter already covers `research_invariants.py`, its tests, the research doc, and itself; change it only if inspection proves a required path is absent.

- [ ] **Step 3: Run the local workflow equivalent**

```bash
python -m py_compile \
  sovereign-omega-v2/python/research_invariants.py \
  sovereign-omega-v2/python/research_preflight.py
python sovereign-omega-v2/python/tests/test_research_invariants.py
python sovereign-omega-v2/python/research_preflight.py --n-f 16 --h 3.5 --target-gamma-max 14.13
set +e
python sovereign-omega-v2/python/research_preflight.py --n-f 12 --h 3.5 --target-gamma-max 14.13
rc=$?
set -e
test "$rc" -eq 2
```

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/zero-discretion-type-gates.yml docs/research/zero-discretion-type-gates-v1.md
git commit -m "docs(ci): attest relational research semantics"
```

- [ ] **Step 5: Exact-head verification**

Resolve the final SHA after all commits. Inspect the hosted workflow bound to that exact SHA. Ancestor GREEN does not count. Classify hosted failures as code/test versus infrastructure before any completion claim.
