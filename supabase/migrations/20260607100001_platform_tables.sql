-- Revenue cycle results and agent activity tables for platform API persistence

CREATE TABLE IF NOT EXISTS public.revenue_cycles (
  id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cycle_id                  text NOT NULL UNIQUE,
  objective                 text NOT NULL,
  mode                      text NOT NULL DEFAULT 'revenue',
  departments_collaborated  integer NOT NULL DEFAULT 0,
  chain_valid               boolean NOT NULL DEFAULT true,
  projection_arr_usd        bigint,
  projection_tier           text,
  constitutional_verdict    text NOT NULL DEFAULT 'APPROVED'
                              CHECK (constitutional_verdict IN ('APPROVED', 'FLAG', 'QUARANTINE')),
  live                      boolean NOT NULL DEFAULT false,
  customer_email            text,
  created_at                timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS revenue_cycles_created_at_idx ON public.revenue_cycles (created_at DESC);
CREATE INDEX IF NOT EXISTS revenue_cycles_verdict_idx    ON public.revenue_cycles (constitutional_verdict);
CREATE INDEX IF NOT EXISTS revenue_cycles_email_idx      ON public.revenue_cycles (customer_email);

ALTER TABLE public.revenue_cycles ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'revenue_cycles' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY service_role_all ON public.revenue_cycles
      FOR ALL USING (true) WITH CHECK (true);
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS public.agent_activity (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  cycle_id        text,
  role            text NOT NULL,
  mode            text NOT NULL DEFAULT 'revenue',
  tool_calls      integer NOT NULL DEFAULT 0,
  input_tokens    integer NOT NULL DEFAULT 0,
  output_tokens   integer NOT NULL DEFAULT 0,
  duration_ms     integer NOT NULL DEFAULT 0,
  quality_score   integer,
  created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_activity_role_idx  ON public.agent_activity (role, created_at DESC);
CREATE INDEX IF NOT EXISTS agent_activity_cycle_idx ON public.agent_activity (cycle_id);

ALTER TABLE public.agent_activity ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies
    WHERE tablename = 'agent_activity' AND policyname = 'service_role_all'
  ) THEN
    CREATE POLICY service_role_all ON public.agent_activity
      FOR ALL USING (true) WITH CHECK (true);
  END IF;
END
$$;
