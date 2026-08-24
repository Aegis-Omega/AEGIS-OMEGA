"""Shared runtime limits for Anthropic Managed Agents."""

# This limit is applied when creating every Managed Agents session.  Registration
# metadata is informational only and must never be treated as an enforcement point.
MANAGED_AGENT_MAX_TOKENS = 4096
