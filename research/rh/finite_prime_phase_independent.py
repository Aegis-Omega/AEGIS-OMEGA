"""Independent check of the finite prime-power phase/sign normalisation.

EPISTEMIC_STATUS: INDEPENDENT_RECONSTRUCTION + INTERVAL_CERTIFIED
NOT CLAIMED: RH, the Weil positivity criterion, or any statement about zeros.

This does not read the integration/rh-weil-evidence-v1 artefacts (they are not
on the remote).  It restates the reported identities in an explicit
parameterisation and checks them with Arb balls, so that a disagreement with
the original formalisation is visible as a disagreement about the
parameterisation rather than about arithmetic.

PARAMETERISATION (stated so it can be refuted):
  For a prime power p^k the Weil prime term carries weight
      w(p,k) = log(p) * p^(-k/2).
  A prime-power entry is placed at the coordinate  x = k,  on the segment
  [0, m] whose length m is the multiplicity ceiling for that prime, and the
  complementary ("reflected") coordinate is  m - x.
  The reported affine normalisation is  m * (1 - y/L) = m - m*y/L.
  The reported odd-reflection premise is  S(m - x) = -S(x).
  The off-diagonal phase used here is
      S(x) = sin(2*pi*x / m)                      (odd about x = m/2)
  which is the smallest nontrivial choice satisfying the premise.
"""
from flint import arb, ctx

ctx.prec = 300


def affine_exact(m, y, L):
    """m*(1 - y/L) == m - m*y/L, checked as an interval identity."""
    lhs = arb(m) * (arb(1) - arb(y) / arb(L))
    rhs = arb(m) - arb(m) * arb(y) / arb(L)
    return lhs, rhs


def S(x, m):
    return (arb(2) * arb.pi() * arb(x) / arb(m)).sin()


def primes_upto(n):
    sieve = [True] * (n + 1)
    sieve[0:2] = [False, False]
    for i in range(2, int(n ** 0.5) + 1):
        if sieve[i]:
            for j in range(i * i, n + 1, i):
                sieve[j] = False
    return [i for i, ok in enumerate(sieve) if ok]


def weight(p, k):
    return arb(p).log() * arb(p) ** (-arb(k) / 2)


def offdiagonal_terms(P):
    """(p, k, m, weight) for every prime power p^k <= P."""
    out = []
    for p in primes_upto(P):
        kmax = 0
        while p ** (kmax + 1) <= P:
            kmax += 1
        for k in range(1, kmax + 1):
            out.append((p, k, kmax, weight(p, k)))
    return out


def direct_sum(terms):
    total = arb(0)
    for p, k, m, w in terms:
        total += w * S(k, m)
    return total


def complementary_sum(terms):
    total = arb(0)
    for p, k, m, w in terms:
        total += w * S(m - k, m)
    return total


def report(label, a, b):
    diff = a - b
    ok = diff.contains(arb(0))
    print(f"  {label:52} diff = {diff}  contains_zero={ok}")
    return ok


print("=" * 78)
print("1. affine normalisation  m(1 - y/L) == m - my/L   (exact, interval)")
allok = True
for m, y, L in [(1, 3, 7), (5, 2, 11), (12, 97, 101), (3, 1, 2), (40, 39, 40)]:
    lhs, rhs = affine_exact(m, y, L)
    allok &= report(f"m={m} y={y} L={L}", lhs, rhs)

print()
print("2. odd-reflection premise  S(m - x) == -S(x)")
for m in (2, 3, 5, 8, 13):
    for x in range(0, m + 1):
        d = S(m - x, m) + S(x, m)
        if not d.contains(arb(0)):
            print(f"  VIOLATED m={m} x={x} -> {d}")
            allok = False
print("  checked all 0<=x<=m for m in {2,3,5,8,13}: no violation" if allok else "  VIOLATIONS FOUND")

print()
print("3. direct vs complementary off-diagonal sum, and the finite-sum lift")
for P in (20, 100, 1000, 20000):
    terms = offdiagonal_terms(P)
    d = direct_sum(terms)
    c = complementary_sum(terms)
    ok = (d + c).contains(arb(0))
    allok &= ok
    print(f"  P={P:<6} terms={len(terms):<5} direct+complementary = {d + c}  contains_zero={ok}")

print()
print("4. induction: every truncation of the finite sum must also cancel")
terms = offdiagonal_terms(20000)
bad = 0
dpart = arb(0)
cpart = arb(0)
for i, (p, k, m, w) in enumerate(terms, 1):
    dpart += w * S(k, m)
    cpart += w * S(m - k, m)
    if not (dpart + cpart).contains(arb(0)):
        bad += 1
print(f"  truncations checked: {len(terms)}   failures: {bad}")
allok &= bad == 0


print()
print("=" * 78)
print("5. FALSIFICATION: does the finite-sum lift depend on arithmetic at all?")
print("   Replace log(p)p^(-k/2) with arbitrary weights.  If cancellation")
print("   survives, the lift carries no arithmetic content.")
import random

random.seed(20260830)
weight_independent = True
for trial in range(4):
    rnd = []
    for _ in range(500):
        m = random.randint(2, 30)
        k = random.randint(0, m)
        rnd.append((k, m, arb(random.uniform(-1e6, 1e6))))
    d = sum((w * S(k, m) for k, m, w in rnd), arb(0))
    c = sum((w * S(m - k, m) for k, m, w in rnd), arb(0))
    survived = (d + c).contains(arb(0))
    weight_independent &= survived
    print(f"   trial {trial}: 500 arbitrary weights -> cancels={survived}")

def S_broken(x, m):
    return (arb(2) * arb.pi() * arb(x) / arb(m)).sin() + arb("0.3")

rnd = [(random.randint(0, 30), 30, arb(random.uniform(-10, 10))) for _ in range(200)]
d = sum((w * S_broken(k, m) for k, m, w in rnd), arb(0))
c = sum((w * S_broken(m - k, m) for k, m, w in rnd), arb(0))
premise_load_bearing = not (d + c).contains(arb(0))
print(f"   premise broken (S not odd about m/2) -> cancels={not premise_load_bearing}")
assert weight_independent, "cancellation should be weight-independent"
assert premise_load_bearing, "breaking the premise must break the cancellation"

print()
print("6. INDEX-SET CLOSURE: does k -> m-k stay inside {1..m}?")
closure = {}
for P in (20, 100, 1000, 20000):
    inside = outside = 0
    for p, k, m, _w in offdiagonal_terms(P):
        if 1 <= m - k <= m:
            inside += 1
        else:
            outside += 1
    closure[P] = {"terms": inside + outside, "inside": inside, "outside": outside}
    print(f"   P={P:<6} terms={inside+outside:<5} inside={inside:<5} OUTSIDE={outside:<5}"
          f"  ({100*outside/(inside+outside):.1f}%)")
assert closure[20000]["outside"] == len(primes_upto(20000)), (
    "the escaping terms should be exactly the top power of each prime")

print()
print("=" * 78)
print("RESULT:", "ALL CHECKS PASS (interval-certified)" if allok else "FAILURES PRESENT")
assert allok

import json

receipt = {
    "prec_bits": ctx.prec,
    "phase": "S(x) = sin(2*pi*x/m)",
    "affine_identity_exact": True,
    "odd_reflection_verified_for_m": [2, 3, 5, 8, 13],
    "p_ladder": [20, 100, 1000, 20000],
    "n_prime_power_terms_p20000": len(offdiagonal_terms(20000)),
    "truncations_checked": len(offdiagonal_terms(20000)),
    "truncation_failures": 0,
    "cancellation_is_weight_independent": weight_independent,
    "premise_is_load_bearing": premise_load_bearing,
    "index_closure": closure,
    "pi_20000": len(primes_upto(20000)),
}
out = "research/rh/receipts/finite_prime_phase_independent_p20000.json"
with open(out, "w") as fh:
    json.dump(receipt, fh, indent=2, sort_keys=True)
    fh.write("\n")
print("receipt written:", out)
