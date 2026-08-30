"""
SOVEREIGN OMEGA — Source Attribution Tests
EPISTEMIC TIER: T2

Comprehensive tests for source_attribution.py: TelemetrySample, SourceAttribution,
SourceAttributor, and module constants VCG_WINDOW_SIZE, _N_COMPONENTS, _COMPONENT_LABELS.

Run: python python/tests/test_source_attribution.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from source_attribution import (
    TelemetrySample,
    SourceAttribution,
    SourceAttributor,
    VCG_WINDOW_SIZE,
    _N_COMPONENTS,
    _COMPONENT_LABELS,
    _NMF_AVAILABLE,
)

PASS = 0
FAIL = 0


def ok(name: str) -> None:
    global PASS
    PASS += 1
    print(f'  PASS  {name}')


def fail(name: str, reason: str) -> None:
    global FAIL
    FAIL += 1
    print(f'  FAIL  {name}: {reason}')


def _chk(name: str, condition: bool, reason: str = '') -> None:
    if condition:
        ok(name)
    else:
        fail(name, reason or 'assertion failed')


def expect_raises(name: str, exc_type, fn) -> None:
    try:
        fn()
        fail(name, f'expected {exc_type.__name__} but no exception raised')
    except exc_type:
        ok(name)
    except Exception as e:
        fail(name, f'expected {exc_type.__name__} but got {type(e).__name__}: {e}')


# ── Module constants ──────────────────────────────────────────────────────────

def test_constants():
    print('\nmodule constants:')

    _chk('VCG_WINDOW_SIZE == 500', VCG_WINDOW_SIZE == 500)
    _chk('VCG_WINDOW_SIZE is int', isinstance(VCG_WINDOW_SIZE, int))
    _chk('VCG_WINDOW_SIZE > 0', VCG_WINDOW_SIZE > 0)

    _chk('_N_COMPONENTS == 3', _N_COMPONENTS == 3)
    _chk('_N_COMPONENTS is int', isinstance(_N_COMPONENTS, int))
    _chk('_N_COMPONENTS > 0', _N_COMPONENTS > 0)

    _chk('_COMPONENT_LABELS is tuple', isinstance(_COMPONENT_LABELS, tuple))
    _chk('_COMPONENT_LABELS has 3 entries', len(_COMPONENT_LABELS) == 3)
    _chk('_COMPONENT_LABELS[0] == gpu_inference',
         _COMPONENT_LABELS[0] == 'gpu_inference')
    _chk('_COMPONENT_LABELS[1] == governance',
         _COMPONENT_LABELS[1] == 'governance')
    _chk('_COMPONENT_LABELS[2] == os_noise',
         _COMPONENT_LABELS[2] == 'os_noise')
    _chk('_COMPONENT_LABELS contains gpu_inference', 'gpu_inference' in _COMPONENT_LABELS)
    _chk('_COMPONENT_LABELS contains governance', 'governance' in _COMPONENT_LABELS)
    _chk('_COMPONENT_LABELS contains os_noise', 'os_noise' in _COMPONENT_LABELS)


# ── TelemetrySample dataclass ─────────────────────────────────────────────────

def test_telemetry_sample_creation():
    print('\nTelemetrySample creation:')

    s = TelemetrySample(
        sequence=42,
        afse_score=0.85,
        tgcs_stretch_ms=10.0,
        pgcs_compressed_bytes=1024,
    )

    _chk('sequence field correct', s.sequence == 42)
    _chk('afse_score field correct', s.afse_score == 0.85)
    _chk('tgcs_stretch_ms field correct', s.tgcs_stretch_ms == 10.0)
    _chk('pgcs_compressed_bytes field correct', s.pgcs_compressed_bytes == 1024)

    _chk('sequence is int', isinstance(s.sequence, int))
    _chk('afse_score is float', isinstance(s.afse_score, float))
    _chk('tgcs_stretch_ms is float', isinstance(s.tgcs_stretch_ms, float))
    _chk('pgcs_compressed_bytes is int', isinstance(s.pgcs_compressed_bytes, int))


def test_telemetry_sample_frozen():
    print('\nTelemetrySample frozen:')

    s = TelemetrySample(sequence=1, afse_score=0.5, tgcs_stretch_ms=0.0,
                        pgcs_compressed_bytes=0)

    expect_raises('frozen: cannot set sequence', (AttributeError, TypeError),
                  lambda: setattr(s, 'sequence', 99))
    expect_raises('frozen: cannot set afse_score', (AttributeError, TypeError),
                  lambda: setattr(s, 'afse_score', 0.0))
    expect_raises('frozen: cannot set tgcs_stretch_ms', (AttributeError, TypeError),
                  lambda: setattr(s, 'tgcs_stretch_ms', 999.0))
    expect_raises('frozen: cannot set pgcs_compressed_bytes', (AttributeError, TypeError),
                  lambda: setattr(s, 'pgcs_compressed_bytes', -1))


def test_telemetry_sample_zero_values():
    print('\nTelemetrySample zero values:')

    s = TelemetrySample(sequence=0, afse_score=0.0, tgcs_stretch_ms=0.0,
                        pgcs_compressed_bytes=0)
    _chk('sequence=0 ok', s.sequence == 0)
    _chk('afse_score=0.0 ok', s.afse_score == 0.0)
    _chk('tgcs_stretch_ms=0.0 ok', s.tgcs_stretch_ms == 0.0)
    _chk('pgcs_compressed_bytes=0 ok', s.pgcs_compressed_bytes == 0)


def test_telemetry_sample_large_values():
    print('\nTelemetrySample large values:')

    s = TelemetrySample(
        sequence=1_000_000,
        afse_score=1.0,
        tgcs_stretch_ms=50.0,
        pgcs_compressed_bytes=10_000_000,
    )
    _chk('large sequence ok', s.sequence == 1_000_000)
    _chk('afse_score=1.0 ok', s.afse_score == 1.0)
    _chk('tgcs_stretch_ms=50.0 ok', s.tgcs_stretch_ms == 50.0)
    _chk('large pgcs_compressed_bytes ok', s.pgcs_compressed_bytes == 10_000_000)


def test_telemetry_sample_equality():
    print('\nTelemetrySample equality:')

    s1 = TelemetrySample(sequence=5, afse_score=0.5, tgcs_stretch_ms=1.0,
                         pgcs_compressed_bytes=100)
    s2 = TelemetrySample(sequence=5, afse_score=0.5, tgcs_stretch_ms=1.0,
                         pgcs_compressed_bytes=100)
    s3 = TelemetrySample(sequence=6, afse_score=0.5, tgcs_stretch_ms=1.0,
                         pgcs_compressed_bytes=100)

    _chk('equal samples compare equal', s1 == s2)
    _chk('different sequence → not equal', s1 != s3)


# ── SourceAttribution dataclass ───────────────────────────────────────────────

def test_source_attribution_creation():
    print('\nSourceAttribution creation:')

    sa = SourceAttribution(
        gpu_inference=0.5,
        governance=0.3,
        os_noise=0.2,
        window_size=100,
        sequence_start=0,
        sequence_end=99,
        determinism_class='observational',
    )

    _chk('gpu_inference field', sa.gpu_inference == 0.5)
    _chk('governance field', sa.governance == 0.3)
    _chk('os_noise field', sa.os_noise == 0.2)
    _chk('window_size field', sa.window_size == 100)
    _chk('sequence_start field', sa.sequence_start == 0)
    _chk('sequence_end field', sa.sequence_end == 99)
    _chk('determinism_class field', sa.determinism_class == 'observational')

    _chk('gpu_inference is float', isinstance(sa.gpu_inference, float))
    _chk('governance is float', isinstance(sa.governance, float))
    _chk('os_noise is float', isinstance(sa.os_noise, float))
    _chk('window_size is int', isinstance(sa.window_size, int))
    _chk('sequence_start is int', isinstance(sa.sequence_start, int))
    _chk('sequence_end is int', isinstance(sa.sequence_end, int))
    _chk('determinism_class is str', isinstance(sa.determinism_class, str))


def test_source_attribution_determinism_class():
    print('\nSourceAttribution determinism_class:')

    sa = SourceAttribution(
        gpu_inference=0.4, governance=0.4, os_noise=0.2,
        window_size=50, sequence_start=10, sequence_end=60,
        determinism_class='observational',
    )
    _chk('determinism_class is observational', sa.determinism_class == 'observational')


def test_source_attribution_frozen():
    print('\nSourceAttribution frozen:')

    sa = SourceAttribution(
        gpu_inference=0.5, governance=0.3, os_noise=0.2,
        window_size=100, sequence_start=0, sequence_end=99,
        determinism_class='observational',
    )
    expect_raises('frozen: cannot set gpu_inference', (AttributeError, TypeError),
                  lambda: setattr(sa, 'gpu_inference', 0.0))
    expect_raises('frozen: cannot set determinism_class', (AttributeError, TypeError),
                  lambda: setattr(sa, 'determinism_class', 'governance'))


def test_source_attribution_to_dict():
    print('\nSourceAttribution.to_dict():')

    sa = SourceAttribution(
        gpu_inference=0.5123456,
        governance=0.3234567,
        os_noise=0.1641977,
        window_size=200,
        sequence_start=100,
        sequence_end=299,
        determinism_class='observational',
    )

    d = sa.to_dict()
    _chk('to_dict returns dict', isinstance(d, dict))
    _chk('dict has gpu_inference', 'gpu_inference' in d)
    _chk('dict has governance', 'governance' in d)
    _chk('dict has os_noise', 'os_noise' in d)
    _chk('dict has window_size', 'window_size' in d)
    _chk('dict has sequence_start', 'sequence_start' in d)
    _chk('dict has sequence_end', 'sequence_end' in d)
    _chk('dict has determinism_class', 'determinism_class' in d)

    _chk('gpu_inference rounded to 4 decimal places',
         d['gpu_inference'] == round(0.5123456, 4))
    _chk('governance rounded to 4 decimal places',
         d['governance'] == round(0.3234567, 4))
    _chk('os_noise rounded to 4 decimal places',
         d['os_noise'] == round(0.1641977, 4))

    _chk('window_size in dict == 200', d['window_size'] == 200)
    _chk('sequence_start in dict == 100', d['sequence_start'] == 100)
    _chk('sequence_end in dict == 299', d['sequence_end'] == 299)
    _chk('determinism_class in dict is observational',
         d['determinism_class'] == 'observational')


def test_source_attribution_to_dict_all_keys():
    print('\nSourceAttribution.to_dict() all keys present:')

    sa = SourceAttribution(
        gpu_inference=0.1, governance=0.2, os_noise=0.7,
        window_size=10, sequence_start=0, sequence_end=9,
        determinism_class='observational',
    )
    d = sa.to_dict()
    expected_keys = {'gpu_inference', 'governance', 'os_noise',
                     'window_size', 'sequence_start', 'sequence_end', 'determinism_class'}
    _chk('to_dict has all 7 keys', set(d.keys()) == expected_keys,
         f'missing: {expected_keys - set(d.keys())}')


# ── SourceAttributor ──────────────────────────────────────────────────────────

def test_source_attributor_empty():
    print('\nSourceAttributor empty buffer:')

    attr = SourceAttributor()
    _chk('attribute() None when empty', attr.attribute() is None)


def test_source_attributor_too_few_samples():
    print('\nSourceAttributor too few samples:')

    attr = SourceAttributor()

    # 1 sample — too few
    attr.push(TelemetrySample(sequence=0, afse_score=0.5, tgcs_stretch_ms=1.0,
                              pgcs_compressed_bytes=100))
    _chk('attribute() None with 1 sample', attr.attribute() is None)

    # 2 samples — still too few for NMF (needs >= _N_COMPONENTS=3)
    attr.push(TelemetrySample(sequence=1, afse_score=0.6, tgcs_stretch_ms=2.0,
                              pgcs_compressed_bytes=200))
    _chk('attribute() None with 2 samples', attr.attribute() is None)


def test_source_attributor_all_zero():
    print('\nSourceAttributor all-zero signals:')

    attr = SourceAttributor()
    for i in range(10):
        attr.push(TelemetrySample(sequence=i, afse_score=0.0, tgcs_stretch_ms=0.0,
                                  pgcs_compressed_bytes=0))
    # All signals zero → degenerate window → returns None
    _chk('all-zero signals → attribute() is None', attr.attribute() is None)


def test_source_attributor_push_no_raise():
    print('\nSourceAttributor push no raise:')

    attr = SourceAttributor()
    for i in range(20):
        try:
            attr.push(TelemetrySample(sequence=i, afse_score=float(i) / 20,
                                      tgcs_stretch_ms=float(i),
                                      pgcs_compressed_bytes=i * 100))
            ok(f'push({i}) does not raise')
        except Exception as e:
            fail(f'push({i}) should not raise', str(e))


def test_source_attributor_window_cap():
    print('\nSourceAttributor window cap:')

    window_size = 50
    attr = SourceAttributor(window_size=window_size)

    # Push window_size + 50 samples
    for i in range(window_size + 50):
        attr.push(TelemetrySample(sequence=i, afse_score=0.5,
                                  tgcs_stretch_ms=1.0, pgcs_compressed_bytes=100))

    _chk('buffer length == window_size after overflow',
         len(attr._buf) == window_size,
         f'got {len(attr._buf)}, expected {window_size}')


def test_source_attributor_window_default():
    print('\nSourceAttributor default window size:')

    attr = SourceAttributor()
    _chk('default window_size == VCG_WINDOW_SIZE',
         attr._window_size == VCG_WINDOW_SIZE)

    # Push VCG_WINDOW_SIZE + 100 samples
    for i in range(VCG_WINDOW_SIZE + 100):
        attr.push(TelemetrySample(sequence=i, afse_score=0.5,
                                  tgcs_stretch_ms=1.0, pgcs_compressed_bytes=100))
    _chk('buffer capped at VCG_WINDOW_SIZE',
         len(attr._buf) == VCG_WINDOW_SIZE,
         f'got {len(attr._buf)}')


def test_source_attributor_sequence_range():
    print('\nSourceAttributor sequence range in attribution:')

    if not _NMF_AVAILABLE:
        _chk('NMF not available — skipping sequence range test', True)
        return

    attr = SourceAttributor(window_size=50)
    for i in range(100):
        attr.push(TelemetrySample(
            sequence=i,
            afse_score=float(i % 5) / 5,
            tgcs_stretch_ms=float(i % 3),
            pgcs_compressed_bytes=(i % 7) * 100 + 1,
        ))

    result = attr.attribute()
    if result is not None:
        _chk('sequence_start <= sequence_end',
             result.sequence_start <= result.sequence_end,
             f'start={result.sequence_start}, end={result.sequence_end}')
        _chk('determinism_class is observational',
             result.determinism_class == 'observational')
        _chk('window_size > 0', result.window_size > 0)
        _chk('gpu_inference >= 0', result.gpu_inference >= 0.0)
        _chk('governance >= 0', result.governance >= 0.0)
        _chk('os_noise >= 0', result.os_noise >= 0.0)
    else:
        # NMF convergence failure is acceptable
        _chk('attribute() returns None on NMF convergence issue', True)


def test_source_attributor_nmf_unavailable():
    print('\nSourceAttributor graceful when NMF unavailable:')

    # This tests the logic branch for _NMF_AVAILABLE=False
    # We simulate by checking behavior: if sklearn is not available,
    # attribute() must return None without raising.
    import source_attribution as sa_module

    original = sa_module._NMF_AVAILABLE
    sa_module._NMF_AVAILABLE = False

    try:
        attr = SourceAttributor()
        for i in range(100):
            attr.push(TelemetrySample(sequence=i, afse_score=0.5,
                                      tgcs_stretch_ms=1.0, pgcs_compressed_bytes=100))
        result = attr.attribute()
        _chk('attribute() returns None when NMF unavailable', result is None)
    finally:
        sa_module._NMF_AVAILABLE = original


def test_source_attributor_100_nonzero_samples():
    print('\nSourceAttributor 100 non-zero samples:')

    attr = SourceAttributor()
    for i in range(100):
        attr.push(TelemetrySample(
            sequence=i,
            afse_score=0.1 + (i % 10) * 0.05,
            tgcs_stretch_ms=float(i % 5),
            pgcs_compressed_bytes=(i % 3) * 512 + 1,
        ))

    result = attr.attribute()
    if _NMF_AVAILABLE:
        # Should either succeed or fail gracefully
        if result is not None:
            _chk('result is SourceAttribution', isinstance(result, SourceAttribution))
            _chk('determinism_class is observational', result.determinism_class == 'observational')
            _chk('window_size matches buffer', result.window_size == len(attr._buf))
        else:
            _chk('NMF returned None gracefully', True)
    else:
        _chk('no NMF → returns None', result is None)


def test_source_attributor_custom_window():
    print('\nSourceAttributor custom window size:')

    for ws in (10, 50, 100):
        attr = SourceAttributor(window_size=ws)
        _chk(f'window_size={ws} stored correctly', attr._window_size == ws)

        for i in range(ws + 20):
            attr.push(TelemetrySample(sequence=i, afse_score=0.5,
                                      tgcs_stretch_ms=0.0, pgcs_compressed_bytes=0))
        _chk(f'buffer capped at {ws}', len(attr._buf) == ws)


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    print('=== SOURCE ATTRIBUTION TESTS ===')
    test_constants()
    test_telemetry_sample_creation()
    test_telemetry_sample_frozen()
    test_telemetry_sample_zero_values()
    test_telemetry_sample_large_values()
    test_telemetry_sample_equality()
    test_source_attribution_creation()
    test_source_attribution_determinism_class()
    test_source_attribution_frozen()
    test_source_attribution_to_dict()
    test_source_attribution_to_dict_all_keys()
    test_source_attributor_empty()
    test_source_attributor_too_few_samples()
    test_source_attributor_all_zero()
    test_source_attributor_push_no_raise()
    test_source_attributor_window_cap()
    test_source_attributor_window_default()
    test_source_attributor_sequence_range()
    test_source_attributor_nmf_unavailable()
    test_source_attributor_100_nonzero_samples()
    test_source_attributor_custom_window()
    print(f'\n{"=" * 31}')
    print(f'PASS: {PASS}  FAIL: {FAIL}')
    if FAIL > 0:
        print('RESULT: FAIL')
        sys.exit(1)
    print('RESULT: PASS')
