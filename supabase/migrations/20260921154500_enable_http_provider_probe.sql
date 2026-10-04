-- Enables raw HTTP probing for provider secret-presence checks.
-- Used only for non-model malformed-request probes where JSON parsing fails
-- before any upstream model execution can occur.

create extension if not exists http with schema extensions;
