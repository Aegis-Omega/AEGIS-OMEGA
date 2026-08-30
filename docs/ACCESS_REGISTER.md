# Access register — accepted invites, memberships, and entitlements

**Purpose.** The revenue model is acceptance-driven: signals → invites → meetings →
artifacts → certificates/proof → monetization. That model has one structural weakness —
the acceptances only exist as scattered email. This register is the proof stage: what
was granted, by whom, when it expires, and what outcome it is supposed to enable.

**Evidence rule.** Every row cites a mail artifact. Rows without one are marked
UNVERIFIED and carry no authority. Derived from a 90-day Gmail sweep on 2026-07-26.

---

## A. Live deadlines — act or lose

| When | What | Status | Note |
|------|------|--------|------|
| **unconfirmed** | **Build with Gemini XPRIZE** — $2M pool, **$500k first place** | ⚠️ **STARTED, NOT SUBMITTED** | "Submission to Build with Gemini XPRIZE started" (Jul 17). Devpost then asked "Still planning on entering?" (Jul 23) — that nudge only fires on incomplete submissions. **Confirm the deadline on the Devpost project page.** |
| Jul 29, 11:00 PT | Zilliz Cloud BYOC webinar | invited | `chloe.williams@zilliz.com`, Jul 20 |
| Jul 31, 14:00 PT | Logan Kilpatrick (Google DeepMind) session — Gemini XPRIZE track | registered | rescheduled session, Jul 25 |
| Jul 30 (approx) | monday.com trial ends | trial | "one more week on us", Jul 23 |
| Jul 31 (approx) | Chrome Enterprise Premium trial ends | trial | "7 days left", Jul 24 |
| **lapsed** | Google Payments card ••8780 verification | ❌ EXPIRED | 3-day expiry issued Jul 21 |

**The XPRIZE entry is the highest-value open item in the register.** Its stated brief is
"build a business with real customers and real revenue" — the same proof boundary the
rest of this repo is blocked on. Finishing it and fixing the revenue path are the same
piece of work, not two.

---

## B. Standing memberships and program access

| Grant | Issuer | Evidence | What it unlocks |
|-------|--------|----------|-----------------|
| **Google Developer Program — GEAR member** | Google | `googledev-noreply@google.com`, Jul 17 ("for GEAR members") | Agent-tooling program access, member resources |
| **Microsoft Ignite — registered attendee** | Microsoft | `ignite@events.microsoft.com`, Jul 23, sent to **info@aegisomega.com** | Digital attendance Nov 17–20 2026 |
| **Azure DevOps — org invite** | Microsoft | `azuredevops@microsoft.com`, Jul 19 | `dev.azure.com/aegisomega` — org-level project access |
| **Devpost — account** | Devpost | Jul 13 | Hackathon submission surface (XPRIZE, Build Week) |
| **OpenAI Build Week — participant** | OpenAI/Devpost | Jul 22 (submissions closed) | Entry made; outcome pending |
| **WorkOS — active integration + shared channel** | WorkOS | `updates@e.workos.com`, Jul 14 & Jul 24 | SSO/directory; vendor offering hands-on help |
| Microsoft AI Frontier Academy / Frontier Transformation Week (Sep 14–17) | Microsoft | Jul 16 | Program tracks, not yet registered |
| infosec.exchange (Mastodon) | community | Jul 25 — invite reviewed + welcomed | Security-community distribution channel |
| Superhuman Mail · Adobe · GeForce NOW · Slack workspaces | various | Jul 23–25 | Tooling accounts |

---

## C. Register discipline

Each row must eventually carry these fields. Rows are candidates until they do.

```
grant_id           stable identifier
issuer             organisation that granted it
granted_at         date of the acceptance artifact
evidence           mail id / document / URL   (no evidence -> UNVERIFIED)
expires_at         date or "none"
scope              what it actually permits
intended_outcome   the named result this access is meant to produce
owner              who is accountable for using it
status             ACTIVE | EXPIRING | LAPSED | UNVERIFIED
```

**Why `intended_outcome` is mandatory.** An acceptance with no named outcome is
indistinguishable from an unused subscription — it looks like inventory but behaves
like cost. The distinction is the whole difference between the acceptance strategy
working and it becoming overhead.

---

## D. Open — needs operator input

- Anthropic "digital visa": referenced by the operator, **not located** in the 90-day
  Gmail sweep of `tarikskalic33@gmail.com`. If it arrived at `info@aegisomega.com`,
  that mailbox is not connected here — supply it and the row can be filled.
- Several rows above lack `expires_at` and `intended_outcome`; they are candidates,
  not entitlements, until those are set.
