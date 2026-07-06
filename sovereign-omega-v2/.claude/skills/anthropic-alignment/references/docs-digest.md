# Anthropic Document Digests — Reference Layer

**Epistemic Tier: T2** (verbatim extracts and structured digests of published Anthropic enterprise documentation)
**Parent skill:** `anthropic-alignment` — this file holds the per-document detail; SKILL.md holds the strategy.
**Read this file when:** drafting compliance documents, answering a specific "what exactly does Anthropic say about X" question, or verifying a quote before it goes into external-facing material.

All quotes below are verbatim from the source documents. Do not re-quote from memory — copy from here.

---

## Enterprise Security Paper Series (4 companion papers)

Common frame: each paper covers the "Claude Enterprise Suite," shares an identical "Continuous verification" section, an identical 48-hour breach-notification commitment ("Anthropic notifies customers in writing without undue delay, and in any event within 48 hours, after becoming aware of a Security Breach affecting Customer Personal Data" — DPA Section G), and a recurring design refrain: **"Detection on its own does not strengthen a boundary."** The architectural stance across all four: controls are held on the customer's side of the boundary — policy, classifiers, keys, identity, audit retention.

### Data Handling & Key Management (Last updated: May 15, 2026)

**CMEK — the dated roadmap item:**
> "*Customer-managed encryption keys (CMEK) is targeting availability in or before Q3 2026. Use of this feature will be subject to Anthropic approval." (footnote)

> "CMEK* via customer KMS (AWS KMS / Google Cloud KMS / Azure Key Vault); envelope encryption — Targeting 2026 Q3 — Customer KMS" (§8 Controls reference)

> "Expansion of CMEK* coverage to additional Claude products and key regions (see Anthropic documentation for current scope), subject to Anthropic customer approval." (§6, "2026 Q3")

> "Where CMEK* is enabled, backup copies of covered data are encrypted under the same customer-held key as primary storage, so revoking the key renders backup copies unreadable on the same basis as primary copies." (§9.3)

> "Data retained for safety review is held under Anthropic-managed encryption regardless of CMEK* status and is subject to its own retention limit." (§9.3)

Key facts:
- AES-256 at rest, TLS 1.2+ in transit (DPA Schedule 2 §E); envelope encryption for CMEK; key rotation is customer-side in their KMS — losing prior key versions = data loss is on the customer.
- Retention defaults: API inputs/outputs auto-deleted within 30 days; Chat/Cowork follow admin-set retention; Trust & Safety flagged content retained up to 2 years; deletion on termination within 30 days.
- "When accessing Claude directly through Anthropic's Claude Platform or Claude Products the user cannot currently set regional residency. We anticipate the option for US-only data in Q2 2026." (§5)
- "Residency and tenant isolation are independent controls." (§5)
- No customer-initiated restore/point-in-time recovery; backups retained ≤30 days; deletions propagate to backups within 30 days.
- "By default, Anthropic employees cannot access customer conversations unless the customer explicitly consents to share data as feedback." (§3.3)
- Sub-processor list at trust.anthropic.com/subprocessors with DPA §C objection right.
- Anthropic uses its own "Claude Security and Claude Code Review" products on control code paths.

Customer-side gaps a governance layer inherits: deletion/legal-hold orchestration before the 30-day windows; export workflows (no restore exists); tracking the safety-retention carve-out (2-year, Anthropic-managed keys, **outside CMEK** — cannot be crypto-shredded by the customer); sub-processor change monitoring.

### Data Loss Prevention & Content Controls (Last updated: May 8, 2026)

The skill's core thesis quote, confirmed verbatim (exec summary, restated §1, §2, FAQ):
> "Anthropic does not ship a native DLP engine. Claude is designed to be inspectable by the customer's DLP, SASE, or CASB over a published endpoint set; content policy and classifiers remain in the customer's stack."

> "Anthropic does not operate a DLP engine, classifier library, or content-policy console of its own." (§1)

The explicit middleware endorsement:
> "Customers place their gateway between calling applications and the Claude API and enforce content policy in that layer." (§3.6, Claude Platform)

The output-side gap (AEGIS's constitutional audit is exactly this):
> "There is no customer-configurable filter today that screens Claude's outbound responses for sensitive data in real time." (§8 FAQ)

> "Anthropic's Usage Policy and model-level safeguards govern harmful content categories (e.g., violence, illegal activity) but are not designed to catch customer-specific sensitive data such as PII or proprietary information." (§8 FAQ)

> "Can Anthropic redact sensitive content before it reaches the model? No. Redaction, blocking, and classification happen in your DLP layer before the request reaches Anthropic." (§8 FAQ)

The audit-log limitation (Compliance API is the content path):
> "Audit logs do not return prompt or response content, file uploads, or conversation context — they cannot satisfy a legal hold, a supervision review, or any workflow that needs to see what was actually said." (§8 FAQ)

Compliance API coverage (§4): GA, off by default, self-serve enable by Primary Owner. Org settings + Chat GA Dec 2025; Claude Platform GA Mar 2026 (AE-led activation, "v1 does not include per-message inference logging or Agent SDK sessions"); **"Claude Code and Claude Cowork — Not covered yet."**

Roadmap item to track (future integration surface AND partial substitute risk for inline gateways):
> "Pre-submission validation hooks — Callout to customer endpoint — Roadmap — Customer" (§7 controls reference; FAQ describes "a callout from Claude to a customer-defined endpoint before inference")

Technical integration facts: published endpoint set per surface (claude.ai, \*.claude.ai, api.anthropic.com, a-api.anthropic.com, a-cdn.anthropic.com, platform.claude.com, mcp-proxy.anthropic.com, \*.claudeusercontent.com; Cowork adds downloads.claude.ai, pivot.claude.ai, storage.googleapis.com); wildcard allowlisting recommended; SSE/WebSocket must be forwarded unbuffered through inline gateways; bridge.claudeusercontent.com (Chrome extension WebSocket) must be exempted from TLS interception; preserve SigV4 headers on bedrock-runtime.\*; exempt a-api/a-cdn when injecting `anthropic-allowed-org-ids`; egress IPs at platform.claude.com/docs/en/api/ip-addresses; Claude Code honors HTTPS_PROXY/HTTP_PROXY/NO_PROXY, managed-settings.json via MDM, mTLS via CLAUDE_CODE_CLIENT_CERT/KEY; OTel SIEM export for Claude Code CLI and Cowork desktop; **Cowork inference pinnable via MDM `inferenceProvider` to Bedrock, Vertex AI, Microsoft Foundry, or "a customer-operated gateway."**

### Identity & Access Controls (Last updated: May 15, 2026)

> "Claude does not operate a directory service; for organizations with SSO enforced, Claude does not maintain a parallel credential store." (§1)

> "Claude does not offer attribute-based access control, per-conversation ACLs, native just-in-time elevation, or Conditional Access signal pass-through." (§4.3)

Key facts:
- SAML 2.0 / OIDC, SCIM 2.0; IdP is authoritative; SCIM deprovision removes org membership, revokes OAuth tokens, ends active web sessions.
- RBAC three layers: custom roles + IdP-synced groups + product-level gating (also gates beta product access).
- Admin permissions (SSO/SCIM config, role management, audit log access, billing) governed by role: **"Targeting availability in June 2026."** (§4.2)
- Workload identity federation GA on Claude Platform: OIDC federation for AWS IAM roles, GCP service accounts, Azure/Entra, Kubernetes SAs, GitHub Actions. Long-lived API keys not discussed — service access framed entirely as OIDC federation.
- Domain capture: "Verified domains route any sign-up on your organization's email domain into your governed tenant rather than an unmanaged personal workspace, preventing shadow usage before it starts." (§3.3)
- Per-resource sharing (Projects, Skills) targets Claude accounts, not IdP groups; no per-user concurrent-session limit.

Gaps a governance layer inherits: ABAC / per-request policy; per-conversation ACLs; JIT elevation; conditional-access signals (device posture, risk) — none pass through to Claude, so a gateway must enforce them.

### Isolation & Connectivity (Last updated: May 15, 2026)

> "Anthropic does not offer per-customer dedicated infrastructure (dedicated VPCs, dedicated databases, dedicated inference hardware) or private network interconnects to its first-party platform." (§1)

> "every customer record carries an organization identifier; the identifier is derived from the authenticated session (not from any request parameter), stamped at write time by the repository layer, and used as a partition key on the primary index so that cross-partition queries are prevented at the storage engine. Application code operates above this layer and cannot bypass it." (§3.1)

> "Customers accessing Claude through Amazon Bedrock or Google Cloud Vertex AI may have access to those providers' private-connectivity options under those providers' terms..." (§4.2)

Key facts:
- Isolation is logical at all three layers (inference compute / app+control plane / storage); shared GPU capacity; "Inference is stateless with respect to customer data."
- Inbound IP allowlisting: per-org, enforced at login and session refresh, configured through the account team (not self-serve).
- No private interconnect on first-party platform; "Anthropic continues to evaluate private interconnect options based on customer requirements."
- Customer audit right: once per 12 months (DPA §F); pen-test summaries on request (DPA Sch. 2 §G.2).
- FAQ method for single-tenancy policies: "decomposing the policy into the specific risks it was written to address" — a ready-made argument template when a customer policy demands dedicated infrastructure.

Gaps a governance layer inherits: private network path (route via Bedrock/Vertex or be the gateway); egress IP churn coordination; continuous assurance between annual audits.

---

## Agentic Product Architectures (Cowork, Office Agents)

> **Handling note:** the Cowork documents are marked NDA-restricted / CONFIDENTIAL ([INTERNAL] in one case). Use for internal strategy only; nothing from this section goes into external-facing material without checking distribution terms. The Vendor Code of Conduct separately requires written authorization before any public statement about a relationship with Anthropic.

### Cowork 3P Security Overview v2.0 (April 2026)

Cowork on third-party platforms = the same commercial Claude Desktop build, MDM-configured to route inference to Bedrock, Vertex AI, or Azure AI Foundry:

> "In this configuration, conversation content never reaches Anthropic infrastructure. Prompts, attached files, tool inputs and outputs, and model responses travel only between the end-user's machine and your chosen cloud inference endpoint." (Overview)

> "Set to your OTLP collector to collect Cowork prompt, tool use, and other event information." (§3, `otlpEndpoint`)

Key facts:
- 12+ MDM policy keys: `allowedWorkspaceFolders`, `coworkEgressAllowedHosts`, `disabledBuiltinTools`, `managedMcpServers`, `isDesktopExtensionSignatureRequired`, `otlpEndpoint/otlpProtocol/otlpHeaders`, telemetry kill-switches (3, default ON), `disableAutoUpdates`, etc. Admin keys take precedence; user controls operate only within admin bounds.
- "Destinations are enforced by Content Security Policy; a destination removed by policy is rejected by the browser engine, not by application logic." (§2) — structural, not behavioral, enforcement.
- Fully air-gappable from Anthropic: with all four disable keys set, "the only remaining egress is to your inference endpoint and the one-time VM image fetch."
- Self-disclosed leak vector: MCP server hostnames leak to Google's favicon service (§1.3).
- Inference pinnable to "a customer-operated gateway" — the AEGIS slot, by configuration.

### Claude Cowork: Desktop Security Architecture Overview (v5.0, Apr 21, 2026 — [INTERNAL])

Host-loop architecture: Agent SDK as host user process; shell/code execution dispatched to a hypervisor-isolated Linux VM (Apple Virtualization.framework / Hyper-V; virtio-vsock / named-pipe RPC; ~4 GB RAM, 10 GB sparse disk, SHA256-validated rootfs).

Deployment-layer enforcement stack (none of it trusts the model):
1. Tool-surface restriction (JS-execution tool deleted outright, "Replaced by VM-proxied Bash tool")
2. Filesystem permission layer — syscall-level path canonicalization, Unicode/UNC/8.3/ADS handling, per-hop symlink containment checks
3. Sensitive-path guard: "Writes to shell profiles, .bashrc, .gitconfig, .git/, and .claude/ always prompt. This check runs before allow-rule evaluation, so a standing allow rule cannot bypass it." (§6.1)
4. Hypervisor VM + per-session Linux user, private mount namespace, privilege drop, `PR_SET_NO_NEW_PRIVS`, seccomp BPF ("prevents spawned processes from establishing direct communication channels to the host")
5. Dual egress allowlists: host web-fetch checks (private-IP reject, per-redirect re-validation) + in-VM SRT domain allowlist
6. Binary/VM-image integrity: pinned SHA-256 digests, "It does not self-update"
7. Server-side Constitutional Classifiers as the final output-policy layer — model-external governance layered on top of model alignment, by Anthropic, for Anthropic's own product

Adversarial notes: "workspace unavailable" degradation is fail-open on the file plane (agent keeps host file tools when the VM is dead); conversation history is structurally invisible to the VM (host-only storage).

### Office Agents 3P Architecture

Three deployment modes, all with "No Anthropic infrastructure in data path": customer LLM Gateway ("LiteLLM / Portkey / Kong / custom Anthropic-compatible /v1/messages endpoint. Customer-controlled URL. Customer manages auth, logging, rate limits"), Bedrock Direct (Entra → STS, 1-hr creds, CloudTrail attribution via RoleSessionName = user UPN), Vertex Direct (Google OAuth). Config precedence: bootstrap > Entra attributes > manifest params. Weak point noted: `gateway_token` / `google_client_secret` can ride as manifest URL params.

### Claude in Excel & PowerPoint (1P baseline)

OAuth 2.0 + PKCE, 1-hr tokens; "Chat history is in-memory only"; content goes to Anthropic API under commercial terms. The thin 1P baseline that the 3P federation was built to replace — evidence that enterprise demand forced the no-Anthropic-in-path architecture.

### Claude Opus 4.8 Model Documentation Form (v1.0, May 28, 2026)

EU AI Act Art. 53(1)(b)/Annex XII form. Deltas vs the Fable/Mythos form: input text max **1M tokens**, **video listed as input modality** (audio not), output max **300K tokens**; release + EU market date both May 28, 2026; distribution incl. Azure AI Foundry and Slack; "A portion of the data corpus comes from acquired physical works, such as books"; "The model itself is not directly trained on user data, but ancillary internal-only models such as preference models and classifiers may be."

### Vendor / corporate governance (skims)

- **Global Vendor Code of Conduct v1.2 (eff. Mar 19, 2025)** — partner table stakes: "Maintain, and make available to Anthropic, industry accepted certification(s) (e.g. SOC 2 Type 2) performed by an independent third party"; breach notice via disclosure@anthropic.com; flow-down compliance to subcontractors; Anthropic audit rights; AI-ethics compliance (fairness, transparency, privacy, accountability); **prior written authorization required** before incorporating Anthropic IP, "Making public statements about their relationship with Anthropic," or using name/logo; no using Anthropic confidential info with other LLM providers.
- **Global Code of Conduct v3.4 (eff. Oct 30, 2025)** — applies to vendors/contingent workers; Vendor and Supply Chain section p.29.
- **Modern Slavery Act Statement (FY2024, signed June 26, 2025)** — "approximately 1,000 employees worldwide"; subsidiaries UK, Ireland, Canada, Switzerland, US.
- **COI (ACORD 25, Apr 29, 2026)** — GL $1M/occ, $2M agg (Zurich); umbrella $5M (HDI Specialty); WC $1M; period 2026-04-08 → 2027-04-08; broker Newfront.

---

## Vendor Questionnaires — VSA Core & CAIQ Lite (March 2025)

### VSA Core ("VSA CORE Questionnaire 2022 FINAL", respondent "Anthropic Compliance Team", scope "Claude AI models")

Hard numbers stated:
- Vulnerability mitigation SLAs: "Critical - 72 Hours, High - 30 Days, Medium - 90 Days, Low - 180 Days." (Q20)
- Breach notification: "Anthropic maintains a 48 hour notification period for customers whose data has been identified as being impacted by a Data Breach." (Q34; repeated against GDPR's 72h question — stricter than GDPR)
- Annual external audits: "SOC 2 Type 2 - CSA STAR Level 2 - ISO 27k1 - ISO 42k1 - penetration tests - HIPAA Security Attestation" (Q42/43)
- Tooling named: CrowdStrike Falcon, CodeQL, JFrog Xray, ECR image scanning, AlloyDB, centralized SIEM/SOAR. Stack: "Python, TypeScript, Kotlin, AWS, GCP."

Notable disclosures:
- **Training carve-out (Q44):** "When information is found to be in violation of our Acceptable Use Policy, such information may be used to improve our safety classification mechanisms." — conditional data-use right on AUP-violating content.
- **"Coffee shop networking"** (Q21): no traditional corporate network, no site-to-site VPNs, no location-based default access to cloud environments.
- Org-wide annual developer security training admitted as aspirational ("currently pursuing"); pen-test methodology answer is "Dependent on pentest"; geographic deployment question left blank.
- "Token counts" explicitly listed as collected metadata. Anthropic Ireland Limited named as the EU service entity (no Art. 27 rep needed).

### CAIQ Lite v4.0.3 (124 questions: **122 Yes / 1 No / 1 NA**; CSC Responsibilities = "None" on every row)

- **The single "No" (IVS-03.2, internal traffic encryption):** "Due to latency and other technological constraints, communications within our kubernetes clusters and other internal resources may not be encrypted." — east-west intra-cluster traffic may be plaintext.
- **The single "NA" (CCC-05.1):** no SLA provisions limiting tenant-impacting changes — multi-tenant SaaS.
- **Two-Party Control on model weights (IAM-10.1):** "Some specific data and systems access internally (e.g. Access to AI Model Weights) necessitate Two-Party Control (2PC)... time-bound and automatically revoked at expiry." Paired admission: ordinary job-duty access "is not time-bound."
- **Key lifecycle fully delegated to cloud KMS** (all CEK rows, "Shared CSP and 3rd-party"): "Anthropic utilizes managed encryption keys supplied by our trusted cloud providers and inherits all associated controls" — consistent with CMEK being roadmap, not current state.
- Access-provisioning logs: "immutable and stored for, at a minimum, 1 year" (IAM-06.1). Tenant isolation: logical, "by OrdID and UUID."
- Non-production use of Customer Data possible "with an explicit signed agreement" (DSP-06.1) — negotiable exception.
- Subprocessor change notice defaults to Trust Center announcements; direct notice only if contracted (DSP-14.1).
- Resilience claim with no RTO/RPO numbers anywhere: able to restore "even in the event of a regional outage of an entire cloud provider" (BCR-08.3); backups "Immutable by default."

AEGIS relevance: the 48h/72h/30d/90d/180d numbers are the SLA baseline an AEGIS-layer contract should match or beat; the IVS-03.2 "No" and the AUP-content training carve-out are the two facts most likely to surface in a customer's vendor review — AEGIS's gateway position can't fix either, but its hash-chained export gives the customer an independent record of what was sent (the compensating control posture).

---

## HECVAT 4.04 — "Claude" (July 2025 v2) — The Higher-Ed Assessment

Anthropic's own workbook self-scores **72% overall (2,305/3,200)**. Weakest sections: IT Accessibility 39%, Company Info 50%, Privacy 54%, Documentation 56%, **AAAI (logging) 61%, AI 66%**. Strongest: Third Parties / App Security / Firewalls / Incident Handling 100%.

### The "No" answers that map to AEGIS mechanisms (verbatim)

- **AIGN-05** (business rules to keep sensitive data out of the model) — No: "Currently, users must implement their own data governance policies before sending data to Claude."
- **AILM-03** (human intervention for LLM actions) — No: "Enterprise customers can implement their own approval workflows and human-in-the-loop processes for specific use cases through their integration architecture if their security requirements demand it."
- **AILM-04/05** — no hard limits on plugin calls per input, no per-step/per-action resource limits; **AILM-07** (taint tracing on plugin content) left entirely unanswered — the only blank AI question.
- **AIPL-03/04** (AI kill-switch) — Yes, but: "Customers are responsible for creating procedures to disable and reenable access to Claude by their team in the event of an AI incident specific to their organization."
- **AAAI-11** (log retention documentation) — No: customers get exactly **180 days** of audit logs, "not impacted by the retention settings that may have been applied by the customer to their data."
- **AAAI-18** (auto session lock) — No: "There are no plans at this time."
- **DATA-04** (FIPS 140-2/3 validated crypto) — No, unexplained.
- **DATA-19** (single tenant) — No; **DCTR-03** (regional storage) — No: hosted only in "GCP us-central1 (Iowa), GCP us-east5 (Ohio), AWS us-east-1 (North Virginia)" — **US-only hosting**.
- **DCTR-16** — blunt admission: "Anthropic leverages key management services provided by its cloud hosting providers. This means cloud hosting providers are able to access all data provided by Anthropic's customers."
- **AISC-01** (remove sensitive data from model) — No: opted-in training data "can be removed from the training data set, but will not be 'removed from the model', per se."
- **DOCU-01/02** (BCP/DRP tested annually) — both No: "Testing plans are currently in process."
- **VULN-02** (share vuln scan results) — No, on principle.
- **ITAC-07** — "Currently, Claude.ai Enterprise does not conform to WCAG 2.1 AA, so Anthropic is unable to agree to meeting this standard as part of a contractual agreement."

### Hard facts

- HIPAA answers scoped to the **API product only**; "For Claude for Work HIPAA compliance is currently in Progress." (HIPA-01); HIPAA log backup/retention explicitly the customer's job (HIPA-23); Zero Data Retention and Custom Data Retention available.
- **No FedRAMP/StateRAMP mention anywhere**, despite disclosure of Anthropic Public Institutions, LLC (CAGE 03J46, "structured to support government contracting").
- Cyber insurance "a minimum of $5 million" (HFIH-04). Security team ~100, CISO-led. Delaware PBC inc. 2021-01-26.
- Security stack named: Cloudflare WAF (+AWS WAF, Cloud Armor), CrowdStrike Falcon, Kandji MDM, Google Santa, Tailscale, Context-Aware Access, CodeQL, JFrog Xray, Dependabot/Secret Scanning, Socket.dev, "Wiz (deployment in progress)", Terraform/Atlantis.
- Vuln SLAs match VSA/CAIQ: 72h/30d/90d/180d. Breach notice 48h. Jan 2024 contractor incident disclosed (customer names + credit balances sent to a third party; "not a breach of Anthropic systems").
- NIST AI RMF: "While not formally mapped to the NIST AI RMF specifically…" — AI risk answers grounded in RSP/ASL/Constitutional AI instead.

### The middleware whitespace, in HECVAT's own grain

Pre-ingestion data governance (AIGN-05), human-in-the-loop approval (AILM-03), tool/plugin limits and taint tracing (AILM-04/05/07), AI kill-switch procedures (AIPL-03/04), audit-log retention beyond 180 days (AAAI-11), session controls (AAAI-18), end-user AI opt-out (DPAI-08 No) — every one is answered "customer-side." An AEGIS-fronted deployment converts most of these No/qualified answers into Yes-with-mechanism for a university's own HECVAT response.

---

## SIG Lite 2025 (March 2025) — Deltas

Scope: "Claude AI", all first-party products, whole company. 128/128 answered. Marked "internal use only. Do not distribute outside of the organization."

- **K.11 retention:** "As a default, we store Customer Data (prompts/responses) for 30 days from receipt or generation, or for up to 2 years if that data was found to be in violation of our Acceptable Use Policy or Terms of Service."
- **M.1** — endpoints never touch scoped data (No): all Customer Data exists only in cloud environments; Context-Aware Access binds access to company-owned approved devices.
- "Coffee shop networking" used to answer No/N/A on DMZ (N.8), wireless (N.9), non-company devices (M.1.5).
- **R.5 (AI inventories):** inventories cover "data used in training, model weights"; governed by the Responsible Scaling Policy; "active ISO 42k1 certification."
- **I.1.1:** "Customer Data is never used within, or copied to, Anthropic's testing environments." (CAIQ adds: unless "an explicit signed agreement.")
- Infra named: GKE + EKS (inference), Cloud Run (front end), AlloyDB/BigQuery/Aurora (storage); Linux-only, no Windows servers.
- SOC 2 Type 2 includes the **Privacy** Trust Services Criteria; DPO elected, aligned with Anthropic Ireland; Executive Risk Council reports to the board.
- All environmental/ESG questions N/A — "inherits the ESG (Environmental) commitments provided by our Trusted Cloud Providers."
- Every privacy-regulation trigger (GLBA, FACTA, state, EU, PIPEDA, minors) deflected to "determined by the customer['s] implementation" — the customer owns data classification and regulatory triggering.

---

## Attestations & Audits

> **Handling note:** the SOC 2 report is restricted-use (specified users only); the pen-test package and ISO SoA are watermarked per-recipient and NDA-restricted. Internal strategy use only.

### SOC 2 Type 2 + CSA STAR Level 2 (Schellman & Company, report dated Nov 12, 2025; period Oct 1, 2024 – Sep 30, 2025)

- Scope: Security, Availability, Confidentiality, **Privacy** (Processing Integrity NOT in scope) + CSA CCM v4.0.3 (= the STAR Level 2 attestation). System: "AI Services" = Console + API, claude.ai web, Claude Desktop, Claude Mobile, and API via Vertex/Bedrock.
- Opinion: unqualified. **Exactly one exception in the extracted matrices (≈291 results):** CC6.2.5 — "logical access privileges were not reviewed by management for one of two quarters sampled" (the quarterly privileged-access review). Everything else "No exceptions noted."
- **Zero-CUEC posture:** "complementary user entity controls are not required, or significant" — followed by 8 advisory CUERs. The strategically loaded one:
  > **CUER.8** — "User entities are responsible for implementing controls to secure the local environments where Claude Code is executed and to review any generated or modified code prior to deployment in their environments." — the only Claude Code mention in the report; agentic-surface governance is formally the customer's job.
- Attestation-grade Vertex/Bedrock boundary quote: "Notably, Anthropic is unable to access prompts or responses sent via these services."
- Privacy criteria P1.1/P2.1/P3.2 + CCM DSP-11 carved out — "the responsibility of the data controller and not Anthropic given its role as a data processor." Controller-side notice/consent obligations are formally outside the attestation.
- Subservice carve-out: GCP + AWS hosting excluded; CSOC.5 expects full encryption-key lifecycle management at the cloud providers (consistent with the CMEK gap).
- Facts: GCP us-central1/us-east5 + AWS us-east-1; hardware-token MFA; Google Santa allowlisting via Kandji; Tailscale-only ingress/egress for R&D; daily backups retained 30 days; "Production data is not used in testing environments unless there is an agreement in place for fine-tuning of a specific model being used on a per client basis."
- AI-specific: Safeguards team + Observability team described; **no model-specific control activities in the testing matrices** — all tested controls are conventional ITGC/security.

### ISO Statement of Applicability v1.4 (ISO 27001:2022 + ISO 42001:2023, combined)

- **Zero excluded controls.** All 93 ISO 27001:2022 Annex A controls (incl. physical 7.x) and the full ISO 42001:2023 Annex A set marked Applicable + "Implemented."
- ISO 42001 controls confirmed in force, the ones AEGIS extends at the customer boundary: A.5.2 (AI system impact assessment), A.6.2.8 (event logs), A.7.5 (data provenance), A.8.3 (external adverse-impact reporting), A.8.4 (incident communication), **A.10.2 (responsibility allocation "between the organization, its partners, suppliers, customers and third parties")** — the formal hook where customer-side allocation lives.

### Annual Penetration Testing Reports (Jan 2026 update)

- Firms: Leviathan Security Group (OSINT + network; web app + API) and Wolfpack Security (Claude Desktop + Mobile attestation).
- **9 findings, all Low severity; 8 Closed, 1 "Partially fixed" due 2026-03-01.**
- **No Claude Code or agentic/AI-behavior testing stream visible** (no prompt-injection / model-level adversarial stream in the customer package) — the assurance gap AEGIS positioning can speak to, carefully (their infra posture is strong; the gap is the agentic layer, not vendor security).

### Anthropic PBC.pdf (actually an ACORD 25 COI, Apr 29, 2026, via Aon)

- Cyber Liability ACL124648501: **$5M aggregate, claims-made, $500K SIR**, includes Tech E&O; period 04/14/2025–06/14/2026. Insurers: Associated Industries (cyber line), Starr Surplus, Federal Insurance.
- Certificate holder: **Anthropic Ireland Limited, Dublin 4 — Register Number 760497** (useful hard fact for EU contracting).
- Note: a second COI in the folder (Newfront, Apr 2026) shows GL $1M/occ + umbrella $5M — two brokers, different lines.

### CVE-2026-22561 (Claude for Windows installer)

- DLL search-order hijacking → local privilege escalation; CVSS 4.0 base 6.6 (Medium), CWE-427; installer-only (installed apps unaffected); fixed in 1.1.3363, Feb 17, 2026; external researcher credited (GMO Cybersecurity by IERAE).
- Citable maturity signals: CVE assignment + CVSS 4.0 scoring + precise blast-radius limitation + coordinated disclosure with credit.

---

## US Federal — "Best Practice Guide: Claude Code for Public Sector" (v1.0, January 2026)

- **Anthropic claims no FedRAMP authorization of its own anywhere in the document.** The FedRAMP High posture is entirely inherited: Option 1 = AWS Bedrock in GovCloud (`bedrock-runtime.us-gov-west-1/us-gov-east-1.amazonaws.com`); Option 2 = GCP Vertex AI with Assured Workloads, region `us-east5`. Config: `CLAUDE_CODE_USE_BEDROCK=1` / `CLAUDE_CODE_USE_VERTEX=1`, plus `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1`, `CLAUDE_CODE_DISABLE_TELEMETRY=1`.
- Shared-responsibility table, Anthropic row (verbatim scope): "Model safety and alignment, Protection against adversarial inputs, Model vulnerability management, Supply chain security for model weights." **Everything else is the agency's**: NIST 800-53 implementation, data classification, usage policies and governance, audit logging and monitoring, "Risk assessment for AI use cases," incident response, continuous monitoring.
- AU family (AU-2/3/12) delegated wholly to CloudTrail / GCP Cloud Audit Logs + agency SIEM — "there is no Anthropic-native, application-level audit trail of prompts/outputs/tool calls." SC-12 recommends agency-held CMEK. 800-53 families touched: AC, AU, CM, IA, SC, SI; the rest left to the agency RMF.
- Cross-fact from HECVAT DATA-04: cryptographic modules are **not FIPS 140-2/3 validated** — the GovCloud-Bedrock route is how the FIPS question gets answered for federal deployments.
- AEGIS fit: the agency-side hole is governance tooling — an AEGIS deployment in the agency's own GCP project (Assured Workloads) supplies the application-level, hash-chained audit trail the guide says to assemble from cloud logs.

## HIPAA-Ready Offering Implementation Guide (2026.05.06)

- "HIPAA-Ready" = a BAA-eligibility construct over a product subset, varying by BAA signature date (pre-12/2/2025 / post-12/2/2025 / 4/1/2026+). Eligible: HIPAA-Ready Claude Enterprise; **Claude Code only with Zero Data Retention enabled ("for qualified accounts")**; 1P API on a HIPAA-enabled org (4/1/2026+ BAAs: API covered only with ZDR).
- **The agentic surfaces are structurally outside the BAA:** Claude Code remote/web/Review/Security/Computer Use — "Available to use without ZDR but this feature is not covered under Anthropic's BAA. This feature is incompatible with ZDR." Batch/Files/Skills/Code Execution/Computer Use APIs: "Not covered under Anthropic BAA and not accessible for HIPAA-Ready API users." MCP connectors: data to third parties "isn't covered under Anthropic's BAA."
- The safest mode (ZDR) and the most agentic modes are mutually exclusive — the sharpest single fact in the guide.
- PHI-prohibited fields (Anthropic disclaims HIPAA processing for them): chat/session names, project names, profile/workspace/skills names, attachment names, support tickets, billing.
- Customer obligations named: SSO+MFA, inactivity logoff, failed-login lockouts, periodic audit-log review. Audit/usage logs "retained for up to one (1) year" — HIPAA documentation needs 6 years; the export-and-preserve burden is the customer's (the hash-chained archive slot).
- Trust & Safety carve-out: "Customer Content may be used to support Trust & Safety-related controls..." — flagged content (potentially PHI) is reviewable by Anthropic personnel even under the BAA.
- Vertex/Bedrock not addressed — 1P surfaces only.

## AB 2013 Training Data Documentation (Claude Model Family, December 2025)

- California Civil Code §3111 disclosure, all Claude models since 2023. Five source categories: public web crawl (robots.txt-respecting, no CAPTCHA bypass), third-party commercial datasets, labeling services/contractors, "Data from Claude users who have not opted-out from model training," internally generated/synthetic.
- Verbatim admissions: datasets "may include material covered by third-party intellectual property rights"; "training data may incidentally include personal information."
- No concrete date ranges or token counts — deferred to model/system cards.
- AEGIS angle: an enterprise fine-tuning on Claude gets no tooling from Anthropic for its own AB 2013 / EU AI Act Art. 53 training-data summaries — provenance disclosure is the artifact class AEGIS's hash-chained lineage produces.

---

*End of digest. 25 documents encoded across: enterprise security paper series (4), attestations/audits (5), vendor questionnaires (4), regulated-market guides (3), agentic product architectures (5), corporate/vendor governance (4).*
