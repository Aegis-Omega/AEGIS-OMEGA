import XCTest
@testable import GemmaEdge

final class AppleInferenceReceiptTests: XCTestCase {
    func testReceiptIsDeterministicAndContentAddressed() {
        let receipt = AppleInferenceReceipt.succeeded(
            prompt: "hello",
            output: "world",
            maxTokens: 32,
            temperature: 0.1
        )

        XCTAssertEqual(
            receipt.prompt_sha256,
            "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )
        XCTAssertEqual(
            receipt.output_sha256,
            "486ea46224d1bb4fb680f34f7c9ad96a8f24ec88be73ea8e5a6c65260e9cb8a7"
        )
        XCTAssertEqual(receipt.prompt_bytes, 5)
        XCTAssertEqual(receipt.output_bytes, 5)
        XCTAssertEqual(receipt.temperature_milli, 100)
        XCTAssertEqual(receipt.authority_effect, "NONE")
        XCTAssertEqual(
            receipt.receipt_sha256,
            "167cb2cdc67d04b374b68a851783dc3ec0a63ba20a0619550676535b3c8211eb"
        )
    }

    func testReceiptDoesNotContainPromptOrOutputText() throws {
        let receipt = AppleInferenceReceipt.succeeded(
            prompt: "private prompt",
            output: "private output",
            maxTokens: 16,
            temperature: 0
        )
        let data = try JSONEncoder().encode(receipt)
        let encoded = String(decoding: data, as: UTF8.self)

        XCTAssertFalse(encoded.contains("private prompt"))
        XCTAssertFalse(encoded.contains("private output"))
    }
}

final class AppleFoundationModelsRunnerPolicyTests: XCTestCase {
    func testUninitializedExecutionFailsClosed() async {
        let runner = AppleFoundationModelsRunner()

        do {
            _ = try await runner.executeInference(
                prompt: "test",
                maxTokens: 32,
                temperature: 0.1
            )
            XCTFail("Expected uninitialized Apple runner to throw")
        } catch let error as AppleFoundationModelsError {
            XCTAssertEqual(error, .notInitialized)
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testRejectsUnsupportedModelNameBeforeAvailability() async {
        let runner = AppleFoundationModelsRunner()

        do {
            try await runner.initializeModel(named: "not-an-apple-model")
            XCTFail("Expected unsupported model name to throw")
        } catch let error as AppleFoundationModelsError {
            XCTAssertEqual(error, .unsupportedModelName("not-an-apple-model"))
        } catch {
            XCTFail("Unexpected error: \(error)")
        }
    }

    func testFailedReinitializationRevokesPreviouslyAvailableModel() async throws {
        let runner = AppleFoundationModelsRunner()
        guard runner.probeAvailability().available else {
            throw XCTSkip("Requires an available native Apple Foundation Models runtime")
        }

        try await runner.initializeModel(named: AppleFoundationModelsRunner.modelName)
        do {
            try await runner.initializeModel(named: "not-an-apple-model")
            XCTFail("Unsupported model name must fail initialization")
        } catch AppleFoundationModelsError.unsupportedModelName(_) { }

        do {
            _ = try await runner.executeInference(prompt: "test", maxTokens: 32, temperature: 0.2)
            XCTFail("Failed reinitialization must revoke prior readiness")
        } catch AppleFoundationModelsError.notInitialized { }
    }

    func testCancelledTaskRejectedByPreflightGuard() async {
        let task = Task {
            withUnsafeCurrentTask { $0?.cancel() }
            do {
                try AppleFoundationModelsRunner.checkTaskCancellation()
                XCTFail("A canceled task must fail before invoking a model")
            } catch is CancellationError {
                // Canceled tasks must not reach generation.
            } catch {
                XCTFail("Unexpected cancellation error: \(error)")
            }
        }
        await task.value
    }

    func testRequestBoundsFailClosed() {
        XCTAssertThrowsError(
            try AppleFoundationModelsRunner.validateRequest(
                prompt: "",
                maxTokens: 32,
                temperature: 0.1
            )
        )

        XCTAssertThrowsError(
            try AppleFoundationModelsRunner.validateRequest(
                prompt: "ok",
                maxTokens: AppleFoundationModelsRunner.maximumResponseTokens + 1,
                temperature: 0.1
            )
        )

        XCTAssertThrowsError(
            try AppleFoundationModelsRunner.validateRequest(
                prompt: "ok",
                maxTokens: 32,
                temperature: 1.1
            )
        )
    }

    func testAvailabilityProbeNeverInventsAvailability() {
        let runner = AppleFoundationModelsRunner()
        let availability = runner.probeAvailability()

        // The test does not require a capable device. It only establishes that
        // availability is explicit and never inferred from documentation access.
        if !availability.available {
            XCTAssertNotNil(availability.reason)
        }
    }
}

final class AppleModelReadinessTests: XCTestCase {
    func testCancelledCompletionMustNotSucceed() async throws {
        let readiness = AppleModelReadiness()
        let token = readiness.beginInitialization()
        XCTAssertTrue(readiness.completeInitialization(token))
        let check = Task {
            withUnsafeCurrentTask { $0?.cancel() }
            XCTAssertThrowsError(try AppleFoundationModelsRunner.validateCompletedGeneration(
                readiness: readiness, token: token,
                availability: .init(available: true, reason: nil)
            )) { error in
                XCTAssertTrue(error is CancellationError, "Expected CancellationError, got \(error)")
            }
        }
        try await check.value
    }

    func testCompletedGenerationRejectsUnavailableModel() {
        let readiness = AppleModelReadiness()
        let token = readiness.beginInitialization()
        XCTAssertTrue(readiness.completeInitialization(token))
        XCTAssertThrowsError(try AppleFoundationModelsRunner.validateCompletedGeneration(
            readiness: readiness, token: token,
            availability: .init(available: false, reason: "MODEL_NOT_READY")
        )) { error in
            XCTAssertEqual(error as? AppleFoundationModelsError, .modelUnavailable("MODEL_NOT_READY"))
        }
    }

    func testCompletedGenerationRejectsRevokedLease() {
        let readiness = AppleModelReadiness()
        let token = readiness.beginInitialization()
        XCTAssertTrue(readiness.completeInitialization(token))
        _ = readiness.beginInitialization()
        XCTAssertThrowsError(try AppleFoundationModelsRunner.validateCompletedGeneration(
            readiness: readiness, token: token,
            availability: .init(available: true, reason: nil)
        )) { error in
            XCTAssertEqual(error as? AppleFoundationModelsError, .notInitialized)
        }
    }

    func testCompletedGenerationAcceptsActiveAvailableModel() throws {
        let readiness = AppleModelReadiness()
        let token = readiness.beginInitialization()
        XCTAssertTrue(readiness.completeInitialization(token))
        XCTAssertNoThrow(try AppleFoundationModelsRunner.validateCompletedGeneration(
            readiness: readiness, token: token,
            availability: .init(available: true, reason: nil)
        ))
    }

    func testNoLeaseBeforeInitialization() {
        let readiness = AppleModelReadiness()
        XCTAssertNil(readiness.activeToken())
    }

    func testSuccessfulInitializationEnablesLease() {
        let readiness = AppleModelReadiness()
        let token = readiness.beginInitialization()
        XCTAssertTrue(readiness.completeInitialization(token))
        XCTAssertEqual(readiness.activeToken(), token)
        XCTAssertTrue(readiness.isActive(token))
    }

    func testReinitializationRevokesInFlightLease() {
        let readiness = AppleModelReadiness()
        let old = readiness.beginInitialization()
        XCTAssertTrue(readiness.completeInitialization(old))
        let next = readiness.beginInitialization()
        XCTAssertFalse(readiness.isActive(old))
        XCTAssertNil(readiness.activeToken())
        XCTAssertTrue(readiness.completeInitialization(next))
        XCTAssertFalse(readiness.isActive(old))
        XCTAssertTrue(readiness.isActive(next))
    }

    func testStaleSuccessfulCompletionCannotReenableRevokedLease() {
        let readiness = AppleModelReadiness()
        let stale = readiness.beginInitialization()
        _ = readiness.beginInitialization()
        XCTAssertFalse(readiness.completeInitialization(stale))
        XCTAssertNil(readiness.activeToken())
    }
}
