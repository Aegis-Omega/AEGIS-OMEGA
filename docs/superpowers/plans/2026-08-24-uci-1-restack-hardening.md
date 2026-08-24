# UCI-1 Core Restack and Validator Hardening Plan

Date: 2026-08-24
Status: EXECUTION
Base: `integration/effect-chain-main-a34d@1406aacca95fef02a942621a7060e0b6b14a5809`
Heritage source: `feat/uci-1-collective-work-contract-v1@56c69bd76b22f1a25d543b216bba74f1abc9c8cc`
Original authoring/design parent: `main@32b7eb6a37fb69d19dd80189390b6641c5004ef1`
PR #309 status: OPEN / NOT ADMITTED

## Goal

Restack only the bounded UCI-1 collective-work contract surface on the open PR #309
base, remove unrelated UCI-2/UCI-3/math/formal/metacognition/reflexive history, and
close runtime/schema boundary gaps before publishing a stacked pull request. The base
commit does not establish admission of PR #309; if admitted, PR #309 supersedes only
the old PR #268 -> #270 -> #272 -> #273 effect-chain integration route.

## Frozen scope

- Keep the 10 UCI-1 executable/schema/test/vector files and the two historical design/plan files.
- Do not include an experiment-admission plan; its original parent binding is stale for this restack.
- Do not modify PR #309 effect-chain files, frozen constitutional files, production wiring, or authority state.
- UCI-1 validates declarations only. It does not authorize, execute, observe effects, issue receipts, or admit state.
- This is a UCI-1-only restack; every later UCI lane and the experiment plan are excluded.
- No AGI, universal-intelligence, Riemann Hypothesis (RH), mathematical-proof,
  production-capability, production-deployment, or repository-admission claim is promoted.

## Task 1 — Heritage extraction and provenance reconciliation

- Restack the exact UCI-1 core commits on the base above.
- Preserve the original design parent as historical provenance.
- Record the current restack base and the excluded semantic lanes in the design and implementation plan.
- Verify that the final diff contains no UCI-2/UCI-3/math/formal/metacognition/reflexive or experiment-plan artifact.

## Task 2 — Runtime/schema boundary hardening (TDD)

Add failing adversarial tests first for:

- sparse arrays;
- non-plain/accessor-bearing records;
- present-but-`undefined` optional fields;
- strings above the schema's 512-character bound;
- unsafe or negative-zero integer budgets/epochs;
- mutation of caller input after successful validation.

Then minimally update the validator so accepted values are plain JSON-like data,
runtime string/integer bounds match the schemas, and successful results return an
independent deeply frozen snapshot. Preserve deterministic error ordering and use
repository-standard `.js` import suffixes. Add no dependency and no authority behavior.

## Task 3 — Exact-head verification and publication

Run, in order:

1. frozen hash verification;
2. Gate 1;
3. focused UCI-1 contract/schema/vector tests twice where determinism is claimed;
4. Gate 8 full tests, typecheck, and build;
5. Automaton-3 and claims validation relevant to the stacked base;
6. clean-diff and exact-head checks.

Publish only to a new branch and a pull request stacked on PR #309. Do not merge while
the base PR has an unresolved required-check question.

## Failure criteria

- Any runtime/schema acceptance mismatch exercised by the new falsifiers.
- Any mutation/reference leak from a successful validation result.
- Any import from an excluded semantic lane.
- Any failure in the ordered gates.
- Any authority, execution, effect, receipt, admission, AGI, or formal-proof promotion.
