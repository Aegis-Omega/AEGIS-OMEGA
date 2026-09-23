// swift-tools-version:5.9
// AEGIS-Ω edge constitutional verifier (iOS/macOS, on-device Gemma).
// FAIL-CLOSED by construction: see Sources/GemmaEdge and Tests/GemmaEdgeTests.
import PackageDescription

let package = Package(
    name: "GemmaEdge",
    platforms: [.iOS(.v16), .macOS(.v13)],
    products: [
        .library(name: "GemmaEdge", targets: ["GemmaEdge"]),
        .library(name: "PocketAuditorCore", targets: ["PocketAuditorCore"]),
        .library(name: "PocketAuditorRevenueCat", targets: ["PocketAuditorRevenueCat"]),
        .library(name: "PocketAuditorUI", targets: ["PocketAuditorUI"]),
    ],
    dependencies: [
        .package(
            url: "https://github.com/RevenueCat/purchases-ios-spm.git",
            from: "5.16.0"
        ),
    ],
    targets: [
        .target(name: "GemmaEdge"),
        .target(
            name: "PocketAuditorCore",
            dependencies: ["GemmaEdge"]
        ),
        .target(
            name: "PocketAuditorRevenueCat",
            dependencies: [
                "PocketAuditorCore",
                .product(
                    name: "RevenueCat",
                    package: "purchases-ios-spm",
                    condition: .when(platforms: [.iOS, .macOS])
                ),
            ]
        ),
        .target(
            name: "PocketAuditorUI",
            dependencies: [
                "PocketAuditorCore",
                "PocketAuditorRevenueCat",
            ]
        ),
        .testTarget(name: "GemmaEdgeTests", dependencies: ["GemmaEdge"]),
        .testTarget(name: "PocketAuditorCoreTests", dependencies: ["PocketAuditorCore"]),
    ]
)
