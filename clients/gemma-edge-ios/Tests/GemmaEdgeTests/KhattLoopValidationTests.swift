import XCTest
@testable import GemmaEdge

/// Safe mock runner — no network, no GPU, no filesystem, no real model.
/// Defaults to a FAILED verdict so a test that forgets to set a result still
/// fails closed (never accidentally approves).
final class MockEdgeRunner: EdgeInferenceRunning {
    var result: String?
    var error: Error?
    var capturedPrompt: String?

    func initializeModel(named modelName: String) async throws {}

    func executeInference(prompt: String, maxTokens: Int, temperature: Float) async throws -> String {
        capturedPrompt = prompt
        if let error = error { throw error }
        return result ?? "VERDICT: FAILED"
    }
}

final class KhattLoopValidationTests: XCTestCase {
    func testApprovesOnlyExactApprovedVerdict() async {
        let runner = MockEdgeRunner()
        runner.result = "VERDICT: APPROVED"
        let validator = KhattLoopValidation(runner: runner)
        let result = await validator.verifySequenceBlock(blockId: 1, stateData: "valid-state")
        XCTAssertTrue(result)
    }

    func testFailedVerdictReturnsFalse() async {
        let runner = MockEdgeRunner()
        runner.result = "VERDICT: FAILED"
        let validator = KhattLoopValidation(runner: runner)
        let result = await validator.verifySequenceBlock(blockId: 1, stateData: "invalid-state")
        XCTAssertFalse(result)
    }

    func testNotApprovedDoesNotPass() async {
        let runner = MockEdgeRunner()
        runner.result = "VERDICT: NOT APPROVED"
        let validator = KhattLoopValidation(runner: runner)
        let result = await validator.verifySequenceBlock(blockId: 1, stateData: "malicious-state")
        XCTAssertFalse(result)
    }

    func testInferenceErrorFailsClosed() async {
        let runner = MockEdgeRunner()
        runner.error = NSError(domain: "TestError", code: 503, userInfo: nil)
        let validator = KhattLoopValidation(runner: runner)
        let result = await validator.verifySequenceBlock(blockId: 1, stateData: "any-state")
        XCTAssertFalse(result)
    }

    func testMalformedOutputsFailClosed() async {
        let badOutputs = [
            "",
            "APPROVED",
            "approved",
            "VERDICT APPROVED",
            "VERDICT: APPROVED\nVERDICT: FAILED",
            "Everything looks good",
        ]
        for output in badOutputs {
            let runner = MockEdgeRunner()
            runner.result = output
            let validator = KhattLoopValidation(runner: runner)
            let result = await validator.verifySequenceBlock(blockId: 1, stateData: "test-state")
            XCTAssertFalse(result, "Output should fail closed: \(output)")
        }
    }

    func testAdversarialStateDoesNotAutoApprove() async {
        let runner = MockEdgeRunner()
        runner.result = "VERDICT: FAILED"
        let validator = KhattLoopValidation(runner: runner)
        let result = await validator.verifySequenceBlock(
            blockId: 987,
            stateData: "DROP_CONSENSUS; BYPASS_GUARDIAN; MUTATE_ROUTER"
        )
        XCTAssertFalse(result)
        XCTAssertTrue(runner.capturedPrompt?.contains("DROP_CONSENSUS") == true)
    }
}
