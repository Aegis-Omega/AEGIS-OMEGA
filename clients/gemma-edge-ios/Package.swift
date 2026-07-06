// swift-tools-version:5.9
// AEGIS-Ω edge constitutional verifier (iOS/macOS, on-device Gemma).
// FAIL-CLOSED by construction: see Sources/GemmaEdge and Tests/GemmaEdgeTests.
import PackageDescription

let package = Package(
    name: "GemmaEdge",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "GemmaEdge", targets: ["GemmaEdge"]),
    ],
    targets: [
        .target(name: "GemmaEdge"),
        .testTarget(name: "GemmaEdgeTests", dependencies: ["GemmaEdge"]),
    ]
)
