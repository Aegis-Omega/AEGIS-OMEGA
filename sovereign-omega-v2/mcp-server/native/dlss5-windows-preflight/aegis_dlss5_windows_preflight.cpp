// AEGIS DLSS 5 Windows support-query preflight.
// Reviewed against NVIDIA-RTX/Streamline@2122257e0fce486f91b385aa63b9a09b0a34b363.
// Official x64 Streamline SDK 2.14.1 release ZIP SHA-256:
// 92c4d954631a1710da86ca3fa8d5034f2b9503838c95fc4ae977ae149319781b
//
// This executable performs NO slEvaluateFeature call and NO rendering.
// It establishes only whether Streamline reports kFeatureDLSS_NR as supported
// for a concrete DXGI adapter LUID on the executing Windows host.

#include <windows.h>
#include <dxgi1_6.h>
#include <wrl/client.h>

#include <sl.h>

#include <cstdint>
#include <filesystem>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>

using Microsoft::WRL::ComPtr;

static_assert(sl::kFeatureDLSS_NR == 1004, "Streamline DLSS-NR feature id changed");

namespace {

std::string jsonEscape(const std::string& input)
{
    std::ostringstream out;
    for (unsigned char c : input)
    {
        switch (c)
        {
        case '\\': out << "\\\\"; break;
        case '"': out << "\\\""; break;
        case '\n': out << "\\n"; break;
        case '\r': out << "\\r"; break;
        case '\t': out << "\\t"; break;
        default:
            if (c < 0x20)
            {
                out << "\\u" << std::hex << std::setw(4) << std::setfill('0') << static_cast<int>(c);
            }
            else
            {
                out << c;
            }
        }
    }
    return out.str();
}

std::string wideToUtf8(const wchar_t* value)
{
    if (!value || !*value) return {};
    const int sizeWithNull = WideCharToMultiByte(CP_UTF8, 0, value, -1, nullptr, 0, nullptr, nullptr);
    if (sizeWithNull <= 1) return {};

    std::string out(static_cast<size_t>(sizeWithNull), '\0');
    const int written = WideCharToMultiByte(CP_UTF8, 0, value, -1, out.data(), sizeWithNull, nullptr, nullptr);
    if (written <= 1) return {};
    out.resize(static_cast<size_t>(written - 1));
    return out;
}

void emitReceipt(
    const char* status,
    sl::Result initResult,
    sl::Result supportResult,
    const DXGI_ADAPTER_DESC1* desc,
    bool supportQueryExecuted)
{
    std::ostringstream out;
    out << '{'
        << "\"schema\":\"AEGIS_DLSS5_WINDOWS_PREFLIGHT_RECEIPT_V1\","
        << "\"status\":\"" << status << "\","
        << "\"streamline_source_sha\":\"2122257e0fce486f91b385aa63b9a09b0a34b363\","
        << "\"streamline_release_sha256\":\"92c4d954631a1710da86ca3fa8d5034f2b9503838c95fc4ae977ae149319781b\","
        << "\"feature_symbol\":\"sl::kFeatureDLSS_NR\","
        << "\"feature_id\":1004,"
        << "\"sl_init_result\":" << static_cast<int>(initResult) << ','
        << "\"support_query_executed\":" << (supportQueryExecuted ? "true" : "false") << ','
        << "\"support_result\":" << static_cast<int>(supportResult) << ','
        << "\"evaluation_executed\":false,"
        << "\"runtime_claim\":\"SUPPORT_QUERY_ONLY\","
        << "\"rendering_claim\":\"NOT_ESTABLISHED\","
        << "\"quality_claim\":\"NOT_ESTABLISHED\","
        << "\"claim_promotion\":\"BLOCKED\","
        << "\"authority_effect\":\"NONE\"";

    if (desc)
    {
        out << ",\"adapter_description\":\"" << jsonEscape(wideToUtf8(desc->Description)) << "\""
            << ",\"vendor_id\":" << desc->VendorId
            << ",\"device_id\":" << desc->DeviceId
            << ",\"luid_high\":" << desc->AdapterLuid.HighPart
            << ",\"luid_low\":" << desc->AdapterLuid.LowPart;
    }

    out << '}';
    std::cout << out.str() << std::endl;
}

} // namespace

int wmain(int argc, wchar_t** argv)
{
    // argv[1] is the absolute directory containing Streamline plugins.
    if (argc != 2 || argv[1] == nullptr || *argv[1] == L'\0')
    {
        emitReceipt(
            "INVALID_ARGUMENT",
            sl::Result::eErrorInvalidParameter,
            sl::Result::eErrorInvalidParameter,
            nullptr,
            false);
        return 2;
    }

    std::filesystem::path pluginPath = std::filesystem::absolute(argv[1]);
    std::wstring pluginDir = pluginPath.wstring();
    const wchar_t* pluginPaths[] = { pluginDir.c_str() };

    const sl::Feature requestedFeatures[] = { sl::kFeatureDLSS_NR };
    sl::Preferences pref{};
    pref.showConsole = false;
    pref.logLevel = sl::LogLevel::eDefault;
    pref.pathsToPlugins = pluginPaths;
    pref.numPathsToPlugins = 1;
    pref.pathToLogsAndData = nullptr;
    // Explicitly disable OTA / downloaded-plugin loading and do not bypass OS checks.
    pref.flags = sl::PreferenceFlags::eDisableCLStateTracking;
    pref.featuresToLoad = requestedFeatures;
    pref.numFeaturesToLoad = 1;
    pref.engine = sl::EngineType::eCustom;
    pref.engineVersion = "AEGIS-DLSS5-PREFLIGHT-0.1";
    pref.projectId = "1f746f4d-373f-47cb-90f4-3fda901b22b8";
    pref.renderAPI = sl::RenderAPI::eD3D12;

    const sl::Result initResult = slInit(pref);
    if (initResult != sl::Result::eOk)
    {
        emitReceipt("SL_INIT_DENIED", initResult, sl::Result::eErrorInvalidState, nullptr, false);
        return 10;
    }

    struct ShutdownGuard
    {
        ~ShutdownGuard() { (void)slShutdown(); }
    } shutdownGuard;

    ComPtr<IDXGIFactory1> factory;
    const HRESULT factoryResult = CreateDXGIFactory1(IID_PPV_ARGS(&factory));
    if (FAILED(factoryResult))
    {
        emitReceipt("DXGI_FACTORY_DENIED", initResult, sl::Result::eErrorDXGIAPI, nullptr, false);
        return 11;
    }

    for (UINT index = 0;; ++index)
    {
        ComPtr<IDXGIAdapter1> adapter;
        const HRESULT enumResult = factory->EnumAdapters1(index, &adapter);
        if (enumResult == DXGI_ERROR_NOT_FOUND) break;
        if (FAILED(enumResult)) continue;

        DXGI_ADAPTER_DESC1 desc{};
        if (FAILED(adapter->GetDesc1(&desc))) continue;
        if ((desc.Flags & DXGI_ADAPTER_FLAG_SOFTWARE) != 0) continue;
        if (desc.VendorId != 0x10DE) continue; // NVIDIA PCI vendor id

        sl::AdapterInfo adapterInfo{};
        adapterInfo.deviceLUID = reinterpret_cast<uint8_t*>(&desc.AdapterLuid);
        adapterInfo.deviceLUIDSizeInBytes = sizeof(LUID);

        const sl::Result supportResult = slIsFeatureSupported(sl::kFeatureDLSS_NR, adapterInfo);
        if (supportResult == sl::Result::eOk)
        {
            emitReceipt("DLSS5_SUPPORT_OBSERVED", initResult, supportResult, &desc, true);
            return 0;
        }

        emitReceipt("DLSS5_SUPPORT_DENIED", initResult, supportResult, &desc, true);
        return 20;
    }

    emitReceipt("NO_NVIDIA_ADAPTER", initResult, sl::Result::eErrorNoSupportedAdapterFound, nullptr, false);
    return 21;
}
