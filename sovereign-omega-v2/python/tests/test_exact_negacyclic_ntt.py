"""Deterministic 104-case, source-bound exact NTT validation.

No external dependencies, network, file writes, or authority to deploy.
Cross-checks convolution against a distinct O(N^2) multiplication algorithm.
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from exact_negacyclic_ntt import (
    GENERATOR, N, N_INVERSE, OMEGA, OMEGA_INVERSE, PSI, PSI_INVERSE,
    Q, from_transform, multiply, ntt, to_transform,
)


def schoolbook(a, b):
    if len(a) != N or len(b) != N:
        raise ValueError("coefficient count mismatch")
    result = [0] * N
    for i, left in enumerate(a):
        for j, right in enumerate(b):
            index = i + j
            if index < N:
                result[index] += left * right
            else:
                result[index - N] -= left * right
    return [value % Q for value in result]


def rejects_wrong_length(function, values):
    try:
        function(values)
    except ValueError:
        return True
    return False


def run_tests():
    rng = random.Random(20261116)
    results = []

    def check(name, condition):
        results.append((name, bool(condition)))

    # Six number-theoretic prerequisites.
    check('q_is_prime', all(Q % i != 0 for i in range(2, math.isqrt(Q) + 1)))
    check('q_minus_one_divisible_by_2n', (Q-1) % (2*N) == 0)
    check('full_order_generator', pow(GENERATOR, (Q-1)//2, Q) != 1)
    check('primitive_512th_root', pow(PSI, 2*N, Q) == 1 and pow(PSI, N, Q) == Q-1)
    check('primitive_256th_root', pow(OMEGA, N, Q) == 1 and pow(OMEGA, N//2, Q) == Q-1)
    check('modular_inverses', PSI * PSI_INVERSE % Q == 1 and
          OMEGA * OMEGA_INVERSE % Q == 1 and N * N_INVERSE % Q == 1)

    # Eight basic algebraic and boundary cases.
    zero = [0] * N
    one = [1] + [0] * (N-1)
    check('zero_roundtrip', from_transform(to_transform(zero)) == zero)
    check('identity_roundtrip', from_transform(to_transform(one)) == one)
    check('ones_roundtrip', from_transform(to_transform([1]*N)) == [1]*N)
    check('minus_one_roundtrip', from_transform(to_transform([-1]*N)) == [Q-1]*N)
    check('zero_product', multiply(zero, one) == zero)
    check('identity_product', multiply(one, [3*i-500 for i in range(N)]) ==
          [(3*i-500)%Q for i in range(N)])
    a = [0]*N; a[N-1] = 1
    b = [0]*N; b[1] = 1
    check('X_to_256_is_minus_one', multiply(a, b) == [Q-1] + [0]*(N-1))
    check('reject_bad_length', rejects_wrong_length(to_transform, [1]*(N+1)))

    # 64 exact inverse checks on deterministic bounded integer vectors.
    for index in range(64):
        if index < 32:
            v = [rng.randint(-2*Q, 2*Q) for _ in range(N)]
        else:
            v = [0]*N
            for _ in range(12):
                v[rng.randrange(N)] = rng.randint(-200000, 200000)
        check(f'inverse_{index:02}', from_transform(to_transform(v)) == [x%Q for x in v])

    # 16 independent negacyclic multiplication tests.
    for index in range(16):
        if index < 8:
            a = [rng.randint(-Q, Q) for _ in range(N)]
            b = [rng.randint(-Q, Q) for _ in range(N)]
        else:
            a, b = [0]*N, [0]*N
            for _ in range(5):
                a[rng.randrange(N)] = rng.randrange(Q)
                b[rng.randrange(N)] = rng.randrange(Q)
        check(f'product_{index:02}', multiply(a, b) == schoolbook(a, b))

    # Eight direct polynomial evaluations at odd 512th roots.
    polynomial = [rng.randrange(Q) for _ in range(N)]
    spectrum = to_transform(polynomial)
    for index in (0, 1, 2, 7, 16, 64, 127, 255):
        x = pow(PSI, 2*index + 1, Q)
        accumulator, factor = 0, 1
        for coefficient in polynomial:
            accumulator = (accumulator + coefficient*factor)%Q
            factor = factor*x%Q
        check(f'evaluation_{index}', spectrum[index] == accumulator)

    # Two other input validation cases.
    check('ntt_short_rejected', rejects_wrong_length(ntt, [1]*3))
    check('inverse_short_rejected', rejects_wrong_length(from_transform, [1]*3))

    failed = [name for name, passed in results if not passed]
    print(f'AEGIS_EXACT_NEGACYCLIC_NTT: {len(results) - len(failed)}/{len(results)} PASS')
    if failed:
        raise AssertionError('Failed cases: ' + ', '.join(failed))
    if len(results) != 104:
        raise AssertionError(f'Unexpected case count: {len(results)} != 104')
    return len(results)


if __name__ == '__main__':
    run_tests()
