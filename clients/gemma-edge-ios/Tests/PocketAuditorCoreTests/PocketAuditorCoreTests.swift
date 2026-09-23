import XCTest
@testable import PocketAuditorCore
import GemmaEdge

private final class MockRunner: EdgeInferenceRunning {
    let output: String
    init(output: String) { self.output = output }

    func executeInference(
        prompt: String,
        maxTokens: Int,
        temperature: Double
    ) async throws -> String {
        output
    }
}

private struct MockAccess: PremiumAccessChecking {
    let enabled: Bool
    func hasPremiumAccess() async -> Bool { enabled }
}

final class PocketAuditorCoreTests: XCTestCase {
    func testFreeAuditDoesNotExposePremiumTier() async {
        let auditor = PocketAuditor(
            validator: KhattLoopValidation(
                runner: MockRunner(output: "VERDICT: APPROVED")
            ),
            access: MockAccess(enabled: false)
        )

        let report = await auditor.audit(
            blockId: 7,
            stateData: "safe"
        )

        XCTAssertEqual(report.tier, .free)
        XCTAssertTrue(report.constitutionalPass)
        XCTAssertEqual(report.evidenceStatus, "LOCAL_VERIFICATION_ONLY")
        XCTAssertEqual(report.findings.count, 1)
    }

    func testPremiumAuditRequiresPositiveEntitlement() async {
        let auditor = PocketAuditor(
            validator: KhattLoopValidation(
                runner: MockRunner(output: "VERDICT: APPROVED")
            ),
            access: MockAccess(enabled: true)
        )

        let report = await auditor.audit(
            blockId: 7,
            stateData: "safe"
        )

        XCTAssertEqual(report.tier, .premium)
        XCTAssertTrue(report.constitutionalPass)
        XCTAssertEqual(
            report.evidenceStatus,
            "LOCAL_VERIFICATION_WITH_PREMIUM_REPORTING"
        )
        XCTAssertEqual(report.findings.count, 2)
    }

    func testConstitutionalFailureRemainsFailureEvenWithPremium() async {
        let auditor = PocketAuditor(
            validator: KhattLoopValidation(
                runner: MockRunner(output: "VERDICT: FAILED")
            ),
            access: MockAccess(enabled: true)
        )

        let report = await auditor.audit(
            blockId: 7,
            stateData: "unsafe"
        )

        XCTAssertEqual(report.tier, .premium)
        XCTAssertFalse(report.constitutionalPass)
        XCTAssertEqual(report.findings.first?.code, "CONSTITUTIONAL_CHECK_FAIL")
    }
}
