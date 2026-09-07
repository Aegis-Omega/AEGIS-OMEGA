import XCTest
@testable import AEGISOmegaAppIntents

// Every test method here is nonisolated and `async`, and the main-actor hop happens inside
// the body. SwiftPM builds its test-discovery list out of unapplied method references, so a
// method's isolation leaks into that list's element type: `@MainActor` methods produce
// `(Self) -> @MainActor () -> Void`, which off-Apple fails to compile when mixed with
// nonisolated methods and fails to *cast* at run time when it isn't. Keeping the whole class
// nonisolated keeps the element type uniform and castable, so the tests are actually invoked.
final class AEGISIntentRouteTests: XCTestCase {

    /// Returns the router to a known-empty state through its public API only,
    /// since `pendingHandoff` is read-only to callers.
    @MainActor
    private func drain(_ router: AEGISIntentRouter) {
        while let h = router.pendingHandoff { router.clear(h) }
    }

    // Exercises the AppIntents-facing enum, so it can only run where AppIntents exists.
    #if canImport(AppIntents)
    func testSessionModesMapWithoutLosingMeaning() async {
        XCTAssertEqual(AEGISSessionModeIntentValue.focused.domainValue, .focused)
        XCTAssertEqual(AEGISSessionModeIntentValue.governed.domainValue, .governed)
        XCTAssertEqual(AEGISSessionModeIntentValue.recovery.domainValue, .recovery)
    }
    #endif

    func testRouterReplacesThePendingHandoffAtomically() async {
        await MainActor.run {
            let router = AEGISIntentRouter.shared
            defer { drain(router) }

            router.accept(.continueContext(text: "first"))
            let first = router.pendingHandoff

            router.accept(.inspectEvidence(reference: "receipt-42"))
            let second = router.pendingHandoff

            XCTAssertNotEqual(first?.id, second?.id)
            XCTAssertEqual(second?.route, .inspectEvidence(reference: "receipt-42"))
        }
    }

    // The route model is pure Foundation, so these run on every platform.
    func testRouteEqualityDistinguishesPayloads() async {
        XCTAssertEqual(
            AEGISIntentRoute.continueContext(text: "a"),
            AEGISIntentRoute.continueContext(text: "a")
        )
        XCTAssertNotEqual(
            AEGISIntentRoute.continueContext(text: "a"),
            AEGISIntentRoute.continueContext(text: "b")
        )
        XCTAssertNotEqual(
            AEGISIntentRoute.startSession(objective: nil, mode: .focused),
            AEGISIntentRoute.startSession(objective: nil, mode: .governed)
        )
    }

    func testSessionModeRoundTripsThroughItsRawValue() async {
        for mode in AEGISSessionMode.allCases {
            XCTAssertEqual(AEGISSessionMode(rawValue: mode.rawValue), mode)
        }
        XCTAssertNil(AEGISSessionMode(rawValue: "not-a-mode"))
    }

    func testClearOnlyDropsTheMatchingHandoff() async {
        await MainActor.run {
            let router = AEGISIntentRouter.shared
            defer { drain(router) }

            router.accept(.startSession(objective: "audit", mode: .recovery))
            guard let stale = router.pendingHandoff else { return XCTFail("expected a handoff") }

            router.accept(.inspectEvidence(reference: "receipt-7"))
            router.clear(stale)

            XCTAssertEqual(
                router.pendingHandoff?.route,
                .inspectEvidence(reference: "receipt-7"),
                "clearing a superseded handoff must not drop the current one"
            )
        }
    }
}
