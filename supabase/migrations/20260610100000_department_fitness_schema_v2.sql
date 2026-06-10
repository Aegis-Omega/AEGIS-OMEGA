-- department_fitness_tracking — schema v2 addendum
-- Adds fitness_version, execution_id, parent_generation, artifact_hash per
-- cowork review: future fitness formula migrations will mix V1/V2/V3 scores
-- in the same convergence graph without an explicit version column.
-- Idempotent — ADD COLUMN IF NOT EXISTS safe to re-run.
-- EPISTEMIC TIER: T1

ALTER TABLE public.department_fitness_tracking
  ADD COLUMN IF NOT EXISTS fitness_version      text        NOT NULL DEFAULT '1.0',
  -- Pinned to FITNESS_VERSION in platform_helpers.py.
  -- Increment when the fitness formula changes.
  -- Allows filtering convergence queries to a single formula version.

  ADD COLUMN IF NOT EXISTS execution_id         text        NOT NULL DEFAULT '',
  -- The bridge execution_id (UUID) that produced this row.
  -- Allows joining fitness records back to /platform/executions/{id}.

  ADD COLUMN IF NOT EXISTS parent_generation    int         NOT NULL DEFAULT -1,
  -- generation - 1 at write time; -1 for generation 0 (no parent).
  -- Makes the evolution DAG queryable without a self-join.

  ADD COLUMN IF NOT EXISTS artifact_hash        text        NOT NULL DEFAULT '';
  -- SHA-256 of the department's output string for this generation.
  -- Allows content-dedup: if artifact_hash matches the previous generation,
  -- the department produced identical output and fitness delta = 0.

-- Index on fitness_version for cross-version convergence isolation
CREATE INDEX IF NOT EXISTS dft_fitness_version_idx
  ON public.department_fitness_tracking (fitness_version, objective_hash, mode);

-- Updated convergence view — includes fitness_version isolation
CREATE OR REPLACE VIEW public.dept_fitness_convergence AS
SELECT
  fitness_version,
  objective_hash,
  mode,
  generation,
  dept_role,
  ROUND(AVG(fitness_score)::numeric, 4)    AS avg_fitness,
  ROUND(AVG(viability_score)::numeric, 4)  AS avg_viability,
  COUNT(*)                                  AS sample_count,
  MAX(created_at)                           AS latest_at
FROM public.department_fitness_tracking
GROUP BY fitness_version, objective_hash, mode, generation, dept_role
ORDER BY fitness_version, objective_hash, mode, generation, avg_fitness DESC;

-- Department leaderboard view: rank departments by fitness within a version
-- Shows most improved (highest fitness delta) and most regressed (lowest delta)
-- across the last two generations for each objective+mode pair.
CREATE OR REPLACE VIEW public.dept_leaderboard AS
WITH ranked AS (
  SELECT
    fitness_version,
    objective_hash,
    mode,
    dept_role,
    generation,
    AVG(fitness_score) AS gen_fitness,
    LAG(AVG(fitness_score)) OVER (
      PARTITION BY fitness_version, objective_hash, mode, dept_role
      ORDER BY generation
    ) AS prev_gen_fitness
  FROM public.department_fitness_tracking
  GROUP BY fitness_version, objective_hash, mode, dept_role, generation
)
SELECT
  fitness_version,
  objective_hash,
  mode,
  dept_role,
  generation,
  ROUND(gen_fitness::numeric, 4)                        AS fitness,
  ROUND((gen_fitness - COALESCE(prev_gen_fitness, gen_fitness))::numeric, 4)
                                                         AS fitness_delta,
  RANK() OVER (
    PARTITION BY fitness_version, objective_hash, mode, generation
    ORDER BY gen_fitness DESC
  )                                                      AS rank
FROM ranked
ORDER BY fitness_version, objective_hash, mode, generation, rank;
