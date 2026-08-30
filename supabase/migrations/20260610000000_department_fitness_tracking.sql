-- department_fitness_tracking: per-department evolutionary fitness scores
-- across consecutive swarm generations for the same objective+mode pair.
-- Used by evaluate_generation_fitness() + store_generation_fitness() in platform_helpers.py.
-- EPISTEMIC TIER: T1 — empirically validated metric (fitness convergence observed across runs)

CREATE TABLE IF NOT EXISTS public.department_fitness_tracking (
  id                     uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  objective_hash         text        NOT NULL,  -- SHA-256 of lowercased objective
  mode                   text        NOT NULL CHECK (mode IN (
                           'revenue','analysis','gtm','retention',
                           'competitive','technical','regulatory','fundraising'
                         )),
  generation             int         NOT NULL CHECK (generation >= 0),
  cycle_id               text        NOT NULL,  -- collaboration cycle_id that produced this score
  dept_role              text        NOT NULL,  -- e.g. 'Strategy', 'Guardian'
  fitness_score          numeric(6,4) NOT NULL CHECK (fitness_score BETWEEN 0 AND 1),
  -- Composite: 0.35×length_stability + 0.25×objective_coverage + 0.25×lexical_consistency + 0.15×viability
  viability_score        numeric(6,4) NOT NULL DEFAULT 1.0 CHECK (viability_score BETWEEN 0 AND 1),
  -- Metabolic constraint: VIABILITY_CHAR_BUDGET / output_length, capped at 1.0
  constitutional_verdict text        NOT NULL CHECK (constitutional_verdict IN ('APPROVED','FLAG','QUARANTINE')),
  created_at             timestamptz NOT NULL DEFAULT now()
);

-- Fast lookup: convergence queries for a given objective across generations
CREATE INDEX IF NOT EXISTS dft_objective_mode_gen_idx
  ON public.department_fitness_tracking (objective_hash, mode, generation);

-- Fast lookup: track a specific department across generations
CREATE INDEX IF NOT EXISTS dft_dept_role_idx
  ON public.department_fitness_tracking (dept_role, objective_hash, mode);

-- Row-level security: service role has full access; no direct client access
ALTER TABLE public.department_fitness_tracking ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'department_fitness_tracking' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY service_role_all ON public.department_fitness_tracking
      USING (auth.role() = 'service_role')
      WITH CHECK (auth.role() = 'service_role');
  END IF;
END $$;

-- Convergence view: average fitness per dept per generation (useful for charting evolution)
CREATE OR REPLACE VIEW public.dept_fitness_convergence AS
SELECT
  objective_hash,
  mode,
  generation,
  dept_role,
  ROUND(AVG(fitness_score)::numeric, 4)    AS avg_fitness,
  ROUND(AVG(viability_score)::numeric, 4)  AS avg_viability,
  COUNT(*)                                  AS sample_count,
  MAX(created_at)                           AS latest_at
FROM public.department_fitness_tracking
GROUP BY objective_hash, mode, generation, dept_role
ORDER BY objective_hash, mode, generation, avg_fitness DESC;
