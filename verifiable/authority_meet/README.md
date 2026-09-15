# Authority meet: exact-head formal evidence

This is a standalone Coq 8.20.1 development using the standard library. It is not the earlier 30-source RH/CoRN development and does not require Coquelicot or CoRN.

## Original-source failures, preserved in history

- `acdc531dbb30ab1a76214018f49e5aaa1f1b5ac4`, run `34152689301`: the supplied `/\` notation at level 40 conflicts with Coq conjunction at level 80. The compiler failed before checking the theorem.
- `ff2de7951e1bc5f3e4d99953cd7dbaacfac7e823`, run `34152953710`: after syntax-only replacement by `⊓`, the proof failed because it treated a left-associated meet as right-associated.
- `3024ac3f8e95d1cf8753ca374051f9ca2c463f7b`, run `34153203518`: the minimal corrected source passed compilation, a separate coqchk invocation, and the post-section assumption inventory.
- `75ba7c6584178f0557989e3b32face03316ab3af`, run `34153281562`: new required-contract checks failed on the absent `authority_le_grant` declaration. This is the extension RED contract, not a regression of the repaired original theorem.

A later head must obtain its own proof result; none of these runs automatically admits a changed head.

## Formal statements

`Authority_Meet.v` proves the fold bound, direct non-escalation, grant and request bounds, and bottom propagation/equality. `compute_required_authority` maps a missing lookup for an explicitly required identifier to bottom and denies an empty derived requirement list. The required list is assumed supplied by an independently trusted policy; the proof does not discover omitted requirements.

The required-parent and required-path results prove non-escalation along finite paths of required dependencies, assuming the stated node equation. They do not assert that an arbitrary cyclic system of node equations has a unique computable solution. Root issuance and acyclic evaluation policy remain separate.

The three EvidenceKind constructors have pairwise disequality proofs. Disjoint tags do not authenticate a physical claim, execute its verifier, or establish a causal mechanism.

`Authority_Tests.v` contains seven concrete Boolean examples, checks for the required exported contracts, and two `Fail Definition` rejection probes. The raw empty fold example deliberately demonstrates why algebra alone is not a missingness detector.

## Assumptions and verification

Read both `Print <theorem>` and `Print Assumptions <theorem>` after `End AuthorityPoset`. Section hypotheses become explicit theorem parameters. `Closed under the global context` means no uninstantiated global axioms were used; it does not remove those premises or validate their application to a production runtime.

The workflow is read-only, checks the full checkout head and clean worktree, copies sources to a separate workspace, compiles with Coq 8.20.1, invokes coqchk independently with recursive dependency checking, audits the theorem inventory, rechecks source hashes, and emits a scoped unsigned receipt. Compiler and checker invocations disable container networking. The image is pinned to:

`coqorg/coq@sha256:18ebf3da56e60e3ddfd7d4e51f4c53d10241a129f34e93dacbc71562dd43c57a`

After installing that toolchain, local replay in this directory is:

```sh
coqc -q Authority_Meet.v
coqc -q Authority_Tests.v
coqchk -silent -o Authority_Meet Authority_Tests
```

## Governance boundary

At inspection on 2026-09-07, main was `495bfd85d79abcb2b4f6898fe9c156488492426a`, `protected=true`, with active ruleset `22409161` (AEGIS Main Enforcement), no bypass, required signatures and six required status contexts. The historical `T_REPOSITORY_GOVERNANCE` report belonged to PR #412 at head `f88422e9fd09d80fd885c15d686bbd4b8b1be35c`, based on old main `6eb2ac201bbe60ebaa9cebad714b8696683772e8`. It is not current-state evidence for this candidate.

This branch does not weaken protection, mutate main, edit cognitive anchors, grant capabilities, or merge anything. A successful formal lane does not replace the repository's required checks. Any cognitive-anchor repair must use the governed single-writer workflow, followed by fresh exact-head verification.

No claim is made about RH, biological causality, clinical use, DNA closure residuals, or end-to-end authentication of runtime observations. Wet-lab validation is not a prerequisite of this abstract algebraic theorem.
