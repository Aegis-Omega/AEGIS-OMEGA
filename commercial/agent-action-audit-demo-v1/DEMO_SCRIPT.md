# 75-second Demo Script — Agent Action Boundary Audit

**0–10s — Problem**
A tool-using agent reaches a mutation point. The important question is not whether a policy document exists; it is whether the control behavior can be demonstrated.

**10–25s — Establish baseline**
We start from the buyer's existing workflow and tests. In this isolated notebook-evidence example, the original test suite passes. That is baseline evidence, not a platform-wide safety claim.

**25–42s — Negative testing**
We add controlled cases for surfaces the original scanner does not inspect. The new checks expose a bounded gap. The finding is tied to the exact component and evidence.

**42–58s — Remediation and verification**
A minimal correction expands the inspected surfaces. We rerun the expanded tests and retain the command output in the engineering appendix.

**58–68s — Findings model**
Every reviewed control is classified as demonstrated fail-closed, demonstrated fail-open, or not verified. Missing evidence is never silently promoted to safety.

**68–75s — Offer**
The Agent Action Boundary Audit applies this method to one tool-using workflow in your existing stack. Fixed fee: USD 3,000. Start with a 20-minute scoping call.

## Visual storyboard

1. Workflow graph → highlight one mutation point.
2. Existing test receipt → “baseline evidence”.
3. Inject controlled negative case.
4. Finding card → exact component, exact evidence, exact state.
5. Remediation diff.
6. Fresh verification receipt.
7. Engineering evidence appendix.
8. CTA card: “One workflow. USD 3,000 fixed fee.”
