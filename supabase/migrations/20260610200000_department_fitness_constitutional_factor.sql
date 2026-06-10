-- AEGIS-Ω — Add constitutional_factor column to department_fitness_tracking
-- Epistemic Tier: T1
-- V1.1 fitness formula: constitutional_factor is stored per-row so leaderboard
-- queries can filter/weight by constitutional audit outcome independently.

ALTER TABLE public.department_fitness_tracking
  ADD COLUMN IF NOT EXISTS constitutional_factor numeric(4,3) NOT NULL DEFAULT 0.85;

COMMENT ON COLUMN public.department_fitness_tracking.constitutional_factor IS
  'V1.1 — CONSTITUTIONAL_FACTORS[verdict]: APPROVED=1.00 FLAG=0.70 QUARANTINE=0.20 null=0.85';

CREATE INDEX IF NOT EXISTS dft_constitutional_factor_idx
  ON public.department_fitness_tracking(constitutional_factor, fitness_version);
