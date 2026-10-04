# Feshbach certificates beyond log 3 (Arb), general L

Same method as `../feshbach_arb_v1/` (L = 1.05), generalised to every prime power q < e^L in the symbol
S(ξ) = Re ψ(1/4 + iξ/2) − log π − Σ_q 2Λ(q) q^{−1/2} cos(ξ log q), in the Krein LP and in the Arb verifier.

| L | prime powers | low block | Krein + slack | c_∞ | Ritz λ₁ | certified μ |
|---|---|---|---|---|---|---|
| 1.2 | 2, 3 | N = 100 (199 dims), rows ≤ 10000 | m = 1.98, slack on [0.05, 450], step 1 | ≥ 1.9206 | 6.639e-5 | **5e-5** (fails 6e-5) |
| 1.3 | 2, 3 | N = 100, rows ≤ 42000 | m = 1.95, same slack layout | ≥ 1.8881 | 2.320e-6 | **2.1e-6** |

Claim (T1, interval arithmetic, not Lean): Q(G) ≥ μ‖G‖² for every moment-zero G in L²[0, L].
Fixed widths, not RH. Each `L*/RECEIPT.json` lists inputs, SHA-256 of every output and the unformalised steps.

Reproduce: `./run_all.sh 1.2 100 10000 2.0 450 1.0 1.98 5e-5` (and `1.3 100 42000 2.0 450 1.0 1.95 2.1e-6`).
`blocks_*.json` is stored gzipped; `gunzip -k` it before running `schur_arb.py` by hand.
