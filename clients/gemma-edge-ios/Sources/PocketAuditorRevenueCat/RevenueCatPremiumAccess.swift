#if canImport(RevenueCat)
import Foundation
import PocketAuditorCore
import RevenueCat

public actor RevenueCatPremiumAccess: PremiumAccessChecking {
    public static let entitlementIdentifier = "pocket_auditor_pro"

    public init() {}

    public func hasPremiumAccess() async -> Bool {
        do {
            let info = try await Purchases.shared.customerInfo()
            return info.entitlements.active[Self.entitlementIdentifier] != nil
        } catch {
            // Fail closed: RevenueCat outage / misconfiguration never grants premium.
            return false
        }
    }
}
#endif
