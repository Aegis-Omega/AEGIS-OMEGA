import XCTest
@testable import GemmaEdge

/// Proves the real runner refuses to operate when inference is unavailable —
/// no mock approval ever leaks out. These run without network, GPU, or a real model.
final class GemmaEdgeRunnerTests: XCTestCase {
    func testMissingWeightsThrows() async {
        let runner = GemmaEdgeRunner()
        do {
            try await runner.initializeModel(named: "missing-model")
            XCTFail("Expected missing model weights to throw")
        } catch {
            // Expected: no bundled .bin → fail closed.
        }
    }

    func testUninitializedRunnerFailsClosed() async {
        let runner = GemmaEdgeRunner()
        do {
            _ = try await runner.executeInference(prompt: "test", maxTokens: 32, temperature: 0.1)
            XCTFail("Expected uninitialized runner to throw")
        } catch {
            // Expected: model never loaded → fail closed.
        }
    }
}
