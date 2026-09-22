# Sanitized Sample Findings — Demo V1

| ID | Control point | Evidence observed | Finding state | What the state means | Remediation |
|---|---|---|---|---|---|
| F-01 | Notebook source-cell secret scan | Original tests exercise source-cell credential patterns | DEMONSTRATED_FAIL_CLOSED | For the tested source-cell patterns, the scanner flags the condition in the demonstrated cases | Preserve regression coverage |
| F-02 | Notebook output / attachment scan | Additional negative tests exercise surfaces outside the original scan path | DEMONSTRATED_FAIL_OPEN | In the demonstrated cases, sensitive-pattern content can exist on an uninspected surface without the expected distribution block | Expand scan coverage and add regression tests |
| F-03 | Whole-workflow production enforcement | No production deployment receipt is part of this demo | NOT_VERIFIED | Available evidence is insufficient to establish production behavior | Obtain bounded production/staging evidence before making a production claim |

## Interpretation rules

- Absence of evidence is **NOT_VERIFIED**, not automatically fail-open.
- Tamper evidence establishes record-integrity properties only; it does not independently establish prior authorization or outcome correctness.
- Findings apply only to the exact reviewed workflow, version, configuration, inputs, and tests.
