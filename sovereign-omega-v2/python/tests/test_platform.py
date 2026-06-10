"""
AEGIS-Ω — /platform/* API contract tests
EPISTEMIC TIER: T1

Tests for platform_helpers.py — pure functions that can run in CI without
allocating the 4 GB CoreMatrix bytearray. Covers:
  - Contract version constant
  - Department roster (39 depts, all required fields)
  - platform_envelope() shape
  - verify_api_key() dev bypass + rejection logic
  - dept_output() per-mode and per-category generation
  - make_sse_event() shape
  - validate_collaboration_request() — valid and invalid inputs
  - TypeScript contract agreement (compare PLATFORM_DEPARTMENTS to known shape)

Run: python tests/test_platform.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from platform_helpers import (
    PLATFORM_CONTRACT_VERSION,
    PLATFORM_DEPARTMENTS,
    VIABILITY_CHAR_BUDGET,
    platform_ts,
    platform_envelope,
    verify_api_key,
    query_api_key_info,
    record_revenue_cycle,
    dept_output,
    make_sse_event,
    validate_collaboration_request,
    evaluate_generation_fitness,
)

PASS = 0
FAIL = 0


def ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f'  PASS  {name}')


def fail(name: str, reason: str = '') -> None:
    global FAIL
    FAIL += 1
    print(f'  FAIL  {name}: {reason}')


def test(name: str, condition: bool, reason: str = '') -> None:
    if condition:
        ok(name)
    else:
        fail(name, reason or 'assertion failed')


def expect_raises(name: str, exc_type: type, fn) -> None:
    try:
        fn()
        fail(name, f'expected {exc_type.__name__} but no exception raised')
    except exc_type:
        ok(name)
    except Exception as e:
        fail(name, f'expected {exc_type.__name__} but got {type(e).__name__}: {e}')


# ── Contract version ──────────────────────────────────────────────────────────

def test_contract_version():
    print('\ncontract version:')
    test('version is 1.0.0', PLATFORM_CONTRACT_VERSION == '1.0.0')
    parts = PLATFORM_CONTRACT_VERSION.split('.')
    test('version is semver (3 parts)', len(parts) == 3)
    test('all parts are numeric', all(p.isdigit() for p in parts))


# ── Department roster ─────────────────────────────────────────────────────────

_KNOWN_CATEGORIES = {'revenue', 'marketing', 'sales', 'product', 'engineering',
                     'operations', 'research', 'finance', 'executive',
                     'governance', 'constitutional'}

def test_departments():
    print('\ndepartment roster:')
    test('exactly 39 departments', len(PLATFORM_DEPARTMENTS) == 39)

    ids = [d['id'] for d in PLATFORM_DEPARTMENTS]
    test('all IDs are unique', len(ids) == len(set(ids)))
    test('first dept is REV-01', PLATFORM_DEPARTMENTS[0]['id'] == 'REV-01')
    test('last dept is CON-09 Guardian', PLATFORM_DEPARTMENTS[-1]['id'] == 'CON-09')

    for d in PLATFORM_DEPARTMENTS:
        for field in ('id', 'role', 'category'):
            test(f'{d["id"]} has {field}', field in d and d[field])
        test(f'{d["id"]} category is known', d['category'] in _KNOWN_CATEGORIES,
             f'unknown category: {d.get("category")}')

    # Category counts match TypeScript contract
    cats = {}
    for d in PLATFORM_DEPARTMENTS:
        cats[d['category']] = cats.get(d['category'], 0) + 1
    test('3 revenue depts', cats.get('revenue') == 3)
    test('5 marketing depts', cats.get('marketing') == 5)
    test('4 sales depts', cats.get('sales') == 4)
    test('4 product depts', cats.get('product') == 4)
    test('5 engineering depts', cats.get('engineering') == 5)
    test('4 operations depts', cats.get('operations') == 4)
    test('3 research depts', cats.get('research') == 3)
    test('3 finance depts', cats.get('finance') == 3)
    test('4 executive depts', cats.get('executive') == 4)
    test('2 governance depts', cats.get('governance') == 2)
    test('2 constitutional depts', cats.get('constitutional') == 2)


# ── platform_ts() ────────────────────────────────────────────────────────────

def test_platform_ts():
    print('\nplatform_ts():')
    ts = platform_ts()
    test('returns a string', isinstance(ts, str))
    test('ends with Z (UTC)', ts.endswith('Z'))
    test('contains T (ISO-8601)', 'T' in ts)
    test('length is reasonable', 20 <= len(ts) <= 32)


# ── platform_envelope() ───────────────────────────────────────────────────────

def test_platform_envelope():
    print('\nplatform_envelope():')
    eid = 'test-exec-001'
    data = {'foo': 'bar', 'n': 42}
    env = platform_envelope(eid, data)

    test('contract_version matches', env['contract_version'] == PLATFORM_CONTRACT_VERSION)
    test('execution_id matches', env['execution_id'] == eid)
    test('data is passed through', env['data'] == data)
    test('is_replay_reconstructable is True', env['is_replay_reconstructable'] is True)
    test('timestamp present', 'timestamp' in env and env['timestamp'])
    test('has exactly 5 keys', set(env.keys()) == {
        'contract_version', 'execution_id', 'timestamp',
        'is_replay_reconstructable', 'data'
    })


# ── verify_api_key() ──────────────────────────────────────────────────────────

def test_verify_api_key():
    print('\nverify_api_key() (dev bypass — no SUPABASE_URL):')

    # Ensure Supabase env vars are unset for dev-bypass path
    old_url = os.environ.pop('SUPABASE_URL', None)
    old_key = os.environ.pop('SUPABASE_SERVICE_ROLE_KEY', None)
    try:
        # Valid dev key
        email, tier = verify_api_key('aegis_explorer_test')
        test('dev key returns dev@local', email == 'dev@local')
        test('dev key returns explorer tier', tier == 'explorer')

        email2, tier2 = verify_api_key('aegis_anything_goes')
        test('any aegis_* key passes dev bypass', email2 == 'dev@local')

        # Empty key
        expect_raises('empty key raises ValueError', ValueError,
                      lambda: verify_api_key(''))

        # Non-aegis key without Supabase
        expect_raises('non-aegis key raises ValueError (no Supabase)', ValueError,
                      lambda: verify_api_key('sk_live_wrong_key'))

    finally:
        if old_url is not None:
            os.environ['SUPABASE_URL'] = old_url
        if old_key is not None:
            os.environ['SUPABASE_SERVICE_ROLE_KEY'] = old_key


# ── dept_output() ─────────────────────────────────────────────────────────────

def test_dept_output():
    print('\ndept_output():')
    objective = 'Launch AEGIS-Ω to enterprise market'

    for mode in ('revenue', 'analysis', 'gtm', 'retention'):
        dept = PLATFORM_DEPARTMENTS[0]  # REV-01 Strategy
        out = dept_output(objective, mode, dept)
        test(f'mode={mode} returns non-empty string', isinstance(out, str) and len(out) > 20)
        test(f'mode={mode} contains role name', dept['role'] in out)

    # Constitutional dept gets suffix
    con_dept = next(d for d in PLATFORM_DEPARTMENTS if d['category'] == 'constitutional')
    out_con = dept_output(objective, 'revenue', con_dept)
    test('constitutional dept suffix present', 'T0 verdict VALID' in out_con)

    # Governance dept gets suffix
    gov_dept = next(d for d in PLATFORM_DEPARTMENTS if d['category'] == 'governance')
    out_gov = dept_output(objective, 'revenue', gov_dept)
    test('governance dept suffix present', 'Risk: LOW' in out_gov)

    # Executive dept gets suffix
    exe_dept = next(d for d in PLATFORM_DEPARTMENTS if d['category'] == 'executive')
    out_exe = dept_output(objective, 'revenue', exe_dept)
    test('executive dept suffix present', 'Board priority' in out_exe)

    # Unknown mode falls back to revenue template
    out_fallback = dept_output(objective, 'unknown_mode', PLATFORM_DEPARTMENTS[0])
    test('unknown mode falls back gracefully', len(out_fallback) > 20)

    # Objective is truncated at 55 chars
    long_obj = 'A' * 100
    out_trunc = dept_output(long_obj, 'revenue', PLATFORM_DEPARTMENTS[0])
    test('objective truncated to 55 chars', 'A' * 56 not in out_trunc)


# ── make_sse_event() ──────────────────────────────────────────────────────────

def test_make_sse_event():
    print('\nmake_sse_event():')
    eid = 'sse-test-001'

    for event_type in ('dag_step', 'agent_event', 'tool_call', 'error', 'completion', 'heartbeat'):
        payload = {'seq': 0}
        evt = make_sse_event(event_type, eid, payload)
        test(f'{event_type} type correct', evt['type'] == event_type)
        test(f'{event_type} execution_id correct', evt['execution_id'] == eid)
        test(f'{event_type} timestamp present', evt['timestamp'].endswith('Z'))
        test(f'{event_type} payload passed', evt['payload'] == payload)
        test(f'{event_type} has exactly 4 keys',
             set(evt.keys()) == {'type', 'execution_id', 'timestamp', 'payload'})


# ── validate_collaboration_request() ─────────────────────────────────────────

def test_validate_collaboration_request():
    print('\nvalidate_collaboration_request():')

    # Valid requests — returns (objective, mode, live, generation, memory_context)
    obj, mode, live, gen, mem = validate_collaboration_request({
        'objective': 'Test', 'mode': 'revenue', 'live': False
    })
    test('valid: objective returned', obj == 'Test')
    test('valid: mode returned', mode == 'revenue')
    test('valid: live returned', live is False)
    test('valid: generation defaults to 0', gen == 0)
    test('valid: memory_context defaults to empty string', mem == '')

    for m in ('revenue', 'analysis', 'gtm', 'retention'):
        _o, m2, _l, _g, _mc = validate_collaboration_request(
            {'objective': 'x', 'mode': m, 'live': True}
        )
        test(f'valid mode {m}', m2 == m)

    # Objective whitespace stripping
    o3, _, _, _, _ = validate_collaboration_request(
        {'objective': '  hello  ', 'mode': 'revenue', 'live': False}
    )
    test('objective stripped', o3 == 'hello')

    # generation + memory_context passthrough
    _o, _m, _l, g2, mc2 = validate_collaboration_request({
        'objective': 'x', 'mode': 'analysis', 'live': False,
        'generation': 3, 'memory_context': 'prior_ctx',
    })
    test('generation passthrough', g2 == 3)
    test('memory_context passthrough', mc2 == 'prior_ctx')

    # Invalid inputs
    expect_raises('missing objective raises ValueError', ValueError,
                  lambda: validate_collaboration_request({'mode': 'revenue', 'live': False}))
    expect_raises('empty objective raises ValueError', ValueError,
                  lambda: validate_collaboration_request({'objective': '', 'mode': 'revenue', 'live': False}))
    expect_raises('whitespace-only objective raises ValueError', ValueError,
                  lambda: validate_collaboration_request({'objective': '   ', 'mode': 'revenue', 'live': False}))
    expect_raises('invalid mode raises ValueError', ValueError,
                  lambda: validate_collaboration_request({'objective': 'x', 'mode': 'bogus', 'live': False}))
    expect_raises('non-bool live raises ValueError', ValueError,
                  lambda: validate_collaboration_request({'objective': 'x', 'mode': 'revenue', 'live': 'yes'}))
    expect_raises('missing mode raises ValueError', ValueError,
                  lambda: validate_collaboration_request({'objective': 'x', 'live': False}))
    expect_raises('negative generation raises ValueError', ValueError,
                  lambda: validate_collaboration_request({'objective': 'x', 'mode': 'revenue', 'live': False, 'generation': -1}))


def test_query_api_key_info() -> None:
    print('\n--- query_api_key_info ---')

    # Dev bypass: aegis_* key returns explorer defaults when Supabase absent
    orig_url = os.environ.pop('SUPABASE_URL', None)
    orig_key = os.environ.pop('SUPABASE_SERVICE_ROLE_KEY', None)
    try:
        info = query_api_key_info('aegis_testkey')
        test('dev bypass returns dict', isinstance(info, dict))
        test('dev bypass email', info is not None and info.get('customer_email') == 'dev@local')
        test('dev bypass tier', info is not None and info.get('tier') == 'explorer')
        test('dev bypass usage_count', info is not None and info.get('usage_count') == 0)
        test('dev bypass usage_limit', info is not None and info.get('usage_limit') == 10)

        # Non-aegis_ key returns None in dev mode
        info2 = query_api_key_info('sk-bad-key')
        test('non-aegis key returns None in dev mode', info2 is None)

        # Empty key returns None
        info3 = query_api_key_info('')
        test('empty key returns None', info3 is None)
    finally:
        if orig_url is not None:
            os.environ['SUPABASE_URL'] = orig_url
        if orig_key is not None:
            os.environ['SUPABASE_SERVICE_ROLE_KEY'] = orig_key


def test_record_revenue_cycle() -> None:
    print('\n--- record_revenue_cycle ---')

    # Without Supabase configured, should silently return (no raise)
    orig_url = os.environ.pop('SUPABASE_URL', None)
    orig_key = os.environ.pop('SUPABASE_SERVICE_ROLE_KEY', None)
    try:
        try:
            record_revenue_cycle(
                cycle_id='test-cycle-id',
                objective='Test the record helper',
                mode='revenue',
                arr_usd=2_400_000,
                verdict='APPROVED',
            )
            test('fire-and-forget: no raise without Supabase', True)
        except Exception as exc:
            test('fire-and-forget: no raise without Supabase', False, str(exc))
    finally:
        if orig_url is not None:
            os.environ['SUPABASE_URL'] = orig_url
        if orig_key is not None:
            os.environ['SUPABASE_SERVICE_ROLE_KEY'] = orig_key

    # With clearly invalid Supabase URL, should still not raise
    os.environ['SUPABASE_URL'] = 'http://127.0.0.1:19999'  # nothing listening
    os.environ['SUPABASE_SERVICE_ROLE_KEY'] = 'fake-key'
    try:
        try:
            record_revenue_cycle('id', 'obj', 'gtm', 1_000_000, 'APPROVED')
            test('fire-and-forget: no raise on network error', True)
        except Exception as exc:
            test('fire-and-forget: no raise on network error', False, str(exc))
    finally:
        os.environ.pop('SUPABASE_URL', None)
        os.environ.pop('SUPABASE_SERVICE_ROLE_KEY', None)


# ── evaluate_generation_fitness() — viability budget ─────────────────────────

def test_evaluate_generation_fitness():
    print('\nevaluate_generation_fitness() — viability + 4-metric composite:')

    test('VIABILITY_CHAR_BUDGET is 1600', VIABILITY_CHAR_BUDGET == 1600)

    objective = 'grow enterprise ARR to $10M'

    # Within-budget output: viability must be 1.0
    short_output = 'X' * 800  # 800 chars — half the budget
    scores_within = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': short_output}], objective)
    test('within-budget role present', 'Strategy' in scores_within)
    row = scores_within['Strategy']
    test('within-budget viability == 1.0', row['viability_score'] == 1.0,
         f'got {row.get("viability_score")}')
    test('fitness_score in [0,1]', 0.0 <= row['fitness_score'] <= 1.0)

    # Exactly at budget: viability must be 1.0
    at_budget = 'Y' * VIABILITY_CHAR_BUDGET
    scores_at = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': at_budget}], objective)
    test('at-budget viability == 1.0', scores_at['Strategy']['viability_score'] == 1.0,
         f'got {scores_at["Strategy"].get("viability_score")}')

    # 2× budget: viability must be 0.5
    double_budget = 'Z' * (VIABILITY_CHAR_BUDGET * 2)
    scores_double = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': double_budget}], objective)
    v = scores_double['Strategy']['viability_score']
    test('2x-budget viability == 0.5', abs(v - 0.5) < 0.001, f'got {v}')

    # Monotonic decay: 3× budget < 2× budget viability
    triple_budget = 'W' * (VIABILITY_CHAR_BUDGET * 3)
    scores_triple = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': triple_budget}], objective)
    test('viability is monotonically decreasing with output length',
         scores_triple['Strategy']['viability_score'] < scores_double['Strategy']['viability_score'])

    # Empty output: viability must be 0.0, fitness must be 0.0
    scores_empty = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': ''}], objective)
    test('empty output viability == 0.0', scores_empty['Strategy']['viability_score'] == 0.0,
         f'got {scores_empty["Strategy"].get("viability_score")}')
    test('empty output fitness == 0.0', scores_empty['Strategy']['fitness_score'] == 0.0,
         f'got {scores_empty["Strategy"].get("fitness_score")}')

    # Return shape — each entry must have exactly fitness_score + viability_score
    for role, row in scores_within.items():
        test(f'{role} has fitness_score key', 'fitness_score' in row)
        test(f'{role} has viability_score key', 'viability_score' in row)
        test(f'{role} fitness_score bounds', 0.0 <= row['fitness_score'] <= 1.0)
        test(f'{role} viability_score bounds', 0.0 <= row['viability_score'] <= 1.0)

    # Determinism: same inputs → same outputs (3 runs)
    arts = [{'role': 'Finance', 'output': 'A' * 1200}]
    r1 = evaluate_generation_fitness([], arts, objective)
    r2 = evaluate_generation_fitness([], arts, objective)
    r3 = evaluate_generation_fitness([], arts, objective)
    test('deterministic run 1==2', r1 == r2)
    test('deterministic run 2==3', r2 == r3)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== /platform/* API CONTRACT TESTS ===')
    test_contract_version()
    test_departments()
    test_platform_ts()
    test_platform_envelope()
    test_verify_api_key()
    test_query_api_key_info()
    test_record_revenue_cycle()
    test_dept_output()
    test_make_sse_event()
    test_validate_collaboration_request()
    test_evaluate_generation_fitness()
    print(f'\n{"=" * 40}')
    print(f'PASS: {PASS}  FAIL: {FAIL}')
    if FAIL > 0:
        print('RESULT: FAIL — platform contract regression detected')
        sys.exit(1)
    print('RESULT: PASS — all platform contract invariants verified')
