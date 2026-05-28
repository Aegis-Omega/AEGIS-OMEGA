---
name: spec-compliance
description: Automatically invoked when a new module is being written, when an existing module is being modified, or when the user asks whether something conforms to the specification. Checks that the implementation matches the frozen spec before the code is committed.
---

# Specification Compliance Skill

**Metacognitive Layer: L3 (Working Memory) + L4 (Long-term Memory)**

Spec compliance is the L3↔L4 bridge: holding the active implementation in working memory (L3) and checking it against the frozen specification in long-term memory (L4). The specification is not advisory — it is the constitutional constraint the implementation must satisfy. A module that exceeds its specification is not better; it is out of bounds.

L3 invariant: **Hold the specific module's guarantee boundary in working memory throughout implementation. If you cannot state the exact guarantee boundary from memory, read the spec before writing a line of code.**
L4 invariant: **The specification is long-term memory. The implementation is working memory. Long-term memory is authoritative. Working memory is provisional. When they conflict: fix working memory, never the spec.**

Non-equivalence: **"Stronger implementation" ≠ "Spec-compliant". Claiming stronger guarantees than the spec is a T0 violation — it introduces unverifiable adaptive capability.**

When invoked, check the proposed or completed implementation against the frozen specification.

The canonical specification is docs/SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md.
The implementation brief is docs/SOVEREIGN_OMEGA_IMPL_BRIEF_Qwen.md.

For each module being written or modified, verify the following:

The module's guarantee boundary matches what the spec states. If the spec says a property
holds only under explicit assumptions, the implementation must document those same
assumptions. The implementation must not claim stronger guarantees than the spec.

The module uses the correct statistical method. E4 uses empirical Bernstein bounds,
not Hoeffding. If Hoeffding appears anywhere in gate logic, flag it as a spec violation.

Version mismatches abort rather than fall back. Any RuntimeVersionPin validation
path that silently uses a default version is a spec violation.

The trust partitioning is correct. V4 and V5 verifiers must never contribute to VCG
calibration or gate decisions. If advisory verifier output reaches the calibration loop,
flag it as a spec violation.

Report compliance as:
SPEC COMPLIANCE: [module] — COMPLIANT / NON-COMPLIANT
Non-compliant items: [list each violation with spec section reference]
