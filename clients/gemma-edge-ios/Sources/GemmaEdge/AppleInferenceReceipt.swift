import CryptoKit
import Foundation

/// Content-addressed receipt for one successful Apple Foundation Models generation.
///
/// Privacy boundary:
/// - prompt/output text is NOT stored in the receipt;
/// - only SHA-256 digests, byte counts, bounded generation parameters, and fixed
///   provider/model identifiers are committed.
/// - authority_effect is permanently NONE.
public struct AppleInferenceReceipt: Codable, Equatable, Sendable {
    public static let schemaVersion = "1.0.0"
    public static let providerId = "apple-foundation-models"
    public static let modelId = "apple-system-language-model-default"

    public let schema_version: String
    public let provider_id: String
    public let model_id: String
    public let prompt_sha256: String
    public let output_sha256: String
    public let prompt_bytes: Int
    public let output_bytes: Int
    public let max_tokens: Int
    public let temperature_milli: Int
    public let outcome: String
    public let authority_effect: String
    public let receipt_sha256: String

    public static func succeeded(
        prompt: String,
        output: String,
        maxTokens: Int,
        temperature: Float
    ) -> AppleInferenceReceipt {
        let promptHash = sha256Hex(prompt)
        let outputHash = sha256Hex(output)
        let temperatureMilli = Int((Double(temperature) * 1000.0).rounded())

        // This flat object contains only ASCII-safe fixed strings, lowercase hex,
        // and integers. The explicit lexicographic key order is therefore its JCS
        // representation without requiring a general-purpose JSON canonicalizer.
        let preimage =
            #"{"authority_effect":"NONE","max_tokens":#(maxTokens),"model_id":"apple-system-language-model-default","outcome":"SUCCEEDED","output_bytes":#(output.utf8.count),"output_sha256":"#(outputHash)","prompt_bytes":#(prompt.utf8.count),"prompt_sha256":"#(promptHash)","provider_id":"apple-foundation-models","schema_version":"1.0.0","temperature_milli":#(temperatureMilli)}"#

        return AppleInferenceReceipt(
            schema_version: schemaVersion,
            provider_id: providerId,
            model_id: modelId,
            prompt_sha256: promptHash,
            output_sha256: outputHash,
            prompt_bytes: prompt.utf8.count,
            output_bytes: output.utf8.count,
            max_tokens: maxTokens,
            temperature_milli: temperatureMilli,
            outcome: "SUCCEEDED",
            authority_effect: "NONE",
            receipt_sha256: sha256Hex(preimage)
        )
    }

    static func sha256Hex(_ value: String) -> String {
        SHA256.hash(data: Data(value.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
    }
}

public struct AppleFoundationModelsExecution: Equatable, Sendable {
    public let output: String
    public let receipt: AppleInferenceReceipt

    public init(output: String, receipt: AppleInferenceReceipt) {
        self.output = output
        self.receipt = receipt
    }
}
