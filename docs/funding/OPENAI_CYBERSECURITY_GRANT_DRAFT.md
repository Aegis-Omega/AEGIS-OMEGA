# OpenAI Cybersecurity Grant Program — AEGIS Ω Draft

Status: READY FOR OPERATOR REVIEW — NOT SUBMITTED
Program: OpenAI Cybersecurity Grant Program / Trusted Access for Cyber ecosystem
Primary sources:
- https://openai.com/index/openai-cybersecurity-grant-program/
- https://openai.com/index/trusted-access-for-cyber/

## Project title

**Capability-Bound Agent Execution: Preventing Tool Misuse and Privilege Drift in Autonomous Security Workflows**

## Requested support

**$50,000 equivalent support**, preferably a mix of API credits and other available program support.

The amount is intentionally aligned to a bounded defensive open-source project and can be resized to the current program mechanism.

## Project summary

Security agents increasingly operate with repository, cloud, CI/CD, scanner, ticketing, and remediation tools. Existing identity controls can establish who an agent is and what credential it possesses, but a valid identity does not prove that a particular action is authorized for the current task, target, state, or point in time.

AEGIS Ω will build an open-source defensive control layer that binds security-agent actions to task-scoped capabilities, delegated authority, resource/state preconditions, and deterministic execution receipts. The project will demonstrate that an agent can have valid credentials yet still be denied when the requested action is stale, excessive, ambiguous, or unsupported by admissible evidence.

The system is intended for authorized defensive workflows only.

## Defensive use cases

The initial benchmark will cover:

1. secure code review and finding validation;
2. patch proposal and patch verification;
3. security backlog triage;
4. threat-model generation and evidence updates;
5. controlled CI security checks;
6. defensive MCP/tool invocation;
7. remediation-plan execution in isolated test environments.

No project milestone requires exploitation or unauthorized testing of third-party systems.

## Core security hypothesis

```text
VALID_IDENTITY != VALID_AUTHORITY
VALID_AUTHORITY != VALID_ACTION_NOW
VALID_ACTION != VERIFIED_OUTCOME
```

The project tests whether a deterministic external governance layer can reduce security-agent privilege drift and confused-deputy behavior without depending on a model to reliably self-police its own authority.

## Technical design

A proposed security-agent action enters an admission contract containing:

- actor/workload identity;
- task identity;
- target resource;
- requested capability;
- delegated authority;
- lease/fence and freshness information;
- observed target state;
- policy/evidence references;
- expected side effect and outcome.

AEGIS evaluates the contract and returns one of:

`ADMIT | DENY | REVIEW | BLOCKED`

An admitted execution emits a canonical, tamper-evident receipt. The verifier separately evaluates the observed outcome and preserves `OUTCOME_UNKNOWN` when a provider or environment cannot establish success or failure.

## Adversarial scenarios

The benchmark will include defensive failure cases such as:

- valid repository token, wrong repository/task scope;
- valid cloud identity, expired delegated lease;
- target changed after approval;
- tool request expands beyond approved remediation;
- malicious instructions embedded in issue/code/tool output;
- retry causes duplicate side effect;
- security scanner returns ambiguous or stale evidence;
- provider timeout after a possibly committed action;
- an agent claims a patch was applied but outcome verification disagrees;
- one agent's assertion is incorrectly treated as independent verification by another.

## Existing AEGIS base

The public AEGIS Ω repository already contains reference implementations and tests for replay-verifiable, tamper-evident evidence handling and deterministic governance envelopes, including cross-language verification.

Public proof commands include:

```bash
python3 genomics/test_replay_proof.py
python3 verifiable/test_generality.py
bash verifiable/cross_language/verify.sh
python3 verifiable/certify_all.py --twice
```

The funded project would turn these general primitives into a focused security-agent benchmark and integration layer.

## Expected deliverables

1. **Open Agent Security Action Contract**
   - typed schema for actor/task/capability/authority/state/evidence/outcome.

2. **Defensive Admission Gateway**
   - read/decision layer usable around MCP and other tool adapters.

3. **Security-Agent Adversarial Benchmark**
   - at least 100 deterministic or receipt-bound scenarios.

4. **Receipt and Replay Verifier**
   - independent validation of action lineage and declared outcomes where observable.

5. **Reference Integrations**
   - at least two bounded integrations, prioritizing open-source repository/AppSec workflows.

6. **Open Evaluation Report**
   - false-admit/false-deny behavior, bypass attempts, limitations, and reproduction guide.

## Why OpenAI support is high leverage

The project directly concerns defensive agent execution and the growing transition from advisory security models to agents capable of acting through tools. OpenAI API/Codex access would enable testing across realistic long-horizon defensive workflows while AEGIS supplies the external authority/evidence boundary.

The research is intentionally compatible with a trust-based access model: increased model capability should not imply increased unbounded authority.

## Public-benefit / open-source plan

The reference schemas, benchmark, verifier, and core integration code will be released in the public AEGIS Ω repository under its existing open-source licensing model or a maximally reusable compatible subcomponent license where necessary.

Results will include negative findings and bypasses rather than only successful demonstrations.

## Success metrics

- unauthorized-action admission rate;
- stale-authority rejection rate;
- duplicate-side-effect prevention/detection rate;
- evidence-chain replay rate;
- outcome-misclassification rate;
- prompt/tool-injection containment rate at the action boundary;
- external reproduction by at least two reviewers.

## Explicit scope limits

This proposal does not request permission for:

- credential theft;
- malware deployment;
- persistence or stealth;
- destructive testing;
- exploitation of systems without explicit authorization;
- bypassing platform safeguards.

All active testing will occur against owned, isolated, open-source, or explicitly authorized targets.

## 6-month execution plan

### Month 1
Contract freeze, threat model, benchmark skeleton.

### Months 2–3
Admission gateway, OpenAI/Codex defensive workflow adapter, first 50 negative controls.

### Month 4
Remaining benchmark cases, outcome verification and retry/timeout semantics.

### Month 5
Independent reproduction and red-team review.

### Month 6
Public release, evaluation report, partner integration guide.

## Operator

Tarik Skalić — AEGIS Ω
Bihać, Bosnia and Herzegovina
Public repository: Aegis-Omega/AEGIS-OMEGA

## Before submission

- [ ] map final answers to current OpenAI application form fields;
- [ ] choose exact request amount/support mix;
- [ ] reference strongest current security/replay demos;
- [ ] include Codex Security integration only after its preflight/execution status is accurately represented;
- [ ] operator review;
- [ ] submit.
