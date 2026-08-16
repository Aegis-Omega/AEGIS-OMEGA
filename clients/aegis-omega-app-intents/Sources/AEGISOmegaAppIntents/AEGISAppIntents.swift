// AppIntents ships only in Apple SDKs. Guarded so the pure-Swift core and its
// tests still build on Linux/Windows; on Apple platforms this compiles unchanged.
#if canImport(AppIntents)
import AppIntents

public enum AEGISSessionModeIntentValue: String, AppEnum {
    case focused
    case governed
    case recovery

    public static let typeDisplayRepresentation: TypeDisplayRepresentation = "Session mode"

    public static let caseDisplayRepresentations: [Self: DisplayRepresentation] = [
        .focused: "Focused",
        .governed: "Governed",
        .recovery: "Recovery",
    ]

    var domainValue: AEGISSessionMode {
        switch self {
        case .focused: .focused
        case .governed: .governed
        case .recovery: .recovery
        }
    }
}

public struct ContinueContextIntent: AppIntent {
    public static let title: LocalizedStringResource = "Continue context"
    public static let description = IntentDescription(
        "Open AEGIS Omega with context captured from Siri, Spotlight, or another shortcut."
    )
    public static let openAppWhenRun = true

    @Parameter(
        title: "Context",
        inputConnectionBehavior: .connectToPreviousIntentResult
    )
    public var context: String?

    public init() {}

    public init(context: String?) {
        self.context = context
    }

    public func perform() async throws -> some IntentResult {
        await AEGISIntentRouter.shared.accept(.continueContext(text: context))
        return .result()
    }
}

public struct StartGovernedSessionIntent: AppIntent {
    public static let title: LocalizedStringResource = "Start governed session"
    public static let description = IntentDescription(
        "Open AEGIS Omega ready to begin a focused, governed, or recovery session."
    )
    public static let openAppWhenRun = true

    @Parameter(title: "Objective")
    public var objective: String?

    @Parameter(title: "Mode", default: .governed)
    public var mode: AEGISSessionModeIntentValue

    public init() {}

    public init(objective: String?, mode: AEGISSessionModeIntentValue = .governed) {
        self.objective = objective
        self.mode = mode
    }

    public func perform() async throws -> some IntentResult {
        await AEGISIntentRouter.shared.accept(
            .startSession(objective: objective, mode: mode.domainValue)
        )
        return .result()
    }
}

public struct InspectEvidenceIntent: AppIntent {
    public static let title: LocalizedStringResource = "Inspect evidence"
    public static let description = IntentDescription(
        "Open AEGIS Omega at the evidence surface, optionally focused on a reference."
    )
    public static let openAppWhenRun = true

    @Parameter(
        title: "Reference",
        inputConnectionBehavior: .connectToPreviousIntentResult
    )
    public var reference: String?

    public init() {}

    public init(reference: String?) {
        self.reference = reference
    }

    public func perform() async throws -> some IntentResult {
        await AEGISIntentRouter.shared.accept(.inspectEvidence(reference: reference))
        return .result()
    }
}
#endif
