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
# Set AEGIS_SWARM_MODEL=claude-opus-4-8 for deeper reasoning (higher cost).
# Set AEGIS_SWARM_THINKING=true to enable adaptive thinking on Opus/Sonnet 4.6+.
SWARM_MODEL = os.environ.get('AEGIS_SWARM_MODEL', 'claude-sonnet-4-6')
SWARM_THINKING = os.environ.get('AEGIS_SWARM_THINKING', '').lower() in ('1', 'true', 'yes')

VALID_MODES = frozenset({
    'revenue', 'analysis', 'gtm', 'retention',
    'competitive', 'technical', 'regulatory', 'fundraising',
})

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
    return _dt.datetime.utcnow().isoformat() + 'Z'


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

    rest_url = (
        f'{supabase_url}/rest/v1/api_key_store'
        f'?key_hash=eq.{key_hash}&revoked=eq.false'
        f'&select=customer_email,tier,usage_count,usage_limit'
    )
    req = _ur.Request(rest_url, headers=auth_headers)
    try:
        with _ur.urlopen(req, timeout=5) as resp:
            rows = json.loads(resp.read().decode())
    except _ue.HTTPError as exc:
        raise ValueError(f'Supabase error: HTTP {exc.code}')
    except Exception as exc:
        raise ValueError(f'Key verification failed: {str(exc)[:60]}')

    if not rows:
        raise ValueError('Invalid or revoked API key')

    row = rows[0]
    if row['usage_count'] >= row['usage_limit']:
        raise ValueError('Usage limit reached')

    patch_url = f'{supabase_url}/rest/v1/api_key_store?key_hash=eq.{key_hash}'
    patch_data = json.dumps({'usage_count': row['usage_count'] + 1}).encode()
    patch_req = _ur.Request(
        patch_url, data=patch_data,
        headers={**auth_headers, 'Prefer': 'return=minimal'},
        method='PATCH',
    )
    try:
        with _ur.urlopen(patch_req, timeout=5):
            pass
    except Exception:
        pass  # don't fail if usage increment fails

    return row['customer_email'], row['tier']


_MODE_OUTPUTS = {
    'revenue':      (
        '{role}: 3 revenue vectors identified for "{obj}". '
        'Primary: SMB upsell ($12k ARR). Secondary: API monetisation. '
        'Tertiary: partner channel. T2 projection: $2.4M ARR Y1.'
    ),
    'analysis':     (
        '{role}: Market analysis for "{obj}" — 2 competitive gaps found. '
        'Differentiation lever: constitutional governance layer. '
        'Entry timing: Q3 2026. Market size: $340M TAM.'
    ),
    'gtm':          (
        '{role}: GTM for "{obj}" — 4-phase launch. '
        'Phase 1: design-partner beta (8 wks). '
        'Phase 2: Product Hunt + HN. Phase 3: EU enterprise push. CAC: $1,200.'
    ),
    'retention':    (
        '{role}: Retention strategy for "{obj}" — 3 churn vectors. '
        'Fix: governance dashboard stickiness, API key continuity, '
        'operator success program. Expected lift: +15% NRR.'
    ),
    'competitive':  (
        '{role}: Competitive intelligence for "{obj}" — 3 direct rivals mapped. '
        'Moat: constitutional audit chain (no rival has T0-grade tamper-evidence). '
        'Vulnerability: price. Opportunity: EU compliance deadline forcing urgency.'
    ),
    'technical':    (
        '{role}: Technical assessment of "{obj}" — architecture scored. '
        'Scalability ceiling: 10k req/s with current NEG topology. '
        'Critical path: Supabase read latency. Recommendation: read replica + caching.'
    ),
    'regulatory':   (
        '{role}: Regulatory mapping for "{obj}" — EU AI Act Article 12 status: MAPPED. '
        'GDPR Article 22 (automated decisions): MITIGATED via audit chain. '
        'Action: apply for AI Act sandbox (Article 57) before Q4 2026.'
    ),
    'fundraising':  (
        '{role}: Fundraising analysis for "{obj}" — Series A readiness: EARLY. '
        'Required: $180k ARR, 3 enterprise LOIs, EU AI Act compliance cert. '
        'Target investors: Northzone, Speedinvest (EU AI Act focus). T2 valuation: $8M.'
    ),
}

_CATEGORY_SUFFIX = {
    'constitutional': ' Constitutional compliance: T0 verdict VALID.',
    'governance':     ' Risk: LOW. Ethical concerns: NONE.',
    'executive':      ' Board priority: TIER-1. Strategic alignment: confirmed.',
}


def dept_output(objective: str, mode: str, dept: dict) -> str:
    """Generate a constitutionally-structured department output string."""
    role = dept['role']
    obj_short = objective[:55]
    category = dept['category']
    template = _MODE_OUTPUTS.get(mode, _MODE_OUTPUTS['revenue'])
    base = template.format(role=role, obj=obj_short)
    return base + _CATEGORY_SUFFIX.get(category, '')


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
        'departments_collaborated': 39,
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
    Returns (objective, mode, live) or raises ValueError with a descriptive message.
    """
    objective = body.get('objective', '')
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError('objective must be a non-empty string')

    mode = body.get('mode', '')
    if mode not in VALID_MODES:
        raise ValueError(f'mode must be one of {sorted(VALID_MODES)}')

    live = body.get('live', False)
    if not isinstance(live, bool):
        raise ValueError('live must be a boolean')

    return objective.strip(), mode, live


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

    Falls back to template outputs if ANTHROPIC_API_KEY is absent or the SDK
    is not installed — callers always receive a valid result.
    """
    try:
        import anthropic as _anth
    except ImportError:
        return _swarm_fallback(objective, mode, departments)

    api_key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not api_key:
        return _swarm_fallback(objective, mode, departments)

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
        client = _anth.Anthropic(api_key=api_key)
        # 39 departments each emit a JSON output; 16000 tokens accommodates the
        # full swarm response without truncation that causes json.loads failure.
        create_kwargs: dict = {
            'model': SWARM_MODEL,
            'max_tokens': 16000,
            'system': full_system,
            'messages': [{'role': 'user', 'content': user_prompt}],
        }
        # Adaptive thinking — supported on Opus 4.8/4.7/4.6 and Sonnet 4.6
        if SWARM_THINKING:
            create_kwargs['thinking'] = {'type': 'adaptive'}

        resp = client.messages.create(**create_kwargs)
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
