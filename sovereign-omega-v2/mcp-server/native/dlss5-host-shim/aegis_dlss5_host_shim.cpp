#include "aegis_dlss5_host_shim.hpp"

namespace aegis::dlss5 {

// Public API review pin: NVIDIA-RTX/Streamline
// commit 2122257e0fce486f91b385aa63b9a09b0a34b363 (Streamline SDK 2.14.1).
static_assert(sl::kFeatureDLSS_NR == 1004,
              "Pinned Streamline DLSS-NR feature identifier changed");

HostProbeObservation probeOnce(
    const sl::AdapterInfo& adapterInfo,
    const sl::FrameToken& frame,
    const sl::BaseStructure** inputs,
    std::uint32_t numInputs,
    sl::CommandBuffer* commandBuffer) {
    const sl::Result support =
        slIsFeatureSupported(sl::kFeatureDLSS_NR, adapterInfo);

    if (support != sl::Result::eOk) {
        return HostProbeObservation{
            .featureSupportResult = support,
            .evaluationExecuted = false,
            .evaluationResult = std::nullopt,
        };
    }

    const sl::Result evaluation = slEvaluateFeature(
        sl::kFeatureDLSS_NR,
        frame,
        inputs,
        numInputs,
        commandBuffer);

    return HostProbeObservation{
        .featureSupportResult = support,
        .evaluationExecuted = true,
        .evaluationResult = evaluation,
    };
}

} // namespace aegis::dlss5
