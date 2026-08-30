# Gate Protocol Rules
## Applied to: all files
## Epistemic Tier: T0

The eight-gate build protocol is enforced in strict sequence. No gate may be
skipped, combined with another gate, or declared passing without running its
designated test command. The commands are specified in AGENTS.md.

If a gate fails, the agent must stop, report the failure in the format defined
in AGENTS.md, and wait for operator instruction. The agent must never attempt
to self-correct a gate failure by weakening the test, modifying the assertion,
or rewriting the module to pass without fixing the underlying issue.

Gate 1 is the foundation. If canonicalizeJCS produces different output for the
same input across any two environments, all subsequent gates are invalid. Gate 1
must pass completely before any other file is written or modified.

Gate 8 is the deployment gate. The command npm run test must exit with code 0.
A build that exits 0 on Gate 8 may proceed to vercel --prod. A build that has
not reached Gate 8 may not be deployed under any circumstances.

When reporting gate results, always include: the exact command run, the pass
count and any failure output, the decision to proceed or halt, and the reason
for that decision.
