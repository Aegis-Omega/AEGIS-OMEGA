(**
  RED contract: complex scalar prime-term support v1.

  This file checks only the formula-level support layer.  It intentionally
  does not require [concrete_prime_term_semantics_v1], whose carrier binding
  remains a separate open obligation.
*)

Require Import ConcreteFiniteGuinandWeilSemanticsV1.

Check finite_prime_positive_integer_ir_v1.
Check finite_prime_reciprocal_ir_v1.
Check finite_prime_scalar_term_cc_v1.
Check canonical_q_reciprocal_ir_v1.
Check canonical_q_prime_scalar_term_cc_v1.
Check finite_prime_scalar_term_leading_zero_v1.
Check finite_prime_scalar_term_tail_index_v1.
