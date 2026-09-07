// swift-tools-version: 5.9

import PackageDescription

let package = Package(
    name: "AEGISOmegaAppIntents",
    defaultLocalization: "en",
    platforms: [
        .iOS(.v17),
        .macOS(.v14),
    ],
    products: [
        .library(
            name: "AEGISOmegaAppIntents",
            targets: ["AEGISOmegaAppIntents"]
        ),
    ],
    targets: [
        .target(
            name: "AEGISOmegaAppIntents"
        ),
        .testTarget(
            name: "AEGISOmegaAppIntentsTests",
            dependencies: ["AEGISOmegaAppIntents"]
        ),
    ]
)
