// AppIntents ships only in Apple SDKs. Guarded so the pure-Swift core and its
// tests still build on Linux/Windows; on Apple platforms this compiles unchanged.
#if canImport(AppIntents)
import AppIntents

public struct AEGISAppShortcuts: AppShortcutsProvider {
    public static var appShortcuts: [AppShortcut] {
        AppShortcut(
            intent: ContinueContextIntent(),
            phrases: [
                "Continue context in \(.applicationName)",
                "Remember this with \(.applicationName)",
            ],
            shortTitle: "Continue context",
            systemImageName: "brain.head.profile"
        )

        AppShortcut(
            intent: StartGovernedSessionIntent(),
            phrases: [
                "Start a governed session in \(.applicationName)",
                "Begin a session with \(.applicationName)",
            ],
            shortTitle: "Start session",
            systemImageName: "point.3.connected.trianglepath.dotted"
        )

        AppShortcut(
            intent: InspectEvidenceIntent(),
            phrases: [
                "Inspect evidence in \(.applicationName)",
                "Open evidence with \(.applicationName)",
            ],
            shortTitle: "Inspect evidence",
            systemImageName: "checkmark.seal"
        )
    }
}
#endif
