# Security Policy

## Supported Versions

Only the `main` branch is supported. There are no versioned releases; fixes land on
`main` and deploy from there.

## Reporting a Vulnerability

Report suspected vulnerabilities privately via **GitHub private vulnerability reporting**
for `Aegis-Omega/AEGIS-OMEGA`: repository **Security** tab → **Report a vulnerability**.

Do **not** open public issues or pull requests for undisclosed security problems.

Include in your report:
- A clear description of the issue and affected component(s)
- Steps to reproduce (proof of concept if available)
- Potential impact and severity assessment
- Any suggested remediation or mitigations

**Response target: 72 hours** for initial acknowledgment and triage. If a report is
accepted we will coordinate fix and disclosure timing with you; if declined we will
explain why.

## Scope

In scope:
- The governance bridge service (`sovereign-omega-v2/python/`, deployed as Cloud Run
  `aegis-vertex`), including all `/platform/*`, `/claude`, and `/node` endpoints
- The hub storefront (`hub/`, aegisomega.com) and its payment flow
- Supabase edge functions (`supabase/functions/` — payment verification, key issuance,
  agent/chat/notify/slack handlers)
- The commercial tools and shared libraries they embed (`packages/shared/`)

Out of scope: sibling research repositories, third-party services themselves
(PayPal/Stripe/Supabase/GCP), and findings that require physical access.

## Bounty

There is no bounty program. Good-faith reports are appreciated and will be credited on
request.
