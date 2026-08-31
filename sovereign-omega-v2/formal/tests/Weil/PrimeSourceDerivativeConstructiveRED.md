# Prime Source Derivative — RED invariant

This branch begins with the theorem contract present and the production module absent.

Expected RED boundary: `Require Import PrimeSourceDerivativeConstructive` in `PrimeSourceDerivativeConstructiveSpec.v` must fail until the production theorem exists.

The target theorem is deliberately narrow: constructive CoRN IR differentiation of `a * sin(kappa * x)`. This checkpoint establishes no O0 trig transport, no prime-power arithmetic semantics, no finite prime sum, no Guinand–Weil explicit formula, no global Weil positivity, and no RH result.
