"""Exact reference kernel for F_65537[X] / (X^256 + 1).

The forward transform evaluates the polynomial at odd powers of a primitive
512th root, via a twisted length-256 NTT. Integer modular arithmetic only.
This is a mathematical reference, NOT an optimized or cryptographic primitive.
"""
from __future__ import annotations

Q = 65537
N = 256


def _primitive_generator() -> int:
    # q - 1 = 2^16; g^32768 != 1 implies its order is q-1.
    for value in range(2, Q):
        if pow(value, (Q - 1) // 2, Q) != 1:
            return value
    raise ArithmeticError("no multiplicative-group generator")


GENERATOR = _primitive_generator()
PSI = pow(GENERATOR, (Q - 1) // (2 * N), Q)
OMEGA = PSI * PSI % Q
PSI_INVERSE = pow(PSI, -1, Q)
OMEGA_INVERSE = pow(OMEGA, -1, Q)
N_INVERSE = pow(N, -1, Q)


def ntt(values: list[int], *, inverse: bool = False) -> list[int]:
    """Compute a size-256 modular NTT; inverse includes factor 1/N."""
    if len(values) != N:
        raise ValueError(f"expected {N} coefficients, received {len(values)}")
    data = [v % Q for v in values]
    position = 0
    for i in range(1, N):
        bit = N >> 1
        while position & bit:
            position ^= bit
            bit >>= 1
        position ^= bit
        if i < position:
            data[i], data[position] = data[position], data[i]
    root = OMEGA_INVERSE if inverse else OMEGA
    length = 2
    while length <= N:
        stage_root = pow(root, N // length, Q)
        half = length // 2
        for start in range(0, N, length):
            power = 1
            for j in range(half):
                left = data[start + j]
                right = data[start + j + half] * power % Q
                data[start + j] = (left + right) % Q
                data[start + j + half] = (left - right) % Q
                power = power * stage_root % Q
        length *= 2
    if inverse:
        return [v * N_INVERSE % Q for v in data]
    return data


def to_transform(coefficients: list[int]) -> list[int]:
    """Forward exact negacyclic evaluation at PSI^(2k+1)."""
    if len(coefficients) != N:
        raise ValueError(f"expected {N} polynomial coefficients")
    twist = 1
    twisted = []
    for coefficient in coefficients:
        twisted.append((coefficient % Q) * twist % Q)
        twist = twist * PSI % Q
    return ntt(twisted)


def from_transform(spectrum: list[int]) -> list[int]:
    """Inverse negacyclic NTT, returning coefficients in [0, Q)."""
    recovered = ntt(spectrum, inverse=True)
    twist = 1
    output = []
    for coefficient in recovered:
        output.append(coefficient * twist % Q)
        twist = twist * PSI_INVERSE % Q
    return output


def multiply(a: list[int], b: list[int]) -> list[int]:
    """Exact product in F_Q[X]/(X^N + 1), not cyclic convolution."""
    if len(a) != N or len(b) != N:
        raise ValueError(f"expected {N} coefficients in each factor")
    A = to_transform(a)
    B = to_transform(b)
    return from_transform([x * y % Q for x, y in zip(A, B)])
