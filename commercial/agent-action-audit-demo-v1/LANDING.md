# AEGIS Agent Action Boundary Audit — Demo V1

Status: COMMERCIAL_DEMO_DRAFT
Price: USD 3,000 fixed fee
Scope: one tool-using workflow
Authority effect: NONE

## The question

When an agent reaches a mutation point, can your team demonstrate what happens when authority is missing, stale, or denied?

## What the audit returns

1. Authority surface map — the mutation points and controls in the reviewed workflow.
2. Pre-mutation approval review — whether consequential actions are bound to a prior approval decision.
3. Controlled failure-case checks — each reviewed control is recorded as:
   - DEMONSTRATED_FAIL_CLOSED
   - DEMONSTRATED_FAIL_OPEN
   - NOT_VERIFIED
4. Audit-record binding assessment — record integrity, action-to-approval binding, and outcome correctness are evaluated separately.
5. Prioritized findings with an engineering evidence appendix.

## Demonstration

The included demo uses an isolated notebook-evidence component. Existing tests pass, while additional negative tests expose notebook surfaces that the original scanner does not inspect. The demonstration then shows a bounded remediation and an expanded verification run.

This demonstrates the audit method on that component only. It does not establish platform-wide AEGIS safety, production enforcement, compliance certification, or customer results.

## Engagement boundary

- One workflow.
- No AEGIS adoption required.
- Production access is not required.
- Do not send credentials, private keys, customer records, or production secrets during initial scoping.
- Delivery target: five business days after written scope agreement, receipt of necessary evidence or staging access, and confirmation of an available delivery slot.
- Written scope and commercial terms are agreed before any payment step.

## CTA

Send a short description of one tool-using workflow and the highest-authority action it can perform. The next step is a 20-minute scoping call.
