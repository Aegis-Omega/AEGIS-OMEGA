# QForm Error Algebra v1

Status: exact-rational formal slice; constructive-real transport remains open.

## Scope

This slice machine-binds the rational algebra used by the conditional QForm error budget. It does not prove the Gaussian tail inequality, the composite-trapezoid remainder theorem, constructive-real transport, any formula-to-Weil identity, global Weil positivity, or RH.

## Proven interfaces

For nonnegative exact rationals `a, ahat, b, bhat, ea, eb` and positive denominator floor `m`, under

- `m <= b`, `m <= bhat`,
- `|ahat-a| <= ea`,
- `|bhat-b| <= eb`,

the formal kernel proves the cross-multiplied error bound

`|ahat*b - a*bhat| <= ea*b + a*eb`

and the normalized quotient bound

`|ahat/bhat - a/b| <= (ea*b + a*eb)/(m*m)`.

Machine authority is carried by:

- `normalized_quotient_cross_error_sound_v1`
- `normalized_quotient_stability_sound_v1`

The proposition-valued `*_v1` interfaces remain directly reducible by the preregistered concrete fixture.

## Authority boundary

```text
rational_cross_error_kernel_machine_bound              true
rational_normalized_quotient_stability_machine_bound   true
constructive_real_transport_machine_bound              false
gaussian_tail_inequality_machine_bound                 false
composite_trapezoid_theorem_machine_bound              false
analytic_error_bound_machine_bound                     false
formula_to_weil_operator_identity_proven               false
global_weil_positivity_proven                          false
rh_proven                                              false
```

Exact-head evidence is emitted by `.github/workflows/qform-error-algebra.yml` and must report both soundness theorems `Closed under the global context` before the receipt can assert the rational kernels as machine-bound.
