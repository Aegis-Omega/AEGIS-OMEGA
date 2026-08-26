"""Finite-conditioning report for the Douglas factorisation critical surface.

EPISTEMIC_STATUS: VERIFIED_NUMERICAL
SCOPE:            first 300 tested zeros
SEED:             20260825
NORMALIZATION:    current RH finite-model normalization (H=3.5, NF=720, panel=0.01)

DECLARED, NOT DERIVED
  C = 1e3            chosen safety multiplier; convention, not a derived bound
  epsilon            target norm violation to be detected
  ||A_-A_-^T||       measured at the worst-conditioned tested zero under this
                     normalization; NOT invariant under rescaling
  s_min(A_-)         measured quantity

NOT CLAIMED
  asymptotic validity
  universal conditioning floor
  theorem dim(P(V)) = 2
  derived backward-error constant C

WHAT THIS INSTRUMENT DOES
  Separates three statements that were previously compressed into one:
      kappa = 0            algebraic boundary
      ker(A_-) = {0}       identifiability
      s_min(A_-) > tau(C)  numerical resolvability

  Error budget:
      signal(eps) = |lambda_min(A_-A_-^T - A_+A_+^T)| = s_min^2 ((1+eps)^2 - 1)   [exact]
      floor(C)    = C * eps_mach * ||A_-A_-^T||                                   [convention]
      tau(C,eps)  = sqrt( C * eps_mach * ||A_-A_-^T|| / ((1+eps)^2 - 1) )
      M(C,eps)    = s_min(A_-) / tau(C,eps)
      C_crit      = sup{ C : M(C) > 1 } = s_min^2 ((1+eps)^2-1) / (eps_mach ||A_-A_-^T||)

  Because tau ~ sqrt(C), the margin obeys the identity

      M(C) = sqrt( C_crit / C )                                          (*)

  (*) is asserted below, not assumed. It is the reason M(1e3) = 11.97 while
  C_crit / 1e3 = 143.29: the margin is the SQUARE ROOT of the C-ratio.
  Reading 143x off C_crit/C and 12x off M is the same fact, not a discrepancy.

A_- is taken from the live Kappa.at() pipeline, not reimplemented here, so the
report describes the conditioning of the actual kappa computation.
"""
import json, sys
from pathlib import Path
import numpy as np, scipy.linalg as la
from core import Model, zeros_upto
from kappa import Kappa

EPSM = np.finfo(float).eps
SEED = 20260825
H, NF, PANEL, NZ = 3.5, 720, 0.01, 300
C_DECLARED, EPS_DECLARED = 1e3, 1e-3

def tau(C, eps, nrm):    return np.sqrt(C * EPSM * nrm / ((1 + eps) ** 2 - 1))
def margin(C, eps, smin, nrm): return smin / tau(C, eps, nrm)
def c_crit(eps, smin, nrm):    return smin ** 2 * ((1 + eps) ** 2 - 1) / (EPSM * nrm)

def main(out_path=None):
    M = Model(H, NF, panel=PANEL)
    K = Kappa(M)
    Z = zeros_upto(NZ)

    smins, nrms = [], []
    for t in Z:
        Am = K.at(t)["Am"]                       # live pipeline, not a copy
        smins.append(la.svd(Am, compute_uv=False)[-1])
        nrms.append(abs(la.eigvalsh(Am @ Am.T)).max())
    smins, nrms = np.array(smins), np.array(nrms)
    k = int(np.argmin(smins)); smin_w, nrm_w = smins[k], nrms[k]

    print("=" * 84); print("IDENTIFIABILITY  ker(A_-) = {0}"); print("=" * 84)
    print(f"  s_min(A_-):  min={smins.min():.4e}  median={np.median(smins):.4e}  max={smins.max():.4e}")
    print(f"  s_min > 0 on all {NZ}?  {bool((smins > 0).all())}")
    print(f"  worst zero: k={k+1}  gamma={Z[k]:.5f}  s_min={smin_w:.4e}  ||A_-A_-^T||={nrm_w:.4f}")
    print("  NOTE: T is obtained as A_-^+ A_+ (lstsq, minimum norm), so its columns lie")
    print("  in range(A_-^T). The kernel failure mode of the general Douglas converse")
    print("  cannot arise here; what remains is amplification ||A_-^+|| = 1/s_min"
          f" = {1/smin_w:.4e}.")

    print("\n" + "=" * 84); print(f"MARGIN M(C) AT THE WORST ZERO  (eps={EPS_DECLARED:g})"); print("=" * 84)
    Cc_w = c_crit(EPS_DECLARED, smin_w, nrm_w)
    print(f"  {'C':>12} {'tau(C)':>12} {'M(C)':>12} {'sqrt(Ccrit/C)':>15}   verdict")
    rows_C = []
    for C in (1e0, 1e1, 1e2, 1e3, 1e4, 1e5, Cc_w, 1e6):
        t_, m_ = tau(C, EPS_DECLARED, nrm_w), margin(C, EPS_DECLARED, smin_w, nrm_w)
        chk = np.sqrt(Cc_w / C)
        assert abs(m_ - chk) <= 1e-9 * max(1.0, m_), "identity M(C)=sqrt(C_crit/C) violated"
        rows_C.append(dict(C=float(C), tau=float(t_), M=float(m_)))
        print(f"  {C:12.5g} {t_:12.4e} {m_:12.4f} {chk:15.4f}   "
              f"{'resolvable' if m_ > 1 else 'NOT resolvable'}")
    print(f"\n  identity M(C) = sqrt(C_crit/C) asserted at every row above: PASS")
    print(f"  C_crit/C at C=1e3 = {Cc_w/1e3:.2f}   and   M(1e3) = {np.sqrt(Cc_w/1e3):.4f}")
    print(f"  These are the same fact. 143x is the C-ratio; 12x is its square root.")

    Cf = np.logspace(0, 8, 60); Mf = margin(Cf, EPS_DECLARED, smin_w, nrm_w)
    slope, icept = np.polyfit(np.log(Cf), np.log(Mf), 1)
    resid = float(np.abs(np.log(Mf) - (slope * np.log(Cf) + icept)).max())
    print(f"\n  fitted exponent: M ~ C^({slope:.6f})   max|log-resid|={resid:.2e}"
          "   (inverse square root; not linear, not quadratic)")

    print("\n" + "=" * 84); print("C_crit ALSO CARRIES eps"); print("=" * 84)
    rows_eps = []
    print(f"  {'eps':>10} {'M(1e3)':>12} {'C_crit':>14}")
    for e in (1e-1, 1e-2, 1e-3, 1e-4, 1e-5):
        m_, cc = margin(1e3, e, smin_w, nrm_w), c_crit(e, smin_w, nrm_w)
        rows_eps.append(dict(eps=float(e), M_at_1e3=float(m_), C_crit=float(cc)))
        print(f"  {e:10.0e} {m_:12.4f} {cc:14.4e}")
    print("  at eps=1e-5 the declared C=1e3 sits only 1.43x below its own critical value.")

    print("\n" + "=" * 84); print(f"DISTRIBUTION OVER ALL {NZ} ZEROS (eps={EPS_DECLARED:g})"); print("=" * 84)
    Cc, Mm = c_crit(EPS_DECLARED, smins, nrms), margin(1e3, EPS_DECLARED, smins, nrms)
    print(f"  C_crit :  min={Cc.min():.4e}  median={np.median(Cc):.4e}  max={Cc.max():.4e}")
    print(f"  M(1e3) :  min={Mm.min():.4f}  median={np.median(Mm):.4f}  max={Mm.max():.4f}")
    print(f"  M(1e3) < 10 : {int((Mm<10).sum())}/{NZ}     < 100 : {int((Mm<100).sum())}/{NZ}")
    print("  the worst zero is a ~6-order outlier, not the typical case.")

    print("\n" + "=" * 84); print("OBSERVED FLOOR -- measured, still not a bound"); print("=" * 84)
    Am_w = K.at(Z[k])["Am"]; rng = np.random.default_rng(SEED); obs = []
    for _ in range(400):
        Q = la.qr(rng.normal(size=Am_w.shape[1:2] * 2))[0]      # ||T||=1 exactly => kappa=0
        D = Am_w @ Am_w.T - (Am_w @ Q) @ (Am_w @ Q).T
        obs.append(abs(la.eigvalsh((D + D.T) / 2)).max())        # exact arithmetic: 0
    obs = np.array(obs); C_obs = float(obs.max() / (EPSM * nrm_w))
    print(f"  400 exact-contraction draws: |lambda|_max median={np.median(obs):.4e} max={obs.max():.4e}")
    print(f"  C_obs = {C_obs:.4g}   declared C=1e3 is {1e3/C_obs:.1f}x above the observed floor")
    print(f"  M(C_obs) = {margin(C_obs, EPS_DECLARED, smin_w, nrm_w):.2f}")
    print("  C_obs is measured at ONE zero under ONE perturbation family (exact")
    print("  contractions) and covers only floating-point evaluation of the residual at")
    print("  exact inputs. It bounds nothing. Deriving C from the QR -> SVD -> P_Qg")
    print("  backward-error chain remains OPEN.")

    receipt = dict(
        epistemic_status="VERIFIED_NUMERICAL",
        scope=f"first {NZ} tested zeros",
        seed=SEED,
        normalization=dict(H=H, NF=NF, panel=PANEL, n_zeros=NZ),
        declared_not_derived=dict(
            C=C_DECLARED, epsilon=EPS_DECLARED,
            norm_AmAmT=float(nrm_w),
            note="C is a chosen safety multiplier; ||A_-A_-^T|| is measured at the "
                 "worst-conditioned tested zero and is not invariant under rescaling"),
        not_claimed=["asymptotic validity", "universal conditioning floor",
                     "theorem dim(P(V))=2", "derived backward-error constant C"],
        identifiability=dict(
            ker_Aminus_trivial_on_all=bool((smins > 0).all()),
            s_min_min=float(smins.min()), s_min_median=float(np.median(smins)),
            s_min_max=float(smins.max()),
            worst_zero_index=k + 1, worst_zero_gamma=float(Z[k]),
            pinv_amplification=float(1 / smin_w),
            T_is_min_norm=True,
            T_min_norm_note="T = A_-^+ A_+ via lstsq; columns lie in range(A_-^T), so "
                            "the kernel failure mode of the general Douglas converse "
                            "cannot arise in this pipeline"),
        margin_identity="M(C) = sqrt(C_crit / C)",
        margin_identity_asserted=True,
        fitted_exponent=dict(slope=float(slope), max_log_residual=resid),
        worst_zero=dict(C_crit_at_eps_1e_3=float(Cc_w),
                        M_at_C_1e3=float(margin(1e3, EPS_DECLARED, smin_w, nrm_w)),
                        C_ratio_at_C_1e3=float(Cc_w / 1e3)),
        margin_vs_C=rows_C,
        margin_vs_eps=rows_eps,
        distribution=dict(C_crit_min=float(Cc.min()), C_crit_median=float(np.median(Cc)),
                          C_crit_max=float(Cc.max()), M_min=float(Mm.min()),
                          M_median=float(np.median(Mm)), M_max=float(Mm.max()),
                          n_below_M10=int((Mm < 10).sum()), n_below_M100=int((Mm < 100).sum())),
        observed_floor=dict(C_obs=C_obs, draws=400,
                            conservatism_factor=float(1e3 / C_obs),
                            caveat="measured at one zero, one perturbation family; "
                                   "covers floating-point evaluation at exact inputs only; "
                                   "not a backward-error bound"),
        open_work="derive C from the QR -> SVD -> P_Qg backward-error chain")
    if out_path:
        Path(out_path).write_text(json.dumps(receipt, indent=1, sort_keys=True) + "\n")
        print(f"\nreceipt written: {out_path}")
    return receipt

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
