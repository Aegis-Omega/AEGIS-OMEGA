#if canImport(SwiftUI)
import SwiftUI
import PocketAuditorCore
import PocketAuditorRevenueCat

@MainActor
public struct PocketAuditorView: View {
    private let auditor: PocketAuditor
    private let purchaseController: PocketAuditorRevenueCatPurchaseController

    @State private var stateData = ""
    @State private var report: PocketAuditReport?
    @State private var purchaseStatus: PocketAuditorPurchaseStatus?
    @State private var isAuditing = false
    @State private var isPurchasing = false

    public init(
        auditor: PocketAuditor,
        purchaseController: PocketAuditorRevenueCatPurchaseController = .init()
    ) {
        self.auditor = auditor
        self.purchaseController = purchaseController
    }

    public var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    header
                    auditInput
                    if let report {
                        reportCard(report)
                    }
                    proCard
                    evidenceBoundary
                }
                .padding(20)
            }
            .background(Color.black)
            .navigationTitle("Pocket Auditor")
            .navigationBarTitleDisplayMode(.inline)
        }
        .preferredColorScheme(.dark)
    }

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("AEGIS OMEGA LABS")
                .font(.caption.monospaced().weight(.semibold))
                .tracking(2)
                .foregroundStyle(.secondary)

            Text("Audit one agent action before it becomes authority.")
                .font(.largeTitle.bold())
                .foregroundStyle(.primary)

            Text("Local verification first. Premium reporting never changes the underlying constitutional verdict.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
    }

    private var auditInput: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("STATE / ACTION")
                .font(.caption.monospaced())
                .foregroundStyle(.secondary)

            TextEditor(text: $stateData)
                .frame(minHeight: 150)
                .padding(10)
                .scrollContentBackground(.hidden)
                .background(Color.white.opacity(0.055))
                .clipShape(RoundedRectangle(cornerRadius: 14))

            Button {
                runAudit()
            } label: {
                HStack {
                    if isAuditing {
                        ProgressView()
                    }
                    Text(isAuditing ? "Auditing…" : "Run local audit")
                    Spacer()
                    Image(systemName: "arrow.right")
                }
                .fontWeight(.semibold)
                .padding(.vertical, 4)
            }
            .buttonStyle(.borderedProminent)
            .disabled(isAuditing || stateData.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
    }

    @ViewBuilder
    private func reportCard(_ report: PocketAuditReport) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack {
                Image(systemName: report.constitutionalPass ? "checkmark.shield.fill" : "xmark.shield.fill")
                    .foregroundStyle(report.constitutionalPass ? .green : .orange)

                Text(report.constitutionalPass ? "VERIFICATION PASS" : "VERIFICATION FAIL")
                    .font(.headline.monospaced())

                Spacer()

                Text(report.tier.rawValue.uppercased())
                    .font(.caption.monospaced().weight(.bold))
                    .foregroundStyle(.secondary)
            }

            ForEach(Array(report.findings.enumerated()), id: \.offset) { _, finding in
                VStack(alignment: .leading, spacing: 4) {
                    Text(finding.code)
                        .font(.caption.monospaced())
                        .foregroundStyle(.secondary)
                    Text(finding.summary)
                        .font(.subheadline)
                }
            }

            Text(report.evidenceStatus)
                .font(.caption2.monospaced())
                .foregroundStyle(.secondary)
        }
        .padding(16)
        .background(Color.white.opacity(0.055))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var proCard: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("POCKET AUDITOR PRO")
                .font(.caption.monospaced().weight(.bold))
                .foregroundStyle(.yellow)

            Text("Unlock deeper replay and evidence-pack guidance.")
                .font(.title3.bold())

            Text("A paid entitlement changes reporting depth only. It never grants execution, repository, signer, deployment, or payment authority.")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            if let purchaseStatus {
                Text(statusLabel(purchaseStatus))
                    .font(.caption.monospaced())
                    .foregroundStyle(statusColor(purchaseStatus))
            }

            HStack {
                Button {
                    buyPro()
                } label: {
                    Text(isPurchasing ? "Processing…" : "Unlock Pro")
                }
                .buttonStyle(.borderedProminent)
                .disabled(isPurchasing)

                Button("Restore") {
                    restore()
                }
                .buttonStyle(.bordered)
                .disabled(isPurchasing)
            }
        }
        .padding(18)
        .background(
            LinearGradient(
                colors: [Color.yellow.opacity(0.12), Color.white.opacity(0.04)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16)
                .stroke(Color.yellow.opacity(0.2), lineWidth: 1)
        )
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }

    private var evidenceBoundary: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("EVIDENCE BOUNDARY")
                .font(.caption.monospaced())
                .foregroundStyle(.secondary)
            Text("This screen reports the result produced by the injected local verifier. RevenueCat controls only the premium-report entitlement.")
                .font(.footnote)
                .foregroundStyle(.secondary)
        }
    }

    private func runAudit() {
        isAuditing = true
        let input = stateData

        Task {
            let result = await auditor.audit(blockId: 1, stateData: input)
            await MainActor.run {
                report = result
                isAuditing = false
            }
        }
    }

    private func buyPro() {
        isPurchasing = true
        Task {
            let result = await purchaseController.purchasePreferredPackage()
            await MainActor.run {
                purchaseStatus = result
                isPurchasing = false
            }
        }
    }

    private func restore() {
        isPurchasing = true
        Task {
            let result = await purchaseController.restore()
            await MainActor.run {
                purchaseStatus = result
                isPurchasing = false
            }
        }
    }

    private func statusLabel(_ status: PocketAuditorPurchaseStatus) -> String {
        switch status {
        case .purchased: return "PRO ENTITLEMENT ACTIVE"
        case .restored: return "PRO ENTITLEMENT RESTORED"
        case .cancelled: return "PURCHASE CANCELLED"
        case .entitlementMissing: return "ENTITLEMENT NOT ACTIVE"
        case .offeringUnavailable: return "OFFERING UNAVAILABLE"
        case .failed: return "PURCHASE FLOW FAILED CLOSED"
        }
    }

    private func statusColor(_ status: PocketAuditorPurchaseStatus) -> Color {
        switch status {
        case .purchased, .restored: return .green
        case .cancelled: return .secondary
        case .entitlementMissing, .offeringUnavailable, .failed: return .orange
        }
    }
}
#endif
