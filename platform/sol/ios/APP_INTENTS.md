# SOL iOS Operator Contract

The iOS app is an operator surface, not an autonomous authority node.

## SwiftUI architecture

- iOS 17+ Observation by default: root-owned `@Observable` state stored with `@State`.
- Shared services use typed `@Environment`; feature-local dependencies use explicit initializer injection.
- `NavigationStack` and enum routing own navigation.
- `.sheet(item:)` owns selected modal state.
- Async work runs through `.task` with explicit loading, error, cancellation, and retry states.
- Views remain small; networking, authority evaluation, and receipt verification stay outside view bodies.

## First App Intents

1. `InspectExecutionIntent`
   - D0, completes inline.
   - Input: execution identifier.
   - Output: normalized state, consequence class, provider, and receipt root.

2. `ReviewDecisionIntent`
   - D0, opens the app to the decision detail.
   - Never approves from Siri or a background invocation.

3. `ContinueApprovedWorkflowIntent`
   - Opens the app.
   - Requires a still-valid approval grant, parent-state match, and lease generation.
   - The app shows the exact provider action before submission.

## App entity surface

`ExecutionEntity` exposes only:

- execution ID;
- display title;
- normalized status;
- consequence class;
- updated time;
- receipt-root prefix.

It does not mirror provider payloads, secrets, prompts, or internal policy objects.

## Operator confirmation screen

Before a D2+ request, show:

- requested action;
- target provider and target object;
- consequence class;
- arguments digest;
- expected parent state;
- compensation or rollback path;
- approval expiry;
- receipt destination.

No ambiguous labels such as “Continue” for consequential actions. Use the explicit verb and target.

## Security

- Tokens reside in Keychain and are never logged.
- App Transport Security remains enabled.
- Universal links and deep links validate host, route, and identifier.
- Background tasks are read-only unless an already-admitted idempotent operation is being observed.
- Device biometrics may confirm operator presence but do not replace Automaton-3 authorization.
