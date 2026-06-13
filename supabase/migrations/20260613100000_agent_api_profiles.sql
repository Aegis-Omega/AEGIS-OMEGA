-- Agent API profiles — outbound API credential store for agent harness.
-- Raw API keys are NEVER stored. Only SHA-256 hash is persisted.
-- Agents read this catalog (read-only projection) via GET /platform/tools.
-- All tool invocations flow through the mediated SSE channel.

CREATE TABLE IF NOT EXISTS agent_api_profiles (
  id             uuid        PRIMARY KEY DEFAULT gen_random_uuid(),
  profile_name   text        NOT NULL,
  api_name       text        NOT NULL,
  endpoint_url   text        NOT NULL,
  key_hash       text        NOT NULL,   -- SHA-256 of raw API key; raw key never stored
  capabilities   jsonb       NOT NULL DEFAULT '[]',
  tier_required  text        NOT NULL DEFAULT 'explorer'
                             CHECK (tier_required IN ('explorer', 'operator', 'sovereign')),
  owner_email    text        NOT NULL,
  revoked        bool        NOT NULL DEFAULT false,
  created_at     timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS agent_api_profiles_profile_idx ON agent_api_profiles (profile_name);
CREATE INDEX IF NOT EXISTS agent_api_profiles_owner_idx   ON agent_api_profiles (owner_email);
CREATE INDEX IF NOT EXISTS agent_api_profiles_revoked_idx ON agent_api_profiles (revoked)
  WHERE revoked = false;
