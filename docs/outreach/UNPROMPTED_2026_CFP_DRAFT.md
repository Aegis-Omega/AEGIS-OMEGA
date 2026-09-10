# [un]prompted II 2026 — CFP Draft

Target track: **Build** (secondary: Govern)
Conference: San Francisco, October 27–29, 2026
CFP deadline: September 8, 2026

## Title

**Determinism Lives Outside the Model: Replay-Verifiable Governance for AI Agent Actions**

## Abstract — <=200 words

Modern AI agents can authenticate correctly, call legitimate tools, and still perform an inadmissible action because the task, authority, state, or evidence changed after the agent was authorized. Prompt guardrails do not solve that problem, and model confidence cannot be treated as an authorization primitive.

This talk presents AEGIS Ω, an open-source experimental runtime that places a deterministic governance envelope around probabilistic agent behavior. The envelope separates capability from authority, canonicalizes evidence, hash-chains execution lineage, and supports replay from genesis so divergence becomes a detectable failure instead of an unverifiable story.

The talk is built around runnable artifacts rather than architecture slides. We will reproduce the same governed result across Python, Node.js, and Rust; deliberately tamper with stored evidence; and show the verifier identify the broken stage. We then extend the pattern to consequential agent actions: task-scoped authority, state preconditions, admission decisions, receipts, and explicit `OUTCOME_UNKNOWN` semantics.

The result is not a claim that models become deterministic. It is a narrower security property: stochastic models can operate inside a system whose authority decisions and evidence trail are independently inspectable and replayable.

## Detailed outline

1. **Why valid credentials are not enough — 4 min**
   - agent identity vs capability vs authority;
   - stale state and confused-deputy failure;
   - why model confidence cannot authorize side effects.

2. **The deterministic governance envelope — 5 min**
   - canonical evidence;
   - append-only lineage;
   - execution receipts;
   - replay invariants.

3. **Live proof: three runtimes, one fingerprint — 6 min**
   - Python / Node.js / Rust canonicalization;
   - tamper one artifact;
   - verifier detects divergence.

4. **From replay to runtime authority — 5 min**
   - task-scoped action contract;
   - leases / fencing / state freshness;
   - `ADMIT`, `DENY`, `REVIEW`, `BLOCKED`;
   - `OUTCOME_UNKNOWN != SUCCESS`.

5. **What failed and what remains unproved — 5 min**
   - GPU nondeterminism boundary;
   - verifier scaling;
   - draft operator-model work;
   - why specifications and passing local tests are not production proof.

## Evidence supporting the talk

Public repository: `Aegis-Omega/AEGIS-OMEGA`

Runnable examples currently exposed in the repository:

```bash
python3 genomics/test_replay_proof.py
python3 verifiable/test_generality.py
bash verifiable/cross_language/verify.sh
python3 verifiable/certify_all.py --twice
```

Repository documentation explicitly limits the claim to the governance envelope rather than domain accuracy.

Additional evidence to attach before CFP submission:

- exact-head CI receipt for the demo branch;
- screen recording of the tamper/replay failure;
- one concise architecture diagram;
- link to the public launch/evaluation brief;
- negative-control result for stale or excessive authority.

## Speaker bio — <=100 words

Tarik Skalić is an independent systems builder from Bihać, Bosnia and Herzegovina, working on AEGIS Ω: an open-source research and engineering project for evidence-governed AI agent execution. His work focuses on deterministic control around probabilistic models, replay-verifiable evidence, task-scoped authority, agent metacognition, and multi-agent governance. AEGIS grew from earlier experiments in persistent simulation, metacognitive evaluation, and autonomous system control into a public repository spanning Rust, TypeScript, Python, cross-language verification, and adversarial governance tests.

## Submission positioning

Do not pitch AEGIS as a product presentation.

Lead with the security property and the failure:

> The agent had valid identity and capability. The action was still invalid. Here is how the runtime proved it.

## Final submission blockers

- run/record the exact public demo on current head;
- choose one authority-denial negative control that is already runnable or can be completed without speculative claims;
- verify every benchmark/test count included in slides;
- remove any reference to unverified municipal/production deployment.
