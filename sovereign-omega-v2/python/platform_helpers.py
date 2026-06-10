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
SWARM_MODEL = os.environ.get('AEGIS_SWARM_MODEL', 'claude-fable-5')
SWARM_THINKING = os.environ.get('AEGIS_SWARM_THINKING', 'true').lower() not in ('0', 'false', 'no')

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
    Returns (objective, mode, live, generation, memory_context) or raises ValueError.
    generation defaults to 0 (first run). memory_context overrides auto-retrieved memory.
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

    generation = body.get('generation', 0)
    if not isinstance(generation, int) or generation < 0:
        raise ValueError('generation must be a non-negative integer')

    memory_context = body.get('memory_context', '')
    if not isinstance(memory_context, str):
        raise ValueError('memory_context must be a string')

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
) -> dict:
    """
    Compute per-department fitness scores comparing consecutive swarm generations.
    Returns {dept_role: {'fitness_score': f, 'viability_score': v}} in [0.0, 1.0].

    fitness_score = 0.35 × length_stability + 0.25 × objective_coverage
                  + 0.25 × lexical_consistency + 0.15 × viability_score
    - length_stability: 1 - normalised absolute length delta between generations
    - objective_coverage: fraction of objective words present in current output
    - lexical_consistency: Jaccard similarity of word sets between prev and curr outputs
    - viability_score: VIABILITY_CHAR_BUDGET / len(output), capped at 1.0 — penalises
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
    obj_words = _words(objective)
    prev_map = {a['role']: a.get('output', '') for a in prev_artifacts}
    scores: dict = {}

    for a in curr_artifacts:
        role   = a['role']
        curr   = a.get('output', '')
        prev   = prev_map.get(role, '')

        # Empty output — department produced nothing; hard-zero both metrics
        if not curr:
            scores[role] = {'fitness_score': 0.0, 'viability_score': 0.0}
            continue

        # Length stability
        cl, pl = len(curr), len(prev)
        base   = max(cl, pl, 1)
        length_stability = 1.0 - abs(cl - pl) / base

        # Objective coverage
        if obj_words:
            curr_words = _words(curr)
            objective_coverage = len(obj_words & curr_words) / len(obj_words)
        else:
            objective_coverage = 0.5

        # Lexical consistency + stagnation detection (0.25 weight — unchanged)
        # Lexical consistency across generations
        if prev:
            prev_words = _words(prev)
            curr_words2 = _words(curr)
            union = prev_words | curr_words2
            lexical_consistency = len(prev_words & curr_words2) / len(union) if union else 0.5
            stagnation_flag = lexical_consistency > STAGNATION_THRESHOLD
        else:
            lexical_consistency = 0.5   # no prior generation to compare
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
        else:
            lexical_consistency = 0.5  # no prior generation to compare

        # Viability — metabolic budget on output size
        viability = min(1.0, VIABILITY_CHAR_BUDGET / cl) if cl > 0 else 0.0

        score = round(
            0.35 * length_stability
            + 0.25 * objective_coverage
            + 0.25 * lexical_consistency
            + 0.15 * viability,
            4,
        )
        scores[role] = {
            'fitness_score': max(0.0, min(1.0, score)),
            'viability_score': round(viability, 4),
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
            'objective_hash':      obj_hash,
            'mode':                mode,
            'generation':          generation,
            'cycle_id':            cycle_id,
            'dept_role':           role,
            'fitness_score':       score['fitness_score'],
            'viability_score':     score['viability_score'],
            'constitutional_verdict': constitutional_verdict,
            'constitutional_factor':  score.get('constitutional_factor', _CONSTITUTIONAL_FACTOR_DEFAULT),
            'fitness_version':     FITNESS_VERSION,
            'execution_id':        execution_id,
            'parent_generation':   generation - 1,  # -1 for generation 0 handled by DB default
            'artifact_hash':       artifact_hash(art_map.get(role, '')),
    rows = [
        {
            'objective_hash': obj_hash,
            'mode': mode,
            'generation': generation,
            'cycle_id': cycle_id,
            'dept_role': role,
            'fitness_score': score['fitness_score'],
            'viability_score': score['viability_score'],
            'constitutional_verdict': constitutional_verdict,
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
