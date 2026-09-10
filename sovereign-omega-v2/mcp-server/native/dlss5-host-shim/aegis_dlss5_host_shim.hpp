#pragma once

#include <cstdint>
#include <optional>
#include <sl.h>

namespace aegis::dlss5 {

// Host-owned observation only. The host application remains responsible for
// Streamline initialization, device setup, frame tokens, resources, command
// buffers, submission, synchronization, and teardown.
struct HostProbeObservation {
    sl::Result featureSupportResult;
    bool evaluationExecuted;
    std::optional<sl::Result> evaluationResult;
};

// This function must be called from an already valid Streamline/render context.
// It does not initialize Streamline, create a device, allocate resources,
// submit command buffers, or assert rendering/quality truth.
HostProbeObservation probeOnce(
    const sl::AdapterInfo& adapterInfo,
    const sl::FrameToken& frame,
    const sl::BaseStructure** inputs,
    std::uint32_t numInputs,
    sl::CommandBuffer* commandBuffer);

} // namespace aegis::dlss5
