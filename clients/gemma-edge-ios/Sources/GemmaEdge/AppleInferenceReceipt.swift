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
    public static let schemaVersion = "1.1.0"
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
    /// Exact IEEE-754 Float32 bits for the actual model temperature.
    /// Optional to retain decoding of historical schema 1.0.0 receipts.
    public let temperature_float_bits_hex: String?
    public let outcome: String
    public let authority_effect: String
    public let receipt_sha256: String

    public static func succeeded(
        prompt: String,
        output: String,
        maxTokens: Int,
        temperature: Float
    ) throws -> AppleInferenceReceipt {
        // The public factory must uphold the same bounds as the inference runner.
        // In particular, NaN or infinity would trap in Float-to-Int conversion.
        try AppleFoundationModelsRunner.validateRequest(
            prompt: prompt, maxTokens: maxTokens, temperature: temperature
        )
        let promptHash = sha256Hex(prompt)
        let outputHash = sha256Hex(output)
        let temperatureMilli = Int((Double(temperature) * 1000.0).rounded())
        let temperatureBitsHex = String(format: "%08x", temperature.bitPattern)

        // This flat object contains only ASCII-safe fixed strings, lowercase hex,
        // and integers. The explicit lexicographic key order is therefore its JCS
        // representation without requiring a general-purpose JSON canonicalizer.
        let preimage =
            #"{"authority_effect":"NONE","max_tokens":\#(maxTokens),"model_id":"apple-system-language-model-default","outcome":"SUCCEEDED","output_bytes":\#(output.utf8.count),"output_sha256":"\#(outputHash)","prompt_bytes":\#(prompt.utf8.count),"prompt_sha256":"\#(promptHash)","provider_id":"apple-foundation-models","schema_version":"1.1.0","temperature_float_bits_hex":"\#(temperatureBitsHex)","temperature_milli":\#(temperatureMilli)}"#

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
            temperature_float_bits_hex: temperatureBitsHex,
            outcome: "SUCCEEDED",
            authority_effect: "NONE",
            receipt_sha256: sha256Hex(preimage)
        )
    }

    /// Checks internal consistency of the receipt, including the canonical digest.
    /// This is NOT an issuer signature or proof that inference actually occurred.
    /// Historical schema 1.0.0 is supported without reconstructing lost Float32 bits.
    public func verifyIntegrity() -> Bool {
        guard provider_id == Self.providerId,
              model_id == Self.modelId,
              outcome == "SUCCEEDED",
              authority_effect == "NONE",
              prompt_bytes > 0,
              prompt_bytes <= AppleFoundationModelsRunner.maximumPromptBytes,
              output_bytes >= 0,
              max_tokens > 0,
              max_tokens <= AppleFoundationModelsRunner.maximumResponseTokens,
              (0...1000).contains(temperature_milli),
              Self.isLowercaseSHA256(prompt_sha256),
              Self.isLowercaseSHA256(output_sha256),
              Self.isLowercaseSHA256(receipt_sha256)
        else { return false }

        let base = #"{"authority_effect":"NONE","max_tokens":\#(max_tokens),"model_id":"apple-system-language-model-default","outcome":"SUCCEEDED","output_bytes":\#(output_bytes),"output_sha256":"\#(output_sha256)","prompt_bytes":\#(prompt_bytes),"prompt_sha256":"\#(prompt_sha256)","provider_id":"apple-foundation-models""#
        let preimage: String
        switch schema_version {
        case "1.0.0":
            // A v1 receipt must not silently carry uncommitted v1.1 metadata.
            guard temperature_float_bits_hex == nil else { return false }
            preimage = base + #","schema_version":"1.0.0","temperature_milli":\#(temperature_milli)}"#
        case "1.1.0":
            guard let bitsHex = temperature_float_bits_hex,
                  bitsHex.count == 8,
                  let bits = UInt32(bitsHex, radix: 16),
                  bitsHex == String(format: "%08x", bits)
            else { return false }
            let temperature = Float(bitPattern: bits)
            guard temperature.isFinite,
                  temperature >= 0,
                  temperature <= 1,
                  Int((Double(temperature) * 1000.0).rounded()) == temperature_milli
            else { return false }
            preimage = base
                + #","schema_version":"1.1.0","temperature_float_bits_hex":"\#(bitsHex)","temperature_milli":\#(temperature_milli)}"#
        default:
            return false
        }
        return Self.sha256Hex(preimage) == receipt_sha256
    }

    /// Also checks the actual supplied prompt/output bytes against the receipt.
    /// A valid hash alone cannot establish that a model produced the output.
    public func verifyContent(prompt: String, output: String) -> Bool {
        verifyIntegrity()
            && prompt.utf8.count == prompt_bytes
            && output.utf8.count == output_bytes
            && Self.sha256Hex(prompt) == prompt_sha256
            && Self.sha256Hex(output) == output_sha256
    }

    private static func isLowercaseSHA256(_ digest: String) -> Bool {
        digest.utf8.count == 64 && digest.utf8.allSatisfy { byte in
            (48...57).contains(byte) || (97...102).contains(byte)
        }
    }

    static func sha256Hex(_ value: String) -> String {
        SHA256.hash(data: Data(value.utf8))
            .map { String(format: "%02x", $0) }
            .joined()
    }
}


// Reject unknown receipt metadata before the canonical digest is verified.
// Foundation's default synthesized Decodable silently discards extra keys,
// which makes Swift less strict than the independent Python verifier.
private struct AppleReceiptAnyKey: CodingKey {
    let stringValue: String
    let intValue: Int? = nil

    init?(stringValue: String) { self.stringValue = stringValue }
    init?(intValue: Int) { return nil }
}

extension AppleInferenceReceipt {
    private enum CodingKeys: String, CodingKey, CaseIterable {
        case schema_version, provider_id, model_id, prompt_sha256, output_sha256
        case prompt_bytes, output_bytes, max_tokens, temperature_milli
        case temperature_float_bits_hex, outcome, authority_effect, receipt_sha256
    }

    public init(from decoder: Decoder) throws {
        let all = try decoder.container(keyedBy: AppleReceiptAnyKey.self)
        let fields = try decoder.container(keyedBy: CodingKeys.self)
        let schema = try fields.decode(String.self, forKey: .schema_version)
        var required = Set(CodingKeys.allCases.map(\.stringValue))
        switch schema {
        case "1.0.0":
            required.remove("temperature_float_bits_hex")
        case "1.1.0":
            break
        default:
            throw DecodingError.dataCorruptedError(
                forKey: .schema_version, in: fields,
                debugDescription: "Unsupported receipt schema")
        }
        let incoming = Set(all.allKeys.map(\.stringValue))
        guard incoming == required else {
            throw DecodingError.dataCorrupted(
                .init(codingPath: decoder.codingPath,
                      debugDescription: "Missing or uncommitted receipt keys"))
        }
        self.schema_version = schema
        self.provider_id = try fields.decode(String.self, forKey: .provider_id)
        self.model_id = try fields.decode(String.self, forKey: .model_id)
        self.prompt_sha256 = try fields.decode(String.self, forKey: .prompt_sha256)
        self.output_sha256 = try fields.decode(String.self, forKey: .output_sha256)
        self.prompt_bytes = try fields.decode(Int.self, forKey: .prompt_bytes)
        self.output_bytes = try fields.decode(Int.self, forKey: .output_bytes)
        self.max_tokens = try fields.decode(Int.self, forKey: .max_tokens)
        self.temperature_milli = try fields.decode(Int.self, forKey: .temperature_milli)
        self.temperature_float_bits_hex = schema == "1.1.0"
            ? try fields.decode(String.self, forKey: .temperature_float_bits_hex)
            : nil
        self.outcome = try fields.decode(String.self, forKey: .outcome)
        self.authority_effect = try fields.decode(String.self, forKey: .authority_effect)
        self.receipt_sha256 = try fields.decode(String.self, forKey: .receipt_sha256)
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
