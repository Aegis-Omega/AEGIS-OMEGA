import SwiftUI
import GemmaEdge

// Read-only local device probe. No governance or repository authority is granted.
@main
struct AEGISAppleLabApp: App {
    var body: some Scene {
        WindowGroup {
            LabView()
        }
    }
}

@MainActor
private struct LabView: View {
    @State private var prompt = "Explain the benefits of on-device inference."
    @State private var output = ""
    @State private var receiptHash = ""
    @State private var modelAvailable = false
    @State private var availabilityReason = "Not checked"
    @State private var running = false

    var body: some View {
        NavigationStack {
            Form {
                Section("On-device model") {
                    Text(modelAvailable ? "Available" : "Unavailable")
                    Text(availabilityReason).font(.footnote)
                    Button("Refresh availability") { refreshAvailability() }
                }

                Section("Prompt") {
                    TextEditor(text: $prompt)
                        .frame(minHeight: 100)
                    Button(running ? "Generating…" : "Generate locally") {
                        Task { await generate() }
                    }
                    .disabled(running || !modelAvailable || prompt.isEmpty || prompt.utf8.count > AppleFoundationModelsRunner.maximumPromptBytes)
                }

                Section("Result") {
                    Text(output.isEmpty ? "No model output" : output)
                        .textSelection(.enabled)
                }
                Section("Content-addressed receipt") {
                    Text(receiptHash.isEmpty ? "No receipt" : receiptHash)
                        .font(.footnote.monospaced())
                        .textSelection(.enabled)
                    Text("Authority effect: NONE. The receipt contains hashes, not prompt or output text.")
                        .font(.caption)
                }
            }
            .navigationTitle("AEGIS Ω Lab")
            .task { refreshAvailability() }
        }
    }

    private func refreshAvailability() {
        let state = AppleFoundationModelsRunner().probeAvailability()
        modelAvailable = state.available
        availabilityReason = state.reason ?? "AVAILABLE"
    }

    private func generate() async {
        running = true
        defer { running = false }
        output = ""
        receiptHash = ""
        let runner = AppleFoundationModelsRunner()
        do {
            try await runner.initializeModel(named: AppleFoundationModelsRunner.modelName)
            let result = try await runner.executeWithReceipt(
                prompt: prompt,
                maxTokens: 256,
                temperature: 0.2
            )
            output = result.output
            receiptHash = result.receipt.receipt_sha256
        } catch {
            output = "FAIL-CLOSED: \(error)"
        }
    }
}
