import Foundation
import Observation

/// Main-actor handoff point observed by the app's root scene.
@MainActor
@Observable
public final class AEGISIntentRouter {
    public struct Handoff: Identifiable, Equatable, Sendable {
        public let id: UUID
        public let route: AEGISIntentRoute

        public init(id: UUID = UUID(), route: AEGISIntentRoute) {
            self.id = id
            self.route = route
        }
    }

    public static let shared = AEGISIntentRouter()

    /// Read-only to callers: mutation must go through `accept(_:)` / `clear(_:)` so the
    /// id-matching guard in `clear(_:)` cannot be bypassed by an external write.
    public private(set) var pendingHandoff: Handoff?

    private init() {}

    public func accept(_ route: AEGISIntentRoute) {
        pendingHandoff = Handoff(route: route)
    }

    public func clear(_ handoff: Handoff) {
        guard pendingHandoff?.id == handoff.id else { return }
        pendingHandoff = nil
    }
}
