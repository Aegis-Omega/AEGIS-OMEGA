#if canImport(RevenueCat)
import Foundation
import RevenueCat

public enum PocketAuditorPurchaseStatus: Sendable, Equatable {
    case purchased
    case restored
    case cancelled
    case entitlementMissing
    case offeringUnavailable
    case failed
}

public struct PocketAuditorRevenueCatPurchaseController {
    public static let entitlementIdentifier = RevenueCatPremiumAccess.entitlementIdentifier

    public init() {}

    public static func configure(publicAPIKey: String) {
        guard !publicAPIKey.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return
        }
        Purchases.configure(withAPIKey: publicAPIKey)
    }

    public func purchasePreferredPackage(
        packageIdentifier: String? = nil
    ) async -> PocketAuditorPurchaseStatus {
        do {
            let offerings = try await Purchases.shared.offerings()

            guard let current = offerings.current else {
                return .offeringUnavailable
            }

            let selected: Package?
            if let packageIdentifier {
                selected = current.availablePackages.first {
                    $0.identifier == packageIdentifier
                }
            } else {
                selected = current.availablePackages.first
            }

            guard let package = selected else {
                return .offeringUnavailable
            }

            let result = try await Purchases.shared.purchase(package: package)

            if result.userCancelled {
                return .cancelled
            }

            return result.customerInfo.entitlements.active[Self.entitlementIdentifier] != nil
                ? .purchased
                : .entitlementMissing
        } catch {
            return .failed
        }
    }

    public func restore() async -> PocketAuditorPurchaseStatus {
        do {
            let customerInfo = try await Purchases.shared.restorePurchases()
            return customerInfo.entitlements.active[Self.entitlementIdentifier] != nil
                ? .restored
                : .entitlementMissing
        } catch {
            return .failed
        }
    }
}
#endif
