import Foundation

/// Abstraction over an on-device inference backend.
///
/// `KhattLoopValidation` depends on this protocol — not a concrete runner — so the
/// constitutional verifier can be exercised with safe mock runners that never touch
/// the network, the GPU, the filesystem, or a real model.
public protocol EdgeInferenceRunning {
    func initializeModel(named modelName: String) async throws
    func executeInference(prompt: String, maxTokens: Int, temperature: Float) async throws -> String
}
