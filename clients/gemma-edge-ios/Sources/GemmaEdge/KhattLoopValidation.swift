import Foundation

/// Khatt-loop constitutional verifier.
///
/// SAFE INVARIANT: only an exact `"VERDICT: APPROVED"` returns `true`. Every other
/// output — `"VERDICT: FAILED"`, `"VERDICT: NOT APPROVED"`, empty/lowercase/
/// multi-line/malformed text — and every thrown inference error fails closed
/// (`false`). Substring matching is deliberately avoided because `.contains("APPROVED")`
/// would accept `"VERDICT: NOT APPROVED"`.
public struct KhattLoopValidation {
    private let runner: EdgeInferenceRunning

    public init(runner: EdgeInferenceRunning) {
        self.runner = runner
    }

    public func verifySequenceBlock(blockId: Int, stateData: String) async -> Bool {
        let structuredPrompt = """
        [SYSTEM: CONSTITUTIONAL ENFORCER]
        Verify block \(blockId) against PHI=0.618. State: \(stateData)
        Output exactly 'VERDICT: APPROVED' or 'VERDICT: FAILED'.
        """

        do {
            let result = try await runner.executeInference(
                prompt: structuredPrompt,
                maxTokens: 32,
                temperature: 0.1
            )
            let normalized = result.trimmingCharacters(in: .whitespacesAndNewlines)
            return normalized == "VERDICT: APPROVED"
        } catch {
            return false
        }
    }
}
