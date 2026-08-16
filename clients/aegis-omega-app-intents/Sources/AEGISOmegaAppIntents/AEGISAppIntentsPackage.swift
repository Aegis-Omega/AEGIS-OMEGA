// Intent definitions that live in a Swift package (rather than the app bundle) are not
// indexed by Siri / Spotlight / Shortcuts unless the app declares the package. Providing
// this type lets the app target opt in:
//
//     struct MyApp: App, AppIntentsPackage {
//         static var includedPackages: [any AppIntentsPackage.Type] {
//             [AEGISOmegaAppIntentsPackage.self]
//         }
//     }
//
// AppIntents ships only in Apple SDKs, so this is guarded like the other intent sources.
#if canImport(AppIntents)
import AppIntents

public struct AEGISOmegaAppIntentsPackage: AppIntentsPackage {
    public init() {}
}
#endif
