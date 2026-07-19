/**
 * SwarmDemoWidget — live interactive preview of the 39-dept swarm
 * EPISTEMIC TIER: T2 (demo outputs are template-based, labeled as such)
 *
 * No API key required. Simulates the swarm response client-side so visitors
 * can experience the output format before purchasing API access.
 * Template outputs are clearly labeled. Real calls use Claude Opus 4.8.
 */
import { useCallback, useRef, useState } from 'react'

type Mode = 'revenue' | 'analysis' | 'gtm' | 'retention' | 'competitive' | 'technical' | 'regulatory' | 'fundraising'

const MODES: { value: Mode; label: string }[] = [
  { value: 'revenue',     label: 'Revenue' },
  { value: 'analysis',    label: 'Analysis' },
  { value: 'gtm',         label: 'GTM' },
  { value: 'retention',   label: 'Retention' },
  { value: 'competitive', label: 'Competitive' },
  { value: 'technical',   label: 'Technical' },
  { value: 'regulatory',  label: 'Regulatory' },
  { value: 'fundraising', label: 'Fundraising' },
]

interface Dept {
  id: string; role: string; category: string
}

const DEPARTMENTS: Dept[] = [
  { id: 'REV-01', role: 'Strategy',    category: 'revenue' },
  { id: 'REV-02', role: 'Finance',     category: 'revenue' },
  { id: 'REV-03', role: 'Pricing',     category: 'revenue' },
  { id: 'MKT-01', role: 'Brand',       category: 'marketing' },
  { id: 'MKT-02', role: 'Content',     category: 'marketing' },
  { id: 'MKT-03', role: 'SEO',         category: 'marketing' },
  { id: 'MKT-04', role: 'Paid',        category: 'marketing' },
  { id: 'MKT-05', role: 'Social',      category: 'marketing' },
  { id: 'SLS-01', role: 'Outbound',    category: 'sales' },
  { id: 'SLS-02', role: 'Inbound',     category: 'sales' },
  { id: 'SLS-03', role: 'Partner',     category: 'sales' },
  { id: 'SLS-04', role: 'Enterprise',  category: 'sales' },
  { id: 'PRD-01', role: 'Product',     category: 'product' },
  { id: 'PRD-02', role: 'UX',          category: 'product' },
  { id: 'PRD-03', role: 'Data',        category: 'product' },
  { id: 'PRD-04', role: 'API',         category: 'product' },
  { id: 'ENG-01', role: 'Backend',     category: 'engineering' },
  { id: 'ENG-02', role: 'Frontend',    category: 'engineering' },
  { id: 'ENG-03', role: 'Infra',       category: 'engineering' },
  { id: 'ENG-04', role: 'Security',    category: 'engineering' },
  { id: 'ENG-05', role: 'AI/ML',       category: 'engineering' },
  { id: 'OPS-01', role: 'RevOps',      category: 'operations' },
  { id: 'OPS-02', role: 'Support',     category: 'operations' },
  { id: 'OPS-03', role: 'Legal',       category: 'operations' },
  { id: 'OPS-04', role: 'Compliance',  category: 'operations' },
  { id: 'RES-01', role: 'Research',    category: 'research' },
  { id: 'RES-02', role: 'Competitive', category: 'research' },
  { id: 'RES-03', role: 'Customer',    category: 'research' },
  { id: 'FIN-01', role: 'Accounting',  category: 'finance' },
  { id: 'FIN-02', role: 'Treasury',    category: 'finance' },
  { id: 'FIN-03', role: 'Tax',         category: 'finance' },
  { id: 'EXE-01', role: 'CEO',         category: 'executive' },
  { id: 'EXE-02', role: 'COO',         category: 'executive' },
  { id: 'EXE-03', role: 'CTO',         category: 'executive' },
  { id: 'EXE-04', role: 'CFO',         category: 'executive' },
  { id: 'GOV-01', role: 'Ethics',      category: 'governance' },
  { id: 'GOV-02', role: 'Risk',        category: 'governance' },
  { id: 'CON-01', role: 'Audit',       category: 'constitutional' },
  { id: 'CON-09', role: 'Guardian',    category: 'constitutional' },
]

const CATEGORY_COLORS: Record<string, string> = {
  revenue:        '#34d399',
  marketing:      '#818cf8',
  sales:          '#60a5fa',
  product:        '#a78bfa',
  engineering:    '#38bdf8',
  operations:     '#fb923c',
  research:       '#facc15',
  finance:        '#4ade80',
  executive:      '#f472b6',
  governance:     '#f87171',
  constitutional: '#fbbf24',
}

function deptOutput(obj: string, mode: Mode, dept: Dept): string {
  const o = obj.slice(0, 50) || 'this objective'
  const templates: Record<Mode, Record<string, string>> = {
    revenue: {
      Strategy:    `3 revenue vectors for "${o}": SMB upsell ($12k ARR), API monetisation, partner channel. T2: $2.4M ARR Y1.`,
      Finance:     `Unit economics: LTV/CAC ratio 3.2x. Payback period 8 months. Gross margin target: 72%. T1 validated.`,
      Pricing:     `Recommended: tiered usage-based pricing. Anchor at $499 sovereign. Decoy: $49 operator. T2 hypothesis.`,
      Brand:       `Positioning: "provable AI governance" — not a feature, an architecture. B2B trust signal. EU AI Act angle.`,
      Content:     `Content moat: technical depth + constitutional framing. Publish audit-chain explainers. SEO: "EU AI Act compliance".`,
      SEO:         `Target keywords: "EU AI Act Article 12", "tamper-evident AI audit", "AI governance API". 3.2k/mo combined volume.`,
      Paid:        `Paid: LinkedIn → compliance officers. CPL estimate $140. Retarget with case study. ROAS target 3.5x.`,
      Social:      `X: technical governance threads. LinkedIn: compliance-angle posts. HN: "Show HN" for dev community.`,
      Outbound:    `ICP: EU SaaS with AI features, regulated fintech, enterprise AI platform teams. Sequence: 4 touch, 6-day cadence.`,
      Inbound:     `Inbound lever: free explorer tier + HN launch. Expected 15% email→trial conversion. Self-serve first.`,
      Partner:     `Partner targets: AI governance consultancies (reseller), EU compliance firms (integration), AWS Marketplace.`,
      Enterprise:  `Enterprise motion: design-partner → pilot → expansion. LOI target: 3 before Series A raise.`,
      Product:     `Product priority: API reliability > audit export > dashboard. Jobs-to-be-done: prove AI decisions to auditors.`,
      UX:          `UX: zero-config onboarding. Key → first call in <2 min. Constitutional dashboard as retention driver.`,
      Data:        `North-star metric: weekly governed calls per active key. Secondary: NRR. Instrumentation: PostHog + BigQuery.`,
      API:         `API: REST first. Streaming SSE for async flows. OpenAPI spec auto-generated from contract types. SDK roadmap: Python, TS.`,
      Backend:     `Backend: Cloud Run (europe-west3). Scale: 0→5 instances. Latency P95: <4s per collaboration cycle. T2.`,
      Frontend:    `Frontend: governance dashboard + cockpit. Vite + React 18. Constitutional telemetry at 5s poll.`,
      Infra:       `Infra: Cloud Run + Supabase + Cloudflare. Cost at 10k calls/mo: ~$180 compute + $25 DB. Margin-safe.`,
      Security:    `Security: SHA-256 key hashing, no plaintext storage, HTTPS-only, service-role gating. No customer data in logs.`,
      'AI/ML':     `AI/ML: Claude Opus 4.8 + adaptive thinking. Model config via env var — upgradeable without redeploy.`,
      RevOps:      `RevOps: Supabase revenue_cycles table tracks every collaboration. PostHog for conversion funnel analysis.`,
      Support:     `Support: email-first (info@aegisomega.com). SLA: 48h. Self-serve docs at /docs.`,
      Legal:       `Legal: AGPL-3.0 for runtime. Commercial license for governance binder. GDPR: no PII in audit chain.`,
      Compliance:  `Compliance: EU AI Act Article 12 mapping COMPLETE. GDPR Article 22 mitigated. ISO 27001 roadmap: Q2 2027.`,
      Research:    `Market: $340M TAM (AI governance tools). SAM: $28M (EU regulated AI). SOM year 1: $2.4M. T2 hypothesis.`,
      Competitive: `Competitors: no direct match on constitutional audit chain. Adjacent: Credo AI (audit), Fiddler (monitoring). Moat: replay.`,
      Customer:    `Customer evidence: 3 design partner conversations (fintech, legal tech, enterprise AI). Common pain: audit readiness.`,
      Accounting:  `COGS: Claude API usage + Cloud Run + Supabase. Estimated 28% gross margin at $49 operator tier. T2.`,
      Treasury:    `Cash runway: bootstrapped. Break-even at 8 operator sales/mo. Target: 50 operator + 2 sovereign by Q3.`,
      Tax:         `Tax: Bosnia-Herzegovina entity. EU VAT registration required before €10k EU revenue. Stripe Tax recommended.`,
      CEO:         `Strategic priority: EU AI Act deadline (Aug 2026) creates urgency. Land 3 enterprise LOIs before Q4 2026.`,
      COO:         `Operations: solo founder → first hire at $5k MRR. Prioritise: sales, then engineering. OKR: $10k MRR in 90 days.`,
      CTO:         `Technical: replay sovereignty ACTIVE. Constitutional membrane VERIFIED. Next: Python SDK + OpenAPI spec.`,
      CFO:         `Financial: unit economics healthy at scale. Raise $500k pre-seed at $8M cap when $5k MRR demonstrated. T2.`,
      Ethics:      `Ethics review: epistemic tier labeling prevents overclaiming. T4/T5 blocked from src/. Risk: LOW.`,
      Risk:        `Risk: Anthropic pricing changes (mitigated: model config env var). GCP outage (mitigated: Cloud Run SLA 99.95%).`,
      Audit:       `Constitutional audit PASSED. All T0 invariants hold. Replay sovereignty active. Hash chain: INTACT.`,
      Guardian:    `GUARDIAN verdict: APPROVED. No T4/T5 constructs detected. AdaptivePower ≤ ReplayVerifiability. Proceed.`,
    },
    analysis: {
      Strategy: `Market analysis for "${o}": 2 competitive gaps. Differentiation: constitutional audit chain. Entry: Q3 2026. TAM: $340M.`,
      Finance: `Financial analysis: EU compliance software market CAGR 18%. AI governance sub-segment: 3× faster. T1 validated.`,
      Pricing: `Price sensitivity analysis: enterprise buyers anchor on legal/compliance budget ($50k+). $499 is noise. Expand upward.`,
      Brand: `Brand analysis: "constitutional AI" is unowned positioning. Technical credibility is the brand moat. T2.`,
      Content: `Content gap analysis: no competitor publishes EU AI Act technical deep-dives. 3 articles/week captures long-tail.`,
      SEO: `Keyword gap analysis: "AI Act Article 12 logging" — 0 competitors ranking. 890 searches/mo. T1 opportunity.`,
      Paid: `Paid channel analysis: LinkedIn CPL $140 vs email list $8. Focus: organic first, paid for retargeting only.`,
      Social: `Social analysis: X developer community + LinkedIn compliance audience. Two distinct ICPs, two content tracks.`,
      Outbound: `ICP analysis: EU SaaS > €1M ARR with AI features. 3,200 companies in TAM. Sequence qualification rate: 12%.`,
      Inbound: `Inbound analysis: HN "Show HN" drives 500-2000 developer visits. 8% email capture, 15% trial conversion. T2.`,
      Partner: `Partner ecosystem analysis: 40 EU AI governance consultancies. Top 5 have 200+ clients each. High-value channel.`,
      Enterprise: `Enterprise analysis: deals above $10k require procurement + legal review. Minimum 90-day sales cycle. Prepare LOI.`,
      Product: `Product analysis: audit export (PDF + JSON) is the #1 missing feature per design partner interviews. Build next.`,
      UX: `UX analysis: onboarding funnel drop at "get API key" step. Add email→instant key without PayPal for explorer.`,
      Data: `Data analysis: zero revenue_cycles recorded yet. Instrumentation is LIVE. Baseline established for launch.`,
      API: `API analysis: REST is correct choice for compliance tooling. GraphQL adds complexity without auditability gain.`,
      Backend: `Backend analysis: Cloud Run cold start 2-4s. Acceptable for compliance use cases. Min instances=1 for paid tiers.`,
      Frontend: `Frontend analysis: hub landing page converts at estimated 2.3% (industry avg). Demo widget projected +40% uplift.`,
      Infra: `Infrastructure analysis: 256MB Cloud Run is sufficient. Peak RSS 273MB confirmed in isolation test.`,
      Security: `Security analysis: no plaintext key storage. SHA-256 hashing in api_key_store. Service role gating: VERIFIED.`,
      'AI/ML': `AI/ML analysis: Claude Opus 4.8 with adaptive thinking is correct choice for 39-dept swarm. Cost: ~$0.12/call.`,
      RevOps: `RevOps analysis: revenue_cycles table gives full collaboration history. ARR projection trend available at 50+ records.`,
      Support: `Support analysis: email-first is correct at <50 customers. Implement ticketing system at 100+ customers.`,
      Legal: `Legal analysis: AGPL-3.0 forces disclosure if embedded in products. Enterprise clients need commercial license.`,
      Compliance: `Compliance analysis: Article 12 mapping covers 80% of requirements. Gap: human oversight documentation.`,
      Research: `Market research: 3 design partner interviews confirm pain: "we can't prove to auditors how the AI decided".`,
      Competitive: `Competitive analysis: 0 direct competitors with hash-chained audit trail. Window: 12-18 months before clones emerge.`,
      Customer: `Customer analysis: compliance officers are buyers, developers are users. Two-persona sales motion required.`,
      Accounting: `Accounting analysis: current COGS model is sustainable. Forecast monthly at $5k MRR: 85% gross margin.`,
      Treasury: `Treasury analysis: Stripe payouts + Supabase edge = <24h cash conversion. No accounts receivable risk at these volumes.`,
      Tax: `Tax analysis: Bosnia tax treaty with EU is favorable. VAT OSS registration required when EU B2C revenue >€10k.`,
      CEO: `CEO analysis: window of opportunity is 18 months. EU AI Act enforcement starts August 2026. Move now.`,
      COO: `COO analysis: operational leverage is high. One person can serve 50 customers with current automation.`,
      CTO: `CTO analysis: architecture is solid. Constitutional membrane VERIFIED. Next technical risk: multi-tenancy at scale.`,
      CFO: `CFO analysis: unit economics support $8M pre-seed at break-even demonstration. Raise after first enterprise LOI.`,
      Ethics: `Ethics analysis: epistemic tier labeling is a genuine differentiator. Prevents AI overclaiming. Industry precedent.`,
      Risk: `Risk analysis: single-point-of-failure is operator (solo founder). Mitigation: document everything in CLAUDE.md.`,
      Audit: `Constitutional audit PASSED. Analysis mode invariants hold. Epistemic tier labeling: COMPLIANT.`,
      Guardian: `GUARDIAN verdict: APPROVED. Analysis mode within constitutional bounds. No T4/T5 detected. Chain: INTACT.`,
    },
    gtm: {
      Strategy: `GTM for "${o}": 4-phase. Phase 1: design partners (8 wks). Phase 2: HN+PH launch. Phase 3: EU enterprise. CAC: $1,200.`,
      Finance: `GTM budget: $0 paid (organic first). Blog + HN = $0. Conference sponsorship at $5k MRR milestone. T2.`,
      Pricing: `GTM pricing: explorer free to drive top-of-funnel. Operator $49 one-time removes friction. Sovereign $499 for enterprise.`,
      Brand: `GTM brand: "EU AI Act compliance, provably." One sentence. Speaks to compliance officers and developers.`,
      Content: `GTM content: "Show HN: AEGIS-Ω — governed multi-agent AI with hash-chained audit trail (EU AI Act)". Ready to post.`,
      SEO: `GTM SEO: target "EU AI Act Article 12 logging" immediately. Write 3 technical posts in week 1. T2 traffic projection.`,
      Paid: `GTM paid: $0 budget week 1. Activate LinkedIn retargeting at $1k MRR. Target: compliance officers at EU SaaS.`,
      Social: `GTM social: LinkedIn launch post ready. X technical thread. HN Show HN. Product Hunt listing drafted.`,
      Outbound: `GTM outbound: 5 cold email templates ready (EU SaaS, fintech, consultancy, enterprise, design partner).`,
      Inbound: `GTM inbound: free explorer tier is the lead magnet. Goal: 100 explorer signups in first 30 days.`,
      Partner: `GTM partners: approach 3 EU AI governance consultancies in week 2 after HN launch social proof.`,
      Enterprise: `GTM enterprise: design partner program. Free sovereign access for 90 days. Requires 1 workflow integration.`,
      Product: `GTM product: live API at launch. Free explorer at /pricing. Custom domain provisioning.`,
      UX: `GTM UX: onboarding must be <2 minutes. Email → key → first call. No friction before value is demonstrated.`,
      Data: `GTM metrics: week 1 goal: 50 explorer signups, 5 operator sales ($245). PostHog conversion tracking.`,
      API: `GTM API: docs at /docs. OpenAPI spec on launch day. Python SDK: week 4.`,
      Backend: `GTM infra: Cloud Run live in europe-west3. Custom domain provisioning (cert ~15 min from now).`,
      Frontend: `GTM frontend: hub at aegisomega.com. Pricing at /pricing. Demo widget on homepage for conversion.`,
      Infra: `GTM infra: Cloudflare DNS + GCP Global LB + Cloud Run. SSL cert PROVISIONING → ACTIVE within 30 min.`,
      Security: `GTM security: payment → key provisioning verified end-to-end. No plaintext exposure. GDPR-compliant.`,
      'AI/ML': `GTM AI: Claude Opus 4.8 live. 39-department swarm with adaptive thinking. Differentiation is provable.`,
      RevOps: `GTM ops: Supabase tracks all keys, cycles, revenue. PostHog tracks all events. BigQuery for trend analysis.`,
      Support: `GTM support: info@aegisomega.com. 24h response goal. Onboarding email sent on key provisioning.`,
      Legal: `GTM legal: no T&C blocking purchase. AGPL-3.0 noted in footer. Commercial license available on request.`,
      Compliance: `GTM compliance: EU AI Act Article 12 mapping documented. This IS the product for compliance buyers.`,
      Research: `GTM research: HN audience = developers. LinkedIn = compliance officers. Product Hunt = early adopters.`,
      Competitive: `GTM competitive: announce before competitors copy the hash-chain positioning. First-mover advantage is real.`,
      Customer: `GTM customer: first 10 customers are design partners. Collect case studies for enterprise sales motion.`,
      Accounting: `GTM unit economics: $49 operator = $35 gross (28% COGS). Break-even: 30 operator sales. Achievable in 30 days.`,
      Treasury: `GTM cash: PayPal → bank in 1-3 days. Supabase $0/month at current scale. Cloud Run ~$5/month.`,
      Tax: `GTM tax: PayPal handles VAT collection for EU B2C. Verify OSS registration before >€10k EU revenue.`,
      CEO: `GTM CEO: post Show HN today. LinkedIn post today. 5 cold emails today. Momentum creates momentum.`,
      COO: `GTM COO: launch day checklist — HN post, LinkedIn post, PH listing, 5 cold emails, monitor Supabase logs.`,
      CTO: `GTM CTO: verify end-to-end payment→key→API call before posting. Smoke test the full path. T0 requirement.`,
      CFO: `GTM CFO: first dollar goal = 1 operator sale = $49. First week goal = $245 (5 sales). First month: $1k MRR.`,
      Ethics: `GTM ethics: all copy stays grounded and falsifiable. "Verifiable governance infrastructure" — not "conscious AI".`,
      Risk: `GTM risk: launch day load spike — Cloud Run max-instances=5 protects against OOM. Rate limiting on /collaborate.`,
      Audit: `Constitutional audit PASSED. GTM mode invariants hold. All outputs epistemic-tier labeled. Proceed.`,
      Guardian: `GUARDIAN verdict: APPROVED. GTM execution within constitutional bounds. No overclaiming detected. Launch authorized.`,
    },
    retention: {
      Strategy: `Retention for "${o}": 3 churn vectors. Fix: governance dashboard stickiness, API key continuity, operator success. +15% NRR.`,
      Finance: `Retention economics: increasing NRR from 90% → 110% = $240k incremental ARR on $1M base. Priority: high.`,
      Pricing: `Retention pricing: usage-based top-ups reduce churn vs hard limits. "Buy 500 more runs" removes upgrade friction.`,
      Brand: `Retention brand: "the audit chain is your compliance record". Switching cost = losing audit history.`,
      Content: `Retention content: monthly governance reports, audit export tutorials, EU AI Act update emails.`,
      SEO: `Retention SEO: "AEGIS audit chain" and "EU AI Act compliance record" as branded terms to own.`,
      Paid: `Retention paid: re-engage dormant keys at 80% usage. Email: "You have 100 runs remaining — upgrade to keep your audit chain."`,
      Social: `Retention social: showcase customer audit chains (anonymised). Community of compliance practitioners.`,
      Outbound: `Retention outbound: usage-based email triggers. At 80% runs used: upgrade CTA. At 100%: re-purchase prompt.`,
      Inbound: `Retention inbound: governance dashboard drives daily active usage. Audit chain history creates switching cost.`,
      Partner: `Retention partners: consultancy partners recommend renewal to their clients. Reseller margin: 20%.`,
      Enterprise: `Retention enterprise: annual contract at $4,999 (sovereign × 10). Dedicated onboarding. SLA 99.9%.`,
      Product: `Retention product: audit export (PDF) is the stickiest feature. Users who export retain at 2× rate. Build this.`,
      UX: `Retention UX: key dashboard shows usage, remaining runs, audit chain history. Visible switching cost.`,
      Data: `Retention metric: usage_count / usage_limit ratio per key. Alert at 80% threshold. Track NRR monthly.`,
      API: `Retention API: maintain backward compatibility. Deprecation window: 6 months minimum. No surprise breakage.`,
      Backend: `Retention backend: uptime is retention. Cloud Run SLA 99.95%. Circuit breaker on Anthropic API errors.`,
      Frontend: `Retention frontend: governance dashboard shows constitutional health. Users become attached to their chain.`,
      Infra: `Retention infra: zero downtime deployments via Cloud Run revision traffic splitting.`,
      Security: `Retention security: no key rotation forced on users. Rotation is available, never mandated without notice.`,
      'AI/ML': `Retention AI: better model outputs (Opus 4.8) increase perceived value. Users stay for quality insights.`,
      RevOps: `Retention RevOps: usage tracking in api_key_store. Trigger expansion email when usage_count > 0.8 × usage_limit.`,
      Support: `Retention support: proactive outreach at 50% and 80% usage. Offer case study interview for loyalty discount.`,
      Legal: `Retention legal: API key continuity is a compliance dependency. Legal teams retain because switching = re-auditing.`,
      Compliance: `Retention compliance: audit chain history cannot be transferred. Compliance officers can't churn without audit loss.`,
      Research: `Retention research: users who integrate API into CI/CD pipeline churn at <5%. Integration depth = retention.`,
      Competitive: `Retention competitive: no competitor has a hash-chained audit history. Churning = losing compliance record.`,
      Customer: `Retention customer: compliance officers are annual budget holders. Frame renewal as compliance program, not SaaS.`,
      Accounting: `Retention accounting: expand revenue from operator ($49) to sovereign ($499) = 10× LTV per customer. Target: 20% upgrade rate.`,
      Treasury: `Retention treasury: one-time payments preferred short-term. Annual contracts preferred long-term for predictability.`,
      Tax: `Retention tax: no tax complexity for renewals (same product, same entity). Clean.`,
      CEO: `Retention CEO priority: audit chain stickiness is the moat. Every retained customer is a competitor's lost sale.`,
      COO: `Retention COO: usage-alert emails are automatable via Supabase triggers. Build at 50 customers.`,
      CTO: `Retention CTO: API stability is a retention promise. Semantic versioning + changelogs + deprecation policy required.`,
      CFO: `Retention CFO: LTV at 2 operator renewals = $98. LTV at 1 sovereign = $499. Expand sovereign sales.`,
      Ethics: `Retention ethics: no dark patterns. Usage alerts are customer-friendly, not manipulative. Grounded messaging.`,
      Risk: `Retention risk: Anthropic API price increase could force price revision. Mitigation: cost-pass-through clause.`,
      Audit: `Constitutional audit PASSED. Retention mode invariants hold. No over-promise in retention strategy.`,
      Guardian: `GUARDIAN verdict: APPROVED. Retention strategy within constitutional bounds. Switching cost is genuine.`,
    },
    competitive: {
      Strategy: `Competitive analysis for "${o}": 3 direct rivals mapped. AEGIS moat: constitutional audit chain (no rival has T0 tamper-evidence). Window: 18 months.`,
      Finance: `Competitive finance: rival pricing 2-5× higher with weaker audit guarantees. Price-value gap: significant.`,
      Pricing: `Competitive pricing: undercut on entry ($49 vs rivals at $200+) while owning the audit-chain narrative.`,
      Brand: `Competitive brand: "provable governance" is unowned. All rivals say "trustworthy AI" — none can prove it.`,
      Content: `Competitive content: rivals publish thought leadership, not technical proof. Our advantage: show the code.`,
      SEO: `Competitive SEO: rivals own "AI governance" broadly. Own "hash-chained AI audit" specifically. Niche wins.`,
      Paid: `Competitive paid: rivals spend on LinkedIn with generic copy. Our USP: "the only audit trail you can replay".`,
      Social: `Competitive social: Credo AI has 8k followers, Fiddler has 12k. We have a constitutional runtime. Different audience.`,
      Outbound: `Competitive outbound: position against rivals explicitly. "Unlike X, AEGIS audit chain is cryptographically verifiable."`,
      Inbound: `Competitive inbound: "AEGIS vs [rival]" comparison pages. Searchers in evaluation mode = highest intent.`,
      Partner: `Competitive partners: some rivals have consultancy partnerships. Approach the same firms with a better product story.`,
      Enterprise: `Competitive enterprise: rivals require 6-month implementation. AEGIS: one API call. Deployment advantage is real.`,
      Product: `Competitive product: rivals have dashboards, not audit chains. Dashboard is UI. Audit chain is evidence. Different.`,
      UX: `Competitive UX: rivals have complex onboarding. AEGIS: email → key → first call in <2 min. UX moat.`,
      Data: `Competitive data: rivals compete on accuracy metrics. AEGIS competes on verifiability. Different dimension wins.`,
      API: `Competitive API: rivals have REST APIs too. Differentiator: our API response includes cryptographic proof.`,
      Backend: `Competitive backend: rivals run on AWS us-east-1. AEGIS is EU-native (europe-west3). GDPR advantage.`,
      Frontend: `Competitive frontend: rivals have enterprise dashboards. AEGIS has constitutional runtime visible in the browser.`,
      Infra: `Competitive infra: rivals have enterprise SLAs. AEGIS: Cloud Run 99.95% + Cloudflare. Comparable.`,
      Security: `Competitive security: rivals store audit logs in databases (editable). AEGIS: hash-chain (tamper-evident). T0 gap.`,
      'AI/ML': `Competitive AI: rivals use GPT-4o or undisclosed models. AEGIS: Claude Opus 4.8 with adaptive thinking. Transparent.`,
      RevOps: `Competitive ops: rivals have sales teams. AEGIS is self-serve first. 10× efficiency advantage at this stage.`,
      Support: `Competitive support: rivals have support teams. AEGIS: founder-led. Personal touch is the advantage, not a gap.`,
      Legal: `Competitive legal: rivals have enterprise legal teams. AEGIS AGPL-3.0 creates open-source credibility.`,
      Compliance: `Competitive compliance: rivals claim EU AI Act compliance. AEGIS can prove it with a hash-chained audit trail.`,
      Research: `Competitive research: 4 rivals mapped — Credo AI, Fiddler, Arthur AI, Verta. None have constitutional audit chain.`,
      Competitive: `Moat depth: replay-verifiable + hash-chained + EU-native + self-serve + constitutional. No rival has all 5.`,
      Customer: `Competitive customer: rivals target ML teams. AEGIS targets compliance officers. Different buyer, less competition.`,
      Accounting: `Competitive accounting: rivals raise VC, burn cash on sales. AEGIS is capital-efficient. Advantage: survivability.`,
      Treasury: `Competitive treasury: rivals have 18-24 months runway. AEGIS is profitable at 30 operator sales. Different math.`,
      Tax: `Competitive tax: EU entity is a feature, not a cost. GDPR compliance built-in. Rivals scramble for this.`,
      CEO: `Competitive CEO: the 18-month window is real. Two years from now, this category is crowded. Move fast.`,
      COO: `Competitive COO: self-serve vs rival sales teams = 10× cost advantage. Protect this model through Series A.`,
      CTO: `Competitive CTO: constitutional membrane + replay sovereignty = architectural moat. Hard to copy quickly.`,
      CFO: `Competitive CFO: rivals need $5M+ to build what AEGIS has. Fundraise at a premium before they catch up.`,
      Ethics: `Competitive ethics: rivals make alignment claims without proofs. AEGIS epistemic tier labeling is differentiated.`,
      Risk: `Competitive risk: Anthropic could build a governance product. Mitigation: model-agnostic architecture.`,
      Audit: `Constitutional audit PASSED. Competitive analysis within constitutional bounds. Claims are T1 evidence-based.`,
      Guardian: `GUARDIAN verdict: APPROVED. Competitive strategy grounded in verifiable claims. No overreach detected.`,
    },
    technical: {
      Strategy: `Technical architecture for "${o}": Python bridge on Cloud Run (europe-west3), 39-dept swarm, Supabase persistence. T0 verified.`,
      Finance: `Technical cost model: $0.12/call (Claude Opus 4.8) + $0.002 (Cloud Run) + $0.001 (Supabase). Total: ~$0.123/governed call.`,
      Pricing: `Technical pricing: cost-plus model. $49 operator = 500 calls = $9.80 COGS. 80% gross margin. Healthy.`,
      Brand: `Technical brand: the architecture IS the brand differentiator. Show the code. Open-source the runtime.`,
      Content: `Technical content: deep-dive on SHA-256 hash-chain implementation. Publish "How AEGIS audit chain works" series.`,
      SEO: `Technical SEO: "deterministic replay AI", "hash-chained audit trail implementation" — developer-intent keywords.`,
      Paid: `Technical paid: developer-targeted ads on Google with "EU AI Act Article 12 implementation" copy.`,
      Social: `Technical social: X thread on constitutional runtime architecture. Code snippets drive developer engagement.`,
      Outbound: `Technical outbound: target CTOs and platform engineering leads. Message: "audit trail without retrofitting."`,
      Inbound: `Technical inbound: developers self-qualify via the free explorer tier. High-intent self-serve motion.`,
      Partner: `Technical partners: SDK partnerships (Python, TypeScript). API-first design enables partner integrations.`,
      Enterprise: `Technical enterprise: on-premise deployment feasibility — Docker container + Supabase hosted. 60 days to implement.`,
      Product: `Technical product roadmap: (1) Python SDK, (2) audit export PDF, (3) webhook notifications, (4) on-premise.`,
      UX: `Technical UX: API-first is developer-native. Dashboard is secondary. CLI tool would increase adoption.`,
      Data: `Technical data: swarm_memory table enables cross-session learning. Objective-hash lookup O(log n) indexed.`,
      API: `Technical API: REST + SSE for streaming. Contract version in every response. Backward-compat policy defined.`,
      Backend: `Technical backend: Flask bridge, CoreMatrix 256MB, metacognitive chain, hash-chained audit. All T0 verified.`,
      Frontend: `Technical frontend: React 18 + Vite, hash chain running in-browser (Web Crypto SHA-256). T0-grade client.`,
      Infra: `Technical infra: Cloud Run + Global LB + Serverless NEG + managed SSL cert. Scalable to 500 req/min.`,
      Security: `Technical security: SHA-256 key hashing, service-role gating, HTTPS-only, no PII in audit chain. T0.`,
      'AI/ML': `Technical AI: Claude Opus 4.8 with adaptive thinking. Model configurable via AEGIS_SWARM_MODEL env var.`,
      RevOps: `Technical RevOps: api_key_store + revenue_cycles + swarm_memory — full observability stack in Supabase.`,
      Support: `Technical support: /docs endpoint on bridge serves API reference. Error messages are constitutional (epistemic tier).`,
      Legal: `Technical legal: AGPL-3.0 forces open-source disclosure. Commercial license for enterprise embedding.`,
      Compliance: `Technical compliance: EU AI Act Article 12 — automatic logging ✓, traceability ✓, reconstruction ✓. T0.`,
      Research: `Technical research: 385-gate Rust inference crate (CL-Ψ). 7178 tests passing. T2 engineering hypothesis.`,
      Competitive: `Technical competitive: deterministic replay across platforms (Linux/macOS/Docker/WASM/ARM/x86). Unique.`,
      Customer: `Technical customer success: developers succeed when first API call returns in <4s with valid audit hash.`,
      Accounting: `Technical accounting COGS: pay-per-token Claude API makes COGS predictable and linearly scalable.`,
      Treasury: `Technical treasury: no infrastructure lock-in. Can migrate Claude → any model. Multi-cloud ready.`,
      Tax: `Technical tax: EU data residency (europe-west3) simplifies GDPR compliance for EU customers.`,
      CEO: `Technical CEO: the constitutional architecture is the strategic asset. Protect it as competitive moat.`,
      COO: `Technical COO: deployment automation via Cloud Build + GitHub Actions. Continuous delivery is live.`,
      CTO: `Technical CTO: Gate 8 (4026+ tests) passes on every commit. Frozen constitutional files hash-verified.`,
      CFO: `Technical CFO: Rust gate modules (385) = computable proof cost. TypeScript runtime = quantifiable latency.`,
      Ethics: `Technical ethics: T4/T5 constructs blocked from src/. Epistemic tier labeling is built into the compiler.`,
      Risk: `Technical risk: single Cloud Run instance. Mitigation: max-instances=5, min-instances=0 cold start <4s.`,
      Audit: `Constitutional audit PASSED. Architecture is T0-verified. All frozen file hashes intact. Proceed.`,
      Guardian: `GUARDIAN verdict: APPROVED. Technical architecture within constitutional bounds. Replay sovereignty: ACTIVE.`,
    },
    regulatory: {
      Strategy: `Regulatory strategy for "${o}": EU AI Act Article 12 mapping COMPLETE. GDPR Article 22 mitigated. ISO 27001: roadmap Q2 2027.`,
      Finance: `Regulatory finance: compliance certification = $25k ARR premium per enterprise customer. ROI on cert: 6 months.`,
      Pricing: `Regulatory pricing: "Article 12 compliance binder" as upsell at $999. Included for sovereign tier.`,
      Brand: `Regulatory brand: "the only AI platform that produces Article 12 evidence by construction." Not by documentation.`,
      Content: `Regulatory content: publish "EU AI Act Article 12 technical mapping" — becomes a lead magnet for compliance teams.`,
      SEO: `Regulatory SEO: "EU AI Act Article 12 logging", "AI audit trail EU compliance" — high-value buyer intent keywords.`,
      Paid: `Regulatory paid: LinkedIn targeting EU compliance officers and DPOs. "Article 12 deadline: August 2026."`,
      Social: `Regulatory social: post EU AI Act timeline infographic. Tag European Commission DG CNECT.`,
      Outbound: `Regulatory outbound: email 5 EU SaaS companies using AI features. Subject: "Article 12 logging for [Company]'s AI."`,
      Inbound: `Regulatory inbound: Article 12 explainer blog → audit trail demo → pricing page. 3-step compliance funnel.`,
      Partner: `Regulatory partners: EU AI Act consultancies as resellers. They need a deployable product; AEGIS is it.`,
      Enterprise: `Regulatory enterprise: compliance certification is a board-level requirement. C-suite buyer, not developer.`,
      Product: `Regulatory product: Article 12 compliance report export. One-click PDF for regulator submission. Build next.`,
      UX: `Regulatory UX: compliance buyers are non-technical. Export-focused UX: "Download your Article 12 report."`,
      Data: `Regulatory data: every swarm_memory entry is a data point for compliance evidence. Retain for 3 years.`,
      API: `Regulatory API: Article 12 requires "automatic logging" — satisfied by every /platform/collaborate call.`,
      Backend: `Regulatory backend: audit chain is append-only, tamper-evident, deterministically replayable. T0 compliance.`,
      Frontend: `Regulatory frontend: compliance dashboard showing audit history. Table: date, objective, verdict, chain hash.`,
      Infra: `Regulatory infra: europe-west3 = EU data residency. GDPR Article 17 right to erasure: key revocation covers this.`,
      Security: `Regulatory security: ISO 27001 controls partially satisfied. Gap analysis: need written ISMS documentation.`,
      'AI/ML': `Regulatory AI: Claude Opus 4.8 = named model, known provider. Article 12 requires identifying the AI system used.`,
      RevOps: `Regulatory RevOps: compliance buyers require vendor audit reports. Add SOC 2 Type 1 to roadmap.`,
      Support: `Regulatory support: compliance customers need 24h SLA. Sovereign tier includes dedicated support channel.`,
      Legal: `Regulatory legal: AGPL-3.0 + commercial license structure is compatible with enterprise procurement.`,
      Compliance: `Regulatory compliance: Article 12 ✓, Article 13 ✓ (transparency), Article 17 (partial). Gap: Article 14 (human oversight).`,
      Research: `Regulatory research: EU AI Act sandbox (Article 57) application could provide regulatory endorsement.`,
      Competitive: `Regulatory competitive: rivals claim compliance but don't show the mechanism. AEGIS shows the code.`,
      Customer: `Regulatory customer: DPOs and Chief Compliance Officers are buyers. Budget: legal/compliance, not IT.`,
      Accounting: `Regulatory accounting: compliance certification increases customer willingness-to-pay 3-5×. High-margin.`,
      Treasury: `Regulatory treasury: EU grant funding (Horizon Europe) possible for AI governance tooling. Explore.`,
      Tax: `Regulatory tax: EU grant funding is non-dilutive. Explore Digital Europe programme for AI governance tools.`,
      CEO: `Regulatory CEO: August 2026 is the weapon. "The deadline is 14 months away. You need this now."`,
      COO: `Regulatory COO: Article 12 audit log = every /collaborate call. Zero additional operational overhead. Sell this.`,
      CTO: `Regulatory CTO: deterministic replay = reconstruction requirement met. Hash chain = tamper-evidence requirement met.`,
      CFO: `Regulatory CFO: cost of non-compliance (EU AI Act fines: up to 3% global revenue) >> cost of AEGIS ($499).`,
      Ethics: `Regulatory ethics: the system IS the ethics mechanism. Constitutional audit provides Article 9 risk assessment.`,
      Risk: `Regulatory risk: regulatory interpretation is evolving. Constitutional architecture is future-proof by design.`,
      Audit: `Constitutional audit PASSED. Regulatory mode claims are accurate and evidenced. No overclaiming detected.`,
      Guardian: `GUARDIAN verdict: APPROVED. Regulatory strategy within constitutional bounds. Article 12 mapping verified.`,
    },
    fundraising: {
      Strategy: `Fundraising strategy for "${o}": Series A readiness: EARLY. Required milestones: $180k ARR, 3 enterprise LOIs, EU AI Act cert.`,
      Finance: `Fundraising finance: current metrics — $0 ARR (pre-launch), $8M pre-seed valuation target. Comps: Credo AI ($12M seed).`,
      Pricing: `Fundraising pricing: raise on metrics not potential. $5k MRR is fundable at pre-seed. $25k MRR is fundable at seed.`,
      Brand: `Fundraising brand: "the only AI governance platform with cryptographic audit proof." Investors want defensibility.`,
      Content: `Fundraising content: public GitHub (AGPL-3.0) + technical blog = credibility signal for investor due diligence.`,
      SEO: `Fundraising SEO: investor searches include "EU AI Act startup" and "AI governance infrastructure." Own both.`,
      Paid: `Fundraising paid: N/A at this stage. Focus capital on product and early sales, not paid acquisition.`,
      Social: `Fundraising social: Twitter/X presence of founder + technical credibility = investor discovery channel.`,
      Outbound: `Fundraising outbound: 20 investor emails after $5k MRR demonstrated. Use Launch Kit cold email templates.`,
      Inbound: `Fundraising inbound: HN "Show HN" → investor discovery. Technical founders-turned-VCs are the target LP.`,
      Partner: `Fundraising partners: Northzone (EU AI focus), Speedinvest (Vienna, EU regulation expertise), Atlantic Labs.`,
      Enterprise: `Fundraising enterprise: 1 LOI from an EU enterprise = fundable. 3 LOIs = seed round material.`,
      Product: `Fundraising product: investors want to see a live product, not a demo. The platform API is the product.`,
      UX: `Fundraising UX: investor demo path — /pricing → explorer key in 30 seconds → first API call → audit hash.`,
      Data: `Fundraising data: swarm_memory corpus will show learning curves. Objective → insight quality improvement over time.`,
      API: `Fundraising API: live REST API with OpenAPI spec = investor-legible proof of product completeness.`,
      Backend: `Fundraising backend: Cloud Run + Supabase + Cloudflare = zero infrastructure risk for investors.`,
      Frontend: `Fundraising frontend: hub landing page at aegisomega.com is the first investor impression. Polish it.`,
      Infra: `Fundraising infra: Cloud Run auto-scales. No infra capex risk. Investors prefer this over owned hardware.`,
      Security: `Fundraising security: SHA-256 audit chain + service-role gating = defensible security posture for due diligence.`,
      'AI/ML': `Fundraising AI: Claude Opus 4.8 (Anthropic) as the inference layer = credible partnership signal.`,
      RevOps: `Fundraising RevOps: cohort analysis possible from day 1 via revenue_cycles table. Show investors usage data.`,
      Support: `Fundraising support: design partners + email support = signal that customers are engaged before scaling.`,
      Legal: `Fundraising legal: AGPL-3.0 open-source core + commercial enterprise license = standard dual-license model.`,
      Compliance: `Fundraising compliance: EU AI Act compliance = a sector with regulatory tailwind. Investors love this story.`,
      Research: `Fundraising research: $340M TAM (AI governance), 18-month competitive window, EU regulatory forcing function.`,
      Competitive: `Fundraising competitive: 0 direct competitors with hash-chained audit trail. First-mover in a regulated market.`,
      Customer: `Fundraising customer: design partners are customer references. 3 is the minimum for a seed round.`,
      Accounting: `Fundraising accounting: gross margin 80%+ at scale. SaaS benchmarks: excellent. Investors will notice.`,
      Treasury: `Fundraising treasury: raise $500k-$1M pre-seed. Use for: 1 sales hire, 2 engineering hires, marketing.`,
      Tax: `Fundraising tax: structure for EU investors — Bosnia entity + EU IP holding structure may be required.`,
      CEO: `Fundraising CEO: raise after demonstrating $5k MRR and one enterprise LOI. Don't raise before proof.`,
      COO: `Fundraising COO: investor deck narrative — "EU AI Act creates a $340M urgency market. We have the proof."`,
      CTO: `Fundraising CTO: 4026+ tests, 385 Rust gate modules, 7178 CL-Ψ tests. Due diligence will love this.`,
      CFO: `Fundraising CFO: $500k at $8M pre-money = 6.25% dilution. Acceptable at this stage. Target: 5% or less.`,
      Ethics: `Fundraising ethics: the constitutional architecture is not a gimmick — it's the product. Investors must understand this.`,
      Risk: `Fundraising risk: solo founder is a flag for investors. Mitigation: strong technical differentiation + live product.`,
      Audit: `Constitutional audit PASSED. Fundraising narrative is grounded. No T4/T5 overclaiming. Projections labeled T2.`,
      Guardian: `GUARDIAN verdict: APPROVED. Fundraising strategy within constitutional bounds. Valuation is T2 hypothesis.`,
    },
  }
  return templates[mode][dept.role] ?? `${dept.role}: Analysis for "${o}" via ${mode} mode — constitutional framework applied. T2 hypothesis.`
}

interface ActivatedDept extends Dept {
  output: string
}

type Phase = 'idle' | 'running' | 'done'

const IArrow = () => (
  <svg width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round">
    <path d="M5 12h14"/><path d="m12 5 7 7-7 7"/>
  </svg>
)

export function SwarmDemoWidget({ ttv }: { ttv?: () => number }) {
  const [objective, setObjective] = useState('')
  const [mode, setMode] = useState<Mode>('gtm')
  const [phase, setPhase] = useState<Phase>('idle')
  const [activated, setActivated] = useState<ActivatedDept[]>([])
  const abortRef = useRef(false)

  const PROJECTIONS: Record<Mode, { arr: number; tier: string }> = {
    revenue:     { arr: 2_400_000, tier: 'T2' },
    analysis:    { arr: 1_800_000, tier: 'T2' },
    gtm:         { arr: 3_200_000, tier: 'T2' },
    retention:   { arr: 1_200_000, tier: 'T2' },
    competitive: { arr: 1_600_000, tier: 'T2' },
    technical:   { arr: 1_400_000, tier: 'T2' },
    regulatory:  { arr: 2_100_000, tier: 'T2' },
    fundraising: { arr: 8_000_000, tier: 'T2' },
  }

  const run = useCallback(async () => {
    const obj = objective.trim() || 'AEGIS-Ω governed AI platform'
    abortRef.current = false
    setPhase('running')
    setActivated([])

    for (const dept of DEPARTMENTS) {
      if (abortRef.current) break
      const output = deptOutput(obj, mode, dept)
      setActivated(prev => [...prev, { ...dept, output }])
      await new Promise(r => setTimeout(r, 55))
    }

    if (!abortRef.current) setPhase('done')
  }, [objective, mode])

  const reset = useCallback(() => {
    abortRef.current = true
    setPhase('idle')
    setActivated([])
  }, [])

  const proj = PROJECTIONS[mode]

  return (
    <section
      className="ld-section ld-section--tight"
      id="demo"
      style={{ borderTop: '1px solid var(--r-line)', background: 'var(--r-bg-2)' }}
    >
      <div className="ld-wrap">
        <div className="ld-section-head">
          <div className="ld-sec-num">05.5 · LIVE DEMO</div>
          <h2>Watch 39 agents activate. Right now.</h2>
          <p style={{ maxWidth: 560, margin: '0 auto' }}>
            Enter any objective. The swarm activates department by department — Strategy,
            Finance, Compliance, Guardian — and returns a constitutional verdict.
            Demo uses template outputs. <b>Real calls use Claude Opus 4.8 with adaptive thinking.</b>
          </p>
        </div>

        {/* Controls */}
        <div style={{
          display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'flex-end',
          maxWidth: 760, margin: '0 auto 24px',
        }}>
          <div style={{ flex: '1 1 280px', minWidth: 200 }}>
            <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--aegis-muted)', marginBottom: 8 }}>
              Objective
            </label>
            <input
              value={objective}
              onChange={e => setObjective(e.target.value)}
              placeholder="e.g. Enter EU fintech market"
              disabled={phase === 'running'}
              style={{
                width: '100%', background: 'var(--r-bg)', border: '1px solid var(--r-line)',
                borderRadius: 6, padding: '10px 14px', color: 'var(--aegis-text)',
                fontFamily: 'var(--font-mono)', fontSize: 12, outline: 'none', boxSizing: 'border-box',
              }}
            />
          </div>
          <div style={{ flex: '0 0 auto' }}>
            <label style={{ display: 'block', fontFamily: 'var(--font-mono)', fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: 'var(--aegis-muted)', marginBottom: 8 }}>
              Mode
            </label>
            <select
              value={mode}
              onChange={e => setMode(e.target.value as Mode)}
              disabled={phase === 'running'}
              style={{
                background: 'var(--r-bg)', border: '1px solid var(--r-line)',
                borderRadius: 6, padding: '10px 14px', color: 'var(--aegis-text)',
                fontFamily: 'var(--font-mono)', fontSize: 12, outline: 'none', cursor: 'pointer',
              }}
            >
              {MODES.map(m => <option key={m.value} value={m.value}>{m.label}</option>)}
            </select>
          </div>
          {phase === 'idle' || phase === 'done' ? (
            <button
              onClick={run}
              style={{
                flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 8,
                background: 'var(--aegis-phi)', color: '#000', border: 'none',
                borderRadius: 6, padding: '10px 20px', fontWeight: 700, fontSize: 13,
                cursor: 'pointer', letterSpacing: '0.04em', fontFamily: 'var(--font-base)',
              }}
            >
              {phase === 'done' ? 'Run again' : 'Activate the Swarm'} <IArrow/>
            </button>
          ) : (
            <button
              onClick={reset}
              style={{
                flex: '0 0 auto', background: 'transparent', color: 'var(--aegis-muted)',
                border: '1px solid var(--r-line)', borderRadius: 6, padding: '10px 20px',
                fontSize: 13, cursor: 'pointer', fontFamily: 'var(--font-base)',
              }}
            >
              Stop
            </button>
          )}
        </div>

        {/* Department stream */}
        {activated.length > 0 && (
          <div style={{
            maxWidth: 760, margin: '0 auto 24px',
            border: '1px solid var(--r-line)', borderRadius: 8, overflow: 'hidden',
            fontFamily: 'var(--font-mono)', fontSize: 11,
          }}>
            <div style={{ padding: '10px 16px', borderBottom: '1px solid var(--r-line)', background: 'var(--r-bg)', display: 'flex', gap: 12, alignItems: 'center' }}>
              <span className="ld-live" style={{ width: 7, height: 7, borderRadius: '50%', background: phase === 'running' ? '#34d399' : '#fbbf24', display: 'inline-block', flexShrink: 0 }}/>
              <span style={{ color: 'var(--aegis-text)', fontWeight: 700, letterSpacing: '0.1em', textTransform: 'uppercase', fontSize: 10 }}>
                {phase === 'running' ? `Activating... ${activated.length} / 39 departments` : `Complete — ${activated.length} departments`}
              </span>
              <span style={{ marginLeft: 'auto', color: 'var(--aegis-muted)' }}>demo · template outputs</span>
            </div>
            <div style={{ maxHeight: 280, overflowY: 'auto', background: 'var(--r-bg-2)' }}>
              {activated.map(dept => (
                <div key={dept.id} style={{ display: 'flex', gap: 12, padding: '8px 16px', borderBottom: '1px solid rgba(255,255,255,0.04)', alignItems: 'flex-start' }}>
                  <span style={{
                    flexShrink: 0, fontFamily: 'var(--font-mono)', fontSize: 9, fontWeight: 700,
                    padding: '2px 7px', borderRadius: 3, letterSpacing: '0.08em',
                    background: `${CATEGORY_COLORS[dept.category]}18`,
                    color: CATEGORY_COLORS[dept.category],
                    minWidth: 60, textAlign: 'center',
                  }}>
                    {dept.id}
                  </span>
                  <span style={{ flex: 1, color: 'var(--aegis-text)', lineHeight: 1.55, fontSize: 11 }}>
                    <b style={{ color: CATEGORY_COLORS[dept.category] }}>{dept.role}:</b>{' '}
                    {dept.output}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Constitutional verdict */}
        {phase === 'done' && (
          <div style={{ maxWidth: 760, margin: '0 auto 32px', display: 'flex', gap: 12, flexWrap: 'wrap' }}>
            <div style={{
              flex: '1 1 200px', padding: '16px 20px', borderRadius: 8,
              border: '1px solid rgba(52,211,153,0.3)', background: 'rgba(52,211,153,0.05)',
            }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.14em', color: '#34d399', marginBottom: 8, textTransform: 'uppercase' }}>Constitutional Audit</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#34d399', letterSpacing: '0.06em' }}>APPROVED</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--aegis-muted)', marginTop: 4 }}>verdict · Guardian: PASS · Audit: PASS</div>
            </div>
            <div style={{
              flex: '1 1 200px', padding: '16px 20px', borderRadius: 8,
              border: '1px solid rgba(251,191,36,0.3)', background: 'rgba(251,191,36,0.05)',
            }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.14em', color: '#fbbf24', marginBottom: 8, textTransform: 'uppercase' }}>Projection · {proj.tier} hypothesis</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#fbbf24' }}>${(proj.arr / 1_000_000).toFixed(1)}M ARR</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--aegis-muted)', marginTop: 4 }}>T2 estimate — empirical validation required</div>
            </div>
            <div style={{
              flex: '1 1 200px', padding: '16px 20px', borderRadius: 8,
              border: '1px solid rgba(129,140,248,0.3)', background: 'rgba(129,140,248,0.05)',
            }}>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, letterSpacing: '0.14em', color: '#818cf8', marginBottom: 8, textTransform: 'uppercase' }}>Audit chain</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: '#818cf8' }}>INTACT</div>
              <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--aegis-muted)', marginTop: 4 }}>chain_valid: true · replay_reconstructable: true</div>
            </div>
          </div>
        )}

        {/* CTA */}
        <div style={{ textAlign: 'center', marginTop: 8 }}>
          {phase === 'done' && (
            <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--aegis-muted)', marginBottom: 16 }}>
              Demo uses template outputs. Real calls use <b style={{ color: 'var(--aegis-text)' }}>Claude Opus 4.8 with adaptive thinking</b> — 39 unique, domain-specific insights per call.
            </p>
          )}
          <a
            className="ld-btn ld-btn-primary ld-btn-lg"
            href="/pricing"
            onClick={() => { if (ttv) { void ttv() } }}
          >
            Get Real API Access <IArrow/>
          </a>
          <p style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color: 'var(--aegis-muted)', marginTop: 12 }}>
            Explorer tier is free · 10 governed calls · no card required
          </p>
        </div>
      </div>
    </section>
  )
}
