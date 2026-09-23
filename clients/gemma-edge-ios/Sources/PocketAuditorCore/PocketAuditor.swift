import Foundation

public enum PocketAuditTier: String, Codable, Sendable {
    case free
    case premium
}

public struct PocketAuditFinding: Codable, Equatable, Sendable {
    public let code: String
    public let summary: String
    public let severity: String

    public init(code: String, summary: String, severity: String) {
        self.code = code
        self.summary = summary
        self.severity = severity
    }
}

public struct PocketAuditReport: Codable, Equatable, Sendable {
    public let tier: PocketAuditTier
    public let constitutionalPass: Bool
    public let findings: [PocketAuditFinding]
    public let evidenceStatus: String

    public init(
        tier: PocketAuditTier,
        constitutionalPass: Bool,
        findings: [PocketAuditFinding],
        evidenceStatus: String
    ) {
        self.tier = tier
        self.constitutionalPass = constitutionalPass
        self.findings = findings
        self.evidenceStatus = evidenceStatus
    }
}

public protocol PremiumAccessChecking: Sendable {
    func hasPremiumAccess() async -> Bool
}

public struct PocketAuditor {
    private let validator: KhattLoopValidation
    private let access: PremiumAccessChecking

    public init(
        validator: KhattLoopValidation,
        access: PremiumAccessChecking
    ) {
        self.validator = validator
        self.access = access
    }

    public func audit(
        blockId: Int,
        stateData: String
    ) async -> PocketAuditReport {
        let pass = await validator.verifySequenceBlock(
            blockId: blockId,
            stateData: stateData
        )

        let premium = await access.hasPremiumAccess()
        let tier: PocketAuditTier = premium ? .premium : .free

        var findings: [PocketAuditFinding] = [
            PocketAuditFinding(
                code: pass ? "CONSTITUTIONAL_CHECK_PASS" : "CONSTITUTIONAL_CHECK_FAIL",
                summary: pass
                    ? "The supplied sequence block passed the local fail-closed verifier."
                    : "The supplied sequence block did not pass the local fail-closed verifier.",
                severity: pass ? "INFO" : "HIGH"
            )
        ]

        if premium {
            findings.append(
                PocketAuditFinding(
                    code: "PREMIUM_REPLAY_GUIDANCE_AVAILABLE",
                    summary: "Premium reporting may include deeper replay and evidence-pack guidance. This does not grant execution authority.",
                    severity: "INFO"
                )
            )
        }

        return PocketAuditReport(
            tier: tier,
            constitutionalPass: pass,
            findings: findings,
            evidenceStatus: premium
                ? "LOCAL_VERIFICATION_WITH_PREMIUM_REPORTING"
                : "LOCAL_VERIFICATION_ONLY"
        )
    }
}
