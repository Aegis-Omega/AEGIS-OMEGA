(*
  AEGIS Ω — constructive trig viability probe

  DIAGNOSTIC ONLY.  This file asks the cheapest load-bearing question before
  attempting a constructive prime-diagonal trig/calculus implementation:
  does the Coq 8.20 constructive-real API already expose CRsin/CRcos/CRpi?

  Expected today: all three names are absent from the imported constructive
  Abstract/Cauchy surface.  `Fail Check` makes that absence executable.  If an
  upstream/version change introduces any of these names, this probe becomes RED
  and forces a fresh trust/API review instead of silently changing semantics.

  This is not proof authority and proves nothing about Weil or RH.
*)

From Coq Require Import Reals.Abstract.ConstructiveReals.
From Coq Require Import Reals.Abstract.ConstructiveLimits.
From Coq Require Import Reals.Abstract.ConstructiveSum.
From Coq Require Import Reals.Abstract.ConstructivePower.
From Coq Require Import Reals.Abstract.ConstructiveMinMax.
From Coq Require Import Reals.Cauchy.ConstructiveRcomplete.
From Coq Require Import Reals.Cauchy.ConstructiveCauchyReals.
From Coq Require Import Reals.Cauchy.ConstructiveCauchyRealsMult.
From Coq Require Import Reals.Cauchy.ConstructiveCauchyAbs.

Check CRealConstructive.

Fail Check CRsin.
Fail Check CRcos.
Fail Check CRpi.
