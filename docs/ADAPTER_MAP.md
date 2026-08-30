# Adapter map — business tools as plugins over one envelope

**Thesis (operator, 2026-07-26).** Business tools are the same tools with different
programming; they serve as plugins. Correct, with one exception documented in §3.

**Consequence.** Acceptance into N tools is not N integrations. It is one canonical
envelope plus N thin adapters. The work scales with primitives, not with vendors.

---

## 1. The six primitives

Every business tool in this workspace reduces to some subset of six verbs. The vendor
differences are naming, pagination, and rate limits — not semantics.

| Primitive | Meaning | Envelope field it touches |
|-----------|---------|---------------------------|
| `IDENTIFY` | who is acting, what they may do | `authority.grant_scope` |
| `QUERY` | find records matching a predicate | `payload.data` |
| `READ` | fetch one record in full | `state.before` |
| `MUTATE` | create / update / delete a record | `state.actual_after` |
| `EMIT` | notify, comment, message, publish | `feedback.next_route` |
| `SCHEDULE` | place something on a timeline | `context.context_canvas` |

## 2. Coverage across connectors live in this session

Verified = the tool schema was loaded and read during this session. Inferred = present
in the connector inventory, schema not individually inspected. Inferred rows are
candidates, not entitlements — same evidence rule as the access register.

| Connector | IDENTIFY | QUERY | READ | MUTATE | EMIT | SCHEDULE | Evidence |
|-----------|:--:|:--:|:--:|:--:|:--:|:--:|---|
| Gmail | — | ✅ | ✅ | ✅ | ✅ | — | verified (`search_threads`, `get_thread`, `create_draft`, `label_*`) |
| Google Drive | — | ✅ | ✅ | ✅ | — | — | verified (`search_files`, `download_file_content`, `create_file`) |
| GitHub | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | verified (`get_me`, `search_*`, `get_job_logs`, `push_files`, `add_issue_comment`, `actions_run_trigger`) |
| Slack | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | inferred (`read_user_profile`, `search_public`, `send_message`, `schedule_message`) |
| Asana | ✅ | ✅ | ✅ | ✅ | ✅ | — | inferred (`get_me`, `search_tasks`, `create_tasks`, `add_comment`) |
| Notion | — | ✅ | ✅ | ✅ | ✅ | — | inferred (`notion-search`, `notion-fetch`, `notion-update-page`, `notion-create-comment`) |
| HubSpot | ✅ | ✅ | ✅ | ✅ | — | — | inferred (`get_user_details`, `search_crm_objects`, `manage_crm_objects`) |
| Supabase | — | ✅ | ✅ | ✅ | — | — | inferred (`execute_sql`, `list_tables`, `apply_migration`) |
| Vercel | ✅ | ✅ | ✅ | ✅ | ✅ | — | inferred (`list_teams`, `list_deployments`, `deploy_to_vercel`, toolbar threads) |
| WorkOS | ✅ | ✅ | — | ✅ | — | — | inferred (`whoami`, `query`, `mutate`) |
| Cloudflare | — | ✅ | ✅ | ✅ | — | — | inferred (`kv_*`, `r2_*`, `d1_database_query`) |
| Zapier | — | ✅ | ✅ | ✅ | ✅ | — | inferred (`discover_*`, `execute_*_action`) — itself an adapter layer |
| Figma | — | ✅ | ✅ | ✅ | — | — | inferred |
| Zoom | — | ✅ | ✅ | ✅ | — | ✅ | inferred (`search_meetings`, `recordings_list`) |

**Reading of the table.** No column is scarce. `QUERY`/`READ`/`MUTATE` are covered
5–14 times over. Adding another tool adds redundancy, not capability. That is the
economic content of the operator's thesis: *the marginal tool is worth ~0 unless it
covers a primitive that is currently uncovered, or it is the system of record for a
customer who is paying.*

## 3. The exception — authority does not commoditize

`IDENTIFY` is the one primitive that is **not** interchangeable. Records and events
port across vendors; identity bindings do not. Each is a separate trust relationship
with its own failure surface.

Evidence from this project, all three the same class, none of them a code defect:

| Failure | Binding that broke |
|---------|--------------------|
| Cloud Run deploys red since May | WIF `attributeCondition` pinned to a stale repo identity |
| 54 of 66 recovered agent runs | `401 Invalid authentication credentials` — credential never authenticated |
| Revenue path, never once completed | `VITE_PAYPAL_CLIENT_ID` unset in the Vercel project |

Reproduced live on 2026-07-26: this sandbox's `CLOUDSDK_AUTH_ACCESS_TOKEN` returns
`invalid_token` against Google's tokeninfo endpoint — the same error string as the 54
archived failures.

**Design rule that follows.** An adapter must not treat `authority` as one more
serialisable field. Every adapter declares its binding explicitly, and the envelope
fails closed when the binding cannot be proven — never when it merely looks present.
This is why `verifier` runs before `committer` in the holon pipeline, and why a
`request_grant` signal must not be recoverable by retry.

## 4. Adapter contract

```
interface ToolAdapter {
  id: string                     // "slack" | "asana" | ...
  primitives: Primitive[]        // subset of the six
  binding: {
    kind: "oauth" | "api_key" | "oidc_federation" | "service_account"
    verify(): Promise<boolean>   // MUST make a live call, never inspect config
    scope: string                // maps to authority.required_scope
  }
  execute(envelope: TransitionEnvelope): Promise<TransitionEnvelope>
}
```

`binding.verify()` making a live call is the whole point. Every failure in §3 would
have been caught at registration time by a single authenticated round-trip, months
before it surfaced as a mysterious downstream symptom.

## 5. What this implies for the acceptance strategy

- Accepting into a tool that covers only already-covered primitives adds **redundancy**,
  and its only defensible value is as a customer's system of record.
- The scarce resource is not tool access. It is `intended_outcome` per grant
  (see `ACCESS_REGISTER.md` §C) and a **verified** binding per adapter.
- Therefore the next unit of work is not another integration. It is
  `binding.verify()` implemented once, run against every connector already held.
