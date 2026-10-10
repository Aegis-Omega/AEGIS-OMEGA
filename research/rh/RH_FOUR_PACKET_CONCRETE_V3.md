# Concrete four-packet continuation V3

Source parent: `db97cff9d4b918b727033c08cbb8bf37b2981039` (PR #594).
Integration ancestor: `cfe368ce2ffa0d196a4319c02b956997edf9f3fa` (PR #580).

## Status and exact scope

This is a written analytic composition with three new Lean SOURCE CANDIDATES.
No Lean compiler was available in the local runtime. No kernel process or
axiom audit ran. The scalar and source-contract tests below are NOT substitutes.
The source contains no new axiom declarations, sorry, admit or native_decide.
This static observation does not certify imported assumptions or successful
elaboration. Every newly declared theorem has a requested `#print axioms`.

The improvement over V2 is replacement of its ten supplied analytic premises
by actual moment/support arguments on a nonempty finite dyadic family.
The target is NOT an arbitrary compact-smooth test function and NOT RH.

## 1. The n=8 prime window

Write L=log(2), P_j=T_(jL)g, and E=energy(g). For total log-support width
at most 1/32, the imported V2.8 transport gives

    exp(u/2) mixed(P_0,P_3)(exp(u)) = R_g(u+3L).

Its right side is zero when |u+3L|>1/32. Positive-integer samples are zero
because log(m)>=0 for m>=1. A reciprocal sample at 1/m can survive only if

    |log(m)-log(8)| <= 1/32.

The elementary exponential bounds exp(1/32)<32/31 and
exp(-1/32)>=31/32 imply

    7 < 8*(31/32) <= m < 8*(32/31) < 9.

Thus m=8. This argument quantifies over ALL positive integers; the Python
finite enumeration only checks the rational envelope and is not its proof.
The original sum is indexed by n with m=n+1, so its surviving term is n=7.
At the centre the imported mixed-correlation identity gives

    mixed(P_0,P_3)(1/8) = 2*sqrt(2)*E.

Since Lambda(8)=Lambda(2^3)=log(2),

    PrimeSum(mixed(P_0,P_3)) = log(2)*sqrt(2)*E/4
                              = log(2)*E/sqrt(8).

No factor 3 is introduced into Lambda. The scalar is <1/4 using
log(2)<7/10 and sqrt(2)<10/7. The latter follows from sqrt(2)^2=2 and
sqrt(2)>=0. The zero centre term and the existing V3.1 moment-based
Archimedean bound <=E/100 therefore give

    |B(P_0,P_3)| <= (1/4+1/100) E = (13/50) E.

## 2. Equal-gap transport covers all other entries

The existing logarithmic mixed identity depends only on d2-d1. Cancelling
its nonzero exponential factor proves equality of mixed functions for equal
gaps on x>0. The positive-support carrier proves both functions zero on x<=0.
Consequently the complete actual B values, not just prime samples, agree.

The pairs 01,12,23 inherit the existing adjacent bound 51E/100. The pairs
02,13 inherit the existing next-neighbour bound 9E/25. The new n=8 argument
supplies 03. All six unordered pairs are present; Hermitian symmetry handles
the reverse orientations through the already existing four-packet expansion.

## 3. A genuinely finer canonical packet

The new bump has inner radius 1/512 and outer radius 1/256. The imported
momentKiller preserves compact support, gives the two logarithmic moments,
and is injective on the relevant compact-smooth class. Thus its output is
nonzero because the bump equals 1 at zero.

The output support lies in [-1/256,1/256], strictly inside [-1/128,1/128].
In particular the two endpoint-vanishing arguments use the smaller interval;
closed target support alone would not justify those endpoint arguments.
Canonical guarded log transport supplies a nonzero gFine in the original
WeilCompactSmoothGV1 carrier, with WeilMomentConditionsV1 and
WidthOneSixtyFourAt gFine 0. Existing gNarrow is unchanged and is not silently
claimed to satisfy the narrower predicate.

For any g in that narrower class, every translation preserves total width
and energy. The V2 narrower-diagonal candidate then supplies all four actual
diagonal bounds 32E/25. Its analytic derivation and imported dependencies
still need their own pinned kernel replay; V3 does not skip them.

## 4. Composition with the existing all-coefficient certificate

For arbitrary complex z_0,...,z_3 put G=sum_j z_j P_j. The existing V2
four-packet bridge is applied to exactly the original repository B, with
all four diagonal and six cross estimates proved in the V3 source above.
The result targeted by `four_packet_coercive_v3` is

    Re(RHS(Autocorrelation(G)))
      <= -(2/125) E * (|z_0|^2+|z_1|^2+|z_2|^2+|z_3|^2).

The exact comparison constant is 158/125 and
32/25-158/125=2/125. No division by E is used. The theorem's only analytic
inputs are the original moment and narrower-support predicates. Specializing
to gFine discharges those inputs and yields `canonical_four_packet_sign_v3`
with only four complex coefficient parameters. This is still a four-packet
family, not the universal FinalSignResidualV1 quantifier.

## 5. Reproduction and evidence boundary

From the root of the V3 package:

    python -m unittest discover -s research/rh -p test_four_packet_concrete_v3.py -v
    python -O -m unittest discover -s research/rh -p test_four_packet_concrete_v3.py -v

The new suite has 12 exact-arithmetic tests and 5 static source-contract tests.
It was first run with the new modules absent: those 5 contracts failed. With
the sources present all 17 tests passed, also under Python optimization.
The inherited 16 V2 tests were rerun and passed in both modes. Separately,
symbolic polynomial/rational checks verified the n=8 coefficient, its square-
root normalization, equal-gap algebra and the translation-energy scalar.
None of these executes the analytic integrals or the Lean kernel.

For Lean replay use the exact candidate checkout, Lean 4.33.1 and Mathlib
0df444a360eaa60ab8c11dca51a86af692955474. Rebuild transitive repository imports
from source. In addition to the V2 modules, build RHFourBlockPrimeEightV3,
RHFineMomentPacketV3 and RHFourBlockConcreteV3 in that order. Archive source
hashes, the actual checkout SHA, toolchain/dependency SHAs, per-module exit
codes and all axiom output. Do not silently reuse stale repository oleans.

A runnerless/zero-step status, skipped compile, source scan or green Python
run is never a kernel PASS. No workflow file, #580 integration branch,
.claude.json, main, access setting or authority boundary is changed here.

    LEAN_KERNEL = NOT_RUN
    LEAN_AXIOM_AUDIT = NOT_RUN
    ACTUAL_FOUR_PACKET_COMPOSITION = SOURCE_CANDIDATE
    GLOBAL_WEIL_SIGN = NOT_PROVEN
    RIEMANN_HYPOTHESIS = NOT_PROVEN
    AUTHORITY_EFFECT = NONE
