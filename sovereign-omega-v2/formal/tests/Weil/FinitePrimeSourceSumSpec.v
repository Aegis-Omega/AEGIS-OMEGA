(*
  AEGIS Ω — finite prime-source sum RED contract v1

  This test is intentionally RED. The production module
  [FinitePrimeSourceSum] does not exist at this checkpoint.

  The dedicated workflow is responsible for proving that:
    1. the verified parent derivative and weight-bridge modules compile first;
    2. this file then fails specifically at logical-module resolution for
       [FinitePrimeSourceSum]; and
    3. no such RED result is promoted to theorem authority.

  A later GREEN transition must introduce the production module and replace
  this import-only contract with an explicit finite-sum theorem contract.
*)

Require Import FinitePrimeSourceSum.
