---
name: anthropic-alignment
description: >
  Strategic and technical alignment between AEGIS and Anthropic's enterprise
  architecture. Auto-activates on: "partnership", "Anthropic enterprise",
  "HIPAA compliance", "ISO 42001", "SOC 2", "DLP", "CASB", "eDiscovery",
  "compliance export", "audit controls", "enterprise governance", "trust center",
  "BAA", "business associate agreement", "regulated industry".
  Documents what AEGIS provides that Anthropic explicitly does not ship natively,
  and the technical evidence for a partnership.
---

# AEGIS ↔ Anthropic Enterprise Alignment

**Epistemic Tier: T2** (engineering hypothesis based on published Anthropic documentation)
**Sources:** Anthropic Enterprise Security Posture (May 15, 2026), HIPAA Type 1 Report (Oct 31, 2025), WCAG ACRs (Web Apr 2026, iOS May 2026), Infrastructure Diagram (Apr 2025), Frontier Compliance Framework (Mar 2026), NIST 800-171r3 Attestation (Coalfire, Jan 2026), Mythos 5/Fable 5 Model Documentation Form (Jun 8, 2026)

---

## The Core Thesis

Anthropic explicitly states (Enterprise Security Posture, §3.2):

> "Anthropic does not ship a native DLP engine. Claude Products and the Claude Platform expose a published, stable endpoint set so the customer's DLP, SASE, or CASB can apply policy and classifiers to Claude traffic at the network layer."

**AEGIS is that layer.**

It sits between the enterprise and Claude's API, providing what Anthropic intentionally left to partners: constitutional content governance, tamper-evident audit trails, and replay-certifiable AI decision records.

---

## Control Family Mapping

Anthropic organizes enterprise security into four control families. AEGIS maps to each:

| Anthropic Control Family | Anthropic Provides | AEGIS Provides |
|--------------------------|-------------------|----------------|
| **Identity & Access Controls** | SAML 2.0/OIDC, SCIM 2.0, RBAC | `api_key_store` table — SHA-256 keyed, tiered access (explorer/operator/sovereign), usage limits |
| **Data Loss Prevention & Content Controls** | Published endpoint set for DLP/CASB integration | Constitutional content filter — every `/platform/collaborate` output passes 39-dept constitutional audit before returning |
| **Data Handling & Key Management** | AES-256 at rest, TLS 1.2+, admin-set retention | All AI decisions stored in `revenue_cycles` (Supabase, encrypted); hash chain provides deletion-proof audit trail |
| **Isolation & Connectivity** | Tenant isolation, TLS, regional deployment | Cloud Run `europe-west3` (EU data residency for GDPR); Vertex AI trust boundary (data stays in customer's GCP project) |

---

## Compliance Certifications Held vs Needed

| Standard | Anthropic | AEGIS (current) | AEGIS (gap) |
|----------|-----------|-----------------|-------------|
| SOC 2 Type II | ✓ (held) | ✗ | Pursue Type II attestation (control design + operating effectiveness) |
| ISO 27001 | ✓ (held) | ✗ | Pursue; AEGIS already implements most technical controls |
| **ISO 42001** | ✓ (held) | **Architecturally satisfies** | Document formally; AEGIS IS an AI Management System |
| HIPAA Type 1 | ✓ (held, zero exceptions Oct 2025) | Via Vertex AI (Anthropic handles ePHI layer) | Add `GET /platform/compliance/export` (done ✓); document §164.312(b) alignment |
| WCAG 2.2 AA | ✓ (Web 89%, iOS 84%) | Not applicable (API-first, no UI) | N/A |
| CSA STAR Level 2 | ✓ (held) | ✗ | Future; after SOC 2 |

**ISO 42001 is the highest-leverage gap to close first.** It is specifically the AI Management System standard. AEGIS's architecture is a direct implementation of it:

```
ISO 42001 §6.1 — Risk assessment for AI systems
  AEGIS: metacognitive chain + constitutional audit (APPROVED/FLAG/QUARANTINE)

ISO 42001 §8.4 — AI system operation
  AEGIS: 39-dept swarm with RALPH loop, replay-certifiable, hash-chained

ISO 42001 §9.1 — Monitoring, measurement, analysis
  AEGIS: /telemetry, /node, PGCS/TGCS/AFSE metrics, Studio observability

ISO 42001 §10.1 — Improvement (nonconformity and corrective action)
  AEGIS: constitutional audit verdicts → FLAG/QUARANTINE → corrective grace withholding
```

---

## Anthropic's Infrastructure — Where AEGIS Plugs In

From the April 2025 Infrastructure Diagram:

```
Claude.ai / API / Claude Code
    ↓
Cloudflare (WAF, rate-limit, TLS)
    ↓
API Load Balancer → /v1/messages
    ↓
Pre-inference: Prompt Caching · Redis rate-limit · Trust & Safety
    ↓
Anthropic Managed Inference Engine (Prompt Routing → Inference)
    ↓ (response)
AlloyDB (users, orgs, chat history, API keys)
```

**AEGIS runs ABOVE this stack** — it is the enterprise's intermediary between their systems and Anthropic's `/v1/messages`. AEGIS:

1. Receives the enterprise's governance request (`POST /platform/collaborate`)
2. Runs the 39-dept constitutional swarm (governed Claude call via Vertex AI)
3. Applies constitutional audit (APPROVED/FLAG/QUARANTINE)
4. Returns a tamper-evident `PlatformEnvelope<CollaborationResult>` with `audit_chain_hash`
5. Writes to `revenue_cycles` for HIPAA audit trail
6. Exports via `GET /platform/compliance/export` for eDiscovery

The enterprise never touches `/v1/messages` directly — they touch AEGIS, which governs every Claude call constitutionally.

---

## The Vertex AI Trust Boundary

Anthropic's HIPAA report notes (§Overview of Operations):

> "Alternatively, customers may use API-based access to Anthropic's models hosted within their own trust boundary on Google Vertex or Amazon Bedrock. Notably, Anthropic is unable to access prompts or responses sent via these services."

AEGIS already deploys to Cloud Run `europe-west3` and uses Vertex AI via ADC (`anth_client.py`). This means:

- **ePHI never leaves the customer's GCP project** (Anthropic can't access it)
- **Data residency is EU** (GDPR compliance for European enterprises)
- **Workload Identity (WIF)** — no long-lived service account keys
- AEGIS is the enterprise's GCP-native governance layer for Claude

---

## The Compliance Export Endpoint (New)

`GET /platform/compliance/export` (requires API key)

Maps directly to:
- **HIPAA §164.312(b)** — Audit Controls: "Implement hardware, software, and/or procedural mechanisms that record and examine activity in information systems that contain or use electronic protected health information"
- **ISO 42001 §9.1** — Monitoring and measurement

Response contains:
```json
{
  "export_id": "<uuid>",
  "chain_terminal_hash": "<sha256>",
  "compliance_framework": "HIPAA §164.312(b) Audit Controls; ISO 42001 AI Management System",
  "records": [
    {
      "cycle_id": "<uuid>",
      "timestamp": "<ISO-8601>",
      "objective_hash": "<sha256 of objective — privacy-preserving>",
      "mode": "revenue",
      "constitutional_verdict": "APPROVED",
      "is_replay_reconstructable": true
    }
  ]
}
```

The `chain_terminal_hash` links the export snapshot to the bridge's metacognitive chain — every exported record is provably part of an unbroken hash chain. Tamper detection: if any record in `revenue_cycles` is modified, the hash chain breaks on next certification.

---

## What Anthropic Gets From Partnership

1. **Enterprise governance middleware** — AEGIS makes Claude deployable in regulated industries (healthcare, finance, legal) that need audit trails for AI decisions
2. **Vertex AI validation** — AEGIS demonstrates real-world Vertex AI + Constitutional AI governance working in production on GCP
3. **ISO 42001 AI governance reference implementation** — AEGIS's architecture is a concrete implementation of the AI Management System standard Anthropic holds
4. **EU data residency showcase** — europe-west3 deployment with GDPR-compliant processing
5. **Open constitutional governance** — The hash chain is inspectable by anyone; Anthropic can independently verify every governance claim

---

## What AEGIS Needs to Advance the Partnership

Priority order (by impact / effort):

1. **`GET /platform/compliance/export`** — done ✓ (commit `006ea2ec`)
2. **FCF loss-of-control mitigation brief** — position AEGIS as the deployment-layer answer to the FCF's Sabotage Tier 1 risk class (see section above); this is the sharpest partnership wedge because it addresses a risk Anthropic has formally committed to mitigating under TFAIA + EU AI Act
3. **ISO 42001 alignment document** — write `docs/ISO_42001_ALIGNMENT.md` mapping AEGIS to all 9 ISO 42001 clauses
4. **NIST 800-171r3 §3.3 self-assessment** — document AEGIS audit controls against the Audit & Accountability family, citing `/platform/compliance/export` as evidence
5. **SOC 2 Type II pursuit** — requires engaging a third-party auditor (Schellman, Coalfire — both audit Anthropic); controls are already in place
6. **HIPAA BAA template** — draft a BAA for AEGIS customers who process ePHI via Claude; mirrors Anthropic's own BAA template
7. **Anthropic Trust Center listing** — AEGIS should appear as a verified partner/integration in the Anthropic partner ecosystem

---

## Frontier Compliance Framework — The Loss-of-Control Angle

Anthropic's FCF (March 2026) is its compliance framework for California's TFAIA and the EU AI Act (Regulation (EU) 2024/1689). It defines four systemic risk categories: cyber offense, CBRN, harmful manipulation, and **sabotage and loss of control**.

The FCF's Sabotage Tier 1 definition (verbatim):

> "AI systems that write large amounts of critical code and/or are otherwise in a position where they are highly relied on and have extensive access to sensitive assets, as well as moderate capacity for autonomous, goal-directed operation and subterfuge."

**This is the exact risk class AEGIS exists to mitigate.** Every constitutional mechanism maps to an FCF loss-of-control concern:

| FCF Loss-of-Control Concern | AEGIS Mitigation |
|------------------------------|------------------|
| "evasion of oversight" | `AdaptivePower(T) ≤ ReplayVerifiability(T)` — adaptation cannot outrun verification |
| "concealment, strategic deception" | Hash-chained MetacognitiveLoop — tamper-evident self-observation; concealment breaks the chain |
| "establishing unauthorized deployments" | Law of Silence — agents communicate only through mediated EventEnvelope |
| "accumulating resources without authorization" | Martingale gate — `E[S_{n+1}|F_n] = S_n`; unbounded accumulation suspends adaptation |
| "manipulate the evidence used to assess their safety" | `verify-hashes.mjs` + frozen-file SHA-256 — evidence integrity is mechanically checked |

The partnership thesis sharpened: **AEGIS operationalizes the FCF's loss-of-control mitigations for downstream agentic deployments.** Anthropic mitigates at the model layer (classifiers, RSP); AEGIS mitigates at the deployment layer (replay-verifiable agent governance). The FCF's own incident-response section (§2.6) requires tracking Serious AI Incidents under EU AI Act Art. 55(1)(c) — AEGIS's hash-chained audit trail is the downstream evidence substrate for exactly that reporting.

---

## EU AI Act — AEGIS Is Formally a Downstream Provider

The Mythos 5/Fable 5 Model Documentation Form is published under **EU AI Act Art. 53(1)(b), Annex XII** — model documentation *for downstream providers*. AEGIS integrates Claude into its own AI system (the 39-dept swarm) and places it on the market: AEGIS **is** a downstream provider in the regulation's sense.

What this means concretely:

- AEGIS inherits its own EU AI Act obligations (Art. 12 record-keeping in particular) — already architecturally satisfied: the audit chain IS Article 12 logging, and `aegis-cl-psi` is tagged EU AI Act-compliant
- Anthropic Ireland Limited is the EU model provider; AEGIS (EU-deployed, Vertex `eu` region, Cloud Run `europe-west3`) sits cleanly in the EU compliance chain
- Key model facts (form v1.0, June 8, 2026): Mythos 5 = Fable 5 with certain cyber/bio classifiers disabled per customer use case, trusted-access program only; both released June 9, 2026; black-box inference-only access; input 1M tokens text + 600 images/request; max output 300K tokens (model capability — API per-request limit remains 128K)

---

## NIST 800-171r3 — The Government Market Gap

Coalfire's attestation (Jan 13, 2026): Anthropic implemented **90 of 98** NIST SP 800-171r3 requirements for Claude + Claude API (CUI protection). The 8 low-severity findings all have remediation plans (account lifecycle, CUI training, security literacy, IR training docs, software program reviews, identifier characteristics).

Relevance for AEGIS:
- NIST 800-171 is the gateway to US federal/defense contractors handling CUI. Anthropic is positioned there; an AEGIS layered on Claude inherits that posture for the model layer but needs its own 800-171 story for the governance layer
- AEGIS's deterministic audit controls (03.03.x family) are its strongest 800-171 chapter — hash chains exceed the audit-record integrity requirements
- Lowest-effort win: document AEGIS against 800-171r3 §3.3 (Audit and Accountability) using the existing `/platform/compliance/export` endpoint as evidence

---

## Anthropic's Own Tools in AEGIS

AEGIS already uses Anthropic's own security practices:
- **CodeQL** — running in CI (confirmed ✓ in PR #153 check runs)
- **Constitutional AI** — AEGIS's metacognitive chain mirrors the Constitutional AI training approach at inference time
- **SSE streaming** — same pattern as Anthropic's production (`/v1/messages` returns SSE; AEGIS's `/platform/executions/live` matches)
- **Prompt caching** — already wired in `bridge.py` (`cache_control=ephemeral`)

---

## Non-Equivalence Invariants

```
AEGIS governance  ≠  Anthropic Constitutional AI training
  (AEGIS governs inference outputs; Anthropic governs model weights)

HIPAA via Vertex  ≠  HIPAA BAA with Anthropic
  (Vertex = data stays in customer GCP; BAA = Anthropic is the business associate)

audit chain hash  ≠  proof of correctness
  (the chain proves tamper-evidence; correctness of AI outputs is not proven)

ISO 42001 alignment  ≠  ISO 42001 certification
  (architectural alignment exists; formal certification requires third-party audit)
```

---

*Tier T2 — engineering hypothesis. Promote to T1 when: (1) formal ISO 42001 gap analysis completed by qualified auditor, (2) SOC 2 Type II controls reviewed by independent assessor.*
