# AEGIS Ω — Enterprise Technical-Evaluation Pitches

Status: DRAFTS ONLY — DO NOT SEND WITHOUT OPERATOR APPROVAL

Purpose: open technical-evaluation conversations with organizations already building the identity/runtime control plane for AI agents.

The pitch is not “replace your product with AEGIS.”

The pitch is:

> Your stack establishes and governs agent identity/access. AEGIS tests whether one specific consequential action remains admissible under the current task, state, authority, and evidence—and emits a deterministic receipt that can be replayed.

---

## 1. Microsoft — Entra Agent ID / Agent 365

Current public fit:
- Microsoft Entra Agent ID provides purpose-built identity, authentication, authorization, access protection, lifecycle governance, sponsors/owners, and audit controls for AI agents.
- Microsoft explicitly treats autonomous agents as a distinct identity/governance problem and applies least-privilege controls.

Primary public references:
- https://learn.microsoft.com/en-us/entra/agent-id/
- https://learn.microsoft.com/en-us/entra/agent-id/authorization-agent-id

### Subject

**Technical evaluation idea: Entra Agent ID + replay-verifiable action admission**

### Draft

Hi Microsoft Agent ID / Agent 365 team,

I’m building AEGIS Ω, an open-source runtime focused on a narrow layer adjacent to agent identity: proving whether a specific consequential action was admissible under the current task, delegated authority, target state, and evidence—and preserving that decision as a deterministic execution receipt.

Microsoft Entra Agent ID already addresses the identity and lifecycle side extremely well. I’d like to test a complementary boundary:

```text
Entra agent identity + authorization
→ AEGIS task/state admission
→ agent action
→ deterministic receipt
→ independent outcome/replay verification
```

The useful negative control is deliberately simple: the agent has a valid Entra identity and valid general capability, but its task authority or observed target state is stale. Identity authentication succeeds; the action should still fail closed.

The repository already contains public replay/tamper-evidence reference implementations across Python, Node.js, and Rust.

Would someone on the Agent ID / Agent 365 security side be interested in a small technical evaluation or architecture review rather than a product pitch?

I can provide a reproducible demo and a one-page threat model first.

Tarik Skalić
AEGIS Ω
Aegis-Omega/AEGIS-OMEGA

### Smallest ask

20–30 minute technical architecture review or referral to the engineering/security owner for agent authorization/runtime controls.

---

## 2. CyberArk — Secure AI Agents / MCP

Current public fit:
- CyberArk Secure AI Agents extends identity controls to MCP servers.
- CyberArk publicly emphasizes discovery, control, governance, agent identity brokerage, privilege controls, visibility, and audit for agents accessing MCP resources.

Primary public reference:
- https://www.cyberark.com/resources/best-practices/extend-agentic-identity-security-to-any-mcp-server

### Subject

**Evaluation proposal: bind MCP privilege to task/state evidence + replayable receipts**

### Draft

Hi CyberArk Secure AI Agents team,

AEGIS Ω is an open-source execution-governance project testing a layer that appears naturally complementary to CyberArk’s agent identity and MCP privilege controls.

The question is not whether an AI agent has a valid identity or can receive just-in-time privilege. The question is whether **this exact tool action is still justified by the task, current state, delegated purpose, and evidence at execution time**, and whether that decision can be independently reconstructed afterward.

I’d like to test one bounded MCP workflow:

```text
CyberArk identity / privilege decision
→ AEGIS action admission
→ MCP tool call
→ canonical execution receipt
→ independent outcome verification
```

Negative controls would include valid privilege with stale task authority, changed resource state, duplicate retry, injected tool instructions, and ambiguous post-call outcome.

This is not a request to replace identity security. It is an integration experiment around execution evidence.

Would your agentic identity/MCP security team be open to a small technical review or reproducibility exercise?

Tarik Skalić
AEGIS Ω

### Smallest ask

One representative MCP privilege workflow + a technical reviewer willing to challenge the admission/receipt model.

---

## 3. Okta — Okta for AI Agents / Agent Gateway

Current public fit:
- Okta treats agents as first-class identities, including discovery, onboarding, protection, governance, short-lived credentials and audit.
- Okta’s current Agent Gateway work explicitly targets runtime control over what agents connect to and what they can do.

Primary public references:
- https://www.okta.com/products/govern-ai-agent-identity/
- https://www.okta.com/en-sg/blog/product-innovation/agent-gateway-runtime-governance/

### Subject

**Technical collaboration idea: identity-governed agents + evidence-bound action receipts**

### Draft

Hi Okta for AI Agents team,

Your current framing around agent identity, runtime access, short-lived credentials, and “what can the agent do?” is almost exactly where a research problem I’ve been working on becomes relevant.

AEGIS Ω adds an evidence contract around an individual consequential action:

```text
who is the agent?
what can it access?
        ↓
what task delegated this action?
what state was observed?
is the authority still fresh?
what actually happened?
can a verifier replay the decision?
```

I’d like to evaluate the boundary between identity/runtime governance and execution evidence using one deliberately adversarial workflow. The agent remains correctly identified and credentialed, but the task/state evidence changes between authorization and action.

AEGIS then has to deny or review the action and produce a deterministic reason/receipt rather than rely on the model to self-assess authority.

Would your Agent Gateway or AI-agent governance team be interested in reviewing a small open reference implementation or providing one integration scenario?

Tarik Skalić
AEGIS Ω

### Smallest ask

Technical review of one task-scoped admission scenario layered after Okta identity/access authorization.

---

## 4. Palo Alto Networks — Prisma AIRS / Agentic Identity Security

Current public fit:
- Palo Alto Networks describes AI agents as privileged identities with nondeterministic runtime behavior.
- Current materials focus on MCP access, identity brokerage, least privilege, centralized visibility, policy and audit.

Primary public references:
- https://www.paloaltonetworks.com/blog/identity-security/secure-ai-agents-controls-visibility-mcp-data-access/
- https://www.paloaltonetworks.com/resources/datasheets/prisma-airs-ai-agent-security

### Subject

**Red-team target: valid privileged agent, inadmissible action**

### Draft

Hi Prisma AIRS / Agentic Identity Security team,

I’m looking for a technical team willing to attack a specific AEGIS Ω claim:

> A valid privileged AI-agent identity should still be unable to perform a consequential action when the task authority, target state, or execution evidence is inadmissible.

AEGIS is an open-source deterministic governance envelope around probabilistic agent actions. It does not attempt to replace identity brokerage or MCP access control. Instead, it binds each proposed side effect to task/state evidence and emits a replayable execution receipt.

A useful joint negative-control demo would be:

1. agent identity is valid;
2. MCP access is valid;
3. requested capability is normally allowed;
4. state or delegated task authority has become stale;
5. AEGIS must deny before the external side effect;
6. verifier reconstructs why.

Given Palo Alto Networks’ current focus on agentic identity, MCP access, runtime policy and audit, I think this would make a useful adversarial integration study.

Would someone on the Prisma AIRS / agentic identity security side be interested in trying to break the model?

Tarik Skalić
AEGIS Ω

### Smallest ask

One reviewer, one MCP-style workflow, one attempt to bypass task/state-bound admission.

---

# Outreach order

1. Microsoft — strongest existing ecosystem foothold and highly aligned Agent ID architecture.
2. OpenAI / Daybreak — funding + defensive agent security ecosystem.
3. CyberArk — direct MCP privilege integration fit.
4. Okta — current runtime Agent Gateway fit.
5. Palo Alto Networks — adversarial security/evaluation fit.

# Send rule

Before sending any pitch:

- replace generic team salutation with a verified person/team contact where available;
- add exactly one public reproducible artifact;
- keep first message <180 words where possible;
- ask for technical evaluation, not “partnership” in the first message;
- do not attach giant decks;
- do not claim production deployment, certification, or precedence unless the message specifically requires and supports it.
