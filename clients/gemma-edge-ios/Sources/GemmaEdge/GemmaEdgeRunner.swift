import Foundation

/// On-device Gemma runner for the AEGIS-Ω edge validation path.
///
/// FAIL CLOSED. Until a real native AIEdge/Metal inference backend is wired in,
/// every path throws rather than returning a mock "VERDICT: APPROVED". A
/// constitutional verifier must never treat mock output as authoritative —
/// missing weights, an uninitialized model, or an unimplemented backend must
/// surface as an error, which `KhattLoopValidation` turns into `false`.
public final class GemmaEdgeRunner: EdgeInferenceRunning {
    /// Native inference context. Stays `nil` until a model is *actually* loaded,
    /// which is what keeps `executeInference` fail-closed.
    private var gemmaModel: Any?

    public init() {}

    public func initializeModel(named modelName: String) async throws {
        guard Bundle.main.path(forResource: modelName, ofType: "bin") != nil else {
            throw NSError(
                domain: "GemmaRunner",
                code: 404,
                userInfo: [NSLocalizedDescriptionKey: "Weights (.bin) missing."]
            )
        }
        // TODO: load the native AIEdge / Metal inference context here.
        // Do NOT assign `gemmaModel` until the model is genuinely loaded.
    }

    public func executeInference(
        prompt: String,
        maxTokens: Int = 128,
        temperature: Float = 0.2
    ) async throws -> String {
        guard gemmaModel != nil else {
            throw NSError(
                domain: "GemmaRunner",
                code: 503,
                userInfo: [NSLocalizedDescriptionKey: "Gemma model not initialized; refusing mock approval."]
            )
        }
        // TODO: execute real inference against the loaded context.
        throw NSError(
            domain: "GemmaRunner",
            code: 501,
            userInfo: [NSLocalizedDescriptionKey: "Native inference not implemented."]
        )
    }
}
