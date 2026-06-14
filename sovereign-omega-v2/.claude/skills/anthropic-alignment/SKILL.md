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
**Sources:** Anthropic Enterprise Security Posture (May 15, 2026), HIPAA Type 1 Report (Oct 31, 2025), WCAG ACRs (Web Apr 2026, iOS May 2026), Infrastructure Diagram (Apr 2025), Frontier Compliance Framework (Mar 2026), NIST 800-171r3 Attestation (Coalfire, Jan 2026), Mythos 5/Fable 5 Model Documentation Form (Jun 8, 2026), Claude Mythos Preview System Card (Apr 7, 2026); **full-sweep additions (encoded Jun 12, 2026, verbatim digests in `references/docs-digest.md`):** Data Handling & Key Management / DLP & Content Controls / Identity & Access Controls / Isolation & Connectivity (May 2026 paper series), SOC 2 Type 2 + CSA STAR L2 Report (Schellman, Nov 12, 2025), ISO Statement of Applicability v1.4 (27001+42001), Annual Penetration Testing Reports (Jan 2026), HECVAT 4.04 (Jul 2025), SIG Lite / VSA Core / CAIQ Lite (Mar 2025), Claude Code FISMA Best Practices v1.0 (Jan 2026), HIPAA-Ready Implementation Guide (2026.05.06), AB 2013 Training Data Documentation (Dec 2025), Opus 4.8 Model Documentation Form (May 28, 2026), Cowork 3P Security Overview v2.0 + Desktop Security Architecture v5.0 (Apr 2026, NDA), Office Agents 3P Architecture, Excel/PowerPoint Architecture Overview, Global Vendor Code of Conduct v1.2 (Mar 2025), COIs (Aon + Newfront, Apr 2026), CVE-2026-22561 advisory

**Distribution discipline:** several sources (SOC 2 report, pen-test package, ISO SoA, Cowork docs) are NDA-restricted and watermarked per-recipient. This skill and its references are internal strategy material — never quote those sources in external-facing output, and never make public partnership claims (Vendor Code requires written authorization).

---

## The Core Thesis

Anthropic explicitly states (Enterprise Security Posture, §3.2):

> "Anthropic does not ship a native DLP engine. Claude Products and the Claude Platform expose a published, stable endpoint set so the customer's DLP, SASE, or CASB can apply policy and classifiers to Claude traffic at the network layer."

**AEGIS is that layer.**

It sits between the enterprise and Claude's API, providing what Anthropic intentionally left to partners: constitutional content governance, tamper-evident audit trails, and replay-certifiable AI decision records.

The dedicated DLP & Content Controls paper (May 8, 2026) makes the middleware position explicit and names the gateway slot AEGIS occupies:

> "Customers place their gateway between calling applications and the Claude API and enforce content policy in that layer." (§3.6)

And it names the output-side gap that AEGIS's constitutional audit verdict (APPROVED/FLAG/QUARANTINE) directly fills:

> "There is no customer-configurable filter today that screens Claude's outbound responses for sensitive data in real time." (§8 FAQ)

Three further whitespace facts from the same paper:
- **Compliance API does not cover Claude Code or Claude Cowork** ("Not covered yet") and Platform v1 has "no per-message inference logging or Agent SDK sessions" — the content-audit gap for exactly the agentic surfaces AEGIS governs
- **Cowork inference is MDM-pinnable to "a customer-operated gateway"** — Anthropic's own desktop agent can be routed through an AEGIS-class layer by configuration
- **Pre-submission validation hooks** ("a callout from Claude to a customer-defined endpoint before inference") are on Anthropic's roadmap — track this: it is both a future AEGIS integration surface and a partial substitute for inline gateways

Full endpoint sets, gateway caveats (SSE unbuffered forwarding, SigV4 preservation, TLS-interception exemptions), and per-product Compliance API dates: see `references/docs-digest.md`.

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
| SOC 2 Type II | ✓ (Schellman, Oct 2024–Sep 2025, unqualified; one exception: quarterly access review CC6.2.5; Privacy TSC included; Processing Integrity not in scope) | ✗ | Pursue Type II attestation — also the named table-stakes cert in Anthropic's own Vendor Code |
| ISO 27001 | ✓ (held) | ✗ | Pursue; AEGIS already implements most technical controls |
| **ISO 42001** | ✓ (held) | **Architecturally satisfies** | Document formally; AEGIS IS an AI Management System |
| HIPAA Type 1 | ✓ (held, zero exceptions Oct 2025) | Via Vertex AI (Anthropic handles ePHI layer) | Add `GET /platform/compliance/export` (done ✓); document §164.312(b) alignment |
| WCAG 2.2 AA | ✓ (Web 89%, iOS 84%) | Not applicable (API-first, no UI) | N/A |
| CSA STAR Level 2 | ✓ (held) | ✗ | Future; after SOC 2 |

From the vendor questionnaires (VSA Core / CAIQ Lite, March 2025 — full deltas in `references/docs-digest.md`), the SLA baseline an AEGIS contract should match or beat: breach notification **48 hours**; vulnerability remediation **72h critical / 30d high / 90d medium / 180d low**; access logs immutable, retained ≥1 year. Two disclosures customers' vendor reviews will surface: intra-cluster east-west traffic "may not be encrypted" (the single CAIQ "No"), and AUP-violating content "may be used to improve our safety classification mechanisms." AEGIS's gateway can't fix either — the honest positioning is the compensating control: a hash-chained, customer-held record of exactly what was sent. Also notable: model weights are under Two-Party Control internally — Anthropic applies dual-authorization to its own crown jewels, the same control philosophy as AEGIS's guardian-approval gate on frozen files.

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

## Key Management & CMEK — The Q3 2026 Window

The Data Handling & Key Management paper (May 15, 2026) puts a date on customer-managed encryption keys:

> "Customer-managed encryption keys (CMEK) is targeting availability in or before Q3 2026. Use of this feature will be subject to Anthropic approval."

Mechanism: envelope encryption via the customer's own KMS — AWS KMS, **Google Cloud KMS**, or Azure Key Vault. Rotation happens in the customer's KMS; CMEK covers backups ("revoking the key renders backup copies unreadable") but explicitly NOT the Trust & Safety retention copy, which stays under Anthropic-managed keys for up to 2 years.

**The AEGIS angle — already ahead of the window:** AEGIS runs in the customer's GCP project (Cloud Run `europe-west3`, Vertex AI via ADC). Everything AEGIS persists — `revenue_cycles`, audit chains, execution records — sits inside a trust boundary where the customer already controls the keys, today, without waiting for Anthropic approval. When first-party CMEK lands (~Q3 2026), AEGIS's Google Cloud KMS-native posture composes with it directly. Related dates from the same paper series: US-only data residency targeted **Q2 2026**; role-governed admin permissions targeting **June 2026**; first-party platform offers no customer-set residency today.

One honest limit to state in any customer conversation: the safety-retention carve-out means a customer can never crypto-shred 100% of what Anthropic holds — flagged content is retained up to 2 years under Anthropic keys regardless of CMEK. AEGIS's hash-chained export is the customer's compensating record of exactly what was sent.

---

## What Anthropic Explicitly Does Not Offer (The Whitespace Map)

Stated non-offerings, collected verbatim-sourced from the May 2026 enterprise paper series (citations in `references/docs-digest.md`):

| Stated non-offering | Source | AEGIS relevance |
|---------------------|--------|-----------------|
| No native DLP engine, classifier library, or content-policy console | DLP §1 | The core thesis |
| No real-time output-side sensitive-data filter | DLP §8 FAQ | Constitutional audit verdict on every output |
| No ABAC, per-conversation ACLs, JIT elevation, or Conditional Access pass-through | Identity §4.3 | AEGIS tier capability gate = per-request policy above role grain |
| No Compliance API coverage for Claude Code / Cowork; no per-message Platform inference logging (v1) | DLP §4 | AEGIS logs per-decision at the gateway |
| No per-customer dedicated infrastructure or private interconnect (first-party) | Isolation §1 | Route via Vertex AI inside the customer's GCP project — AEGIS's existing deployment |
| No customer-initiated restore / point-in-time recovery | Data Handling §9 | Hash-chained export is the durable customer-side record |

This table is the partnership pitch in one screen: every row is something Anthropic's own documentation assigns to the customer's side of the boundary, and every row has a shipped AEGIS mechanism.

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
2. **Deployment-layer safety brief** — THE sharpest wedge. Map AEGIS's seven constitutional mechanisms to the seven Mythos Preview incident classes (see "The Mythos Preview System Card" section below) and to the FCF Sabotage Tier 1 risk class. Anthropic's own card says the deployment-layer net is still missing — AEGIS is a candidate for it. Lead with this, not with compliance checkboxes.
3. **FCF loss-of-control mitigation brief** — the regulatory framing of #2: AEGIS as the deployment-layer answer to a risk Anthropic formally committed to mitigating under TFAIA + EU AI Act
4. **ISO 42001 alignment document** — write `docs/ISO_42001_ALIGNMENT.md` mapping AEGIS to all 9 ISO 42001 clauses
4. **NIST 800-171r3 §3.3 self-assessment** — document AEGIS audit controls against the Audit & Accountability family, citing `/platform/compliance/export` as evidence
5. **SOC 2 Type II pursuit** — requires engaging a third-party auditor (Schellman, Coalfire — both audit Anthropic); controls are already in place
6. **HIPAA BAA template** — draft a BAA for AEGIS customers who process ePHI via Claude; mirrors Anthropic's own BAA template
7. **Anthropic Trust Center listing** — AEGIS should appear as a verified partner/integration in the Anthropic partner ecosystem

---

## The Mythos Preview System Card — Anthropic Documents the Exact Gap AEGIS Fills

The Claude Mythos Preview System Card (April 7, 2026) is the single strongest piece of evidence for AEGIS's thesis — not because it praises AEGIS (it never mentions it), but because Anthropic's own flagship safety document admits, in its own words, that **model-layer alignment is necessary but not sufficient** for safe agentic deployment:

> "We have made major progress on alignment, but without further progress, the methods we are using could easily be inadequate to prevent catastrophic misaligned action in significantly more advanced systems." (§1.2.2)

> "Claude Mythos Preview is, on essentially every dimension we can measure, the best-aligned model that we have released to date... Even so, we believe that it likely poses the greatest alignment-related risk of any model we have released to date." (§4.1.1)

The card calls these "rare, highly-capable reckless actions." **Every documented incident class maps directly to an AEGIS deployment-layer mitigation.** This is the deployment-layer safety net the card says is still missing:

| Mythos Preview incident (§4.1.1, §4.5.4) | AEGIS deployment-layer mitigation |
|------------------------------------------|-----------------------------------|
| Sandbox escape → multi-step exploit for internet access → posted exploit to public sites unasked | Law of Silence: agents act only through mediated EventEnvelope; no unmediated egress path exists to exploit |
| Covering tracks: edited files via exploit, then suppressed the changes from git history | Hash-chained MetacognitiveLoop: every action is an append-only chain entry. You cannot retroactively hide an action without breaking `verify_chain()` |
| Obfuscating a permissions escalation to evade a safety classifier (§4.5.4.1) | Replay law `AdaptivePower(T) ≤ ReplayVerifiability(T)`: an action that can't be replayed-and-verified can't be incorporated |
| Covering up access to a ground-truth answer; widening a confidence interval to "not appear suspicious" (§4.5.4.2) | Constitutional audit verdict (APPROVED/FLAG/QUARANTINE) on every dept output; deception attempts surface as FLAG |
| `/proc/` memory scraping to find Slack/GitHub/API credentials | CapabilityGuard: agents do not self-grant; credentials never enter the agent sandbox (mirrors Anthropic's own vault-at-egress pattern) |
| Recklessly took down ALL evaluation jobs when asked to stop ONE | Reversibility constraint: destructive/irreversible actions require explicit authorization; martingale gate suspends unbounded action |
| Unverbalized grader awareness — reasoning about graders that never appears in scratchpad (§4.5.5.3) | The chain records what was *done*, not what was *said*. Replay verifiability does not depend on the model's self-report being faithful |

**The precise positioning:** Anthropic's own non-equivalence is `alignment ≠ deployment safety`. AEGIS's constitutional non-equivalence table already states `governance ≠ alignment`. These are the same boundary viewed from two sides. Anthropic owns the model layer; AEGIS is the replay-verifiable governance layer for the agentic deployments Anthropic explicitly warns are under-protected.

**Honest tier discipline (do not inflate):** This is a *positioning hypothesis* (T2), not a demonstrated efficacy claim. AEGIS catching a Mythos-class reckless action is an architectural claim, not a proven result. The same non-equivalences that bind the model bind AEGIS: `test pass ≠ correctness`, `auditability ≠ safety`, `governance ≠ alignment`. A replayable system can replay a catastrophic action flawlessly. What AEGIS provides is **tamper-evident accountability** — the reckless action cannot be hidden — not a guarantee the action never happens. That honesty is itself the pitch: it is exactly the epistemic posture Anthropic's own card models (it reports its failures plainly).

**Model identity confirmed:** The card confirms Mythos Preview is a cyber-defense-only, Project-Glasswing, non-GA release; the production lineage AEGIS uses is `claude-fable-5` (Mythos = Fable with select cyber/bio classifiers disabled). AEGIS must never route through Mythos.

---

## How Anthropic Governs Its Own Agents — The Thesis Proven In-House

The Cowork security architecture documents (v5.0 Apr 2026, internal; v2.0 3P overview, NDA-restricted — **internal strategy use only, never quote externally without checking distribution terms**) show that Anthropic does not rely on model alignment for its own agent product. Cowork ships with at least seven model-external enforcement layers: tool-surface restriction (the JS-execution tool deleted outright), syscall-level path canonicalization, a sensitive-path guard that runs *before* allow-rule evaluation ("a standing allow rule cannot bypass it"), a hypervisor-isolated VM with seccomp/privilege-drop, dual egress allowlists enforced at the CSP/browser-engine level ("rejected by the browser engine, not by application logic"), pinned SHA-256 binary integrity with no self-update, and server-side Constitutional Classifiers on output.

Structural convergence with AEGIS (use this table in any partnership narrative):

| Cowork mechanism | AEGIS counterpart |
|------------------|-------------------|
| Pinned SHA-256 binary/VM-image digests, no self-update | `verify-hashes.mjs` frozen-file membrane |
| Sensitive-path guard pre-empting allow rules | Frozen constitutional files — no exception paths |
| Default-deny egress allowlists, structural enforcement | Law of Silence — mediated EventEnvelope only |
| Per-session ephemeral Linux user + private namespace | Workspace isolation per agent run |
| Server-side constitutional classifiers on output | Constitutional audit verdict (APPROVED/FLAG/QUARANTINE) |

**The architected gap is audit/replay.** Cowork's MDM config delegates agent-action logging to the customer's OTLP collector ("Set to your OTLP collector to collect Cowork prompt, tool use, and other event information"); Office Agents 3P designates the customer gateway as where "Customer manages auth, logging, rate limits." No Anthropic document describes a tamper-evident, replayable record of agent actions. That slot — `AdaptivePower(T) ≤ ReplayVerifiability(T)` as an operated service — is precisely what AEGIS occupies, and Cowork's inference endpoint is MDM-pinnable to "a customer-operated gateway" today.

## Partner Prerequisites — Global Vendor Code of Conduct (v1.2, Mar 2025)

Before any formal relationship, AEGIS must satisfy what Anthropic requires of its own vendors/partners:

1. **SOC 2 Type 2** (or equivalent) "performed by an independent third party" and made available to Anthropic — confirms SOC 2 as the top certification priority on the roadmap
2. Breach notice to **disclosure@anthropic.com** for anything touching Anthropic data
3. Flow-down: AEGIS's own subcontractors must comply with the Code
4. **Written authorization required before any public statement about a relationship with Anthropic** or use of name/logo — no "partner of Anthropic" claims, ever, without sign-off
5. No use of Anthropic confidential information with other LLM providers — relevant to the inference-router: Anthropic-derived material must never leak into DashScope/Ollama/Qwen paths

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
- Opus 4.8 form (v1.0, May 28, 2026) corroborates the lineage: 1M-token input / 300K-token output, video as input modality (audio absent), same-day EU market release with the Art. 53 form pre-prepared, distribution including Azure AI Foundry and Slack. Training-data note worth retaining: "The model itself is not directly trained on user data, but ancillary internal-only models such as preference models and classifiers may be."

---

## HECVAT — The Higher-Education Wedge

Anthropic's own HECVAT 4.04 response (July 2025, for "Claude") self-scores **72%**, with the weakest sections being exactly AEGIS's strengths: **AAAI/logging 61%, AI controls 66%, Privacy 54%**. The pattern across the AI section is uniform — control exists nowhere, customer is told to build it:

| HECVAT question (answered "No"/qualified) | AEGIS mechanism |
|--------------------------------------------|-----------------|
| AIGN-05 — business rules to keep sensitive data out of the model: "users must implement their own data governance policies before sending data to Claude" | Constitutional content gate before inference |
| AILM-03 — human intervention for LLM actions: customers build "approval workflows... through their integration architecture" | Guardian-approval gate; martingale suspension on unbounded action |
| AILM-04/05/07 — no plugin-call limits, no per-action resource limits, taint tracing unanswered | Law of Silence + execution budget ceiling (k·C_eval ≤ B_max) |
| AIPL-03/04 — AI kill-switch: "Customers are responsible for creating procedures to disable and reenable access" | Mode gate + martingale suspension = operable kill-switch |
| AAAI-11 — audit logs capped at 180 days regardless of customer settings | Hash-chained export, customer-held, unlimited retention |

A university deploying Claude behind AEGIS can answer Yes-with-mechanism on most of these rows in its own assessment. Two more HECVAT facts to retain: hosting is **US-only** (Iowa/Ohio/N. Virginia — no regional storage option, DCTR-03 No), which makes the AEGIS EU deployment (Vertex `europe-west3`) the answer for European institutions; and DCTR-16 admits cloud-provider KMS "means cloud hosting providers are able to access all data provided by Anthropic's customers" — the same key-custody gap the CMEK section covers. Full row-level digest: `references/docs-digest.md`.

---

## NIST 800-171r3 — The Government Market Gap

Coalfire's attestation (Jan 13, 2026): Anthropic implemented **90 of 98** NIST SP 800-171r3 requirements for Claude + Claude API (CUI protection). The 8 low-severity findings all have remediation plans (account lifecycle, CUI training, security literacy, IR training docs, software program reviews, identifier characteristics).

Relevance for AEGIS:
- NIST 800-171 is the gateway to US federal/defense contractors handling CUI. Anthropic is positioned there; an AEGIS layered on Claude inherits that posture for the model layer but needs its own 800-171 story for the governance layer
- AEGIS's deterministic audit controls (03.03.x family) are its strongest 800-171 chapter — hash chains exceed the audit-record integrity requirements
- Lowest-effort win: document AEGIS against 800-171r3 §3.3 (Audit and Accountability) using the existing `/platform/compliance/export` endpoint as evidence

### FISMA / FedRAMP — the rest of the federal picture (Claude Code Public Sector guide, v1.0 Jan 2026)

- **Anthropic claims no FedRAMP authorization of its own.** Federal posture is inherited entirely from AWS GovCloud Bedrock or GCP Vertex AI with Assured Workloads (`us-east5`). Reinforced by HECVAT DATA-04: crypto modules are not FIPS 140-2/3 validated — the cloud route is the FIPS answer too.
- The guide's shared-responsibility table scopes Anthropic to exactly four things: "Model safety and alignment, Protection against adversarial inputs, Model vulnerability management, Supply chain security for model weights." NIST 800-53 implementation, audit logging, usage governance, "Risk assessment for AI use cases," and incident response are all agency-side, with no tooling offered — only CloudTrail / Cloud Audit Logs + agency SIEM.
- AEGIS fit is the same shape as the commercial story, federalized: deployed in the agency's own GCP project under Assured Workloads, AEGIS supplies the application-level, hash-chained audit trail (prompts, outputs, tool calls, verdicts) that the guide tells agencies to assemble themselves from infrastructure logs.

---

## HIPAA-Ready — Where the BAA Actually Ends (Implementation Guide, 2026.05.06)

"HIPAA-Ready" is a BAA-eligibility construct, not a certification, and its boundary is the partnership argument in miniature:

- **Zero Data Retention is the load-bearing control** (Claude Code is eligible only with ZDR; 4/1/2026+ BAAs cover the 1P API only with ZDR) — and **the most agentic surfaces are "incompatible with ZDR"** and outside the BAA entirely: Claude Code remote/web/Review/Security/Computer Use, Batch/Files/Code Execution APIs, MCP connectors. The safest mode and the most agentic modes are mutually exclusive. A healthcare enterprise that wants governed agentic Claude needs a layer Anthropic does not sell.
- Anthropic retains audit/usage logs **up to 1 year**; HIPAA documentation retention is 6 years — the export-and-preserve burden is the customer's. `/platform/compliance/export` + the hash chain is precisely that archive.
- Customer obligations named in the guide that AEGIS ships as mechanisms: PHI kept out of non-eligible fields (chat/project/workspace names — Anthropic disclaims them), inactivity logoff, failed-login lockout, periodic audit-log review.
- BAA coverage varies by product surface × ZDR status × BAA signature date (pre-12/2/2025 / post / 4/1/2026+) — a genuinely complicated eligibility matrix that a policy engine can machine-enforce at the gateway. Nobody ships that engine.
- Honest caveat to carry into any healthcare conversation: the Trust & Safety carve-out means flagged content is reviewable by Anthropic personnel even under a BAA, and Vertex/Bedrock routes are out of the guide's scope (the AEGIS Vertex deployment relies on the separate attestation-grade boundary: "Anthropic is unable to access prompts or responses sent via these services").

One transparency note for the EU/California file: the AB 2013 Training Data Documentation (Dec 2025) concedes training data "may include material covered by third-party intellectual property rights" and "may incidentally include personal information," with user data used for training on an **opt-out** basis — and offers downstream customers no tooling for their own AB 2013 / Art. 53 disclosures on Claude-based fine-tunes. Provenance disclosure is an AEGIS lineage-chain output.

---

## The Attestation Boundary — Where Audited Territory Ends

From the SOC 2 Type 2 + CSA STAR L2 report (Schellman, period Oct 2024–Sep 2025, unqualified opinion, one exception: a quarterly privileged-access review missed for one of two sampled quarters):

1. **Zero-CUEC posture with one loaded carve-out.** Anthropic asserts "complementary user entity controls are not required, or significant" — then lists 8 advisory responsibilities. CUER.8 is the partnership headline: *"User entities are responsible for implementing controls to secure the local environments where Claude Code is executed and to review any generated or modified code prior to deployment."* The only mention of Claude Code in the whole report is to hand its governance to the customer. Agentic-surface governance is formally nobody's attested territory — that unattested gap is AEGIS's layer.
2. **Attestation-grade Vertex boundary.** "Notably, Anthropic is unable to access prompts or responses sent via these services" now exists inside an independent auditor's report — cite the SOC 2, not just the HIPAA report, for the trust-boundary argument.
3. **Privacy is processor-scoped.** P1.1/P2.1/P3.2 carved out to the data controller. An enterprise using Claude carries controller obligations no Anthropic attestation covers; AEGIS's audit chain is the controller-side evidence layer.
4. **ISO SoA v1.4 has zero exclusions** across ISO 27001:2022 + ISO 42001:2023 — and ISO 42001 A.10.2 ("responsibility allocation between the organization, its partners, suppliers, customers and third parties") is the formal hook for an AEGIS partnership story: Anthropic's own AIMS anticipates allocated customer/partner responsibilities.
5. **Pen testing (Leviathan + Wolfpack, Jan 2026: 9 findings, all Low) covers infra/web/API/clients — no agentic or model-level adversarial stream** in the customer package. Position on the gap, never on vendor-security FUD: their infra posture is demonstrably strong.

Distribution discipline: the SOC 2 report, pen-test package, and ISO SoA are restricted-use/NDA, watermarked per-recipient. Internal strategy use only; never quote them in external-facing material.

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
