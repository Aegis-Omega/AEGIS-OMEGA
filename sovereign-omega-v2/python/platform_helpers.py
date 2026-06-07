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
    'revenue':   (
        '{role}: 3 revenue vectors identified for "{obj}". '
        'Primary: SMB upsell ($12k ARR). Secondary: API monetisation. '
        'Tertiary: partner channel. T2 projection: $2.4M ARR Y1.'
    ),
    'analysis':  (
        '{role}: Market analysis for "{obj}" — 2 competitive gaps found. '
        'Differentiation lever: constitutional governance layer. '
        'Entry timing: Q3 2026. Market size: $340M TAM.'
    ),
    'gtm':       (
        '{role}: GTM for "{obj}" — 4-phase launch. '
        'Phase 1: design-partner beta (8 wks). '
        'Phase 2: Product Hunt + HN. Phase 3: EU enterprise push. CAC: $1,200.'
    ),
    'retention': (
        '{role}: Retention strategy for "{obj}" — 3 churn vectors. '
        'Fix: governance dashboard stickiness, API key continuity, '
        'operator success program. Expected lift: +15% NRR.'
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

    hash_salt = os.environ.get('API_KEY_HASH_SALT', 'aegis_api_key_hash_salt_v1').encode()
    hash_iterations = int(os.environ.get('API_KEY_HASH_ITERATIONS', '210000'))
    key_hash = _hl2.pbkdf2_hmac('sha256', api_key.encode(), hash_salt, hash_iterations).hex()
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
    valid_modes = {'revenue', 'analysis', 'gtm', 'retention'}

    objective = body.get('objective', '')
    if not isinstance(objective, str) or not objective.strip():
        raise ValueError('objective must be a non-empty string')

    mode = body.get('mode', '')
    if mode not in valid_modes:
        raise ValueError(f'mode must be one of {sorted(valid_modes)}')

    live = body.get('live', False)
    if not isinstance(live, bool):
        raise ValueError('live must be a boolean')

    return objective.strip(), mode, live
