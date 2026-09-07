import Foundation

/// The single system-facing route passed from App Intents into the main scene.
public enum AEGISIntentRoute: Equatable, Sendable {
    case continueContext(text: String?)
    case startSession(objective: String?, mode: AEGISSessionMode)
    case inspectEvidence(reference: String?)
}

public enum AEGISSessionMode: String, CaseIterable, Codable, Sendable {
    case focused
    case governed
    case recovery
}
