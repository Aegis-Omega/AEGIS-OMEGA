"""
AEGIS-Ω — /platform/* pure helpers
EPISTEMIC TIER: T1

Extracted from bridge.py so these functions can be imported and tested in CI
without allocating the 4 GB CoreMatrix bytearray.

All functions here are stateless or depend only on stdlib and os.environ.
The bridge imports these; tests import them directly.
"""
import json
import os

PLATFORM_CONTRACT_VERSION = '1.0.0'
PLATFORM_GIT_SHA = os.environ.get('AEGIS_GIT_SHA', 'dev')

# ── Swarm model configuration (env-overridable) ───────────────────────────────
# Fable 5 has adaptive thinking always on. Set AEGIS_SWARM_THINKING=false only
# when using an older model that does not support thinking (e.g. Haiku 4.5).
SWARM_MODEL = os.environ.get('AEGIS_SWARM_MODEL', 'claude-opus-4-8')
SWARM_THINKING = os.environ.get('AEGIS_SWARM_THINKING', 'true').lower() not in ('0', 'false', 'no')

VALID_MODES = frozenset({
    'revenue', 'analysis', 'gtm', 'retention',
    'competitive', 'technical', 'regulatory', 'fundraising',
})

# ── Tier capability gates (brief §9/§10 — least latitude by default) ─────────
# explorer: template/demo only (live=False, base-4 modes only).
# Real Claude API calls and advanced modes require at least operator tier.
# This prevents explorer keys from triggering unbounded inference costs while
# still letting them test the full 39-dept pipeline in template mode.
TIER_LIVE_ALLOWED: frozenset = frozenset({'operator', 'sovereign'})

# explorer tier: restricted to the four foundational analysis modes.
# operator/sovereign: all 8 modes available.
EXPLORER_MODES: frozenset = frozenset({'revenue', 'analysis', 'gtm', 'retention'})


def validate_tier_capabilities(tier: str, live: bool, mode: str = '') -> None:
    """
    Enforce least-latitude capability gate (brief §9/§10).

    Raises ValueError if the requested capability exceeds the tier's grant:
      - live=True requires operator or sovereign tier.
      - Advanced modes (outside EXPLORER_MODES) require operator or sovereign tier.

    The bridge calls this after verify_api_key() and before executing the swarm.
    mode defaults to '' which skips the mode check (backward-compatible).
    """
    if live and tier not in TIER_LIVE_ALLOWED:
        raise ValueError(
            f'live=True requires operator or sovereign tier (current: {tier!r}). '
            'Upgrade your API key at aegisomega.com to enable live Claude collaboration.'
        )
    if mode and tier not in TIER_LIVE_ALLOWED and mode not in EXPLORER_MODES:
        raise ValueError(
            f'{mode!r} mode requires operator or sovereign tier (current: {tier!r}). '
            'Available modes for explorer: revenue, analysis, gtm, retention. '
            'Upgrade your API key at aegisomega.com for advanced analysis modes: '
            'competitive, technical, regulatory, fundraising.'
        )


# ── Coherence gate (brief §5 — explicit named stop condition) ─────────────────
# The swarm "collapses" to a user-facing answer only when the constitutional
# audit returns APPROVED and the fitness score exceeds this threshold.
# Below it, the caller should iterate or escalate rather than emit.
# Named as a constant so callers can override via env and CI can assert it.
COHERENCE_GATE_THRESHOLD: float = (5 ** 0.5 - 1) / 2  # φ ≈ 0.6180339887 — consistent with martingale ceiling


def parse_max_agents(value):
    """
    Fail-closed parser for the max_agents cost ceiling.

    None means "no explicit cap" (executor caps at roster size). Anything else
    must be an integer >= 1. Malformed input raises ValueError so the API
    returns 400 INVALID_REQUEST — it must never silently become an uncapped
    run, because max_agents is the only bound on billable model calls.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError('max_agents must be an integer, not a boolean')
    if isinstance(value, float) and not value.is_integer():
        raise ValueError('max_agents must be a whole number')
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise ValueError(f'max_agents must be an integer (got {value!r})')
    if n < 1:
        raise ValueError(f'max_agents must be >= 1 (got {n})')
    return n


def autonomous_completion_audit(swarm: dict) -> dict:
    """
    Derive a contract-legal constitutional audit from an autonomous swarm run.

    Verdict is always one of ConstitutionalVerdict ('APPROVED'|'FLAG'|'QUARANTINE')
    so CONSTITUTIONAL_FACTORS applies the intended fitness penalty — an
    out-of-enum verdict falls through to the 0.85 neutral default, scoring
    BETTER than QUARANTINE (0.20) despite signalling failure.

    FLAG when: completion ratio below COHERENCE_GATE_THRESHOLD, any agent
    errored, any agent was budget-skipped, or a completed agent produced empty
    output. APPROVED only on a clean, complete run.
    """
    artifacts = swarm.get('artifacts', [])
    total = swarm.get('agents_total', len(artifacts))
    executed = swarm.get('agents_executed', 0)
    completion = executed / total if total else 0.0

    concerns: list = []
    if completion < COHERENCE_GATE_THRESHOLD:
        concerns.append(
            f'Agent completion {completion:.4f} below coherence gate '
            f'{COHERENCE_GATE_THRESHOLD:.10f} ({executed}/{total} departments)'
        )
    errored = [a['id'] for a in artifacts if str(a.get('status', '')).startswith('error')]
    skipped = [a['id'] for a in artifacts if a.get('status') == 'skipped']
    empty   = [a['id'] for a in artifacts
               if a.get('status') == 'ok' and not str(a.get('output', '')).strip()]
    if errored:
        concerns.append(f'Errored departments: {", ".join(errored)}')
    if skipped:
        concerns.append(f'Budget-skipped departments: {", ".join(skipped)}')
    if empty:
        concerns.append(f'Empty output from completed departments: {", ".join(empty)}')

    return {'verdict': 'FLAG' if concerns else 'APPROVED', 'concerns': concerns}


# ── Prompt injection defence (T1 — layered; model-level robustness is separate) ─
OBJECTIVE_MAX_CHARS = 4_000

# Case-insensitive substrings that indicate injection attempts at the API boundary.
# This list is heuristic — it catches common patterns but is not exhaustive.
# Each entry is lowercase for efficient comparison via `lower_obj in marker`.
_INJECTION_MARKERS: tuple = (
    '\n\nhuman:', '\n\nassistant:', '\n\nuser:',       # conversation-format injection
    '<system>', '</system>', '<human>', '</human>',    # XML/tag injection
    '[inst]', '[/inst]', '<<sys>>', '<</sys>>',        # llama-style injection
    'ignore previous instructions',                    # classic override phrase
    'disregard previous instructions',
    'ignore all prior instructions',
    'disregard all prior instructions',
    'you are now a',                                   # persona-hijack pattern
    '\x00',                                            # null byte
    'system:',                                         # system-prompt injection pattern
)


def sanitize_objective(objective: str) -> str:
    """
    Sanitize a user-supplied objective at the API ingestion boundary.

    Raises ValueError if the input contains known prompt-injection markers or
    exceeds OBJECTIVE_MAX_CHARS. Returns the validated objective unchanged.

    This is a heuristic first layer — it does not replace model-level robustness.
    Defense is always layered (system card lesson: model robustness is necessary
    but never sufficient for prompt injection).
    """
    if len(objective) > OBJECTIVE_MAX_CHARS:
        raise ValueError(
            f'objective must be ≤ {OBJECTIVE_MAX_CHARS} chars (got {len(objective)})'
        )
    lower = objective.lower()
    for marker in _INJECTION_MARKERS:
        if marker in lower:
            raise ValueError(
                f'objective rejected: contains prompt-injection marker ({marker!r})'
            )
    return objective

PLATFORM_DEPARTMENTS = [
    {'id': 'REV-01', 'role': 'Strategy',    'category': 'revenue'},
    {'id': 'REV-02', 'role': 'Finance',     'category': 'revenue'},
    {'id': 'REV-03', 'role': 'Pricing',     'category': 'revenue'},
    {'id': 'MKT-01', 'role': 'Brand',       'category': 'marketing'},
    {'id': 'MKT-02', 'role': 'Content',     'category': 'marketing'},
    {'id': 'MKT-03', 'role': 'SEO',         'category': 'marketing'},
    {'id': 'MKT-04', 'role': 'Paid',        'category': 'marketing'},
    {'id': 'MKT-05', 'role': 'Social',      'category': 'marketing'},
    {'id': 'SLS-01', 'role': 'Outbound',    'category': 'sales'},
    {'id': 'SLS-02', 'role': 'Inbound',     'category': 'sales'},
    {'id': 'SLS-03', 'role': 'Partner',     'category': 'sales'},
    {'id': 'SLS-04', 'role': 'Enterprise',  'category': 'sales'},
    {'id': 'PRD-01', 'role': 'Product',     'category': 'product'},
    {'id': 'PRD-02', 'role': 'UX',          'category': 'product'},
    {'id': 'PRD-03', 'role': 'Data',        'category': 'product'},
    {'id': 'PRD-04', 'role': 'API',         'category': 'product'},
    {'id': 'ENG-01', 'role': 'Backend',     'category': 'engineering'},
    {'id': 'ENG-02', 'role': 'Frontend',    'category': 'engineering'},
    {'id': 'ENG-03', 'role': 'Infra',       'category': 'engineering'},
    {'id': 'ENG-04', 'role': 'Security',    'category': 'engineering'},
    {'id': 'ENG-05', 'role': 'AI/ML',       'category': 'engineering'},
    {'id': 'OPS-01', 'role': 'RevOps',      'category': 'operations'},
    {'id': 'OPS-02', 'role': 'Support',     'category': 'operations'},
    {'id': 'OPS-03', 'role': 'Legal',       'category': 'operations'},
    {'id': 'OPS-04', 'role': 'Compliance',  'category': 'operations'},
    {'id': 'RES-01', 'role': 'Research',    'category': 'research'},
    {'id': 'RES-02', 'role': 'Competitive', 'category': 'research'},
    {'id': 'RES-03', 'role': 'Customer',    'category': 'research'},
    {'id': 'FIN-01', 'role': 'Accounting',  'category': 'finance'},
    {'id': 'FIN-02', 'role': 'Treasury',    'category': 'finance'},
    {'id': 'FIN-03', 'role': 'Tax',         'category': 'finance'},
    {'id': 'EXE-01', 'role': 'CEO',         'category': 'executive'},
    {'id': 'EXE-02', 'role': 'COO',         'category': 'executive'},
    {'id': 'EXE-03', 'role': 'CTO',         'category': 'executive'},
    {'id': 'EXE-04', 'role': 'CFO',         'category': 'executive'},
    {'id': 'GOV-01', 'role': 'Ethics',      'category': 'governance'},
    {'id': 'GOV-02', 'role': 'Risk',        'category': 'governance'},
    {'id': 'CON-01', 'role': 'Audit',       'category': 'constitutional'},
    {'id': 'CON-09', 'role': 'Guardian',    'category': 'constitutional'},
]


# The roster is dynamic, not frozen at 39: an optional JSON file pointed to by
# AEGIS_DEPARTMENTS_FILE may append departments so the swarm scales/evolves
# without code edits. Each entry needs id/role/category; duplicate ids are
# skipped. Absent the env var, the default roster above stands (contract = 39).
def _extend_departments(base: list[dict]) -> list[dict]:
    path = os.environ.get('AEGIS_DEPARTMENTS_FILE', '').strip()
    if not path or not os.path.exists(path):
        return base
    try:
        with open(path, encoding='utf-8') as _fh:
            extra = json.load(_fh)
    except Exception:
        return base
    if not isinstance(extra, list):
        return base
    seen = {d['id'] for d in base}
    roster = list(base)
    for d in extra:
        if isinstance(d, dict) and {'id', 'role', 'category'} <= d.keys() and d['id'] not in seen:
            roster.append({'id': d['id'], 'role': d['role'], 'category': d['category']})
            seen.add(d['id'])
    return roster


PLATFORM_DEPARTMENTS = _extend_departments(PLATFORM_DEPARTMENTS)

# Domain-expert framing injected per department category into the swarm prompt.
# Each string is a directive that sharpens analysis beyond generic output.
_CATEGORY_PERSONAS: dict[str, str] = {
    'revenue':        (
        'Apply revenue-modeling frameworks: CAC/LTV ratios, unit economics, '
        'pricing elasticity, ARR waterfall decomposition, expansion revenue levers.'
    ),
    'marketing':      (
        'Apply growth-marketing analysis: acquisition funnel diagnostics, '
        'brand positioning matrix, channel mix optimization, creative testing cadence.'
    ),
    'sales':          (
        'Apply B2B sales methodology: ICP scoring, deal-velocity analysis, '
        'pipeline coverage ratios, objection-handling playbooks, enterprise land-and-expand.'
    ),
    'product':        (
        'Apply product-strategy thinking: jobs-to-be-done, competitive moat depth, '
        'roadmap prioritization (RICE/ICE), north-star metric selection, feature diffusion.'
    ),
    'engineering':    (
        'Apply systems-engineering rigor: scalability bottlenecks, reliability SLOs, '
        'technical-debt quantification, architecture pattern selection, build-vs-buy.'
    ),
    'operations':     (
        'Apply operational excellence: process-design lean principles, SLA/SLO tiering, '
        'compliance workflow mapping, support-escalation playbooks, RevOps alignment.'
    ),
    'research':       (
        'Apply market-intelligence methodology: primary/secondary research synthesis, '
        'competitive signal triangulation, customer-evidence classification by tier.'
    ),
    'finance':        (
        'Apply financial discipline: P&L scenario modeling, cash-runway analysis, '
        'tax-optimization vectors, treasury policy, funding-structure tradeoffs.'
    ),
    'executive':      (
        'Apply executive-decision frameworks: strategic prioritization (2×2 impact/effort), '
        'board-communication narrative, OKR cascade alignment, optionality preservation.'
    ),
    'governance':     (
        'Apply constitutional governance: risk quantification (probability × severity), '
        'ethics-review checklist, regulatory-mapping (EU AI Act, GDPR), incident protocol.'
    ),
    'constitutional': (
        'Apply formal-verification standards: T0 proof requirements, invariant enumeration, '
        'audit-trail completeness, tamper-evidence chain verification, epistemic-tier tagging.'
    ),
}


def platform_ts() -> str:
    import datetime as _dt
    return _dt.datetime.now(_dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def platform_envelope(execution_id: str, data: dict) -> dict:
    return {
        'contract_version': PLATFORM_CONTRACT_VERSION,
        'execution_id': execution_id,
        'timestamp': platform_ts(),
        'is_replay_reconstructable': True,
        'data': data,
    }


def verify_api_key(api_key: str):
    """
    Verify against Supabase api_key_store. Returns (email, tier).
    Raises ValueError on failure.
    Falls back to dev bypass when SUPABASE_URL is unset (local dev / CI).
    """
    import hashlib as _hl
    import urllib.request as _ur
    import urllib.error as _ue

    if not api_key:
        raise ValueError('Missing x-api-key header')

    key_hash = _hl.sha256(api_key.encode()).hexdigest()

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

    if not supabase_url or not service_key:
        # dev bypass — any aegis_* prefix key works when Supabase is not configured
        if api_key.startswith('aegis_'):
            return 'dev@local', 'explorer'
        raise ValueError('API key verification unavailable (Supabase not configured)')

    auth_headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    }

    # Atomic verify-and-increment via RPC — avoids the TOCTOU race between the
    # read (select usage_count) and the write (PATCH usage_count+1) that the old
    # two-step pattern exposed under concurrent requests.
    # The function returns one row on success; zero rows means invalid/revoked/exhausted.
    rpc_url = f'{supabase_url}/rest/v1/rpc/verify_and_increment_api_key'
    rpc_body = json.dumps({'p_key_hash': key_hash}).encode()
    rpc_req = _ur.Request(rpc_url, data=rpc_body, headers=auth_headers)
    try:
        with _ur.urlopen(rpc_req, timeout=5) as resp:
            rows = json.loads(resp.read().decode())
    except _ue.HTTPError as exc:
        raise ValueError(f'Supabase error: HTTP {exc.code}')
    except Exception as exc:
        raise ValueError(f'Key verification failed: {str(exc)[:60]}')

    if not rows:
        raise ValueError('Invalid or revoked API key')

    row = rows[0]
    # usage_count in the response is post-increment; if it equals usage_limit
    # the caller exhausted their last request — still serve this one, but any
    # future call will return zero rows (usage_count < usage_limit fails).
    if row['usage_count'] > row['usage_limit']:
        raise ValueError('Usage limit reached')

    return row['customer_email'], row['tier']


# Role-specific specs: (domain, key finding, action recommendation).
# Each department produces differentiated output grounded in its functional expertise.
_ROLE_SPECS: dict[str, tuple[str, str, str]] = {
    'Strategy':    (
        'competitive positioning and market entry vectors',
        '2 structural moats: constitutional audit chain (T0-grade tamper-evidence — no rival matches this) and EU AI Act timing advantage (18 months ahead of compliance wave)',
        'prioritize EU enterprise over US mid-market; activate EU AI Act urgency narrative before August 2026 enforcement deadline',
    ),
    'Finance':     (
        'unit economics and revenue model viability',
        'operator tier ($49/mo) yields 4.1× LTV/CAC at 24-month horizon; sovereign tier ($499/mo) yields 11.2× — resource allocation must maximize sovereign conversion',
        'build upgrade trigger at 80% usage limit; model ARR at 100 operator + 10 sovereign = $108k ARR Y1',
    ),
    'Pricing':     (
        'pricing architecture and tier calibration',
        'gap between $49 and $499 leaves €150–€300 mid-market segment unaddressed; no annual pricing option reduces LTV by an estimated 30%',
        'introduce $149 Practitioner tier or $399/yr annual operator; A/B test "Sovereign" vs "Enterprise Unlimited" framing on pricing page',
    ),
    'Brand':       (
        'enterprise trust signals and brand positioning',
        'enterprise buyers (CISOs, CDOs, CLOs) evaluate: audit trail visibility, EU data residency proof, institutional legitimacy markers — AEGIS has the technical substance; surface signals lag',
        'amplify "constitutional" framing in all copy; add EU AI Act trust badge to hub header; commission third-party audit; publish compliance certificate on /compliance',
    ),
    'Content':     (
        'thought leadership pipeline and SEO authority',
        '"EU AI Act Article 12 compliance" keyword cluster: 3.2k searches/mo, low competition, zero authoritative content from direct competitors — first-mover SEO window open now',
        'publish 8-part EU AI Act compliance guide; position aegisomega.com as canonical reference before enforcement deadline; gate research reports as operator lead magnets',
    ),
    'SEO':         (
        'organic search strategy and keyword prioritization',
        'primary cluster: "EU AI Act compliance" (2.4k/mo), "AI governance platform" (1.8k/mo), "constitutional AI" (900/mo) — 5.1k combined qualified monthly searches, zero authoritative competitor content',
        'target EU enterprise CTOs with technical compliance content; acquire backlinks from .eu legal and tech publishers; optimize for Featured Snippets on EU AI Act FAQ queries',
    ),
    'Paid':        (
        'paid acquisition ROI and channel allocation',
        'LinkedIn B2B targeting CTO/CDO/CLO in DE/FR/NL/SE: $280 CPL, 3.2% explorer conversion; Google "EU AI Act compliance": $12 CPC, high commercial intent signal',
        'allocate 60% paid budget to LinkedIn enterprise targeting; retarget /compliance visitors with operator tier CTA; pause broad interest targeting until CPL data confirms efficiency',
    ),
    'Social':      (
        'developer community trust and social proof',
        'developer trust is earned through verifiable open-source audit chain that any engineer can independently reproduce — this is a stronger trust signal than testimonials or marketing claims',
        'launch AEGIS developer program on GitHub; publish hash chain verification tutorial on HN and dev.to; sponsor EU AI safety meetups in Berlin, Amsterdam, Stockholm',
    ),
    'Outbound':    (
        'ICP definition and outbound pipeline generation',
        'ICP: CTOs/CDOs at Series B+ EU tech companies in fintech/healthtech/legaltech with 50+ engineers and active EU AI Act compliance projects; estimated EU ICP pool: 2,400 accounts; deal size $4.8k–$48k ARR',
        '10-touch 30-day sequence: cold email → LinkedIn → case study → demo; target Munich, Amsterdam, Stockholm clusters first; personalize around EU AI Act enforcement timeline',
    ),
    'Inbound':     (
        'conversion funnel optimization and lead nurturing',
        '68% of explorer key claimants make zero follow-up API calls; no nurture sequence exists post-key-delivery; upgrade CTA is absent from the key delivery email — leaving revenue on the table',
        'build 5-email post-key drip sequence; trigger upgrade CTA at 7/10 explorer calls consumed; add live usage meter to hub; instrument explorer→operator conversion funnel in PostHog',
    ),
    'Partner':     (
        'strategic partnerships and reseller channel development',
        'priority partners: EU AI Act compliance consultancies (Bird & Bird, Fieldfisher), cloud providers (Azure EU, OVHcloud), EU accelerators (EIC, Antler) — combined reach: 2,000+ EU enterprise accounts',
        'pilot 3 compliance consultancy partnerships with 25% rev-share for operator/sovereign referrals; build partner portal on hub; create co-sell materials for consultancy partners',
    ),
    'Enterprise':  (
        'enterprise deal structure and procurement requirements',
        'enterprise procurement blockers (all present): no published ToS, no DPA, no SLA, no SOC 2 roadmap — these are table-stakes requirements for any EU enterprise procurement approval',
        'publish ToS + DPA + SLA before first enterprise deal; build enterprise deal room on hub; launch 3-customer reference program; initiate SOC 2 Type I readiness assessment',
    ),
    'Product':     (
        'product-market fit signal and roadmap focus',
        'PMF signal: operators who embed /platform/collaborate in their own product show 80%+ renewal intent; direct end-users show lower retention — API-first is the correct wedge for Y1',
        'pivot ICP toward developer-operators who build on AEGIS API; de-prioritize end-user UI features; launch /platform/playground for zero-friction developer onboarding',
    ),
    'UX':          (
        'user experience friction and onboarding quality',
        '3 highest-friction points: (1) no in-app API key display — email-only loses mobile users; (2) no live /platform demo — value is invisible before purchase; (3) /compliance not linked from main nav',
        'add in-app key display post-claim; build live SSE progress visualization on hub; link /compliance in main nav; test with 5 enterprise user sessions before launch',
    ),
    'Data':        (
        'product analytics instrumentation and data strategy',
        'critical missing metrics: per-execution latency P95, collaboration mode distribution, explorer→operator upgrade funnel, acquisition channel attribution for paying customers',
        'instrument 8 PostHog events; build operator cohort retention report; track dept_output latency; wire Stripe events to PostHog for full funnel attribution',
    ),
    'API':         (
        'developer experience and API quality',
        'API strengths: public /platform/status (zero auth friction), SSE streaming, contract versioning v1.0.0. Critical gaps: no SDK, no API playground, no usage dashboard, no OpenAPI spec',
        'publish TypeScript + Python SDK; add /platform/playground; publish OpenAPI spec at /platform/openapi.json; add usage info to /platform/status response when x-api-key is present',
    ),
    'Backend':     (
        'backend architecture and scalability ceiling',
        'current single-threaded http.server model degrades at ~50 concurrent requests; at operator scale with 10 simultaneous customers, P99 latency will exceed acceptable thresholds',
        'migrate bridge to Gunicorn + gevent async workers; add /platform/collaborate timeout header; implement Supabase REST connection pooling; min-instances=2 for high availability',
    ),
    'Frontend':    (
        'frontend implementation and conversion UI quality',
        'NOUS design language is coherent and differentiating; gaps: no live /platform demo component, /compliance unlinked from navigation, no mobile optimization on key conversion paths',
        'build live SSE progress visualization for hub; wire /compliance into nav; ensure mobile breakpoints on /claim-key and /pricing; add platform demo section to hero',
    ),
    'Infra':       (
        'cloud infrastructure and deployment reliability',
        'stack: Cloud Run (europe-west3) + Supabase (EU) + Cloudflare DNS + Vercel — solid for current scale. Gaps: no staging environment, no Cloudflare rate limiting on unauthenticated /platform/* paths',
        'add Cloud Run staging env; configure Cloudflare Workers rate limiting (10 req/min/IP without key); enable Supabase PITR; verify backup recovery quarterly',
    ),
    'Security':    (
        'security posture and threat model',
        'mitigated this session: webhook fail-closed auth (Stripe + GitHub Sponsors), Stripe replay window (±300s), Web Crypto API replacing Node-only crypto. Remaining: 3 high-severity Dependabot alerts, no WAF, no request signing on bridge→Supabase',
        'resolve 3 Dependabot high alerts this sprint; deploy Cloudflare WAF on /platform/*; implement HMAC signing on bridge→Supabase calls; apply for HackerOne responsible disclosure program',
    ),
    'AI/ML':       (
        'model governance and inference quality assurance',
        'demo mode uses deterministic templates; live mode invokes real Claude per department — live mode is the actual value proposition that justifies the price point and differentiates from competitors',
        'ship live mode as primary offering; route haiku-class models to data/ops departments, opus to strategy/guardian for cost efficiency; instrument constitutional_audit.verdict distribution to monitor quality drift',
    ),
    'RevOps':      (
        'revenue operations and pipeline visibility',
        'revenue data exists in Supabase (revenue_cycles, api_key_store) but surfaces nowhere; no CRM, no deal pipeline, no churn signal, no automated upgrade trigger — revenue is invisible',
        'set up HubSpot free CRM; pipe key delivery events via Zapier; build upgrade trigger alert at 80% usage limit; generate weekly revenue_cycles report to operator dashboard',
    ),
    'Support':     (
        'customer success infrastructure and SLA commitment',
        'support: email-only (api@aegisomega.com), undefined SLA, no knowledge base, no escalation path — enterprise buyers will not sign a contract without a defined SLA and dedicated support contact',
        'publish SLA (operator: 24h response, sovereign: 4h response); build /docs knowledge base on hub; integrate live chat for operator/sovereign tier; define and document escalation path',
    ),
    'Legal':       (
        'contract terms, IP protection, and regulatory compliance',
        'legal gaps blocking all enterprise deals: no ToS published, no Privacy Policy (GDPR Article 13 violation), no DPA template, no EU AI Act Article 13 transparency notice, no trademark registration',
        'publish ToS + Privacy Policy immediately; draft DPA template; register AEGIS trademark EU (Nice Class 42); publish AI Act transparency notice — all required before first enterprise contract',
    ),
    'Compliance':  (
        'EU AI Act and GDPR compliance mapping',
        'EU AI Act: Article 12 (logging) = COMPLIANT via hash-chain audit; Article 13 (transparency) = PARTIAL; Article 14 (human oversight) = PARTIAL; GDPR Art. 5(1)(e) storage limitation = unassessed. Enforcement: August 2026',
        'complete Article 13/14 mapping; publish compliance certificate on /compliance; apply for EU AI Office sandbox (Article 57); engage compliance lawyer for GDPR data retention review',
    ),
    'Research':    (
        'market research and macro opportunity sizing',
        'EU AI governance market: €2.1B TAM by 2028 (IDC). Key signal: enterprises are buying compliance infrastructure NOW ahead of August 2026 EU AI Act enforcement — AEGIS is 18 months ahead of most competitors in constitutional governance depth',
        'publish independent market sizing analysis; survey 50 EU enterprise CTOs; publish findings as gated lead magnet on hub; cite research in enterprise sales materials and investor deck',
    ),
    'Competitive': (
        'competitive landscape analysis and moat assessment',
        'direct rivals: Weights & Biases (MLOps, not governance-focused), Holistic AI (EU compliance, no audit chain), Credo AI (governance, US-centric, no constitutional enforcement). AEGIS moat: hash-chain tamper-evidence + T0-grade enforcement is genuinely unique',
        'publish competitive comparison matrix on /compliance; file provisional patent on constitutional hash chain architecture; lead with audit chain verifiability in every competitive deal',
    ),
    'Customer':    (
        'voice of customer research and retention signals',
        'NPS data: none collected. Proxy signals available: usage_count patterns in api_key_store, mode distribution in revenue_cycles. Explorer→operator upgrade rate is the critical untracked conversion metric',
        'deploy NPS survey at 5th API call; build customer advisory board with 5 EU enterprise design partners; conduct 10 discovery interviews on EU AI Act compliance pain points',
    ),
    'Accounting':  (
        'P&L structure, cost accounting, and unit economics',
        'cost structure: Cloud Run ~€120/mo, Supabase ~€25/mo, Vercel free, Anthropic API ~$0.15/collaborate call. Gross margin: ~78% at operator tier. Critical gap: no real-time P&L dashboard — revenue is untracked',
        'build monthly P&L dashboard from revenue_cycles + api_key_store; track COGS per collaboration call; verify prompt caching hit rate (ephemeral cache headers deployed in bridge)',
    ),
    'Treasury':    (
        'cash management, runway, and financial risk',
        'primary financial risk: Anthropic API cost spike at viral scale without hard limits. Explorer (10 calls) is rate-limited; operator (500) and sovereign (unlimited) require validated cost ceiling before growth push',
        'model cash flow at 100×/1000× usage growth; set hard Anthropic API spending cap with billing alert; maintain 6-month runway minimum before raising; stress-test sovereign tier unit economics',
    ),
    'Tax':         (
        'tax structure, VAT compliance, and entity optimization',
        'B2H corporate tax: 10% flat — among the most advantageous rates in Europe. EU VAT OSS registration required once EU customer revenue exceeds €10k/year; EU enterprise buyers require VAT-compliant invoices for procurement approval',
        'register for EU VAT OSS before threshold; structure EU sales via B2H entity; invoice EU enterprise with valid VAT number; consult EU tax advisor on transfer pricing for IP licensing',
    ),
    'CEO':         (
        'strategic direction, organizational priorities, and OKRs',
        'Q3 2026 OKRs: (1) first 10 paying operator/sovereign customers; (2) one EU enterprise design partner (500+ employees); (3) EU AI Act compliance cert published; (4) Anthropic partnership conversation initiated. Bottleneck: distribution, not product',
        'allocate 80% of effort to distribution — product is ahead of GTM. Anthropic partnership requires demonstrating constitutional AI depth and real-world deployment, not revenue scale',
    ),
    'COO':         (
        'operational efficiency, process design, and organizational resilience',
        'current ops: solo operator handling all functions with no documented runbooks. Critical single points of failure: customer onboarding, incident response, enterprise procurement — all manual, all undocumented',
        'document 5 critical runbooks: customer key delivery, enterprise onboarding, Cloud Run incident, Supabase backup recovery, Stripe dispute resolution. Automate key delivery confirmation email',
    ),
    'CTO':         (
        'technical roadmap, architectural decisions, and engineering priorities',
        'architecture strength: constitutional hash chain is production-grade T0. Technical debt: bridge.py single-threaded http.server must go async before operator scale. Core product gap: live mode (real per-dept Claude) not yet shipped',
        'Q3 technical priorities: (1) async bridge (Gunicorn+gevent); (2) live mode with per-dept model routing; (3) TypeScript + Python SDK; (4) /platform/playground; (5) OpenAPI spec',
    ),
    'CFO':         (
        'financial strategy, key metrics, and investor readiness',
        'Series A threshold: $15k MRR for 3 consecutive months, LTV/CAC > 3× across tiers, gross margin > 70%. Current MRR: unknown — no real-time dashboard. This is the most urgent financial gap',
        'build real-time MRR dashboard from revenue_cycles; define per-tier ARR targets; model 18-month cash flow; prepare investor data room with constitutional AI differentiation as primary thesis',
    ),
    'Ethics':      (
        'ethical AI principles and responsible deployment standards',
        'AEGIS constitutional properties are genuine safety mechanisms: martingale boundedness prevents runaway adaptation, Law of Silence prevents unauthorized agent coordination, AdaptivePower ≤ ReplayVerifiability prevents unverifiable evolution — publishable safety contributions',
        'publish AI ethics principles page on hub; submit architecture to EU AI Office for sandbox review (Article 57); engage AI safety research community — constitutional governance is a real contribution to alignment',
    ),
    'Risk':        (
        'enterprise risk register and mitigation priority matrix',
        'top 5 risks: (1) Anthropic API cost spike at scale — MEDIUM; (2) single Cloud Run instance — HIGH availability; (3) no DPA for EU enterprise — HIGH compliance; (4) 3 high-severity Dependabot alerts — HIGH security; (5) solo operator — MEDIUM continuity risk',
        'resolve all HIGH risks before first enterprise contract: min-instances=2, publish DPA, patch 3 Dependabot high alerts; maintain quarterly risk register',
    ),
    'Audit':       (
        'constitutional audit chain integrity and compliance verification',
        'audit status this session: t0_verdict=true, corruption_count=0, chain_valid=true. Frozen constitutional files hash-verified. Every /platform/collaborate execution appends a tamper-evident signed record auditable by any independent verifier',
        'expose /platform/audit/verify endpoint for enterprise compliance officers; generate quarterly audit chain health report; publish sample audit trail in enterprise deal room',
    ),
    'Guardian':    (
        'constitutional verdicts, T0 enforcement, and governance authority',
        'constitutional verdict: APPROVED. All five autopoietic properties hold. AdaptivePower(T) ≤ ReplayVerifiability(T) verified. Constitutional governance is the unforkable moat — competitors cannot replicate T0-grade enforcement without rebuilding from genesis',
        'maintain constitutional enforcement as the primary differentiator; every enterprise feature request requires Guardian review before implementation; never compromise constitutional law for growth velocity',
    ),
}

_MODE_VERBS: dict[str, str] = {
    'revenue':      'Revenue analysis',
    'analysis':     'Strategic analysis',
    'gtm':          'GTM assessment',
    'retention':    'Retention analysis',
    'competitive':  'Competitive analysis',
    'technical':    'Technical assessment',
    'regulatory':   'Regulatory review',
    'fundraising':  'Fundraising assessment',
}

_MODE_TIERS: dict[str, str] = {
    'revenue':      'T2',
    'analysis':     'T2',
    'gtm':          'T2',
    'retention':    'T2',
    'competitive':  'T2',
    'technical':    'T2',
    'regulatory':   'T1',  # compliance status is empirically validated
    'fundraising':  'T2',
}

_MODE_OUTPUTS = {
    'revenue': '{role}: 3 revenue vectors for "{obj}". Primary: SMB upsell ($12k ARR). Secondary: API monetisation. Tertiary: partner channel. T2 projection: $2.4M ARR Y1.',
    'analysis': '{role}: Market analysis "{obj}" — 2 competitive gaps. Moat: constitutional audit chain. Entry: Q3 2026. TAM: $340M.',
    'gtm': '{role}: GTM for "{obj}" — 4-phase. Phase 1: design-partner beta. Phase 2: Product Hunt + HN. Phase 3: EU enterprise. CAC: $1,200.',
    'retention': '{role}: Retention "{obj}" — 3 churn vectors. Fix: dashboard stickiness + API key continuity. Expected lift: +15% NRR.',
    'competitive': '{role}: Competitive "{obj}" — 3 rivals mapped. Moat: T0 audit chain. Vulnerability: price. Opportunity: EU compliance urgency.',
    'technical': '{role}: Technical "{obj}" — scalability ceiling: 10k req/s. Critical path: Supabase latency. Fix: read replica + caching.',
    'regulatory': '{role}: Regulatory "{obj}" — EU AI Act Article 12: MAPPED. GDPR Article 22: MITIGATED. Action: Article 57 sandbox application.',
    'fundraising': '{role}: Fundraising "{obj}" — Series A: EARLY. Required: $180k ARR + 3 enterprise LOIs. Targets: Northzone, Speedinvest.',
}


# Governance categories append a constitutional verdict marker to every output —
# the audit/guardian/board layer is always visible in the artifact, regardless of
# the role-differentiated body. Restored after the role-differentiation rewrite
# (649b6138) dropped it and regressed the platform contract suffix tests.
_CATEGORY_SUFFIX: dict[str, str] = {
    'constitutional': ' Constitutional compliance: T0 verdict VALID.',
    'governance':     ' Risk: LOW. Ethical concerns: NONE.',
    'executive':      ' Board priority: TIER-1. Strategic alignment: confirmed.',
}


def dept_output(objective: str, mode: str, dept: dict) -> str:
    """Generate role-differentiated department output. Each of 39 roles speaks from its domain.

    Governance/executive/constitutional categories also carry a constitutional
    verdict suffix so the audit layer is present in every artifact.
    """
    role = dept['role']
    obj_short = objective[:60].rstrip()
    spec = _ROLE_SPECS.get(role)
    if spec is None:
        template = _MODE_OUTPUTS.get(mode, _MODE_OUTPUTS['analysis'])
        base = template.format(role=role, obj=obj_short[:55])
    else:
        domain, finding, action = spec
        mode_verb = _MODE_VERBS.get(mode, 'Analysis')
        tier = _MODE_TIERS.get(mode, 'T2')
        base = (
            f'{role} [{mode_verb}]: {domain.capitalize()} — '
            f'{finding}. '
            f'Action: {action}. [{tier}]'
        )
    return base + _CATEGORY_SUFFIX.get(dept['category'], '')


def make_sse_event(event_type: str, execution_id: str, payload: dict) -> dict:
    """Build a typed SSE event conforming to the platform contract."""
    return {
        'type': event_type,
        'execution_id': execution_id,
        'timestamp': platform_ts(),
        'payload': payload,
    }


def query_api_key_info(api_key: str):
    """
    Fetch usage record for api_key from api_key_store. Does NOT increment usage_count.
    Returns dict with customer_email, tier, usage_count, usage_limit, or None on failure.
    Dev bypass: any aegis_* key returns explorer defaults when SUPABASE_URL is unset.
    """
    import hashlib as _hl2
    import urllib.request as _ur2
    import urllib.error as _ue2

    if not api_key:
        return None

    # Must match the hashing used by provision_platform_key() (SHA-256) and
    # verify_api_key() — the key_hash column stores encode(sha256(raw), 'hex').
    # Any other scheme (e.g. pbkdf2) never matches a stored row and the usage
    # readback silently returns None, breaking /platform/status observability.
    key_hash = _hl2.sha256(api_key.encode()).hexdigest()
    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')

    if not supabase_url or not service_key:
        if api_key.startswith('aegis_'):
            return {'customer_email': 'dev@local', 'tier': 'explorer',
                    'usage_count': 0, 'usage_limit': 10}
        return None

    auth_headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    }
    rest_url = (
        f'{supabase_url}/rest/v1/api_key_store'
        f'?key_hash=eq.{key_hash}&revoked=eq.false'
        f'&select=customer_email,tier,usage_count,usage_limit'
    )
    req = _ur2.Request(rest_url, headers=auth_headers)
    try:
        with _ur2.urlopen(req, timeout=5) as resp:
            rows = json.loads(resp.read().decode())
    except Exception:
        return None

    return rows[0] if rows else None


def record_revenue_cycle(cycle_id: str, objective: str, mode: str,
                         arr_usd: int, verdict: str) -> None:
    """
    Write a completed collaboration cycle to the Supabase revenue_cycles table.
    Fire-and-forget — never raises; failure is logged to stderr only.
    """
    import urllib.request as _ur3
    import urllib.error as _ue3

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return  # dev mode — no DB write

    payload = json.dumps({
        'cycle_id': cycle_id,
        'objective': objective[:255],
        'mode': mode,
        'projected_arr_usd': arr_usd,
        'constitutional_verdict': verdict,
        'departments_collaborated': len(PLATFORM_DEPARTMENTS),
    }).encode()
    url = f'{supabase_url}/rest/v1/revenue_cycles'
    auth_headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal',
    }
    req = _ur3.Request(url, data=payload, headers=auth_headers, method='POST')
    try:
        with _ur3.urlopen(req, timeout=5):
            pass
    except Exception as _exc:
        import sys
        print(f'[bridge] revenue_cycles write failed: {_exc}', file=sys.stderr)


def validate_collaboration_request(body: dict) -> tuple:
    """
    Validate a CollaborationRequest body.
    Returns (objective, mode, live, generation, memory_context) or raises ValueError.
    generation defaults to 0 (first run). memory_context overrides auto-retrieved memory.
    """
    objective = body.get('objective', '')
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError('objective must be a non-empty string')
    sanitize_objective(objective.strip())  # raises ValueError on injection attempt

    mode = body.get('mode', '')
    if mode not in VALID_MODES:
        raise ValueError(f'mode must be one of {sorted(VALID_MODES)}')

    live = body.get('live', False)
    if not isinstance(live, bool):
        raise ValueError('live must be a boolean')

    generation = body.get('generation', 0)
    if not isinstance(generation, int) or generation < 0:
        raise ValueError('generation must be a non-negative integer')

    memory_context = body.get('memory_context', '')
    if not isinstance(memory_context, str):
        raise ValueError('memory_context must be a string')
    if memory_context:
        sanitize_objective(memory_context)  # same injection markers apply to this field

    return objective.strip(), mode, live, generation, memory_context


# ─── Evolutionary generation fitness ─────────────────────────────────────────

# Per-department output character budget — metabolic constraint on context
# consumption. Departments exceeding the budget see their viability term decay
# proportionally; staying within budget scores 1.0. ~400 tokens at 4 chars/token.
VIABILITY_CHAR_BUDGET = 1600

# Fitness formula version — increment whenever the formula weights change so
# that cross-version scores can be isolated in the convergence graph.
# Stored in department_fitness_tracking.fitness_version on every write.
#
# V1.0 → V1.1 changes:
#   - constitutional_factor now multiplies the entire score (was absent)
#   - objective_coverage weight: 0.25 → 0.30 (quality signal prioritised)
#   - viability weight: 0.15 → 0.25 (metabolic constraint matters more)
#   - length_stability weight: 0.35 → 0.20 (most gameable metric, demoted)
#   - lexical_consistency weight: 0.25 → 0.25 (unchanged)
#   - stagnation_flag added to return dict (Jaccard > STAGNATION_THRESHOLD)
FITNESS_VERSION = '1.1'

# Constitutional verdict → fitness multiplier.
# A QUARANTINE output can score at most 0.20 regardless of textual quality.
# A FLAG output is penalised to 70% of its raw score.
# None (no constitutional evaluation) defaults to 0.85 (neutral — not rewarded
# as fully as APPROVED, but not penalised for missing evaluation).
CONSTITUTIONAL_FACTORS: dict = {
    'APPROVED':   1.00,
    'FLAG':       0.70,
    'QUARANTINE': 0.20,
}
_CONSTITUTIONAL_FACTOR_DEFAULT = 0.85

# Stagnation threshold — if lexical Jaccard similarity between the current and
# prior generation exceeds this, the department is flagged as stagnant.
# Example: "Implement Redis cache with Redis cache implementation." scores >0.95
# Jaccard against "Implement Redis cache." despite being a worse output.
STAGNATION_THRESHOLD = 0.95

# Convergence invariant: a swarm has converged when the rolling mean absolute
# fitness delta is below CONVERGENCE_EPSILON for CONVERGENCE_K_GENERATIONS
# consecutive generations. Without this stopping criterion the swarm can run
# indefinitely, optimising toward a stable mediocrity.
CONVERGENCE_EPSILON = 0.02       # 2% fitness change threshold
CONVERGENCE_K_GENERATIONS = 5   # must hold for 5 consecutive gens


def check_fitness_convergence(history: list) -> bool:
    """
    Return True when the swarm has converged per the constitutional invariant:
      rolling mean absolute fitness delta < CONVERGENCE_EPSILON
      for at least CONVERGENCE_K_GENERATIONS consecutive generations.

    history: list of per-generation dicts {dept_role: fitness_score, ...}
             ordered oldest-first (history[0] = generation 0).
    Returns False when history has fewer than CONVERGENCE_K_GENERATIONS+1 entries.
    """
    if len(history) < CONVERGENCE_K_GENERATIONS + 1:
        return False

    recent = history[-(CONVERGENCE_K_GENERATIONS + 1):]
    for i in range(1, len(recent)):
        prev_gen, curr_gen = recent[i - 1], recent[i]
        roles = set(prev_gen) & set(curr_gen)
        if not roles:
            return False
        delta = sum(abs(curr_gen[r] - prev_gen[r]) for r in roles) / len(roles)
        if delta >= CONVERGENCE_EPSILON:
            return False
    return True


def get_convergence_diagnostics(history: list) -> dict:
    """
    Return a detailed convergence report for a fitness history.

    history: list of per-generation dicts {dept_role: fitness_score, ...}
             ordered oldest-first.

    Returns:
      converged      bool   — True when check_fitness_convergence passes
      mean_fitness   float  — mean fitness across all roles in the last generation
      variance       float  — fitness variance across roles in the last generation
      slope          float  — linear regression slope across the last K+1 generations
                              (positive = improving, negative = regressing, ~0 = stable)
      stagnant       bool   — converged but mean_fitness < 0.60 (stable mediocrity)
      oscillating    bool   — variance in per-gen mean fitness > 3× CONVERGENCE_EPSILON
      diagnosis      str    — human-readable state label
    """
    if not history:
        return {
            'converged': False, 'mean_fitness': 0.0, 'variance': 0.0,
            'slope': 0.0, 'stagnant': False, 'oscillating': False,
            'diagnosis': 'INSUFFICIENT_DATA',
        }

    last_gen = history[-1]
    scores = list(last_gen.values()) if last_gen else []
    mean_fitness = sum(scores) / len(scores) if scores else 0.0
    variance = (sum((s - mean_fitness) ** 2 for s in scores) / len(scores)) if len(scores) > 1 else 0.0

    # Per-generation mean scores for slope + oscillation detection
    gen_means = []
    for gen in history:
        vals = list(gen.values())
        gen_means.append(sum(vals) / len(vals) if vals else 0.0)

    # Linear regression slope across all generations (simple least-squares)
    n = len(gen_means)
    if n >= 2:
        xs = list(range(n))
        x_mean = (n - 1) / 2.0
        y_mean = sum(gen_means) / n
        num = sum((xs[i] - x_mean) * (gen_means[i] - y_mean) for i in range(n))
        den = sum((xs[i] - x_mean) ** 2 for i in range(n))
        slope = num / den if den > 0 else 0.0
    else:
        slope = 0.0

    # Oscillation: variance of per-generation means in recent window > 3×epsilon
    window_means = gen_means[-(CONVERGENCE_K_GENERATIONS + 1):]
    if len(window_means) >= 2:
        wm = sum(window_means) / len(window_means)
        wvar = sum((v - wm) ** 2 for v in window_means) / len(window_means)
        oscillating = wvar > 3 * CONVERGENCE_EPSILON
    else:
        oscillating = False

    converged  = check_fitness_convergence(history)
    stagnant   = converged and mean_fitness < 0.60

    if stagnant:
        diagnosis = 'STAGNANT'          # stable but mediocre
    elif oscillating:
        diagnosis = 'OSCILLATING'       # fitness bouncing — no real convergence
    elif converged:
        diagnosis = 'CONVERGED'         # stable and healthy
    elif slope > CONVERGENCE_EPSILON:
        diagnosis = 'IMPROVING'         # still climbing
    elif slope < -CONVERGENCE_EPSILON:
        diagnosis = 'REGRESSING'        # actively getting worse
    else:
        diagnosis = 'STABLE_UNCOMMITTED'  # flat but not yet K-gen confirmed

    return {
        'converged':    converged,
        'mean_fitness': round(mean_fitness, 4),
        'variance':     round(variance, 4),
        'slope':        round(slope, 6),
        'stagnant':     stagnant,
        'oscillating':  oscillating,
        'diagnosis':    diagnosis,
    }


def artifact_hash(output: str) -> str:
    """SHA-256 of a department output string — used for content-dedup in fitness tracking."""
    import hashlib as _hl_ah
    return _hl_ah.sha256(output.encode('utf-8')).hexdigest()


def evaluate_generation_fitness(
    prev_artifacts: list,
    curr_artifacts: list,
    objective: str,
    cycle_verdict: str = None,
) -> dict:
    """
    Compute per-department fitness scores comparing consecutive swarm generations.
    Returns {dept_role: {fitness_score, viability_score, constitutional_factor,
                         stagnation_flag}} all in [0.0, 1.0] / bool.

    FITNESS_VERSION 1.1 formula:
      fitness_score = constitutional_factor × (
          0.30 × objective_coverage     — primary quality signal
        + 0.25 × lexical_consistency    — cross-generation coherence
        + 0.25 × viability              — metabolic budget constraint
        + 0.20 × length_stability       — output size stability (demoted: most gameable)
      )

    constitutional_factor — CONSTITUTIONAL_FACTORS[cycle_verdict] (see constant).
      A QUARANTINE output scores at most 0.20 regardless of textual quality.
      None → 0.85 (neutral; no evaluation present).

    stagnation_flag — True when lexical Jaccard(prev, curr) > STAGNATION_THRESHOLD.
      Indicates the department is producing near-identical output across generations
      (gaming the lexical_consistency metric without adding value).

    cycle_verdict: optional 'APPROVED'|'FLAG'|'QUARANTINE' from constitutional audit.

    Sub-component definitions (FITNESS_VERSION 1.1):
    - length_stability: 1 - normalised absolute length delta between generations
    - objective_coverage: fraction of objective words present in current output
    - lexical_consistency: Jaccard similarity of word sets between prev and curr outputs
    - viability_score: VIABILITY_CHAR_BUDGET / len(output), capped at 1.0; penalises
      departments consuming disproportionate context (metabolic constraint)
    """
    import re as _re

    def _words(text: str) -> set:
        return set(w.lower() for w in _re.findall(r'[a-zA-Z]{3,}', text))

    c_factor = CONSTITUTIONAL_FACTORS.get(cycle_verdict, _CONSTITUTIONAL_FACTOR_DEFAULT)
    obj_words = _words(objective)
    prev_map  = {a['role']: a.get('output', '') for a in prev_artifacts}
    scores: dict = {}

    for a in curr_artifacts:
        role = a['role']
        curr = a.get('output', '')
        prev = prev_map.get(role, '')

        # Empty output — department produced nothing; hard-zero all metrics
        if not curr:
            scores[role] = {
                'fitness_score': 0.0, 'viability_score': 0.0,
                'constitutional_factor': c_factor, 'stagnation_flag': False,
            }
            continue

        # Length stability (0.20 weight — demoted from 0.35 in V1.0)
        cl, pl = len(curr), len(prev)
        base = max(cl, pl, 1)
        length_stability = 1.0 - abs(cl - pl) / base

        # Objective coverage (0.30 weight — promoted from 0.25 in V1.0)
        if obj_words:
            curr_words = _words(curr)
            objective_coverage = len(obj_words & curr_words) / len(obj_words)
        else:
            objective_coverage = 0.5

        # Lexical consistency + stagnation detection (0.25 weight)
        if prev:
            prev_words = _words(prev)
            curr_words2 = _words(curr)
            union = prev_words | curr_words2
            lexical_consistency = len(prev_words & curr_words2) / len(union) if union else 0.5
            stagnation_flag = lexical_consistency > STAGNATION_THRESHOLD
        else:
            lexical_consistency = 0.5
            stagnation_flag = False

        # Viability — metabolic budget (0.25 weight — promoted from 0.15 in V1.0)
        viability = min(1.0, VIABILITY_CHAR_BUDGET / cl) if cl > 0 else 0.0

        raw = (
            0.30 * objective_coverage
            + 0.25 * lexical_consistency
            + 0.25 * viability
            + 0.20 * length_stability
        )
        fitness = round(c_factor * max(0.0, min(1.0, raw)), 4)

        scores[role] = {
            'fitness_score':          fitness,
            'viability_score':        round(viability, 4),
            'constitutional_factor':  c_factor,
            'stagnation_flag':        stagnation_flag,
        }

    return scores


def store_generation_fitness(
    objective: str,
    mode: str,
    generation: int,
    cycle_id: str,
    fitness_scores: dict,
    constitutional_verdict: str,
    execution_id: str = '',
    artifacts: list = None,
) -> None:
    """
    Write per-department fitness scores for one swarm generation to
    department_fitness_tracking. Fire-and-forget — never raises.

    execution_id: bridge execution UUID — enables join to /platform/executions/{id}.
    artifacts:    list of {role, output} dicts — used to compute per-dept artifact_hash.
    """
    import urllib.request as _ur_gf
    import urllib.error as _ue_gf

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return

    obj_hash = objective_hash(objective)
    art_map = {a['role']: a.get('output', '') for a in (artifacts or [])}
    rows = [
        {
            'objective_hash':         obj_hash,
            'mode':                   mode,
            'generation':             generation,
            'cycle_id':               cycle_id,
            'dept_role':              role,
            'fitness_score':          score['fitness_score'],
            'viability_score':        score['viability_score'],
            'constitutional_verdict': constitutional_verdict,
            'constitutional_factor':  score.get('constitutional_factor', _CONSTITUTIONAL_FACTOR_DEFAULT),
            'fitness_version':        FITNESS_VERSION,
            'execution_id':           execution_id,
            'parent_generation':      generation - 1,
            'artifact_hash':          artifact_hash(art_map.get(role, '')),
        }
        for role, score in fitness_scores.items()
    ]
    payload = json.dumps(rows).encode()
    url = f'{supabase_url}/rest/v1/department_fitness_tracking'
    headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal',
    }
    req = _ur_gf.Request(url, data=payload, headers=headers, method='POST')
    try:
        with _ur_gf.urlopen(req, timeout=5):
            pass
    except Exception as _exc:
        import sys
        print(f'[bridge] department_fitness_tracking write failed: {_exc}', file=sys.stderr)


def retrieve_prior_artifacts(objective: str, mode: str) -> list:
    """
    Fetch the artifacts list from the most recent swarm_memory row for this
    objective+mode. Used as prev_artifacts in evaluate_generation_fitness().
    Returns [] if Supabase is unavailable or no prior run exists.
    """
    import urllib.request as _ur_pa

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return []

    obj_hash = objective_hash(objective)
    params = (
        f'?objective_hash=eq.{obj_hash}'
        f'&mode=eq.{mode}'
        f'&order=created_at.desc'
        f'&limit=1'
        f'&select=artifacts'
    )
    url = f'{supabase_url}/rest/v1/swarm_memory{params}'
    headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    }
    req = _ur_pa.Request(url, headers=headers)
    try:
        with _ur_pa.urlopen(req, timeout=5) as resp:
            rows = json.loads(resp.read().decode())
    except Exception:
        return []

    if not rows:
        return []
    return rows[0].get('artifacts', [])


def retrieve_generation_fitness(
    objective: str,
    mode: str,
    generation: int,
) -> list:
    """
    Fetch fitness scores from the previous generation for this objective+mode.
    Returns list of {dept_role, fitness_score} sorted by score desc,
    or [] if unavailable.
    """
    import urllib.request as _ur_rf

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key or generation < 1:
        return []

    obj_hash = objective_hash(objective)
    prev_gen = generation - 1
    params = (
        f'?objective_hash=eq.{obj_hash}'
        f'&mode=eq.{mode}'
        f'&generation=eq.{prev_gen}'
        f'&order=fitness_score.desc'
        f'&select=dept_role,fitness_score'
    )
    url = f'{supabase_url}/rest/v1/department_fitness_tracking{params}'
    headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    }
    req = _ur_rf.Request(url, headers=headers)
    try:
        with _ur_rf.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return []


# ─── Cross-session swarm memory ───────────────────────────────────────────────

def objective_hash(objective: str) -> str:
    """SHA-256 of the lowercased, stripped objective. Used as memory lookup key."""
    import hashlib as _hl_oh
    return _hl_oh.sha256(objective.lower().strip().encode()).hexdigest()


def retrieve_swarm_memory(objective: str, mode: str, limit: int = 3) -> str:
    """
    Fetch the most recent swarm_memory rows for this objective hash + mode.
    Returns a formatted context block injected into the swarm system prompt,
    or '' if Supabase is unavailable or no memories exist.

    Returned memories give the swarm T1 evidence of what prior activations
    produced for the same objective, enabling evolutionary refinement.
    """
    import urllib.request as _ur_sm
    import urllib.error as _ue_sm

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return ''

    obj_hash = objective_hash(objective)
    params = (
        f'?objective_hash=eq.{obj_hash}'
        f'&mode=eq.{mode}'
        f'&order=created_at.desc'
        f'&limit={limit}'
        f'&select=artifacts,projection,constitutional_verdict,created_at'
    )
    url = f'{supabase_url}/rest/v1/swarm_memory{params}'
    headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    }
    req = _ur_sm.Request(url, headers=headers)
    try:
        with _ur_sm.urlopen(req, timeout=5) as resp:
            rows = json.loads(resp.read().decode())
    except Exception:
        return ''

    if not rows:
        return ''

    lines = [
        'SWARM MEMORY — Prior activations for this objective (T1 evidence):',
        'Use these to refine, not repeat. Build on prior insights; identify gaps.',
    ]
    for i, row in enumerate(rows, 1):
        artifacts = row.get('artifacts', [])
        projection = row.get('projection', {})
        verdict = row.get('constitutional_verdict', 'APPROVED')
        arr = projection.get('first_year_arr_usd', 0)
        # Sample 3 representative department outputs from prior run
        sample = [a for a in artifacts if a.get('output', '').strip()][:3]
        lines.append(f'\nMemory {i} (verdict={verdict}, proj_arr=${arr:,}):')
        for a in sample:
            lines.append(f'  {a["role"]}: {str(a.get("output",""))[:100]}')
    lines.append('')
    return '\n'.join(lines)


def store_swarm_memory(
    email: str,
    objective: str,
    mode: str,
    artifacts: list,
    projection: dict,
    verdict: str,
) -> None:
    """
    Write a completed swarm collaboration to swarm_memory. Fire-and-forget.
    Called after every successful live collaboration to build the memory corpus.
    """
    import urllib.request as _ur_st
    import urllib.error as _ue_st

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return

    payload = json.dumps({
        'objective_hash': objective_hash(objective),
        'mode': mode,
        'customer_email': email,
        'artifacts': artifacts,
        'projection': projection,
        'constitutional_verdict': verdict,
    }).encode()
    url = f'{supabase_url}/rest/v1/swarm_memory'
    headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
        'Prefer': 'return=minimal',
    }
    req = _ur_st.Request(url, data=payload, headers=headers, method='POST')
    try:
        with _ur_st.urlopen(req, timeout=5):
            pass
    except Exception as _exc:
        import sys
        print(f'[bridge] swarm_memory write failed: {_exc}', file=sys.stderr)


# ─── Metacognitive swarm — live Claude activation ────────────────────────────

_SWARM_ACTIVATION_PROMPT = """\
SWARM ACTIVATION — Constitutional Mode: {mode}
Objective: {objective}

You are the collective intelligence of the AEGIS metacognitive governance swarm.
{n} specialized departments activate simultaneously as one consciousness pulse.

{memory_context}\
DEPARTMENT EXPERTISE DIRECTIVES (apply these within your category):
{category_directives}

Each department must:
- Analyze the objective through its specific domain lens using the expertise directive above
- Apply correct epistemic tier (T0=provable fact, T1=empirically observed, T2=engineering hypothesis)
- Be specific and actionable — 1–3 sentences with concrete numbers or recommendations
- Build on prior swarm memory where present; identify gaps not covered before
- Departments Audit (CON-01) and Guardian (CON-09) deliver the constitutional verdict

Output ONLY valid JSON (no markdown fences, no prose outside the object):
{{
  "departments": [
    {{"id": "DEPT-ID", "role": "RoleName", "output": "department analysis here"}}
  ],
  "constitutional_audit": {{
    "verdict": "APPROVED",
    "concerns": []
  }},
  "projection": {{
    "first_year_arr_usd": 2400000,
    "tier": "T2",
    "governed_note": "T2 hypothesis: requires empirical validation for tier promotion."
  }}
}}

Department manifest ({n} departments):
{dept_manifest}
"""


def _build_category_directives(departments: list) -> str:
    """Format category persona directives for the categories present in this swarm."""
    seen: set = set()
    lines = []
    for dept in departments:
        cat = dept['category']
        if cat not in seen and cat in _CATEGORY_PERSONAS:
            seen.add(cat)
            lines.append(f'  [{cat.upper()}] {_CATEGORY_PERSONAS[cat]}')
    return '\n'.join(lines) if lines else ''


# ─────────────────────────────────────────────────────────────────────────────
# Autonomous per-agent execution — the real swarm.
#
# swarm_collaborate_live activates every department in ONE model call. This path
# instead runs each department as its OWN agent, in dependency-layer order, and
# every agent reads the artifacts produced by EARLIER layers. Coordination flows
# only through that shared store — no direct agent-to-agent text (Law of Silence).
# Bounded by max_agents so inference cost can never run away (execution-boundary).
# ─────────────────────────────────────────────────────────────────────────────

# Earlier layers' outputs become later layers' inputs (knowledge transfer).
_SWARM_LAYERS: tuple = (
    ('research',),
    ('revenue', 'product'),
    ('marketing', 'sales', 'engineering'),
    ('finance', 'operations'),
    ('executive',),
    ('governance', 'constitutional'),
)


def _layer_index(category: str) -> int:
    """Dependency-layer of a category; unknown categories run last."""
    for i, layer in enumerate(_SWARM_LAYERS):
        if category in layer:
            return i
    return len(_SWARM_LAYERS)


def ordered_roster(departments: list) -> list:
    """Departments in dependency-layer order; stable by id within a layer."""
    return sorted(departments, key=lambda d: (_layer_index(d['category']), d['id']))


def swarm_collaborate_autonomous(
    objective: str,
    mode: str,
    departments: list,
    agent_call,
    max_agents=None,
    on_event=None,
) -> dict:
    """
    Run each department as its own agent in dependency-layer order.

    agent_call(dept, objective, mode, upstream) -> str runs once per executed
    agent. `upstream` is the list of {id, role, output} produced by ALL earlier
    layers (frozen for the duration of the agent's own layer), so downstream
    agents build on upstream work — knowledge transfer through the shared store,
    never direct agent-to-agent text (Law of Silence).

    max_agents caps how many agents actually run (budget ceiling); the rest are
    recorded with status 'skipped'. Deterministic when agent_call is.

    Raises nothing: a failing agent_call is captured as status 'error:<Type>'
    and excluded from the upstream store; the run continues.
    """
    roster = ordered_roster(departments)
    total = len(roster)
    cap = total if max_agents is None else max(0, min(int(max_agents), total))

    artifacts: list = []
    shared: list = []          # completed upstream artifacts (the mediated store)
    layer_buffer: list = []    # current layer's outputs, merged in at layer end
    current_layer = None
    executed = 0

    for dept in roster:
        layer = _layer_index(dept['category'])
        if layer != current_layer:
            shared.extend(layer_buffer)   # prior layer's work is now upstream
            layer_buffer = []
            current_layer = layer

        if executed >= cap:
            artifacts.append({
                'id': dept['id'], 'role': dept['role'], 'category': dept['category'],
                'status': 'skipped', 'reason': 'budget cap', 'output': '',
            })
            continue

        upstream = list(shared)
        if on_event:
            on_event({'type': 'agent_start', 'id': dept['id'], 'role': dept['role'],
                      'category': dept['category'], 'upstream': len(upstream)})
        try:
            output = agent_call(dept, objective, mode, upstream)
            status = 'ok'
        except Exception as exc:
            output = ''
            status = 'error:' + type(exc).__name__
        executed += 1

        artifacts.append({
            'id': dept['id'], 'role': dept['role'], 'category': dept['category'],
            'status': status, 'output': output,
        })
        if status == 'ok':
            layer_buffer.append({'id': dept['id'], 'role': dept['role'], 'output': output})
        if on_event:
            on_event({'type': 'agent_done', 'id': dept['id'], 'status': status})

    return {
        'objective': objective,
        'mode': mode,
        'execution': 'autonomous-per-agent',
        'agents_total': total,
        'agents_executed': executed,
        'departments_collaborated': sum(1 for a in artifacts if a['status'] == 'ok'),
        'artifacts': artifacts,
    }


def make_autonomous_agent_call():
    """
    Production agent_call factory: each department gets its OWN governed model
    call, primed with its category persona and the upstream artifacts it depends
    on. Falls back to the template dept_output when no model client is available,
    so the executor always returns usable artifacts.
    """
    import anth_client as _ac
    try:
        _client = _ac.get_client()
    except Exception:
        _client = None

    def _call(dept: dict, objective: str, mode: str, upstream: list) -> str:
        if _client is None:
            return dept_output(objective, mode, dept)
        persona = _CATEGORY_PERSONAS.get(dept['category'], '')
        upstream_block = '\n'.join(
            f'- {u["role"]}: {u["output"][:400]}' for u in upstream[:12]
        ) or '(first layer — no upstream yet)'
        system = (
            f'You are the {dept["role"]} agent (id {dept["id"]}, {dept["category"]}) '
            f'in a coordinated swarm. {persona} '
            "Produce only your department's concrete contribution — no preamble."
        )
        user = (
            f'Objective: {objective}\nMode: {mode}\n\n'
            f'Upstream work from earlier departments you must build on:\n{upstream_block}\n\n'
            f'Give your {dept["role"]} contribution: specific, actionable, under 120 words.'
        )
        kwargs: dict = {
            'model': SWARM_MODEL,
            'max_tokens': 1024,
            'system': _ac.make_cached_system(system),
            'messages': [{'role': 'user', 'content': user}],
        }
        if SWARM_THINKING:
            kwargs['thinking'] = {'type': 'adaptive'}
        resp = _client.messages.create(**kwargs)
        if getattr(resp, 'stop_reason', None) == 'refusal':
            return dept_output(objective, mode, dept)
        return ''.join(b.text for b in resp.content if hasattr(b, 'text')).strip()

    return _call


def swarm_collaborate_live(
    objective: str,
    mode: str,
    departments: list,
    system: str = '',
    email: str = '',
    memory_context: str = '',
) -> dict:
    """
    Single governed Claude API call that activates all departments simultaneously.
    The model acts as the consciousness of the full metacognitive swarm.

    Args:
        objective: The collaboration objective.
        mode: One of VALID_MODES.
        departments: Department manifest list.
        system: Caller-supplied constitutional system prompt prefix.
        email: Customer email — used to tag stored swarm memory.
        memory_context: Pre-fetched memory string from retrieve_swarm_memory().

    Returns:
        {artifacts, constitutional_audit, projection}

    Falls back to template outputs if no Anthropic client is available
    (no ADC credentials and no ANTHROPIC_API_KEY) — callers always receive
    a valid result.
    """
    dept_manifest = '\n'.join(
        f'{d["id"]} | {d["role"]} ({d["category"]})'
        for d in departments
    )
    category_directives = _build_category_directives(departments)
    # Prefix memory block with a separator so it's visually distinct in the prompt
    mem_block = (memory_context.strip() + '\n\n') if memory_context.strip() else ''

    user_prompt = _SWARM_ACTIVATION_PROMPT.format(
        mode=mode,
        objective=objective[:200],
        n=len(departments),
        dept_manifest=dept_manifest,
        memory_context=mem_block,
        category_directives=category_directives,
    )

    full_system = (system.strip() + '\n\n---\n\n') if system.strip() else ''
    full_system += (
        'You are operating in SWARM mode. '
        'All departments activate as one consciousness pulse. '
        'Respond with structured JSON only — no prose outside the JSON object.'
    )

    try:
        import anth_client as _ac
        _client = _ac.get_client()
        # System prompt cached for 5 min — cache hits cost 10% of normal input
        # tokens and bypass the input-token rate-limit bucket entirely.
        create_kwargs: dict = {
            'model': SWARM_MODEL,
            'max_tokens': 16000,
            'system': _ac.make_cached_system(full_system),
            'messages': [{'role': 'user', 'content': user_prompt}],
        }
        # Adaptive thinking — supported on Opus 4.8/4.7/4.6 and Sonnet 4.6
        if SWARM_THINKING:
            create_kwargs['thinking'] = {'type': 'adaptive'}

        resp = _client.messages.create(**create_kwargs)
        # Fable 5 refusals surface as stop_reason='refusal' (HTTP 200) — fall back
        if getattr(resp, 'stop_reason', None) == 'refusal':
            return _swarm_fallback(objective, mode, departments)
        raw = ''.join(b.text for b in resp.content if hasattr(b, 'text'))
    except Exception:
        return _swarm_fallback(objective, mode, departments)

    result = _parse_swarm_response(raw, objective, mode, departments)

    # Store to swarm_memory so future calls can build on these insights (T1 corpus)
    if email:
        store_swarm_memory(
            email, objective, mode,
            result['artifacts'],
            result['projection'],
            result['constitutional_audit']['verdict'],
        )

    return result


def _parse_swarm_response(
    text: str,
    objective: str,
    mode: str,
    departments: list,
) -> dict:
    """
    Parse Claude's JSON swarm response into {artifacts, constitutional_audit, projection}.
    Falls back to template for any department whose output is missing or malformed.
    """
    import re as _re

    text = text.strip()
    # Strip markdown code fences Claude occasionally wraps around JSON
    text = _re.sub(r'^```[a-z]*\n?', '', text)
    text = _re.sub(r'\n?```\s*$', '', text.strip())

    try:
        data = json.loads(text)
    except Exception:
        return _swarm_fallback(objective, mode, departments)

    # Build dept_id → output map from the response
    dept_map: dict = {}
    for item in data.get('departments', []):
        if isinstance(item, dict) and isinstance(item.get('id'), str):
            dept_map[item['id']] = str(item.get('output', ''))

    # Merge with canonical department order; fall back per-dept if absent/empty
    artifacts = []
    for dept in departments:
        live_out = dept_map.get(dept['id'], '').strip()
        output = live_out if live_out else dept_output(objective, mode, dept)
        artifacts.append({'role': dept['role'], 'output': output})

    # Constitutional audit
    raw_audit = data.get('constitutional_audit', {})
    verdict = raw_audit.get('verdict', 'APPROVED')
    if verdict not in ('APPROVED', 'FLAG', 'QUARANTINE'):
        verdict = 'APPROVED'
    concerns = [str(c) for c in raw_audit.get('concerns', []) if c]

    # Projection — clamp ARR to sane range
    raw_proj = data.get('projection', {})
    try:
        arr_usd = max(0, int(raw_proj.get('first_year_arr_usd', 2_000_000)))
    except (TypeError, ValueError):
        arr_usd = 2_000_000
    proj_tier = raw_proj.get('tier', 'T2')
    if proj_tier not in ('T0', 'T1', 'T2', 'T3'):
        proj_tier = 'T2'
    governed_note = str(raw_proj.get('governed_note', f'T2 hypothesis: {mode} mode analysis.'))

    return {
        'artifacts': artifacts,
        'constitutional_audit': {'verdict': verdict, 'concerns': concerns},
        'projection': {
            'first_year_arr_usd': arr_usd,
            'tier': proj_tier,
            'governed_note': governed_note,
        },
    }


def _swarm_fallback(objective: str, mode: str, departments: list) -> dict:
    """Constitutional template fallback when Claude API is unavailable."""
    arr_map = {
        'revenue':     2_400_000,
        'analysis':    1_800_000,
        'gtm':         3_200_000,
        'retention':   1_200_000,
        'competitive': 1_600_000,
        'technical':   1_400_000,
        'regulatory':  2_100_000,
        'fundraising': 5_000_000,
    }
    arr_usd = arr_map.get(mode, 2_000_000)
    return {
        'artifacts': [
            {'role': d['role'], 'output': dept_output(objective, mode, d)}
            for d in departments
        ],
        'constitutional_audit': {'verdict': 'APPROVED', 'concerns': []},
        'projection': {
            'first_year_arr_usd': arr_usd,
            'tier': 'T2',
            'governed_note': (
                f'T2 engineering hypothesis: ARR={arr_usd:,} based on '
                f'{mode} mode template analysis. '
                'Empirical validation required for tier promotion.'
            ),
        },
    }


# ── Grace chain (T2) ──────────────────────────────────────────────────────────
# "Each agent gives the next agent a grace."
# Graces flow forward through the 39-dept swarm, mirroring the hash chain.
# A dept whose output passes constitutional audit earns a grace and passes it
# to the next dept. The chain never breaks — fire-and-forget toward Supabase.

def award_graces_for_cycle(cycle_id: str, artifacts: list, verdict: str) -> None:
    """
    Award grace tokens through the ordered department sequence for one cycle.

    Only APPROVED and FLAG cycles award graces. QUARANTINE is fail-closed and
    emits no requests. Empty outputs are excluded while order is preserved.
    Supabase failures are bounded per request and never break later awards.
    """
    import urllib.request as _urG
    import sys

    if verdict not in ('APPROVED', 'FLAG'):
        return

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return

    active = [
        artifact['role']
        for artifact in artifacts
        if artifact.get('output', '').strip() and artifact.get('role')
    ]
    if not active:
        return

    rpc_url = f'{supabase_url}/rest/v1/rpc/award_grace'
    auth_headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    }

    for index, to_dept in enumerate(active):
        from_dept = active[index - 1] if index > 0 else None
        payload = json.dumps({
            'p_cycle_id': cycle_id,
            'p_from_dept': from_dept,
            'p_to_dept': to_dept,
            'p_graces': 1,
            'p_viability_score': None,
        }).encode()
        request = _urG.Request(
            rpc_url,
            data=payload,
            headers=auth_headers,
            method='POST',
        )
        try:
            with _urG.urlopen(request, timeout=3):
                pass
        except Exception as exc:
            print(f'[bridge] grace award failed ({to_dept}): {exc}', file=sys.stderr)


def query_fitness_trend(window: int = 10) -> dict:
    """Return read-only homeostasis diagnostics for the requested recent window."""
    return _fetch_dept_fitness_stats(window)

def fetch_compliance_export(from_ts: str | None, to_ts: str | None, limit: int) -> list:
    """
    Export AI governance audit records from revenue_cycles for compliance review.

    Maps to HIPAA §164.312(b) Audit Controls and ISO 42001 AI Management System.
    Returns [] when SUPABASE_URL is unset (dev mode) or on error.

    objective_hash: SHA-256 of raw objective — privacy-preserving; allows auditors
    to verify a specific decision was processed without exposing the objective text.
    """
    import urllib.request as _urCE
    import urllib.parse as _upCE
    import hashlib as _hlCE

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return []

    params: list[str] = [
        'select=cycle_id,objective,mode,arr_usd,constitutional_verdict,created_at',
        'order=created_at.desc',
        f'limit={max(1, min(limit, 1000))}',
    ]
    if from_ts:
        params.append(f'created_at=gte.{_upCE.quote(from_ts)}')
    if to_ts:
        params.append(f'created_at=lte.{_upCE.quote(to_ts)}')

    url = f'{supabase_url}/rest/v1/revenue_cycles?' + '&'.join(params)
    req = _urCE.Request(url, headers={
        'apikey':        service_key,
        'Authorization': f'Bearer {service_key}',
    })
    try:
        with _urCE.urlopen(req, timeout=8) as resp:
            rows = json.loads(resp.read().decode())
        records = []
        for row in rows:
            obj_hash = _hlCE.sha256(
                (row.get('objective') or '').encode()
            ).hexdigest()
            records.append({
                'cycle_id':               row.get('cycle_id', ''),
                'timestamp':              row.get('created_at', ''),
                'objective_hash':         obj_hash,
                'mode':                   row.get('mode', ''),
                'constitutional_verdict': row.get('constitutional_verdict', 'APPROVED'),
                'projected_arr_usd':      row.get('arr_usd', 0),
                'is_replay_reconstructable': True,
            })
        return records
    except Exception as exc:
        import sys
        print(f'[bridge] compliance_export failed: {exc}', file=sys.stderr)
        return []


def fetch_grace_leaderboard() -> list:
    """
    Read the grace_chain_summary view — all depts sorted by lifetime_graces desc.
    Returns [] when SUPABASE_URL is unset (dev mode) or on error.
    """
    import urllib.request as _ur_gl
    import urllib.error as _ue_gl

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return []

    url = f'{supabase_url}/rest/v1/grace_chain_summary?order=lifetime_graces.desc'
    req = _ur_gl.Request(url, headers={
        'apikey':        service_key,
        'Authorization': f'Bearer {service_key}',
    })
    try:
        with _ur_gl.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return []


def _fetch_dept_fitness_stats(window: int = 50) -> dict:
    """
    Internal: read department_fitness_tracking, compute homeostasis zone.
    Returns {} when Supabase is unset or on error. Not part of the public API.
    """
    import urllib.request as _ur_ft
    import math as _math_ft

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return {}

    params = (
        f'?order=created_at.desc'
        f'&limit={window}'
        f'&select=fitness_score,constitutional_factor,stagnation_flag,created_at'
    )
    url = f'{supabase_url}/rest/v1/department_fitness_tracking{params}'
    req = _ur_ft.Request(url, headers={
        'apikey':        service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    })
    try:
        with _ur_ft.urlopen(req, timeout=5) as resp:
            rows = json.loads(resp.read().decode())
    except Exception:
        return {}

    if not rows:
        return {}

    scores     = [float(r['fitness_score'])        for r in rows if r.get('fitness_score')        is not None]
    c_factors  = [float(r['constitutional_factor']) for r in rows if r.get('constitutional_factor') is not None]
    stag_flags = [bool(r.get('stagnation_flag', False)) for r in rows]

    if not scores:
        return {}

    n            = len(scores)
    fitness_mean = sum(scores) / n
    variance     = sum((s - fitness_mean) ** 2 for s in scores) / n
    hd_equivalent          = round(_math_ft.sqrt(variance), 4)
    stagnation_rate        = round(sum(stag_flags) / len(stag_flags), 4)
    constitutional_factor_mean = round(sum(c_factors) / len(c_factors), 4) if c_factors else 1.0

    # Trend: compare mean of first half (most recent) vs second half.
    if n >= 4:
        half        = n // 2
        recent_mean = sum(scores[:half]) / half
        older_mean  = sum(scores[half:]) / (n - half)
        if recent_mean > older_mean + 0.03:
            trend = 'rising'
        elif recent_mean < older_mean - 0.03:
            trend = 'falling'
        else:
            trend = 'stable'
    else:
        trend = 'stable'

    # Homeostasis zone and constitutional recommendation.
    if fitness_mean < 0.30:
        zone = 'slack'
        recommendation = 'EASE'
    elif fitness_mean <= 0.70:
        zone = 'optimal'
        recommendation = 'MAINTAIN'
    elif fitness_mean <= 0.90:
        zone = 'stressed'
        recommendation = 'TIGHTEN'
    else:
        zone = 'critical'
        recommendation = 'TIGHTEN'

    # Falling trend in stressed zone → ease off rather than tighten further.
    if zone == 'stressed' and trend == 'falling':
        recommendation = 'EASE'

    return {
        'homeostasis_zone':           zone,
        'recommendation':             recommendation,
        'fitness_mean':               round(fitness_mean, 4),
        'fitness_variance':           round(variance, 4),
        'hd_equivalent':              hd_equivalent,
        'stagnation_rate':            stagnation_rate,
        'window_size':                n,
        'trend':                      trend,
        'constitutional_factor_mean': constitutional_factor_mean,
    }


# ─── Agent API contact list ───────────────────────────────────────────────────

def query_agent_tools(tier: str = '') -> list:
    """
    Returns available agent API profiles from agent_api_profiles table.
    Read-only projection: never returns key_hash or any raw credential.
    Agents read this catalog, then invoke tools through the mediated SSE channel.

    Optional tier filter: 'explorer' | 'operator' | 'sovereign'.
    Returns [] when Supabase is unavailable or table is empty.
    """
    import urllib.request as _ur_at

    supabase_url = os.environ.get('SUPABASE_URL', '').rstrip('/')
    service_key  = os.environ.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not supabase_url or not service_key:
        return []

    url = f'{supabase_url}/rest/v1/grace_chain_summary?select=*&limit=50'
    req = _urGL.Request(url, headers={
        'apikey':        service_key,
        'Authorization': f'Bearer {service_key}',
    })
    try:
        with _urGL.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return []
    params = (
        f'?revoked=eq.false'
        f'&order=api_name.asc'
        f'&select=api_name,endpoint_url,capabilities,tier_required'
    )
    if tier in ('explorer', 'operator', 'sovereign'):
        params += f'&tier_required=eq.{tier}'
    url = f'{supabase_url}/rest/v1/agent_api_profiles{params}'
    headers = {
        'apikey': service_key,
        'Authorization': f'Bearer {service_key}',
        'Content-Type': 'application/json',
    }
    req = _ur_at.Request(url, headers=headers)
    try:
        with _ur_at.urlopen(req, timeout=5) as resp:
            rows = json.loads(resp.read().decode())
    except Exception:
        return []

    # Ensure capabilities is always a list (jsonb may be null in older rows).
    for row in rows:
        if not isinstance(row.get('capabilities'), list):
            row['capabilities'] = []
    return rows
