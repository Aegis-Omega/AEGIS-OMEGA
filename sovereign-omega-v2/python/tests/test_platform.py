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
    FITNESS_VERSION,
    CONVERGENCE_EPSILON,
    CONVERGENCE_K_GENERATIONS,
    CONSTITUTIONAL_FACTORS,
    STAGNATION_THRESHOLD,
    platform_ts,
    platform_envelope,
    verify_api_key,
    query_api_key_info,
    record_revenue_cycle,
    dept_output,
    make_sse_event,
    validate_collaboration_request,
    evaluate_generation_fitness,
    check_fitness_convergence,
    get_convergence_diagnostics,
    artifact_hash,
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


def _chk(name: str, condition: bool, reason: str = '') -> None:
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
    _chk('version is 1.0.0', PLATFORM_CONTRACT_VERSION == '1.0.0')
    parts = PLATFORM_CONTRACT_VERSION.split('.')
    _chk('version is semver (3 parts)', len(parts) == 3)
    _chk('all parts are numeric', all(p.isdigit() for p in parts))


# ── Department roster ─────────────────────────────────────────────────────────

_KNOWN_CATEGORIES = {'revenue', 'marketing', 'sales', 'product', 'engineering',
                     'operations', 'research', 'finance', 'executive',
                     'governance', 'constitutional'}

def test_departments():
    print('\ndepartment roster:')
    _chk('exactly 39 departments', len(PLATFORM_DEPARTMENTS) == 39)

    ids = [d['id'] for d in PLATFORM_DEPARTMENTS]
    _chk('all IDs are unique', len(ids) == len(set(ids)))
    _chk('first dept is REV-01', PLATFORM_DEPARTMENTS[0]['id'] == 'REV-01')
    _chk('last dept is CON-09 Guardian', PLATFORM_DEPARTMENTS[-1]['id'] == 'CON-09')

    for d in PLATFORM_DEPARTMENTS:
        for field in ('id', 'role', 'category'):
            _chk(f'{d["id"]} has {field}', field in d and d[field])
        _chk(f'{d["id"]} category is known', d['category'] in _KNOWN_CATEGORIES,
             f'unknown category: {d.get("category")}')

    # Category counts match TypeScript contract
    cats = {}
    for d in PLATFORM_DEPARTMENTS:
        cats[d['category']] = cats.get(d['category'], 0) + 1
    _chk('3 revenue depts', cats.get('revenue') == 3)
    _chk('5 marketing depts', cats.get('marketing') == 5)
    _chk('4 sales depts', cats.get('sales') == 4)
    _chk('4 product depts', cats.get('product') == 4)
    _chk('5 engineering depts', cats.get('engineering') == 5)
    _chk('4 operations depts', cats.get('operations') == 4)
    _chk('3 research depts', cats.get('research') == 3)
    _chk('3 finance depts', cats.get('finance') == 3)
    _chk('4 executive depts', cats.get('executive') == 4)
    _chk('2 governance depts', cats.get('governance') == 2)
    _chk('2 constitutional depts', cats.get('constitutional') == 2)


# ── platform_ts() ────────────────────────────────────────────────────────────

def test_platform_ts():
    print('\nplatform_ts():')
    ts = platform_ts()
    _chk('returns a string', isinstance(ts, str))
    _chk('ends with Z (UTC)', ts.endswith('Z'))
    _chk('contains T (ISO-8601)', 'T' in ts)
    _chk('length is reasonable', 20 <= len(ts) <= 32)


# ── platform_envelope() ───────────────────────────────────────────────────────

def test_platform_envelope():
    print('\nplatform_envelope():')
    eid = 'test-exec-001'
    data = {'foo': 'bar', 'n': 42}
    env = platform_envelope(eid, data)

    _chk('contract_version matches', env['contract_version'] == PLATFORM_CONTRACT_VERSION)
    _chk('execution_id matches', env['execution_id'] == eid)
    _chk('data is passed through', env['data'] == data)
    _chk('is_replay_reconstructable is True', env['is_replay_reconstructable'] is True)
    _chk('timestamp present', 'timestamp' in env and env['timestamp'])
    _chk('has exactly 5 keys', set(env.keys()) == {
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
        _chk('dev key returns dev@local', email == 'dev@local')
        _chk('dev key returns explorer tier', tier == 'explorer')

        email2, tier2 = verify_api_key('aegis_anything_goes')
        _chk('any aegis_* key passes dev bypass', email2 == 'dev@local')

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
        _chk(f'mode={mode} returns non-empty string', isinstance(out, str) and len(out) > 20)
        _chk(f'mode={mode} contains role name', dept['role'] in out)

    # Constitutional dept gets suffix
    con_dept = next(d for d in PLATFORM_DEPARTMENTS if d['category'] == 'constitutional')
    out_con = dept_output(objective, 'revenue', con_dept)
    _chk('constitutional dept suffix present', 'T0 verdict VALID' in out_con)

    # Governance dept gets suffix
    gov_dept = next(d for d in PLATFORM_DEPARTMENTS if d['category'] == 'governance')
    out_gov = dept_output(objective, 'revenue', gov_dept)
    _chk('governance dept suffix present', 'Risk: LOW' in out_gov)

    # Executive dept gets suffix
    exe_dept = next(d for d in PLATFORM_DEPARTMENTS if d['category'] == 'executive')
    out_exe = dept_output(objective, 'revenue', exe_dept)
    _chk('executive dept suffix present', 'Board priority' in out_exe)

    # Unknown mode falls back to revenue template
    out_fallback = dept_output(objective, 'unknown_mode', PLATFORM_DEPARTMENTS[0])
    _chk('unknown mode falls back gracefully', len(out_fallback) > 20)

    # Objective is truncated at 55 chars
    long_obj = 'A' * 100
    out_trunc = dept_output(long_obj, 'revenue', PLATFORM_DEPARTMENTS[0])
    _chk('objective truncated to 55 chars', 'A' * 56 not in out_trunc)


# ── make_sse_event() ──────────────────────────────────────────────────────────

def test_make_sse_event():
    print('\nmake_sse_event():')
    eid = 'sse-test-001'

    for event_type in ('dag_step', 'agent_event', 'tool_call', 'error', 'completion', 'heartbeat'):
        payload = {'seq': 0}
        evt = make_sse_event(event_type, eid, payload)
        _chk(f'{event_type} type correct', evt['type'] == event_type)
        _chk(f'{event_type} execution_id correct', evt['execution_id'] == eid)
        _chk(f'{event_type} timestamp present', evt['timestamp'].endswith('Z'))
        _chk(f'{event_type} payload passed', evt['payload'] == payload)
        _chk(f'{event_type} has exactly 4 keys',
             set(evt.keys()) == {'type', 'execution_id', 'timestamp', 'payload'})


# ── validate_collaboration_request() ─────────────────────────────────────────

def test_validate_collaboration_request():
    print('\nvalidate_collaboration_request():')

    # Valid requests — returns (objective, mode, live, generation, memory_context)
    obj, mode, live, gen, mem = validate_collaboration_request({
        'objective': 'Test', 'mode': 'revenue', 'live': False
    })
    _chk('valid: objective returned', obj == 'Test')
    _chk('valid: mode returned', mode == 'revenue')
    _chk('valid: live returned', live is False)
    _chk('valid: generation defaults to 0', gen == 0)
    _chk('valid: memory_context defaults to empty string', mem == '')

    for m in ('revenue', 'analysis', 'gtm', 'retention'):
        _o, m2, _l, _g, _mc = validate_collaboration_request(
            {'objective': 'x', 'mode': m, 'live': True}
        )
        _chk(f'valid mode {m}', m2 == m)

    # Objective whitespace stripping
    o3, _, _, _, _ = validate_collaboration_request(
        {'objective': '  hello  ', 'mode': 'revenue', 'live': False}
    )
    _chk('objective stripped', o3 == 'hello')

    # generation + memory_context passthrough
    _o, _m, _l, g2, mc2 = validate_collaboration_request({
        'objective': 'x', 'mode': 'analysis', 'live': False,
        'generation': 3, 'memory_context': 'prior_ctx',
    })
    _chk('generation passthrough', g2 == 3)
    _chk('memory_context passthrough', mc2 == 'prior_ctx')

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
        _chk('dev bypass returns dict', isinstance(info, dict))
        _chk('dev bypass email', info is not None and info.get('customer_email') == 'dev@local')
        _chk('dev bypass tier', info is not None and info.get('tier') == 'explorer')
        _chk('dev bypass usage_count', info is not None and info.get('usage_count') == 0)
        _chk('dev bypass usage_limit', info is not None and info.get('usage_limit') == 10)

        # Non-aegis_ key returns None in dev mode
        info2 = query_api_key_info('sk-bad-key')
        _chk('non-aegis key returns None in dev mode', info2 is None)

        # Empty key returns None
        info3 = query_api_key_info('')
        _chk('empty key returns None', info3 is None)
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
            _chk('fire-and-forget: no raise without Supabase', True)
        except Exception as exc:
            _chk('fire-and-forget: no raise without Supabase', False, str(exc))
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
            _chk('fire-and-forget: no raise on network error', True)
        except Exception as exc:
            _chk('fire-and-forget: no raise on network error', False, str(exc))
    finally:
        os.environ.pop('SUPABASE_URL', None)
        os.environ.pop('SUPABASE_SERVICE_ROLE_KEY', None)


# ── evaluate_generation_fitness() — viability budget ─────────────────────────

def test_evaluate_generation_fitness():
    print('\nevaluate_generation_fitness() — viability + 4-metric composite:')

    _chk('VIABILITY_CHAR_BUDGET is 1600', VIABILITY_CHAR_BUDGET == 1600)

    objective = 'grow enterprise ARR to $10M'

    # Within-budget output: viability must be 1.0
    short_output = 'X' * 800  # 800 chars — half the budget
    scores_within = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': short_output}], objective)
    _chk('within-budget role present', 'Strategy' in scores_within)
    row = scores_within['Strategy']
    _chk('within-budget viability == 1.0', row['viability_score'] == 1.0,
         f'got {row.get("viability_score")}')
    _chk('fitness_score in [0,1]', 0.0 <= row['fitness_score'] <= 1.0)

    # Exactly at budget: viability must be 1.0
    at_budget = 'Y' * VIABILITY_CHAR_BUDGET
    scores_at = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': at_budget}], objective)
    _chk('at-budget viability == 1.0', scores_at['Strategy']['viability_score'] == 1.0,
         f'got {scores_at["Strategy"].get("viability_score")}')

    # 2× budget: viability must be 0.5
    double_budget = 'Z' * (VIABILITY_CHAR_BUDGET * 2)
    scores_double = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': double_budget}], objective)
    v = scores_double['Strategy']['viability_score']
    _chk('2x-budget viability == 0.5', abs(v - 0.5) < 0.001, f'got {v}')

    # Monotonic decay: 3× budget < 2× budget viability
    triple_budget = 'W' * (VIABILITY_CHAR_BUDGET * 3)
    scores_triple = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': triple_budget}], objective)
    _chk('viability is monotonically decreasing with output length',
         scores_triple['Strategy']['viability_score'] < scores_double['Strategy']['viability_score'])

    # Empty output: viability must be 0.0, fitness must be 0.0
    scores_empty = evaluate_generation_fitness([], [{'role': 'Strategy', 'output': ''}], objective)
    _chk('empty output viability == 0.0', scores_empty['Strategy']['viability_score'] == 0.0,
         f'got {scores_empty["Strategy"].get("viability_score")}')
    _chk('empty output fitness == 0.0', scores_empty['Strategy']['fitness_score'] == 0.0,
         f'got {scores_empty["Strategy"].get("fitness_score")}')

    # Return shape — V1.1: fitness_score, viability_score, constitutional_factor, stagnation_flag
    for role, row in scores_within.items():
        _chk(f'{role} has fitness_score key', 'fitness_score' in row)
        _chk(f'{role} has viability_score key', 'viability_score' in row)
        _chk(f'{role} has constitutional_factor key', 'constitutional_factor' in row)
        _chk(f'{role} has stagnation_flag key', 'stagnation_flag' in row)
        _chk(f'{role} fitness_score bounds', 0.0 <= row['fitness_score'] <= 1.0)
        _chk(f'{role} viability_score bounds', 0.0 <= row['viability_score'] <= 1.0)
        _chk(f'{role} constitutional_factor in [0,1]', 0.0 <= row['constitutional_factor'] <= 1.0)
        _chk(f'{role} stagnation_flag is bool', isinstance(row['stagnation_flag'], bool))

    # Determinism: same inputs → same outputs (3 runs)
    arts = [{'role': 'Finance', 'output': 'A' * 1200}]
    r1 = evaluate_generation_fitness([], arts, objective)
    r2 = evaluate_generation_fitness([], arts, objective)
    r3 = evaluate_generation_fitness([], arts, objective)
    _chk('deterministic run 1==2', r1 == r2)
    _chk('deterministic run 2==3', r2 == r3)


# ── Fitness version + convergence invariant ───────────────────────────────────

def test_fitness_version():
    print('\nfitness version + convergence constants:')
    _chk('FITNESS_VERSION is a non-empty string', isinstance(FITNESS_VERSION, str) and FITNESS_VERSION)
    parts = FITNESS_VERSION.split('.')
    _chk('FITNESS_VERSION is semver-shaped', len(parts) >= 1 and parts[0].isdigit())
    _chk('CONVERGENCE_EPSILON is float in (0,1)', 0.0 < CONVERGENCE_EPSILON < 1.0)
    _chk('CONVERGENCE_K_GENERATIONS >= 2', CONVERGENCE_K_GENERATIONS >= 2)


def test_check_fitness_convergence():
    print('\ncheck_fitness_convergence():')

    # Fewer than K+1 entries → never converged
    _chk('empty history → False', check_fitness_convergence([]) is False)
    _chk('K entries → False (need K+1)', check_fitness_convergence(
        [{'Strategy': 0.8}] * CONVERGENCE_K_GENERATIONS
    ) is False)

    # K+1 identical generations → converged (delta == 0 < epsilon)
    stable = [{'Strategy': 0.8, 'Finance': 0.75}] * (CONVERGENCE_K_GENERATIONS + 1)
    _chk('K+1 identical generations → True', check_fitness_convergence(stable) is True)

    # Large delta in the last window → not converged
    unstable = [{'Strategy': float(i) / 10} for i in range(CONVERGENCE_K_GENERATIONS + 1)]
    _chk('large delta window → False', check_fitness_convergence(unstable) is False)

    # Converged tail after noisy prefix — only last K+1 matter
    noisy_prefix = [{'Strategy': float(i) / 5} for i in range(10)]
    stable_tail  = [{'Strategy': 0.9}] * (CONVERGENCE_K_GENERATIONS + 1)
    mixed = noisy_prefix + stable_tail
    _chk('stable tail after noise → True', check_fitness_convergence(mixed) is True)

    # Delta exactly at epsilon → NOT converged (strict <)
    eps = CONVERGENCE_EPSILON
    at_boundary = [{'Strategy': 0.5}, {'Strategy': 0.5 + eps}] * (CONVERGENCE_K_GENERATIONS + 1)
    # at_boundary alternates, so at least one delta >= eps
    _chk('delta at epsilon boundary → False', check_fitness_convergence(at_boundary) is False)

    # No shared roles → False (can't compute delta)
    disjoint = [{'A': 0.8}] * (CONVERGENCE_K_GENERATIONS + 1)
    disjoint[-1] = {'B': 0.8}  # last gen has different role
    _chk('disjoint roles in last gen → False', check_fitness_convergence(disjoint) is False)


def test_artifact_hash():
    print('\nartifact_hash():')
    h1 = artifact_hash('hello world')
    h2 = artifact_hash('hello world')
    h3 = artifact_hash('different')
    _chk('deterministic: same input → same hash', h1 == h2)
    _chk('different inputs → different hash', h1 != h3)
    _chk('returns 64-char hex string (SHA-256)', len(h1) == 64 and all(c in '0123456789abcdef' for c in h1))
    _chk('empty string → defined hash (not crash)', len(artifact_hash('')) == 64)


def test_evolution_consistency():
    print('\nevolution consistency (bounded variance over 20 runs):')

    objective = 'grow enterprise ARR to $10M'
    arts = [
        {'role': 'Strategy',  'output': 'S' * 900},
        {'role': 'Finance',   'output': 'F' * 1200},
        {'role': 'Guardian',  'output': 'G' * 400},
    ]

    # Run evaluate_generation_fitness 20 times — scores must be identical
    results = [evaluate_generation_fitness([], arts, objective) for _ in range(20)]
    r0 = results[0]
    _chk('all 20 runs produce identical output', all(r == r0 for r in results))

    # Variance of fitness_score across 20 runs must be 0.0 (pure determinism)
    for role in r0:
        scores = [results[i][role]['fitness_score'] for i in range(20)]
        variance = sum((s - scores[0]) ** 2 for s in scores) / len(scores)
        _chk(f'{role}: fitness variance == 0 across 20 runs', variance == 0.0,
             f'variance={variance}')

    # Fitness scores stay in [0,1] across all roles and runs
    for role in r0:
        for run in results:
            f = run[role]['fitness_score']
            v = run[role]['viability_score']
            _chk(f'{role}: fitness in [0,1]', 0.0 <= f <= 1.0, f'got {f}')
            _chk(f'{role}: viability in [0,1]', 0.0 <= v <= 1.0, f'got {v}')

    # Generation number monotonicity: validate_collaboration_request enforces >= 0
    # and callers must increment. Verify the validator rejects non-monotonic inputs.
    expect_raises('generation -1 rejected', ValueError,
                  lambda: validate_collaboration_request(
                      {'objective': 'x', 'mode': 'revenue', 'live': False, 'generation': -1}
                  ))
    for g in (0, 1, 5, 100):
        _, _, _, gen_out, _ = validate_collaboration_request(
            {'objective': 'x', 'mode': 'revenue', 'live': False, 'generation': g}
        )
        _chk(f'generation {g} passthrough', gen_out == g)

    # artifact_hash is stable — same output → same hash across generations
    output_text = 'stable department output across generations'
    h_gen0 = artifact_hash(output_text)
    h_gen1 = artifact_hash(output_text)
    _chk('artifact_hash stable across generation calls', h_gen0 == h_gen1)


# ── V1.1: constitutional multiplier ──────────────────────────────────────────

def test_constitutional_fitness_multiplier():
    print('\nconstitutional fitness multiplier (V1.1):')
    objective = 'grow enterprise ARR to $10M'
    arts = [{'role': 'Strategy', 'output': 'S' * 1200}]

    scores_approved = evaluate_generation_fitness([], arts, objective, cycle_verdict='APPROVED')
    row_a = scores_approved['Strategy']
    _chk('APPROVED constitutional_factor == 1.00',
         row_a['constitutional_factor'] == 1.00,
         f'got {row_a.get("constitutional_factor")}')

    scores_flag = evaluate_generation_fitness([], arts, objective, cycle_verdict='FLAG')
    row_f = scores_flag['Strategy']
    _chk('FLAG constitutional_factor == 0.70',
         row_f['constitutional_factor'] == 0.70,
         f'got {row_f.get("constitutional_factor")}')
    _chk('FLAG fitness <= APPROVED fitness',
         row_f['fitness_score'] <= row_a['fitness_score'],
         f'FLAG={row_f["fitness_score"]} APPROVED={row_a["fitness_score"]}')

    scores_quar = evaluate_generation_fitness([], arts, objective, cycle_verdict='QUARANTINE')
    row_q = scores_quar['Strategy']
    _chk('QUARANTINE constitutional_factor == 0.20',
         row_q['constitutional_factor'] == 0.20,
         f'got {row_q.get("constitutional_factor")}')
    _chk('QUARANTINE fitness <= 0.20', row_q['fitness_score'] <= 0.20,
         f'got {row_q["fitness_score"]}')

    scores_none = evaluate_generation_fitness([], arts, objective, cycle_verdict=None)
    row_n = scores_none['Strategy']
    _chk('None verdict constitutional_factor == 0.85',
         row_n['constitutional_factor'] == 0.85,
         f'got {row_n.get("constitutional_factor")}')

    _chk('CONSTITUTIONAL_FACTORS has APPROVED', CONSTITUTIONAL_FACTORS.get('APPROVED') == 1.00)
    _chk('CONSTITUTIONAL_FACTORS has FLAG', CONSTITUTIONAL_FACTORS.get('FLAG') == 0.70)
    _chk('CONSTITUTIONAL_FACTORS has QUARANTINE', CONSTITUTIONAL_FACTORS.get('QUARANTINE') == 0.20)


# ── V1.1: stagnation flag ─────────────────────────────────────────────────────

def test_stagnation_flag():
    print('\nstagnation_flag detection (V1.1):')
    objective = 'test'

    arts_no_prev = [{'role': 'Strategy', 'output': 'implement Redis cache'}]
    scores_no_prev = evaluate_generation_fitness([], arts_no_prev, objective)
    _chk('no prev generation → stagnation_flag=False',
         scores_no_prev['Strategy']['stagnation_flag'] is False)

    same_output = ('implement Redis cache with TTL and eviction policy '
                   'for distributed session storage at scale')
    prev_arts = [{'role': 'Strategy', 'output': same_output}]
    curr_arts = [{'role': 'Strategy', 'output': same_output}]
    scores_same = evaluate_generation_fitness(prev_arts, curr_arts, objective)
    _chk('identical prev/curr → stagnation_flag=True',
         scores_same['Strategy']['stagnation_flag'] is True,
         f'got {scores_same["Strategy"]["stagnation_flag"]}')

    prev_arts2 = [{'role': 'Strategy', 'output': 'initial strategy for enterprise growth and ARR targets'}]
    curr_arts2 = [{'role': 'Strategy', 'output': 'pivot to SMB market with product-led growth and viral coefficients'}]
    scores_diff = evaluate_generation_fitness(prev_arts2, curr_arts2, objective)
    _chk('sufficiently different prev/curr → stagnation_flag=False',
         scores_diff['Strategy']['stagnation_flag'] is False,
         f'got {scores_diff["Strategy"]["stagnation_flag"]}')

    _chk('STAGNATION_THRESHOLD == 0.95', STAGNATION_THRESHOLD == 0.95)


# ── V1.1: convergence diagnostics ────────────────────────────────────────────

def test_convergence_diagnostics():
    print('\nget_convergence_diagnostics():')

    d_empty = get_convergence_diagnostics([])
    _chk('empty → diagnosis INSUFFICIENT_DATA', d_empty['diagnosis'] == 'INSUFFICIENT_DATA')
    _chk('empty → converged=False', d_empty['converged'] is False)
    _chk('empty → mean_fitness=0.0', d_empty['mean_fitness'] == 0.0)

    improving = [{'Strategy': round(i / 10.0, 1)} for i in range(1, 8)]
    d_imp = get_convergence_diagnostics(improving)
    _chk('improving → slope > 0', d_imp['slope'] > 0)
    _chk('improving → diagnosis is IMPROVING', d_imp['diagnosis'] == 'IMPROVING')

    regressing = [{'Strategy': round(1.0 - i / 10.0, 1)} for i in range(1, 8)]
    d_reg = get_convergence_diagnostics(regressing)
    _chk('regressing → slope < 0', d_reg['slope'] < 0)
    _chk('regressing → diagnosis REGRESSING', d_reg['diagnosis'] == 'REGRESSING')

    stagnant_hist = [{'Strategy': 0.40}] * (CONVERGENCE_K_GENERATIONS + 1)
    d_st = get_convergence_diagnostics(stagnant_hist)
    _chk('stagnant (0.40) → converged=True', d_st['converged'] is True)
    _chk('stagnant (0.40) → stagnant=True', d_st['stagnant'] is True)
    _chk('stagnant → diagnosis STAGNANT', d_st['diagnosis'] == 'STAGNANT')

    converged_hist = [{'Strategy': 0.80}] * (CONVERGENCE_K_GENERATIONS + 1)
    d_cv = get_convergence_diagnostics(converged_hist)
    _chk('converged (0.80) → converged=True', d_cv['converged'] is True)
    _chk('converged (0.80) → stagnant=False', d_cv['stagnant'] is False)
    _chk('converged → diagnosis CONVERGED', d_cv['diagnosis'] == 'CONVERGED')

    oscillating_hist = [
        {'Strategy': 0.3 + 0.6 * (i % 2)}
        for i in range(CONVERGENCE_K_GENERATIONS + 3)
    ]
    d_osc = get_convergence_diagnostics(oscillating_hist)
    _chk('oscillating → oscillating=True', d_osc['oscillating'] is True)
    _chk('oscillating → diagnosis OSCILLATING', d_osc['diagnosis'] == 'OSCILLATING')

    required_keys = {'converged', 'mean_fitness', 'variance', 'slope',
                     'stagnant', 'oscillating', 'diagnosis'}
    _chk('diagnostics has all required keys',
         required_keys.issubset(d_cv.keys()),
         f'missing: {required_keys - set(d_cv.keys())}')


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
    test_fitness_version()
    test_check_fitness_convergence()
    test_artifact_hash()
    test_evolution_consistency()
    test_constitutional_fitness_multiplier()
    test_stagnation_flag()
    test_convergence_diagnostics()
    print(f'\n{"=" * 40}')
    print(f'PASS: {PASS}  FAIL: {FAIL}')
    if FAIL > 0:
        print('RESULT: FAIL — platform contract regression detected')
        sys.exit(1)
    print('RESULT: PASS — all platform contract invariants verified')
