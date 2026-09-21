import Foundation

#if canImport(FoundationModels)
import FoundationModels
#endif

public enum AppleFoundationModelsError: Error, Equatable {
    case frameworkUnavailable
    case unsupportedModelName(String)
    case modelUnavailable(String)
    case notInitialized
    case invalidPrompt
    case invalidMaxTokens(Int)
    case invalidTemperature(Float)
}

public struct AppleFoundationModelsAvailability: Equatable, Sendable {
    public let available: Bool
    public let reason: String?

    public init(available: Bool, reason: String?) {
        self.available = available
        self.reason = reason
    }
}

/// Real Apple Foundation Models backend for the existing AEGIS edge inference protocol.
///
/// This runner never treats documentation access as model availability. Initialization
/// succeeds only when the FoundationModels framework is present, the OS API is available,
/// and SystemLanguageModel.default reports .available.
///
/// Authority boundary: model output is data only. This runner cannot grant repository,
/// cloud, App Store, signing, Apple Business Manager, MDM, or governance authority.
public final class AppleFoundationModelsRunner: EdgeInferenceRunning {
    public static let modelName = "apple-foundation-models-default"

    /// Hard execution bounds for the first governed adapter revision.
    public static let maximumPromptBytes = 16_384
    public static let maximumResponseTokens = 1_024

    private var initialized = false

    public init() {}

    public func probeAvailability() -> AppleFoundationModelsAvailability {
        #if canImport(FoundationModels)
        if #available(iOS 26.0, macOS 26.0, *) {
            switch SystemLanguageModel.default.availability {
            case .available:
                return AppleFoundationModelsAvailability(available: true, reason: nil)
            case .unavailable(let reason):
                return AppleFoundationModelsAvailability(
                    available: false,
                    reason: Self.reasonCode(reason)
                )
            @unknown default:
                return AppleFoundationModelsAvailability(
                    available: false,
                    reason: "UNKNOWN_AVAILABILITY"
                )
            }
        }
        #endif

        return AppleFoundationModelsAvailability(
            available: false,
            reason: "FOUNDATION_MODELS_FRAMEWORK_UNAVAILABLE"
        )
    }

    public func initializeModel(named modelName: String) async throws {
        guard modelName == Self.modelName else {
            throw AppleFoundationModelsError.unsupportedModelName(modelName)
        }

        let availability = probeAvailability()
        guard availability.available else {
            throw AppleFoundationModelsError.modelUnavailable(
                availability.reason ?? "UNKNOWN_AVAILABILITY"
            )
        }

        initialized = true
    }

    public func executeInference(
        prompt: String,
        maxTokens: Int = 128,
        temperature: Float = 0.2
    ) async throws -> String {
        try await executeWithReceipt(
            prompt: prompt,
            maxTokens: maxTokens,
            temperature: temperature
        ).output
    }

    public func executeWithReceipt(
        prompt: String,
        maxTokens: Int = 128,
        temperature: Float = 0.2
    ) async throws -> AppleFoundationModelsExecution {
        guard initialized else {
            throw AppleFoundationModelsError.notInitialized
        }

        try Self.validateRequest(
            prompt: prompt,
            maxTokens: maxTokens,
            temperature: temperature
        )

        #if canImport(FoundationModels)
        if #available(iOS 26.0, macOS 26.0, *) {
            let model = SystemLanguageModel.default
            guard model.isAvailable else {
                throw AppleFoundationModelsError.modelUnavailable(
                    Self.availabilityReasonCode(model.availability)
                )
            }

            let session = LanguageModelSession(
                model: model,
                tools: []
            ) {
                """
                You are a bounded AEGIS inference provider.
                Return model output only. Do not claim external authority, side effects,
                repository mutations, deployment, signing, or approval.
                """
            }

            let options = GenerationOptions(
                samplingMode: nil,
                temperature: Double(temperature),
                maximumResponseTokens: maxTokens
            )

            let response = try await session.respond(to: prompt, options: options)
            let output = response.content
            let receipt = AppleInferenceReceipt.succeeded(
                prompt: prompt,
                output: output,
                maxTokens: maxTokens,
                temperature: temperature
            )
            return AppleFoundationModelsExecution(output: output, receipt: receipt)
        }
        #endif

        throw AppleFoundationModelsError.frameworkUnavailable
    }

    static func validateRequest(
        prompt: String,
        maxTokens: Int,
        temperature: Float
    ) throws {
        guard !prompt.isEmpty, prompt.utf8.count <= maximumPromptBytes else {
            throw AppleFoundationModelsError.invalidPrompt
        }
        guard maxTokens > 0, maxTokens <= maximumResponseTokens else {
            throw AppleFoundationModelsError.invalidMaxTokens(maxTokens)
        }
        guard temperature.isFinite, temperature >= 0.0, temperature <= 1.0 else {
            throw AppleFoundationModelsError.invalidTemperature(temperature)
        }
    }

    #if canImport(FoundationModels)
    @available(iOS 26.0, macOS 26.0, *)
    private static func reasonCode(
        _ reason: SystemLanguageModel.Availability.UnavailableReason
    ) -> String {
        switch reason {
        case .appleIntelligenceNotEnabled:
            return "APPLE_INTELLIGENCE_NOT_ENABLED"
        case .deviceNotEligible:
            return "DEVICE_NOT_ELIGIBLE"
        case .modelNotReady:
            return "MODEL_NOT_READY"
        @unknown default:
            return "UNKNOWN_UNAVAILABLE_REASON"
        }
    }

    @available(iOS 26.0, macOS 26.0, *)
    private static func availabilityReasonCode(
        _ availability: SystemLanguageModel.Availability
    ) -> String {
        switch availability {
        case .available:
            return "AVAILABLE"
        case .unavailable(let reason):
            return reasonCode(reason)
        @unknown default:
            return "UNKNOWN_AVAILABILITY"
        }
    }
    #endif
}
