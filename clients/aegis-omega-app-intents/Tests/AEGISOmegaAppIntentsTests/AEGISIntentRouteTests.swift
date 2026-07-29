import XCTest
@testable import AEGISOmegaAppIntents

final class AEGISIntentRouteTests: XCTestCase {

    // Exercises the AppIntents-facing enum, so it can only run where AppIntents exists.
    #if canImport(AppIntents)
    func testSessionModesMapWithoutLosingMeaning() {
        XCTAssertEqual(AEGISSessionModeIntentValue.focused.domainValue, .focused)
        XCTAssertEqual(AEGISSessionModeIntentValue.governed.domainValue, .governed)
        XCTAssertEqual(AEGISSessionModeIntentValue.recovery.domainValue, .recovery)
    }
    #endif

    @MainActor
    func testRouterReplacesThePendingHandoffAtomically() {
        let router = AEGISIntentRouter.shared
        defer { router.pendingHandoff = nil }

        router.accept(.continueContext(text: "first"))
        let first = router.pendingHandoff

        router.accept(.inspectEvidence(reference: "receipt-42"))
        let second = router.pendingHandoff

        XCTAssertNotEqual(first?.id, second?.id)
        XCTAssertEqual(second?.route, .inspectEvidence(reference: "receipt-42"))
    }

    // The route model is pure Foundation, so these run on every platform.
    func testRouteEqualityDistinguishesPayloads() {
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

    func testSessionModeRoundTripsThroughItsRawValue() {
        for mode in AEGISSessionMode.allCases {
            XCTAssertEqual(AEGISSessionMode(rawValue: mode.rawValue), mode)
        }
        XCTAssertNil(AEGISSessionMode(rawValue: "not-a-mode"))
    }

    @MainActor
    func testClearOnlyDropsTheMatchingHandoff() {
        let router = AEGISIntentRouter.shared
        defer { router.pendingHandoff = nil }

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
