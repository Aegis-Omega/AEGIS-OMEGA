# Operator action: require Automaton checks on `main`

Repository: `Aegis-Omega/AEGIS-OMEGA`  
Target: canonical branch `main` or its merge-queue ruleset

Required status-check contexts:

- `aegis / automaton-2`
- `aegis / automaton-3`

Recommended configuration:

- require branches to be up to date before merging;
- preserve every existing required check and review restriction;
- enable the same contexts for merge queue / `merge_group` evaluation;
- prohibit bypass except the existing emergency administrator path, with audit logging;
- do not mark Vercel account-rate-limit statuses as repository correctness gates.

Verification procedure:

1. Open repository Settings → Rules → Rulesets.
2. Select the active `main` branch ruleset.
3. Add both exact context names under required status checks.
4. Enable strict up-to-date checking and merge-queue compatibility.
5. Open a test PR and confirm both checks are listed as required.
6. Attempt a merge while either check is absent or failing; GitHub must deny it.

This document is an administration instruction, not evidence that the ruleset has been changed.
