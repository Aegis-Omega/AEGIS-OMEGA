# AEGIS Omega — App Intents client

Siri / Spotlight / Shortcuts entry points that hand a single system-facing route into the app's
root scene.

## Why this is in the repository

It was previously stranded in a transient agent scratch directory
(`Documents\Codex\2026-07-28\build-ios-apps-ios-app-intents-2\outputs\`). That is the same class
of location where the "holon-gram compiler" (8 files, +4446/−889) was lost permanently when its
container was reclaimed — see `CLAUDE.md` § *Verified Failure Modes* V1. Work that only exists in
an agent's working directory is one cleanup away from gone.

## Layout

| File | Platform | Purpose |
|---|---|---|
| `AEGISIntentRoute.swift` | any | `AEGISIntentRoute` / `AEGISSessionMode` — pure `Foundation` route model |
| `AEGISIntentRouter.swift` | any | `@MainActor @Observable` singleton the root scene observes |
| `AEGISAppIntents.swift` | Apple only | `AppIntent` conformances + `AEGISSessionModeIntentValue` |
| `AEGISAppShortcuts.swift` | Apple only | `AppShortcutsProvider` phrases |

## Cross-platform guard

`AppIntents` ships only in Apple SDKs. The two Apple-only sources are wrapped in
`#if canImport(AppIntents)`, and the test that exercises `AEGISSessionModeIntentValue` is guarded
the same way. On Apple platforms everything compiles unchanged; on Linux/Windows the pure
`Foundation` core and its tests still build, so the routing logic stays continuously verifiable
without a Mac.

## Build

```bash
swift build
swift test
```

**Windows prerequisite:** the Swift toolchain requires MSVC's `link.exe`. Without the Visual
Studio C++ workload, `swift build` fails with `toolchain is invalid: could not find CLI tool
'link'`. Installing that workload requires an **elevated** process — a non-elevated
`setup.exe --quiet` exits `5007` and silently does nothing.

**iOS builds require macOS + Xcode.** No Windows toolchain can produce an iOS app; on Windows only
the cross-platform core and its tests are exercised.

## Tests

`AEGISIntentRouteTests` covers route equality by payload, `AEGISSessionMode` raw-value round trip
(including the rejection of an unknown value), that `accept` replaces the pending handoff with a
fresh identity, and that `clear` on a superseded handoff does not drop the current one. Router
tests reset shared state via `defer`, since `AEGISIntentRouter.shared` is a singleton.
